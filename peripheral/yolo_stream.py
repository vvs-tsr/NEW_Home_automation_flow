# yolo_stream.py
# YOLO camera monitoring — reads IP camera stream, runs YOLOv8 inference,
# publishes security alerts (person/vehicle/animal) via MQTT with debouncing,
# and serves the annotated stream via a Flask MJPEG endpoint.
# Moved from: old manual files/yolo_gpu_b.py

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import time
import json
import threading
from datetime import datetime

import cv2
import torch
import paho.mqtt.client as mqtt
from flask import Flask, Response, render_template_string
from ultralytics import YOLO

from config.settings import settings

# ── Configuration ─────────────────────────────────────────────────────────────
IPCAM_URL          = settings.camera_source
MODEL_PATH         = settings.yolo_model_path
CONF_THRESHOLD     = 0.4
BUFFER_SIZE        = 1
MQTT_TOPIC_ALERTS  = "home/ip_cam/yolo_alerts"
MQTT_CLIENT_ID     = f"yolo_processor_{int(time.time())}"

FLASK_HOST                 = "0.0.0.0"
FLASK_PORT                 = 5000
OUTPUT_STREAM_RESOLUTION   = (640, 480)

ALERT_DEBOUNCE_TIME = 10  # seconds between same-class alerts

SECURITY_CLASSES = [
    "person",
    "bicycle", "car", "motorcycle", "bus", "truck", "train", "airplane", "boat",
    "cat", "dog", "horse", "sheep", "cow", "bear",
]

# ── MQTT setup ────────────────────────────────────────────────────────────────
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=MQTT_CLIENT_ID)
mqtt_client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

def on_connect(client, userdata, flags, rc):
    status = "Connected" if rc == 0 else f"Failed (rc={rc})"
    print(f"[MQTT] {status} to {settings.mqtt_broker_host}")

try:
    mqtt_client.on_connect = on_connect
    mqtt_client.tls_set()
    mqtt_client.connect(settings.mqtt_broker_host, settings.mqtt_broker_port, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT] Connection error: {e}")

# ── YOLO model ────────────────────────────────────────────────────────────────
try:
    model = YOLO(MODEL_PATH)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    print(f"[YOLO] Model '{MODEL_PATH}' loaded on {device.upper()}")
except Exception as e:
    print(f"[YOLO] Error loading model: {e}")
    raise SystemExit(1)

# ── Flask stream ──────────────────────────────────────────────────────────────
output_frame = None
lock = threading.Lock()

app = Flask(__name__)

HTML_PAGE = """
<html>
  <head><title>YOLO Stream</title>
  <style>body { font-family: sans-serif; text-align: center; background: #333; color: #eee; }</style>
  </head>
  <body>
    <h1>Live YOLO Annotated Stream</h1>
    <img src="{{ url_for('video_feed') }}" width="640" height="480" style="border: 2px solid #0f0;">
  </body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

def generate_frames():
    global output_frame
    while True:
        with lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            ret, buffer = cv2.imencode(".jpg", output_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
        time.sleep(0.03)

@app.route("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

threading.Thread(
    target=lambda: app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False, threaded=True),
    daemon=True,
).start()
print(f"[Flask] Stream at http://{FLASK_HOST}:{FLASK_PORT}/video_feed")

# ── Main loop ─────────────────────────────────────────────────────────────────
last_alert_times: dict[str, datetime] = {}

cap = cv2.VideoCapture(IPCAM_URL, cv2.CAP_FFMPEG)
cap.set(cv2.CAP_PROP_BUFFERSIZE, BUFFER_SIZE)
time.sleep(1)

if not cap.isOpened():
    print(f"[Camera] Cannot open stream from {IPCAM_URL}")
    raise SystemExit(1)

print(f"[Camera] Stream opened from {IPCAM_URL}")

while True:
    ret, frame = cap.read()
    if not ret:
        print("[Camera] Frame not received — attempting reconnect...")
        cap.release()
        time.sleep(2)
        cap = cv2.VideoCapture(IPCAM_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, BUFFER_SIZE)
        time.sleep(1)
        if not cap.isOpened():
            print("[Camera] Reconnect failed. Exiting.")
            break
        print("[Camera] Reconnected.")
        continue

    try:
        results = model(frame, conf=CONF_THRESHOLD, verbose=False)
    except Exception as e:
        print(f"[YOLO] Inference error: {e} — skipping frame")
        continue

    annotated_frame        = frame.copy()
    new_detections_for_mqtt = []
    now = datetime.now()

    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label  = model.names[cls_id]
            conf   = float(box.conf[0])

            if label not in SECURITY_CLASSES:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
            cv2.putText(
                annotated_frame, f"{label} {conf:.2f}",
                (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2,
            )

            last = last_alert_times.get(label)
            if last is None or (now - last).total_seconds() > ALERT_DEBOUNCE_TIME:
                new_detections_for_mqtt.append({"label": label, "confidence": round(conf, 2)})
                last_alert_times[label] = now

    if new_detections_for_mqtt:
        alert_payload = {
            "ts":     int(time.time()),
            "source": "vision",
            "entity": "ip_camera",
            "type":   "object_detected",
            "data": {
                "objects":      [d["label"] for d in new_detections_for_mqtt],
                "confidences":  [d["confidence"] for d in new_detections_for_mqtt],
                "count":        len(new_detections_for_mqtt),
            },
        }
        try:
            mqtt_client.publish("event/vision/detection", json.dumps(alert_payload))
            print(f"[MQTT] Alert: {[d['label'] for d in new_detections_for_mqtt]}")
        except Exception as e:
            print(f"[MQTT] Publish error: {e}")

    try:
        resized = cv2.resize(annotated_frame, OUTPUT_STREAM_RESOLUTION)
        with lock:
            output_frame = resized.copy()
    except Exception as e:
        print(f"[Frame] Resize error: {e}")
        continue

# ── Cleanup ───────────────────────────────────────────────────────────────────
cap.release()
cv2.destroyAllWindows()
mqtt_client.loop_stop()
mqtt_client.disconnect()
print("YOLO stream stopped.")
