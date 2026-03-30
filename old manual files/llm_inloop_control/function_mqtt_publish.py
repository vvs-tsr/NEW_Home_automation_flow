# mqtt_publisher.py
import paho.mqtt.client as mqtt
import time
import json

# ── Configuration ────────────────────────────────────────────────
BROKER   = "51552d777a9f492cba1b3cc4ef6b37a9.s1.eu.hivemq.cloud"
PORT     = 8883
USERNAME = "pythontester1"
PASSWORD = "YOUR_MQTT_PASSWORD_HERE"

# You can change default topic later — but better to always pass it explicitly
DEFAULT_TOPIC = "home/test"

# Global client (created once, reused)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = mqtt.Client()
        _client.username_pw_set(USERNAME, PASSWORD)
        _client.tls_set()  # required for HiveMQ Cloud
        _client.on_connect = lambda c, u, f, r: print(f"[MQTT] Connected → result code {r}")

        print("[MQTT] Connecting to broker...")
        _client.connect(BROKER, PORT, keepalive=60)
        _client.loop_start()
        time.sleep(1.5)  # give connection a moment

    return _client


def mqtt_publish(topic: str, payload: str | dict, qos: int = 1) -> str:
    """
    Publishes a message to MQTT.
    payload can be str or dict (dict gets auto-converted to JSON)
    
    Returns: success message or error string
    """
    client = _get_client()

    # Auto-convert dict → JSON string
    if isinstance(payload, dict):
        payload = json.dumps(payload, ensure_ascii=False)

    try:
        result = client.publish(topic, payload, qos=qos)
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Published → {topic} : {payload!r}")
            return f"OK: published to {topic}"
        else:
            return f"Error: publish failed (rc={result.rc})"
    except Exception as e:
        return f"❌ MQTT publish failed: {str(e)}"


def main():
    print("=== MQTT Publisher Test (standalone) ===")
    print("Enter lines in format:  topic  payload")
    print("Example: home/light/living on")
    print("         home/sensor/temp  {\"value\":23.5, \"unit\":\"°C\"}")
    print("(type 'quit' to exit)\n")

    while True:
        line = input("> ").strip()
        if line.lower() in ('quit', 'q', 'exit'):
            break

        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            print("Format: topic payload")
            continue

        topic = parts[0]
        payload = parts[1]

        # Optional: try to interpret payload as JSON if it looks like one
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            pass  # keep as string

        result = mqtt_publish(topic, payload)
        print(f"  → {result}\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye.")
    finally:
        if _client is not None:
            _client.loop_stop()
            _client.disconnect()