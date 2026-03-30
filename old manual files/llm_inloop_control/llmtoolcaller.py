# llm_mqtt_tester.py
from groq import Groq
import json
import sys

# ── Your Groq setup ──────────────────────────────────────────────
GROQ_API_KEY = "gsk_YOUR_GROQ_API_KEY_HERE"
MODEL = "openai/gpt-oss-120b"   

client = Groq(api_key=GROQ_API_KEY)

# ── Import our MQTT function ─────────────────────────────────────
from function_mqtt_publish import mqtt_publish

# ── Tool definition (OpenAI-compatible format for Groq) ──────────
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "mqtt_publish",
            "description": "Send a command or value to a device via MQTT (lights, switches, sensors, etc)",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "MQTT topic, e.g. home/light/livingroom/set"
                    },
                    "payload": {
                        "type": "string",
                        "description": "Payload - usually 'ON', 'OFF', number, or JSON string"
                    }
                },
                "required": ["topic", "payload"]
            }
        }
    }
]


def run_llm_with_tools(messages):
    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=512
        )

        choice = response.choices[0]
        msg = choice.message
        messages.append(msg)

        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)

                print(f"\n[TOOL CALL] {func_name}({args})")

                if func_name == "mqtt_publish":
                    topic = args.get("topic")
                    payload = args.get("payload")
                    result = mqtt_publish(topic, payload)
                    print(f"[TOOL RESULT] {result}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": result
                    })
                else:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": func_name,
                        "content": "Unknown tool"
                    })
        else:
            # normal text response → show and exit loop
            print("\nJarvis:", msg.content.strip())
            return messages


def main():
    print("=== LLM + MQTT Function Calling Test ===")
    print("Talk to Jarvis. He can publish MQTT messages when needed.")
    print("Type 'quit' or Ctrl+C to exit\n")

    messages = [
        {"role": "system", "content": (
            "You are Jarvis, a helpful home assistant. "
            "Be concise and friendly. "
            "When the user wants to control a device (light, fan, switch, etc), "
            "use the mqtt_publish tool with a proper topic and payload. "
            "Common patterns:\n"
            "Do not use any Markdown formatting (no **bold**, *italic*, # headers, - lists, etc.)."
            "Do not use special characters like *, # since your response is going to be spoken by a text-to-speech model."
            "  home/light/<room>/set → ON / OFF\n"
            "  home/switch/<name>/set → ON / OFF\n"
            "  home/scene/<name>/activate → ON\n"
            "Do NOT hallucinate topics — only use ones that make sense."
        )}
    ]

    try:
        while True:
            user_input = input("You: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                break
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})
            messages = run_llm_with_tools(messages)
            print("-" * 60)
    except KeyboardInterrupt:
        print("\nGoodbye.")


if __name__ == "__main__":
    main()