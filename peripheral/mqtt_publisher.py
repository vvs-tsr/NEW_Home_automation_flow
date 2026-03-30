# mqtt_publisher.py
# Standalone MQTT publisher utility for the peripheral layer.
# Stub — extend this for publishing sensor readings, status updates, etc.
# For LLM-callable MQTT publishing see: main files/llm_tools/function_mqtt_publish.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        _client.on_connect = lambda c, u, f, r: print(f"[MQTT] Connected rc={r}")
        _client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, keepalive=60)
        _client.loop_start()
        time.sleep(1.5)
    return _client


def publish(topic: str, payload: str | dict, qos: int = 1) -> str:
    """Publish a message to the MQTT broker."""
    client = _get_client()
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)
    try:
        result = client.publish(topic, payload, qos=qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Published → {topic} : {payload!r}")
            return f"OK: published to {topic}"
        return f"Error: rc={result.rc}"
    except Exception as e:
        return f"Publish failed: {e}"


if __name__ == "__main__":
    # TODO: add periodic publishing logic here (e.g. sensor readings)
    print("mqtt_publisher.py stub — extend for your use case.")
