# function_mqtt_publish.py
# MQTT publish tool for the LLM.
# Registered in llm_tools/__init__.py — no dependency on the registry here.
# Template for future tool files.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

import time
import json
import paho.mqtt.client as mqtt
from config.settings import settings

_client = None


def _get_client() -> mqtt.Client:
    global _client
    if _client is None:
        _client = mqtt.Client()
        _client.username_pw_set(settings.mqtt_username, settings.mqtt_password)
        _client.tls_set()
        _client.on_connect = lambda c, u, f, r: print(f"[MQTT] Connected → rc={r}")

        print("[MQTT] Connecting to broker...")
        _client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60)
        _client.loop_start()
        time.sleep(1.5)

    return _client


def mqtt_publish(topic: str, payload: str) -> str:
    """
    Send a command or value to a home device via MQTT (lights, switches, scenes, etc).
    topic: MQTT topic, e.g. home/light/livingroom/set
    payload: Payload value, usually ON, OFF, a number, or a JSON string
    """
    client = _get_client()

    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)

    try:
        result = client.publish(topic, payload, qos=1)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Published → {topic} : {payload!r}")
            return f"OK: published to {topic}"
        else:
            return f"Error: publish failed (rc={result.rc})"
    except Exception as e:
        return f"MQTT publish failed: {e}"


if __name__ == "__main__":
    print("=== MQTT Publisher standalone test ===")
    print("Format:  topic  payload   (type 'quit' to exit)\n")
    while True:
        line = input("> ").strip()
        if line.lower() in ("quit", "q", "exit"):
            break
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            print("Format: topic payload")
            continue
        topic, raw_payload = parts
        try:
            raw_payload = json.loads(raw_payload)
        except json.JSONDecodeError:
            pass
        print(f"  → {mqtt_publish(topic, raw_payload)}\n")

    if _client:
        _client.loop_stop()
        _client.disconnect()
