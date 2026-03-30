# transcribe_function.py
from faster_whisper import WhisperModel

# Initialize model once globally if this script is part of a larger application
# Or pass it in if the model is initialized in the main server
_whisper_model = None

def get_whisper_model(model_size="base", device="cuda", compute_type="float16"):
    global _whisper_model
    if _whisper_model is None:
        print(f"Loading Whisper model '{model_size}' (device: {device}, type: {compute_type})...")
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type)
    return _whisper_model

def transcribe_audio_file(audio_filepath: str) -> str:
    """
    Transcribes an audio file using Faster Whisper.
    Args:
        audio_filepath: Path to the WAV file to transcribe.
    Returns:
        The transcribed text.
    """
    model = get_whisper_model() # Get or initialize the model
    
    print(f"Transcribing {audio_filepath}...")
    segments, info = model.transcribe(audio_filepath)
    
    full_transcript = []
    for segment in segments:
        full_transcript.append(segment.text)
    
    print(f"Detected language: {info.language}")
    print("Transcription complete.")
    return " ".join(full_transcript)

# Example usage if run directly (for testing)
if __name__ == "__main__":
    test_audio = "audio_16k_mono2.wav" # Ensure this file exists for testing
    if _whisper_model is None: # Load model only if not already loaded for main server
        get_whisper_model()
    
    if input(f"Transcribe '{test_audio}'? (y/n): ").lower() == 'y':
        transcript = transcribe_audio_file(test_audio)
        print("\nFull Transcript:")
        print(transcript)