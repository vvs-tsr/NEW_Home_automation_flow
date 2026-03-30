# routine_tools.py
# Home routine tools — callable by the LLM via the @register registry.
# Stub implementation — define your routines and wire up MQTT sequences when ready.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from llm_tools import register

# Map routine names to sequences of (topic, payload) tuples
# Add your own routines here
ROUTINES: dict[str, list[tuple[str, str]]] = {
    "good_night": [
        ("home/light/livingroom/set", "OFF"),
        ("home/light/bedroom/set",    "OFF"),
        ("home/switch/tv/set",        "OFF"),
    ],
    "movie_mode": [
        ("home/light/livingroom/set", "OFF"),
        ("home/switch/tv/set",        "ON"),
    ],
    "good_morning": [
        ("home/light/bedroom/set",    "ON"),
        ("home/light/livingroom/set", "ON"),
    ],
}


@register
def run_routine(name: str) -> str:
    """
    Run a named home routine that triggers a sequence of device commands.
    name: Routine name, e.g. good_night, movie_mode, good_morning
    """
    routine = ROUTINES.get(name.lower().replace(" ", "_"))
    if routine is None:
        available = ", ".join(ROUTINES.keys())
        return f"Unknown routine '{name}'. Available: {available}"

    # TODO: import and call mqtt_publish for each step once fully wired
    # from llm_tools.function_mqtt_publish import mqtt_publish
    # for topic, payload in routine:
    #     mqtt_publish(topic, payload)

    steps = "\n".join(f"  {t} → {p}" for t, p in routine)
    return f"[stub] Routine '{name}' would run:\n{steps}\nUncomment MQTT calls to activate."
