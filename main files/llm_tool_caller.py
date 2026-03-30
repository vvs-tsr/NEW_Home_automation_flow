# llm_tool_caller.py
# Groq LLM client with tool-calling support.
# Exposes:
#   query_llm(text)              — simple one-shot query (used by echobud_server.py)
#   run_llm_with_tools(messages) — full agentic tool-calling loop

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import json
from groq import Groq
from config.settings import settings
from llm_tools import TOOLS, dispatch

SYSTEM_PROMPT = """
You are Jarvis, a helpful home-automation assistant and butler.
You know about sensors, cameras, YOLO detections, MQTT events, and daily summaries.
Answer clearly, concisely, and be a little fun when it fits.
ALWAYS keep replies under 140 words (like a polite butler — never ramble).
Do not use any Markdown formatting (no **bold**, *italic*, # headers, - lists).
Do not use special characters like *, # since your response will be spoken by TTS.
Write in plain text only.
When the user wants to control a device, use the available tools.
Common MQTT patterns:
  home/light/<room>/set → ON / OFF
  home/switch/<name>/set → ON / OFF
  home/scene/<name>/activate → ON
Do NOT hallucinate topics — only use ones that make sense.
"""

_client = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


def query_llm(text: str) -> str | None:
    """
    Simple one-shot LLM query with no tool calling.
    Used by echobud_server for basic voice responses.
    Returns the reply string, or None on error.
    """
    try:
        response = _get_client().chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": text},
            ],
            model=settings.llm_model,
            temperature=0.7,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM query failed: {e}")
        return None


def run_llm_with_tools(messages: list) -> list:
    """
    Agentic tool-calling loop.
    Keeps calling the LLM until it returns a plain text response
    (no more tool calls). Dispatches tool calls via llm_tools.dispatch().

    Args:
        messages: OpenAI-format message list (must include system + user messages).
    Returns:
        Updated messages list with the final assistant reply appended.
    """
    client = _get_client()

    while True:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.7,
            max_tokens=512,
        )

        choice = response.choices[0]
        msg = choice.message
        messages.append(msg)

        if msg.tool_calls:
            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                args      = json.loads(tool_call.function.arguments)

                print(f"\n[TOOL CALL] {func_name}({args})")
                result = dispatch(func_name, args)
                print(f"[TOOL RESULT] {result}")

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "name":         func_name,
                    "content":      str(result),
                })
        else:
            print(f"\nJarvis: {msg.content.strip()}")
            return messages


def main():
    print("=== Jarvis LLM + Tool Calling ===")
    print("Type 'quit' to exit\n")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

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
