import random
import time
import ssl
import threading
import sys
import traceback
import paho.mqtt.client as mqtt

print("\n==============================")
print(" Virtual NodeMCU Emulator ")
print("==============================\n")

# =========================
# MQTT CONFIG
# =========================
BROKER = "51552d777a9f492cba1b3cc4ef6b37a9.s1.eu.hivemq.cloud"
PORT = 8883
USERNAME = "NodeMCU"
PASSWORD = "YOUR_MQTT_PASSWORD_HERE"
CLIENT_ID = "Virtual_NodeMCU_Debug"

# =========================
# SYSTEM TOPICS
# =========================
STATUS_TOPIC = "home/system/status/nodemcu"
RSSI_TOPIC = "home/system/rssi/nodemcu"

# =========================
# TOPICS
# =========================
LAMP1_CMD = "home/devices/lamp1/command"
LAMP2_CMD = "home/devices/lamp2/command"
LAMP3_CMD = "home/devices/lamp3/command"
BUZZER_CMD = "home/devices/buzzer/command"

ULTRASONIC_CMD = "home/sensor/ultrasonic/command"
LDR_CMD = "home/sensor/ldr/command"
POT_CMD = "home/sensor/potentiometer/command"

LAMP1_STATE = "home/devices/lamp1/state"
LAMP2_STATE = "home/devices/lamp2/state"
LAMP3_STATE = "home/devices/lamp3/state"
BUZZER_STATE = "home/devices/buzzer/state"

ULTRASONIC_STATE = "home/sensor/ultrasonic/state"
LDR_STATE = "home/sensor/ldr/state"
POT_STATE = "home/sensor/potentiometer/state"

# =========================
# SENSOR RANGES
# =========================
ULTRASONIC_RANGE = (10.0, 200.0)
LDR_RANGE = (100, 200)
POT_RANGE = (0, 1023)
RSSI_RANGE = (-85, -45)

RSSI_INTERVAL = 120  # seconds (2 minutes)

# =========================
# STATES
# =========================
lamp_state = {1: "off", 2: "off", 3: "off"}
buzzer_state = "idle"
running = True

# =========================
# CALLBACKS
# =========================
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] Connected rc={rc}")

    if rc != 0:
        return

    # Publish ONLINE
    client.publish(STATUS_TOPIC, "online", retain=True)
    print("[SYSTEM] Status → online")

    topics = [
        LAMP1_CMD, LAMP2_CMD, LAMP3_CMD,
        BUZZER_CMD,
        ULTRASONIC_CMD, LDR_CMD, POT_CMD
    ]

    for t in topics:
        client.subscribe(t)
        print(f"[MQTT] Subscribed → {t}")

    publish_lamps()
    client.publish(BUZZER_STATE, buzzer_state, retain=True)

def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode().strip()

        print(f"\n[RX] {topic} → '{payload}'")

        # Lamps
        if topic == LAMP1_CMD:
            handle_lamp(1, payload)
        elif topic == LAMP2_CMD:
            handle_lamp(2, payload)
        elif topic == LAMP3_CMD:
            handle_lamp(3, payload)

        # Buzzer
        elif topic == BUZZER_CMD and payload == "buzz":
            threading.Thread(target=handle_buzzer).start()

        # Sensors
        elif payload == "read":
            if topic == ULTRASONIC_CMD:
                v = round(random.uniform(*ULTRASONIC_RANGE), 2)
                client.publish(ULTRASONIC_STATE, str(v), retain=True)
                print(f"[TX] Ultrasonic → {v} cm")

            elif topic == LDR_CMD:
                v = random.randint(*LDR_RANGE)
                client.publish(LDR_STATE, str(v), retain=True)
                print(f"[TX] LDR → {v}")

            elif topic == POT_CMD:
                v = random.randint(*POT_RANGE)
                client.publish(POT_STATE, str(v), retain=True)
                print(f"[TX] POT → {v}")

    except Exception:
        traceback.print_exc()

# =========================
# HELPERS
# =========================
def handle_lamp(lamp_id, cmd):
    if cmd not in ("on", "off"):
        return
    lamp_state[lamp_id] = cmd
    client.publish(f"home/devices/lamp{lamp_id}/state", cmd, retain=True)
    print(f"[TX] Lamp {lamp_id} → {cmd}")

def publish_lamps():
    for i in lamp_state:
        client.publish(f"home/devices/lamp{i}/state", lamp_state[i], retain=True)
        print(f"[TX] Lamp {i} init → {lamp_state[i]}")

def handle_buzzer():
    global buzzer_state
    buzzer_state = "buzzing"
    client.publish(BUZZER_STATE, buzzer_state, retain=True)
    print("[TX] Buzzer → buzzing")

    time.sleep(2.5)

    buzzer_state = "idle"
    client.publish(BUZZER_STATE, buzzer_state, retain=True)
    print("[TX] Buzzer → idle")

def rssi_publisher():
    while running:
        rssi = random.randint(*RSSI_RANGE)
        client.publish(RSSI_TOPIC, str(rssi), retain=True)
        print(f"[SYS] RSSI → {rssi} dBm")
        time.sleep(RSSI_INTERVAL)

# =========================
# MAIN
# =========================
try:
    client = mqtt.Client(
        client_id=CLIENT_ID,
        clean_session=True
    )

    # LWT: offline on crash
    client.will_set(STATUS_TOPIC, "offline", retain=True)

    client.username_pw_set(USERNAME, PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

    client.on_connect = on_connect
    client.on_message = on_message

    print("[SYSTEM] Connecting to broker...")
    client.connect(BROKER, PORT, 60)

    # Start RSSI thread
    threading.Thread(target=rssi_publisher, daemon=True).start()

    print("[SYSTEM] Emulator running (Ctrl+C to stop)")
    client.loop_forever()

except KeyboardInterrupt:
    print("\n[SYSTEM] Shutdown requested")
    running = False
    client.disconnect()
    sys.exit(0)

except Exception:
    print("\n[FATAL] Crash detected")
    traceback.print_exc()
    sys.exit(1)
