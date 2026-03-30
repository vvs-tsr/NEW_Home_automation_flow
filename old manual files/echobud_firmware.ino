// Unified ESP32 Audio Node – Button Wake + Mic Stream + Speaker Response
// Debug-heavy version – prints almost every important step / value / transition
// LED on GPIO13: ON during MIC_ACTIVE or SPEAK_READY

#include <WiFi.h>
#include <WiFiUdp.h>
#include <driver/i2s.h>

#define DEBUG 1  // comment out or set 0 to disable debug prints

#if DEBUG
  #define DPRINT(msg)           Serial.printf("[%lu] %s\n", millis(), msg)
  #define DPRINT_VAL(msg, val)  Serial.printf("[%lu] %s: %d\n", millis(), msg, (int)(val))
  #define DPRINT_STR(msg, str)  Serial.printf("[%lu] %s: %s\n", millis(), msg, str)
  #define DPRINT_STATE(state)   Serial.printf("[%lu] → State: %s\n", millis(), \
                                            (state == IDLE ? "IDLE" : \
                                             state == MIC_ACTIVE ? "MIC_ACTIVE" : "SPEAK_READY"))
#else
  #define DPRINT(msg)
  #define DPRINT_VAL(msg, val)
  #define DPRINT_STR(msg, str)
  #define DPRINT_STATE(state)
#endif

// ────────────────────────────────────────────────
// PINS
#define LED_PIN         13      // Status LED – HIGH = on
#define BUTTON_PIN      15       // Button to GND (active LOW)
#define LDR_PIN         16      // Analog light sensor

// STATES
enum State { IDLE, MIC_ACTIVE, SPEAK_READY };
State currentState = IDLE;

// ────────────────────────────────────────────────
// NETWORK & PORTS
const char* ssid = "Trojan_2";
const char* password = "antivirus";

const IPAddress pcIP(192, 168, 76, 100);      // your PC IP
const uint16_t AUDIO_RX_PORT   = 8888;        // ESP → PC (mic stream)
const uint16_t AUDIO_TX_PORT   = 12345;       // PC → ESP (speaker stream)
const uint16_t CONTROL_PORT    = 9999;        // wake_trigger / speak_now

// ────────────────────────────────────────────────
// I2S CONFIG
#define I2S_WS         5
#define I2S_SCK       17
#define I2S_SD_IN      7     // INMP441 → ESP (mic)
#define I2S_DATA_OUT   4     // MAX98357 ← ESP (speaker)

#define SAMPLE_RATE       16000
#define BUFFER_SAMPLES    512
#define BUFFER_BYTES      (BUFFER_SAMPLES * 2)

// TIMINGS
#define CAPTURE_DURATION_MS   10000   // 10 seconds mic capture
#define GLOBAL_TIMEOUT_MS     15000   // max time in any non-idle state
#define SILENCE_TIMEOUT_MS    2000    // end playback if no packets

// ────────────────────────────────────────────────
// GLOBALS
WiFiUDP udpControl;
WiFiUDP udpAudioRx;    // mic → PC
WiFiUDP udpAudioTx;    // PC → speaker

unsigned long stateStartTime = 0;
volatile bool buttonFlag = false;
bool playingAudio = false;
unsigned long lastAudioPacket = 0;
unsigned long micPacketCount = 0;

// ────────────────────────────────────────────────
// INTERRUPT HANDLER
void IRAM_ATTR onButtonPress() {
  buttonFlag = true;
#if DEBUG
  Serial.printf("[%lu] ISR: Button pressed!\n", millis());
#endif
}

void setup() {
  Serial.begin(115200);
  delay(400);
#if DEBUG
  Serial.println("\n=== Jarvis Unified Audio Node – Debug Build ===");
  Serial.printf("Compile time: %s %s\n", __DATE__, __TIME__);
#endif

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);
  DPRINT("LED pin initialized");

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), onButtonPress, FALLING);
  DPRINT_VAL("Button interrupt attached on GPIO", BUTTON_PIN);

  pinMode(LDR_PIN, INPUT);
  DPRINT("LDR pin set as input");

  // WiFi
  DPRINT("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  unsigned long wifiStart = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - wifiStart < 15000) {
    delay(400);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    DPRINT_STR("WiFi connected", WiFi.localIP().toString().c_str());
  } else {
    DPRINT("WiFi connection failed!");
  }

  // UDP
  if (udpControl.begin(CONTROL_PORT)) {
    DPRINT_VAL("UDP Control started on port", CONTROL_PORT);
  } else {
    DPRINT("UDP Control bind failed");
  }

  if (udpAudioRx.begin(AUDIO_RX_PORT)) {
    DPRINT_VAL("UDP Audio RX started on port", AUDIO_RX_PORT);
  } else {
    DPRINT("UDP Audio RX bind failed");
  }

  if (udpAudioTx.begin(AUDIO_TX_PORT)) {
    DPRINT_VAL("UDP Audio TX started on port", AUDIO_TX_PORT);
  } else {
    DPRINT("UDP Audio TX bind failed");
  }

  // I2S
  i2s_config_t i2s_cfg = {
    .mode                 = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
    .sample_rate          = SAMPLE_RATE,
    .bits_per_sample      = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format       = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags     = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count        = 8,
    .dma_buf_len          = 64,
    .use_apll             = false,
    .tx_desc_auto_clear   = true,
    .fixed_mclk           = 0
  };

  esp_err_t err = i2s_driver_install(I2S_NUM_0, &i2s_cfg, 0, NULL);
  if (err == ESP_OK) {
    DPRINT("I2S driver installed");
  } else {
    Serial.printf("I2S install failed: %d\n", err);
  }

  i2s_pin_config_t pins = {
    .bck_io_num   = I2S_SCK,
    .ws_io_num    = I2S_WS,
    .data_out_num = I2S_DATA_OUT,
    .data_in_num  = I2S_SD_IN
  };

  err = i2s_set_pin(I2S_NUM_0, &pins);
  if (err == ESP_OK) {
    DPRINT("I2S pins configured");
  } else {
    Serial.printf("I2S set_pin failed: %d\n", err);
  }

  i2s_zero_dma_buffer(I2S_NUM_0);
  DPRINT("I2S DMA buffer zeroed");

  goIdle();
  DPRINT("Boot complete – now in IDLE");
  DPRINT("Press button to test wake → mic stream");
}

void loop() {
  unsigned long now = millis();

  // Periodic state debug
  static uint32_t lastStateLog = 0;
  if (now - lastStateLog > 4000) {
    DPRINT_VAL("Current state", currentState);
    DPRINT_VAL("buttonFlag", buttonFlag);
    DPRINT_VAL("playingAudio", playingAudio);
    lastStateLog = now;
  }

  // Global timeout (only when not actively playing audio)
  if (currentState != IDLE && !playingAudio &&
      (now - stateStartTime > GLOBAL_TIMEOUT_MS)) {
    DPRINT_VAL("Global timeout → forcing IDLE", now - stateStartTime);
    goIdle();
  }

  switch (currentState) {
    case IDLE:
      // LDR debug
      static uint32_t lastLdr = 0;
      if (now - lastLdr > 5000) {
        int ldr = analogRead(LDR_PIN);
        DPRINT_VAL("LDR raw value", ldr);
        lastLdr = now;
      }

      // Button flag check
      if (buttonFlag) {
        DPRINT("Button flag detected → starting mic capture");
        buttonFlag = false;
        startMicCapture();
      }

      // Check for speak_now from PC
      checkForSpeakCommand(now);
      break;

    case MIC_ACTIVE:
      streamMicToPC(now);
      if (now - stateStartTime > CAPTURE_DURATION_MS) {
        DPRINT_VAL("Mic capture timeout → stopping", now - stateStartTime);
        stopMicCapture();
        goIdle();
      }
      break;

    case SPEAK_READY:
      playIncomingAudio(now);
      break;
  }

  delay(8);  // ~125 Hz loop
}

// ────────────────────────────────────────────────

void goIdle() {
  DPRINT_STATE(IDLE);
  currentState = IDLE;
  stateStartTime = millis();
  digitalWrite(LED_PIN, LOW);
  playingAudio = false;
  lastAudioPacket = 0;
  micPacketCount = 0;
}

void startMicCapture() {
  DPRINT_STATE(MIC_ACTIVE);
  currentState = MIC_ACTIVE;
  stateStartTime = millis();
  digitalWrite(LED_PIN, HIGH);
  micPacketCount = 0;

  udpControl.beginPacket(pcIP, CONTROL_PORT);
  const char* msg = "wake_trigger";
  int len = strlen(msg);
  udpControl.write((const uint8_t*)msg, len);
  udpControl.endPacket();
  DPRINT_STR("wake_trigger sent", msg);

  Serial.println("→ Mic capture started (10 seconds)");
}

void stopMicCapture() {
  DPRINT("stopMicCapture called");

  // ←←← NEW: Send mic_end to PC
  udpControl.beginPacket(pcIP, CONTROL_PORT);
  const char* msg = "mic_end";
  udpControl.write((const uint8_t*)msg, strlen(msg));
  udpControl.endPacket();
  DPRINT_STR("mic_end sent to PC", msg);

  goIdle();  // keep your original behaviour
}

void streamMicToPC(unsigned long now) {
  int16_t buf[BUFFER_SAMPLES];
  size_t bytesRead = 0;

  esp_err_t res = i2s_read(I2S_NUM_0, buf, BUFFER_BYTES, &bytesRead, 10);

  if (res == ESP_OK && bytesRead > 0) {
    micPacketCount++;
    udpAudioRx.beginPacket(pcIP, AUDIO_RX_PORT);
    int sent = udpAudioRx.write((const uint8_t*)buf, bytesRead);
    udpAudioRx.endPacket();

    if (sent == bytesRead) {
      DPRINT_VAL("Mic packet OK", bytesRead);
    } else {
      DPRINT_VAL("Mic partial send (sent)", sent);
      DPRINT_VAL("Mic read was", bytesRead);
    }
  } else if (res != ESP_OK) {
    DPRINT_VAL("i2s_read failed", res);
  }
}

void checkForSpeakCommand(unsigned long now) {
  int pkt = udpControl.parsePacket();
  if (pkt > 0) {
    DPRINT_VAL("Control packet received", pkt);
    char buf[32];
    int len = udpControl.read(buf, sizeof(buf)-1);
    if (len > 0) {
      buf[len] = '\0';
      DPRINT_STR("Control message", buf);

      if (strstr(buf, "speak_now")) {
        DPRINT("speak_now detected → entering SPEAK_READY");
        currentState = SPEAK_READY;
        stateStartTime = now;
        digitalWrite(LED_PIN, HIGH);
        playingAudio = false;
        lastAudioPacket = now;
      }
    }
  }
}

void playIncomingAudio(unsigned long now) {
  int pktSize = udpAudioTx.parsePacket();
  if (pktSize > 0) {
    DPRINT_VAL("Speaker packet received", pktSize);
    uint8_t buf[1024];
    int len = udpAudioTx.read(buf, sizeof(buf));
    if (len > 0) {
      size_t written = 0;
      esp_err_t res = i2s_write(I2S_NUM_0, buf, len, &written, 10);
      playingAudio = true;
      lastAudioPacket = now;

      if (res == ESP_OK) {
        DPRINT_VAL("Played bytes", written);
      } else {
        DPRINT_VAL("i2s_write failed", res);
      }
    }
  } else {
    // silence detection
    if (playingAudio && (now - lastAudioPacket > SILENCE_TIMEOUT_MS)) {
      DPRINT_VAL("Silence timeout → ending playback", now - lastAudioPacket);
      playingAudio = false;
      goIdle();
    }
  }
}