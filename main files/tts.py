# tts.py
# Piper text-to-speech — wraps piper-tts with lazy voice model loading.
# Exposes: get_piper_voice(), generate_tts_wav()

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import wave
import time
from config.settings import settings
from piper.voice import PiperVoice

_piper_voice = None


def get_piper_voice() -> PiperVoice | None:
    """Lazy-load the Piper voice model (only once). Returns None on failure."""
    global _piper_voice

    if _piper_voice is not None:
        return _piper_voice

    model_path = os.path.join(settings.piper_model_path, settings.piper_voice)

    if not os.path.exists(model_path):
        print(f"ERROR: Piper voice model not found at {model_path}")
        print("  → Download from https://github.com/rhasspy/piper/releases")
        print(f"  → Place .onnx + .onnx.json in: {settings.piper_model_path}/")
        return None

    print(f"Loading Piper TTS voice: {model_path} ...")
    try:
        _piper_voice = PiperVoice.load(model_path)
        print("Piper TTS model loaded successfully.")
    except Exception as e:
        print(f"Error loading Piper TTS model: {e}")
        _piper_voice = None

    return _piper_voice


def generate_tts_wav(text: str, output_filepath: str) -> bool:
    """
    Convert text to a WAV file using Piper.
    Returns True if the file was written successfully.
    """
    voice = get_piper_voice()
    if voice is None:
        print("TTS model not loaded → cannot generate audio.")
        return False

    print(f"Generating TTS → {output_filepath}")
    print(f"  Text (first 60 chars): {text[:60]}{'...' if len(text) > 60 else ''}")

    try:
        with wave.open(output_filepath, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        print(f"Audio saved: {output_filepath} ({os.path.getsize(output_filepath):,} bytes)")
        return True
    except Exception as e:
        print(f"Failed to generate WAV: {e}")
        return False


if __name__ == "__main__":
    print("Piper TTS standalone test")
    if not get_piper_voice():
        print("Cannot continue — model failed to load.")
    else:
        test_sentences = [
            "This is a test. Jarvis is speaking.",
            "All systems nominal. How can I help you today?",
        ]
        os.makedirs("tts_test_output", exist_ok=True)
        for i, sentence in enumerate(test_sentences, 1):
            out = os.path.join("tts_test_output", f"test_{i}_{int(time.time())}.wav")
            generate_tts_wav(sentence, out)
        print("Done. Check tts_test_output/")
