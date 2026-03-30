"""
llm_tools/__init__.py
═══════════════════════════════════════════════════════════════
Tool registry for Jarvis LLM.

HOW TO ADD A NEW TOOL
─────────────────────
1. Create a new file in llm_tools/  e.g. my_tool.py
2. Write your function with type hints + docstring (see function_mqtt_publish.py as template)
3. Add ONE line below in the "Active tools" section:
       from llm_tools.my_tool import my_function; register(my_function)
   That's it. The schema is built automatically.

CURRENTLY ACTIVE
────────────────
  • mqtt_publish  — send MQTT commands to devices

PLANNED (see LLM functions .txt)
─────────────────────────────────
  • get_sensor_status, get_daily_summary, activate_routine,
    get_camera_report, query_past_events, list_available_devices,
    alert_all_phones, speak, vacuum_control, get_energy_usage, confirm_action
═══════════════════════════════════════════════════════════════
"""

import inspect
import typing

_REGISTRY: dict[str, callable] = {}
TOOLS:     list[dict]          = []

_TYPE_MAP = {
    str:   "string",
    int:   "integer",
    float: "number",
    bool:  "boolean",
}


def register(func: callable) -> callable:
    """
    Register a plain function as an LLM-callable tool.
    Builds the OpenAI-compatible JSON schema from type hints + docstring.

    Docstring format:
        First line  → tool description shown to the LLM
        param_name: → per-parameter description (one per line)
    """
    hints    = typing.get_type_hints(func)
    sig      = inspect.signature(func)
    params   = {}
    required = []

    for name, param in sig.parameters.items():
        hint   = hints.get(name, str)
        origin = typing.get_origin(hint)

        # Unwrap Optional[X] → X, and don't mark as required
        if origin is typing.Union:
            inner = [a for a in typing.get_args(hint) if a is not type(None)]
            hint  = inner[0] if inner else str
        else:
            required.append(name)

        json_type  = _TYPE_MAP.get(hint, "string")
        param_desc = ""
        if func.__doc__:
            for line in func.__doc__.splitlines():
                line = line.strip()
                if line.startswith(f"{name}:"):
                    param_desc = line.split(":", 1)[1].strip()
                    break

        params[name] = {"type": json_type, "description": param_desc}

    description = (func.__doc__ or "").strip().splitlines()[0].strip()

    TOOLS.append({
        "type": "function",
        "function": {
            "name":        func.__name__,
            "description": description,
            "parameters": {
                "type":       "object",
                "properties": params,
                "required":   required,
            },
        },
    })
    _REGISTRY[func.__name__] = func
    return func


def dispatch(name: str, args: dict) -> str:
    """Call a registered tool by name. Returns result as string."""
    func = _REGISTRY.get(name)
    if func is None:
        return f"Error: unknown tool '{name}'"
    try:
        return str(func(**args))
    except Exception as e:
        return f"Error calling {name}: {e}"


# ══════════════════════════════════════════════════════════════
# ACTIVE TOOLS — add / remove lines here to enable / disable
# ══════════════════════════════════════════════════════════════
from llm_tools.function_mqtt_publish import mqtt_publish; register(mqtt_publish)  # noqa: E402, E702

# from llm_tools.db_tools import query_system_state; register(query_system_state)
# from llm_tools.db_tools import query_alerts; register(query_alerts)
# from llm_tools.routine_tools import run_routine; register(run_routine)
