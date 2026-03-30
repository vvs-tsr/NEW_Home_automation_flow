# llm_api_test.py
import os
from groq import Groq # pip install groq
import sys

# --- Configuration  ---
GROQ_API_KEY = "gsk_YOUR_GROQ_API_KEY_HERE"

# Choose your Groq model. 
GROQ_MODEL = "openai/gpt-oss-120b" 

# --- SYSTEM PROMPT for Jarvis ---
SYSTEM_PROMPT = """
You are a helpful, friendly home-automation assistant/butler named Jarvis.
You know about sensors, cameras, YOLO detections, MQTT events, and daily summaries.
Answer clearly, concisely, and be a little fun when it fits.
ALWAYS keep replies under 140 words (like a polite butler — never ramble).
Do not use any Markdown formatting (no **bold**, *italic*, # headers, - lists, etc.).
Do not use special characters like *, # since your response is going to be spoken by a text-to-speech model.
Write in plain text only.

When the question requires current information, news, weather, dates or facts beyond your training,
use the available search tool to get up-to-date information before answering.
Always be honest if you used search and mention key sources briefly.
"""

# Initialize Groq client once globally
client = Groq(api_key=GROQ_API_KEY)


def query_groq_llm_bare(text_input: str, model: str = GROQ_MODEL) -> str | None:
    """
    Queries the Groq LLM API with the given text input, including a system prompt.
    Bare minimum implementation with hardcoded API key.
    Args:
        text_input: The user's prompt to send to the LLM.
        model: The Groq model to use.
    Returns:
        The LLM's generated text response, or None if an error occurs.
    """
    if GROQ_API_KEY == "gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE":
        print("ERROR: Please replace 'gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE' with your real Groq API key.")
        return None

    print(f"Querying Groq LLM '{model}' with input: '{text_input}'...")
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT}, # <-- NEW: System Prompt
                {"role": "user", "content": text_input},     # <-- User's input
            ],
            model=model,
            temperature=0.7, 
            max_tokens=512, 
        )
        
        return chat_completion.choices[0].message.content.strip()

    except Exception as e:
        print(f"An error occurred during Groq LLM query: {e}")
        return None

if __name__ == "__main__":
    print("--- Groq LLM API Test (Bare Minimum with System Prompt) ---")
    
    if GROQ_API_KEY == "gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE":
        print("Please replace 'gsk_YOUR_ACTUAL_GROQ_API_KEY_HERE' with your real Groq API key to run tests.")
        sys.exit(1)

    test_prompts = [
        "tell me a joke ",
        "twll me a tech joke.",
        "tell me a motivational quote?", # Test system prompt awareness
    ]

    for i, prompt in enumerate(test_prompts):
        print(f"\n--- Test {i+1} ---")
        print(f"Prompt: {prompt}")
        response = query_groq_llm_bare(prompt)
        if response:
            print(f"LLM Response:\n{response}")
        else:
            print("Failed to get LLM response.")
    
    while True:
        user_input = input("\nEnter a prompt (or 'quit' to exit): ")
        if user_input.lower() == 'quit':
            break
        
        response = query_groq_llm_bare(user_input)
        if response:
            print(f"LLM Response:\n{response}")
        else:
            print("Failed to get LLM response.")