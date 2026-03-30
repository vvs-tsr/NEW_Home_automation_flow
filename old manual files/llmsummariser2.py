import sqlite3
import time
import json
from datetime import datetime
from google import genai
from google.genai import types

# -----------------------------
# CONFIG
# ---------------'--------------
GEMINI_API_KEY = "Your_GEMINI_API_KEY"
SHOW_PREVIEW = True          # ← Set to False when you don't want to see the raw events anymore
PREVIEW_LIMIT = 25           # How many events to show in preview (avoid flooding terminal)

client = genai.Client(api_key=GEMINI_API_KEY)

# -----------------------------
# 1. Database
# -----------------------------
print("=== Database operations ===")
print("Connecting to events.db ...")
conn = sqlite3.connect("events.db")
cur = conn.cursor()
print("Connection successful.")

today_start = int(time.mktime(datetime.now().date().timetuple()))
print(f"Fetching events from midnight today (timestamp >= {today_start})")

cur.execute("""
    SELECT ts, source, entity, event_type, payload
    FROM events
    WHERE ts >= ?
    ORDER BY ts ASC
""", (today_start,))

rows = cur.fetchall()

print(f"Found {len(rows)} events today.")
conn.close()
print("Database connection closed.")

if not rows:
    print("No events today.")
    exit()

# ────────────────────────────────────────────────
# Optional: Print preview of what would be sent to LLM
# Very useful when tuning what details reach the model
# ────────────────────────────────────────────────
if SHOW_PREVIEW:
    print("\n" + "="*60)
    print("=== RAW EVENTS PREVIEW (first {} events) ===".format(PREVIEW_LIMIT))
    print("="*60)
    
    for i, (ts, source, entity, event_type, payload_str) in enumerate(rows[:PREVIEW_LIMIT], 1):
        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
        payload_preview = payload_str[:140] + "..." if len(payload_str) > 140 else payload_str
        print(f"{i:3d}. [{time_str}] {source:8} | {entity:30} | {event_type:14} | {payload_preview}")
    
    if len(rows) > PREVIEW_LIMIT:
        print(f"... ({len(rows) - PREVIEW_LIMIT} more events not shown)")
    print("="*60 + "\n")
# ────────────────────────────────────────────────

# -----------------------------
# 2. Build richer event log for LLM (start using payload!)
# -----------------------------
event_lines = []
for ts, source, entity, event_type, payload_str in rows:
    time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    
    extra = ""
    try:
        payload = json.loads(payload_str)
        
        # ── Add useful context depending on source / event ──
        if source == "vision" and "objects" in payload:
            objs = payload.get("objects", [])
            confs = payload.get("confidences", [])
            if objs:
                pairs = [f"{o} ({c:.0%})" for o, c in zip(objs, confs) if c > 0.4]
                extra = f" → detected {', '.join(pairs)}"
        
        elif "name" in payload and payload["name"] in ["on", "off", "toggle"]:
            extra = f" → {payload['name']}"
            if "brightness" in payload:
                extra += f" (brightness {payload['brightness']})"
        
        elif "reason" in payload:
            extra = f" (reason: {payload.get('reason')})"
        
        elif "from" in payload and "to" in payload:
            extra = f" {payload['from']} → {payload['to']}"
    
    except json.JSONDecodeError:
        extra = " (invalid json)"
    except Exception:
        extra = ""
    
    line = f"[{time_str}] ({source}) {entity} → {event_type}{extra}"
    event_lines.append(line)

events_text = "\n".join(event_lines)

# -----------------------------
# 3. Prompt – now has much more context
# -----------------------------
prompt = f"""
You are a home automation assistant named Jarvis.
Below is a chronological log of meaningful events that happened today in the home.

Summarise the day for the owner in natural language:
- Focus on security, arrivals/departures, deliveries, unusual activity
- Mention specific objects detected by cameras if relevant (person, package, vehicle, animal…)
- Note important device state changes (lights, doors, vacuum, etc.)
- Ignore boring repetitive noise (temperature ticks, tiny brightness changes)
- Be concise, human-readable, use times only when they matter
- If nothing interesting happened, just say so honestly

EVENT LOG:
{events_text}
"""

# -----------------------------
# 4. Gemini call
# -----------------------------
MODEL_NAME = "gemini-2.5-flash"

print(f"=== Using model: {MODEL_NAME} ===")
print("Sending request to Gemini...")

try:
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            # max_output_tokens=600,   # uncomment & tune if summaries get cut off
        )
    )
    summary = response.text.strip()
    print("Generation successful.")
except Exception as e:
    print(f"Generation failed: {e}")
    summary = "Could not generate summary due to an error."

# -----------------------------
# Output
# -----------------------------
print("\n" + "="*50)
print("===== DAILY SUMMARY =====")
print("="*50 + "\n")
print(summary)
