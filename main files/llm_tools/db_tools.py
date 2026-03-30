# db_tools.py
# Database query tools — callable by the LLM via the @register registry.
# Stub implementations — wire up to memory/logger.py queries when ready.

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv()

from typing import Optional
from config.settings import settings
from llm_tools import register


@register
def query_system_state(entity: str) -> str:
    """
    Query the current state of a home device or sensor from the event log.
    entity: Device or sensor name, e.g. bedroom_temp, livingroom_lux, lamp1
    """
    # TODO: query memory/echobud.db — SELECT latest event for this entity
    return f"[stub] State for '{entity}' not yet implemented. Connect to {settings.db_path}."


@register
def query_alerts(hours: Optional[int] = None) -> str:
    """
    Query recent security alerts detected by the camera system.
    hours: How many hours back to look (default: 24)
    """
    hours = hours or 24
    # TODO: query alerts table in memory/echobud.db
    return f"[stub] Alerts for last {hours}h not yet implemented. Connect to {settings.db_path}."
