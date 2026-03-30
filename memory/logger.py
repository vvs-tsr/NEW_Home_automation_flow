# memory/logger.py
# SQLite event logger — subscribes to MQTT and writes all events to echobud.db.
# Adapted from: old manual files/sqlite_mqtt.py
# Run this as a background service alongside the main stack.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
import time
import sqlite3
import ssl
from datetime import datetime
from paho.mqtt.client import Client
from config.settings import settings

# ── Database setup ────────────────────────────────────────────────────────────
conn = sqlite3.connect(settings.db_path, check_same_thread=False)
cur  = conn.cursor()

# Ensure schema exists (idempotent — safe to run multiple times)
with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r") as f:
    conn.executescript(f.read())
conn.commit()
print(f"[DB] Connected to {settings.db_path}")


# ── Write helpers ─────────────────────────────────────────────────────────────
def write_event(source: str, event_type: str, payload: dict, raw_topic: str = "") -> int:
    """Insert a row into the events table. Returns the new row id."""
    cur.execute(
        """
        INSERT INTO events (timestamp, source, event_type, payload, raw_mqtt_topic)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(time.time()), source, event_type, json.dumps(payload), raw_topic),
    )
    conn.commit()
    return cur.lastrowid


def write_alert(source: str, threat_class: str, confidence: float, location: str = "") -> int:
    """Insert a row into the alerts table. Returns the new row id."""
    cur.execute(
        """
        INSERT INTO alerts (timestamp, source, threat_class, confidence, location, acknowledged)
        VALUES (?, ?, ?, ?, ?, 0)
        """,
        (int(time.time()), source, threat_class, confidence, location),
    )
    conn.commit()
    return cur.lastrowid


def write_conversation(session_id: str, role: str, content: str) -> int:
    """Insert a row into the conversations table. Returns the new row id."""
    cur.execute(
        """
        INSERT INTO conversations (session_id, timestamp, role, content)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, int(time.time()), role, content),
    )
    conn.commit()
    return cur.lastrowid


# ── MQTT subscriber ───────────────────────────────────────────────────────────
def on_message(client, userdata, msg):
    try:
        raw = msg.payload.decode()
        data = json.loads(raw)

        source     = data.get("source", msg.topic.split("/")[0])
        event_type = data.get("type", data.get("name", "unknown"))

        # Route vision detection alerts to the alerts table too
        if source == "vision" and event_type == "object_detected":
            detection_data = data.get("data", {})
            objects       = detection_data.get("objects", [])
            confidences   = detection_data.get("confidences", [])
            for obj, conf in zip(objects, confidences):
                write_alert(source=source, threat_class=obj, confidence=conf)

        write_event(source=source, event_type=event_type, payload=data, raw_topic=msg.topic)
        print(f"[DB] Logged: {msg.topic} → {event_type}")

    except json.JSONDecodeError:
        # Non-JSON payload — log as raw string
        write_event(
            source=msg.topic.split("/")[0],
            event_type="raw",
            payload={"raw": msg.payload.decode(errors="replace")},
            raw_topic=msg.topic,
        )
    except Exception as e:
        print(f"[DB] Error processing message: {e}")


mqtt_client = Client(client_id="db_sqlite_logger")
mqtt_client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLS)
mqtt_client.on_message = on_message

mqtt_client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port)
mqtt_client.subscribe("#")   # log everything — filter in queries, not here

print(f"[Logger] Listening on event/# → writing to {settings.db_path}")
print("[Logger] Press Ctrl+C to stop")

try:
    mqtt_client.loop_forever()
except KeyboardInterrupt:
    print("\n[Logger] Shutting down.")
    conn.close()
    mqtt_client.disconnect()
