# sst.py
# Whisper speech-to-text — wraps faster-whisper with lazy model loading.
# Exposes: get_whisper_model(), transcribe_audio_file()

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from faster_whisper import WhisperModel

_whisper_model = None


def get_whisper_model() -> WhisperModel:
    global _whisper_model
    if _whisper_model is None:
        model_size    = settings.whisper_model
        device        = settings.whisper_device
        compute_type  = "float16" if device == "cuda" else "int8"
        print(f"Loading Whisper model '{model_size}' (device: {device}, compute: {compute_type})...")
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _whisper_model


def transcribe_audio_file(audio_filepath: str) -> str:
    """
    Transcribes a WAV file using Faster Whisper.
    Returns the full transcript as a single string.
    """
    model = get_whisper_model()
    print(f"Transcribing {audio_filepath}...")
    segments, info = model.transcribe(audio_filepath)
    transcript = " ".join(seg.text for seg in segments)
    print(f"Detected language: {info.language} | Transcription complete.")
    return transcript


if __name__ == "__main__":
    test_audio = input("Path to WAV file to transcribe: ").strip()
    if os.path.exists(test_audio):
        print(transcribe_audio_file(test_audio))
    else:
        print(f"File not found: {test_audio}")
