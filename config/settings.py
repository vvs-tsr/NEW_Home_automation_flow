"""
config/settings.py
Central configuration — reads all .env variables once, exposes a single Settings object.
Every other module imports from here instead of calling os.getenv() directly.

Usage:
    from config.settings import settings
    print(settings.mqtt_broker_host)
"""

from dotenv import load_dotenv
import os

load_dotenv()

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _abspath(env_var: str, default: str) -> str:
    """Read a path from .env — if relative, resolve it against the project root."""
    raw = os.getenv(env_var, "")
    if not raw:
        return default
    return raw if os.path.isabs(raw) else os.path.join(_PROJECT_ROOT, raw)


class Settings:
    # ── LLM ──────────────────────────────────────────────────────────────────
    groq_api_key: str      = os.getenv("GROQ_API_KEY", "")
    llm_model: str         = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

    # ── MQTT ─────────────────────────────────────────────────────────────────
    mqtt_broker_host: str  = os.getenv("MQTT_BROKER_HOST", "")
    mqtt_broker_port: int  = int(os.getenv("MQTT_BROKER_PORT", "8883"))
    mqtt_username: str     = os.getenv("MQTT_USERNAME", "")
    mqtt_password: str     = os.getenv("MQTT_PASSWORD", "")

    # ── Piper TTS ─────────────────────────────────────────────────────────────
    piper_voice: str       = os.getenv("PIPER_VOICE", "en_US-eminem-medium.onnx")
    piper_model_path: str  = _abspath(
        "PIPER_MODEL_PATH",
        os.path.join(_PROJECT_ROOT, "main files", "voices")
    )

    # ── Whisper STT ───────────────────────────────────────────────────────────
    whisper_model: str     = os.getenv("WHISPER_MODEL", "base")
    whisper_device: str    = os.getenv("WHISPER_DEVICE", "cuda")

    # ── UDP / ESP32 ───────────────────────────────────────────────────────────
    udp_host: str          = os.getenv("UDP_HOST", "")
    udp_audio_port: int    = int(os.getenv("UDP_AUDIO_PORT", "8888"))
    udp_control_port: int  = int(os.getenv("UDP_CONTROL_PORT", "9999"))
    udp_speaker_port: int  = int(os.getenv("UDP_SPEAKER_PORT", "12345"))

    # ── Database ──────────────────────────────────────────────────────────────
    db_path: str           = _abspath(
        "DB_PATH",
        os.path.join(_PROJECT_ROOT, "memory", "echobud.db")
    )

    # ── Camera / YOLO ─────────────────────────────────────────────────────────
    camera_source: str     = os.getenv("CAMERA_SOURCE", "")
    yolo_model_path: str   = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")


settings = Settings()
