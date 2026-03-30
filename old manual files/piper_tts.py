# piper_tts.py
# Known-working style + standalone test block
# Use your confirmed-good Eminem voice model

from piper.voice import PiperVoice
import wave
import os
import time

VOICES_DIR = "voices"
VOICE_MODEL_NAME = "en_US-eminem-medium.onnx"          # ← your requested voice

_piper_voice = None  # Global singleton


def get_piper_voice(
    model_path: str = os.path.join(VOICES_DIR, VOICE_MODEL_NAME)
) -> PiperVoice | None:
    """
    Lazy-load the Piper voice model (only once).
    Returns None + prints error if model is missing or fails to load.
    """
    global _piper_voice

    if _piper_voice is not None:
        return _piper_voice

    if not os.path.exists(model_path):
        print(f"ERROR: Piper voice model not found at {model_path}")
        print("  → Download from https://github.com/rhasspy/piper/releases")
        print(f"  → Place .onnx + .onnx.json in folder: {VOICES_DIR}/")
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
    Convert text → WAV file using Piper.
    Returns True if file was written successfully.
    """
    voice = get_piper_voice()
    if voice is None:
        print("TTS model not loaded → cannot generate audio.")
        return False

    print(f"Generating TTS → {output_filepath}")
    print(f"  Text (first 60 chars): {text[:60]}{'...' if len(text)>60 else ''}")

    try:
        with wave.open(output_filepath, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        print(f"Audio saved successfully: {output_filepath}")
        print(f"  Size: {os.path.getsize(output_filepath):,} bytes")
        return True
    except Exception as e:
        print(f"Failed to generate WAV: {e}")
        return False


# ────────────────────────────────────────────────
# Standalone test / demo when running this file directly
# ────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 50)
    print(" Piper TTS standalone test")
    print("═" * 50)

    # Pre-load model (shows loading messages)
    if not get_piper_voice():
        print("Cannot continue — model failed to load.")
    else:
        # You can change these test sentences
        test_sentences = [
            "This is a test. Jarvis is speaking with the Eminem voice.",
            "Hey , milan how is life at IIT kanpur? and How ia food at hall 10?" ,
            "Vishnu is awesome ",
            "Beep boop. Testing one two three. This voice has attitude.",
        ]

        OUTPUT_DIR = "tts_test_output"
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        for i, sentence in enumerate(test_sentences, 1):
            filename = os.path.join(
                OUTPUT_DIR,
                f"test_{i}_{int(time.time())}.wav"
            )
            success = generate_tts_wav(sentence, filename)
            if success:
                print(f"   → Created: {os.path.basename(filename)}")
            print("-" * 60)

        print("\nAll tests finished.")
        print(f"Listen to the files in: ./{OUTPUT_DIR}/")
        print("You can now safely import and use generate_tts_wav() in other scripts.")