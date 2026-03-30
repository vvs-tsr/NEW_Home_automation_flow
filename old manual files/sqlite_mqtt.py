import json, time, sqlite3, ssl
from paho.mqtt.client import Client

# ==== MQTT CONFIG ====
BROKER = "51552d777a9f492cba1b3cc4ef6b37a9.s1.eu.hivemq.cloud"
PORT = 8883
USERNAME = "db_logger"
PASSWORD = "YOUR_MQTT_PASSWORD_HERE"
CLIENT_ID = "db_sqlite_logger"

# ==== SQLITE SETUP ====
conn = sqlite3.connect("events.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER,
  source TEXT,
  entity TEXT,
  event_type TEXT,
  severity TEXT,
  payload TEXT
)
""")
conn.commit()

# ==== MQTT CALLBACK ====
def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())

        event = {
             "ts": data.get("ts", int(time.time())),
             "source": data.get("source", msg.topic.split("/")[0]),
             "entity": data.get("entity", msg.topic),
            "event_type": data.get("type", data.get("name", "unknown")),
            "severity": "info",
          "payload": json.dumps(data)          # full rich payload
}

        cur.execute("""
            INSERT INTO events (ts, source, entity, event_type, severity, payload)
            VALUES (?, ?, ?, ?, ?, ?)
        """, tuple(event.values()))

        conn.commit()

    except Exception as e:
        print("Error processing message:", e)

# ==== MQTT CLIENT ====
client = Client(client_id=CLIENT_ID)

# Credentials
client.username_pw_set(USERNAME, PASSWORD)

# TLS (REQUIRED for HiveMQ Cloud)
client.tls_set(
    cert_reqs=ssl.CERT_REQUIRED,
    tls_version=ssl.PROTOCOL_TLS
)

client.on_message = on_message

# Connect & subscribe
client.connect(BROKER, PORT)
client.subscribe("event/#")          # ← HA devices
#client.subscribe("telemetry/#")      # ← your own devices

print("SQLite MQTT logger running...")
client.loop_forever()
