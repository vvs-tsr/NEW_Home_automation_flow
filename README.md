# Jarvis EchoBud — Home Agent System

A voice-controlled home automation agent running on an ESP32 + PC.
Press a button on the device, speak, and Jarvis replies via a speaker —
while YOLO watches your cameras and Home Assistant runs your automations.

---

## What it does

- **Voice loop**: ESP32 (mic + speaker) sends audio over UDP to the PC server.
  The PC runs Whisper STT → Groq LLM → Piper TTS → streams audio back.
- **Camera monitoring**: YOLO detects people, vehicles, and animals on an IP camera
  and publishes MQTT alerts with debouncing.
- **Event logging**: All MQTT events are written to a local SQLite database.
- **LLM tool calling**: Jarvis can publish MQTT commands to control devices,
  query the event database, and run home routines.
- **Home Assistant integration**: HA listens on MQTT and runs automations
  triggered by Jarvis commands or YOLO alerts.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        ESP32 (EchoBud)                      │
│  Button → wake_trigger (UDP 9999) ──────────────────────┐   │
│  Mic (INMP441) → audio stream (UDP 8888) ───────────────┤   │
│  Speaker (MAX98357) ← audio stream (UDP 12345) ─────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │ UDP / WiFi
┌─────────────────────────────────────────────────────────────┐
│                       PC Server                             │
│                                                             │
│  echobud_server.py                                          │
│    ├── sst.py          (Whisper STT — faster-whisper)       │
│    ├── llm_tool_caller.py (Groq LLM + tool calling)         │
│    │     └── llm_tools/  (mqtt_publish, db_tools, routines) │
│    └── tts.py          (Piper TTS)                          │
│                                                             │
│  peripheral/yolo_stream.py  (YOLO + Flask stream)           │
│  memory/logger.py           (MQTT → SQLite)                 │
└─────────────────────────────────────────────────────────────┘
                            │ MQTT (HiveMQ Cloud TLS)
┌─────────────────────────────────────────────────────────────┐
│              Home Assistant (VM)                            │
│  Subscribes to MQTT → runs automations                      │
└─────────────────────────────────────────────────────────────┘
```

---

## Folder structure

```
Jarvis_Echobud/
├── main files/
│   ├── echobud_server.py       # Main voice loop server
│   ├── llm_tool_caller.py      # Groq LLM client + tool calling
│   ├── sst.py                  # Whisper speech-to-text
│   ├── tts.py                  # Piper text-to-speech
│   ├── llm_tools/
│   │   ├── __init__.py         # @register decorator + TOOLS + dispatch()
│   │   ├── function_mqtt_publish.py
│   │   ├── db_tools.py
│   │   └── routine_tools.py
│   ├── firmware_esp/
│   │   └── echobud.ino
│   └── voices/                 # Piper .onnx models (gitignored)
├── peripheral/
│   ├── yolo_stream.py          # YOLO camera monitoring
│   └── mqtt_publisher.py
├── memory/
│   ├── logger.py               # MQTT → SQLite logger
│   ├── schema.sql
│   └── echobud.db              # gitignored
├── firmware/
│   └── echobud/echobud.ino
├── config/
│   └── settings.py             # Central config — reads .env
├── old manual files/           # Reference scripts and experiments
├── .env                        # Your secrets — NEVER committed
├── .env.example                # Blank template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Setup

```bash
# 1. Clone
git clone https://github.com/vvs-tsr/NEW_Home_automation_flow.git
cd NEW_Home_automation_flow

# 2. Create virtual environment
python -m venv venv

# 3. Activate venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment
copy .env.example .env
# Open .env and fill in all values (see Environment variables below)

# 6. Initialise the database (first time only)
sqlite3 memory/echobud.db < memory/schema.sql
```

---

## How to run each component

All commands should be run from the project root with the venv active.

**Voice server (main pipeline):**
```bash
python "main files/echobud_server.py"
```

**LLM tool-calling interactive session:**
```bash
python "main files/llm_tool_caller.py"
```

**Camera monitoring (YOLO + MQTT alerts + Flask stream):**
```bash
python peripheral/yolo_stream.py
# View annotated stream at: http://localhost:5000/video_feed
```

**Event logger (MQTT → SQLite):**
```bash
python memory/logger.py
```

**TTS standalone test:**
```bash
python "main files/tts.py"
```

**STT standalone test:**
```bash
python "main files/sst.py"
```

---

## Environment variables reference

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key | `gsk_...` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `LLM_MODEL` | Groq model ID | `openai/gpt-oss-120b` |
| `MQTT_BROKER_HOST` | HiveMQ Cloud hostname | `abc123.s1.eu.hivemq.cloud` |
| `MQTT_BROKER_PORT` | MQTT TLS port | `8883` |
| `MQTT_USERNAME` | MQTT username | `pythontester1` |
| `MQTT_PASSWORD` | MQTT password | `...` |
| `PIPER_MODEL_PATH` | Folder containing .onnx voice files | `main files/voices` |
| `PIPER_VOICE` | Voice model filename | `en_US-eminem-medium.onnx` |
| `WHISPER_MODEL` | Whisper model size | `base` |
| `WHISPER_DEVICE` | Inference device | `cuda` or `cpu` |
| `UDP_HOST` | ESP32 IP address | `192.168.1.50` |
| `UDP_AUDIO_PORT` | Port for mic audio from ESP32 | `8888` |
| `UDP_CONTROL_PORT` | Port for control messages | `9999` |
| `UDP_SPEAKER_PORT` | Port for speaker audio to ESP32 | `12345` |
| `DB_PATH` | SQLite database file path | `memory/echobud.db` |
| `CAMERA_SOURCE` | IP Webcam URL | `http://192.168.1.50:8080/video` |
| `YOLO_MODEL_PATH` | YOLO model file | `yolov8n.pt` |
