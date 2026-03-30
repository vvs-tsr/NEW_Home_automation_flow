# echobud_server.py
# Full closed-loop Jarvis voice interaction: wake → STT → LLM → TTS → playback
# With resampling to force 16000 Hz for ESP32 I2S compatibility
# Now supports mic_end signal from ESP32

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import socket
import wave
import time
import threading
from enum import Enum, auto

from dotenv import load_dotenv
load_dotenv()

from config.settings import settings
from sst import transcribe_audio_file, get_whisper_model
from llm_tool_caller import run_llm_with_tools, SYSTEM_PROMPT
from tts import generate_tts_wav, get_piper_voice

import soundfile as sf
import librosa

# ── Configuration ────────────────────────────────────────────────────────────
UDP_AUDIO_PORT   = settings.udp_audio_port
UDP_CONTROL_PORT = settings.udp_control_port
ESP_IP           = settings.udp_host
SPEAKER_PORT     = settings.udp_speaker_port

RECORD_SECONDS   = 8.0          # safety net — mic_end from ESP32 fires earlier for short commands
CHUNK_SIZE       = 2048         # bytes per UDP packet (~64 ms @ 16 kHz)
WAV_SAVE_DIR     = "captures"   # Directory for input & output WAVs
WAKE_DELAY       = 0.50         # seconds — give ESP time to switch to SPEAK_READY

# ── PC State Machine ─────────────────────────────────────────────────────────
class PcState(Enum):
    IDLE_WAIT      = auto()
    LISTEN_READY   = auto()
    LISTENING      = auto()
    PROCESSING     = auto()

current_pc_state = PcState.IDLE_WAIT
print(f"PC Echo-Bud Server starting in state: {current_pc_state.name}")

# ── Globals ──────────────────────────────────────────────────────────────────
capturing_audio    = False
capture_start_time = 0
audio_frames       = []

shutdown_flag = threading.Event()

# ── Sockets ──────────────────────────────────────────────────────────────────
audio_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
audio_sock.bind(("0.0.0.0", UDP_AUDIO_PORT))
audio_sock.settimeout(0.1)

control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
control_sock.bind(("0.0.0.0", UDP_CONTROL_PORT))
control_sock.settimeout(0.1)

# ── Utility Functions ────────────────────────────────────────────────────────
def transition_state(new_state: PcState):
    global current_pc_state
    print(f"State Transition: {current_pc_state.name} → {new_state.name}")
    current_pc_state = new_state

def save_audio_recording(frames_data: list) -> str | None:
    if not os.path.exists(WAV_SAVE_DIR):
        os.makedirs(WAV_SAVE_DIR)

    filename = os.path.join(WAV_SAVE_DIR, f"input_{int(time.time())}.wav")
    try:
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            for frame in frames_data:
                wf.writeframes(frame)
        print(f"Audio saved: {filename} ({len(frames_data)} chunks)")
        return filename
    except Exception as e:
        print(f"Save failed: {e}")
        return None

def force_16000_hz(input_path: str) -> str:
    """Resample Piper output to exactly 16000 Hz if needed"""
    try:
        y, sr = librosa.load(input_path, sr=None, mono=True)
        print(f"DEBUG: TTS generated at {sr} Hz, {len(y)/sr:.1f} seconds")

        if sr == 16000:
            print("Already 16000 Hz — no resampling needed")
            return input_path

        output_path = input_path.replace(".wav", "_16khz.wav")
        print(f"Resampling {sr} Hz → 16000 Hz...")
        y_res = librosa.resample(y=y, orig_sr=sr, target_sr=16000)
        sf.write(output_path, y_res, 16000, subtype='PCM_16')
        print(f"Resampled file ready: {output_path}")
        return output_path
    except Exception as e:
        print(f"Resampling failed ({e}) — falling back to original file")
        return input_path

def play_response_to_echobud(response_wav_path: str) -> bool:
    if not os.path.exists(response_wav_path):
        print(f"Response file missing: {response_wav_path}")
        return False

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        sock.sendto(b"speak_now", (ESP_IP, UDP_CONTROL_PORT))
        print(f"→ Sent speak_now to {ESP_IP}:{UDP_CONTROL_PORT}")
        time.sleep(WAKE_DELAY)

        data, sr = sf.read(response_wav_path, dtype='int16')
        print(f"DEBUG playback: {len(data)} samples @ {sr} Hz")

        if sr != 16000:
            print(f"Warning: still not 16000 Hz — playback may sound off")

        if len(data.shape) > 1:
            data = data.mean(axis=1).astype('int16')

        duration_sec = len(data) / 16000
        print(f"→ Streaming {duration_sec:.1f} seconds")

        if duration_sec < 0.5:
            print("WARNING: Audio is too short — likely silent TTS output")

        chunk_samples = 512
        start_time = time.time()
        bytes_sent = 0

        for i in range(0, len(data), chunk_samples):
            chunk = data[i:i + chunk_samples]
            sock.sendto(chunk.tobytes(), (ESP_IP, SPEAKER_PORT))
            bytes_sent += len(chunk) * 2

            elapsed = time.time() - start_time
            expected = bytes_sent / (sr * 2)
            sleep_t = expected - elapsed
            if sleep_t > 0:
                time.sleep(sleep_t)

        print("→ Playback stream finished")
        return True

    except Exception as e:
        print(f"Playback failed: {e}")
        return False
    finally:
        if sock:
            sock.close()

# ── Threads ──────────────────────────────────────────────────────────────────
def audio_listener_thread():
    global capturing_audio, capture_start_time, audio_frames
    while not shutdown_flag.is_set():
        if capturing_audio:
            try:
                data, _ = audio_sock.recvfrom(CHUNK_SIZE)
                audio_frames.append(data)

                if time.time() - capture_start_time >= RECORD_SECONDS:
                    print("→ 10-second timeout reached (safety net)")
                    capturing_audio = False
                    transition_state(PcState.PROCESSING)
            except socket.timeout:
                continue
            except Exception as e:
                print(f"Audio thread error: {e}")
        else:
            time.sleep(0.03)

def control_listener_thread():
    global capturing_audio, capture_start_time, audio_frames
    while not shutdown_flag.is_set():
        try:
            data, addr = control_sock.recvfrom(1024)
            msg = data.decode("utf-8", errors="ignore").strip('\x00')

            if msg == "wake_trigger":
                if not capturing_audio:
                    print(f"[{time.strftime('%H:%M:%S')}] Wake trigger from {addr}")
                    capturing_audio = True
                    capture_start_time = time.time()
                    audio_frames.clear()
                    transition_state(PcState.LISTENING)
                else:
                    print("Already capturing → ignoring duplicate trigger")

            elif msg == "mic_end":
                if capturing_audio:
                    elapsed = time.time() - capture_start_time
                    print(f"→ mic_end received from ESP after {elapsed:.1f} seconds → processing now")
                    capturing_audio = False
                    transition_state(PcState.PROCESSING)
                else:
                    print("mic_end received but not capturing → ignoring")

        except socket.timeout:
            continue
        except Exception as e:
            print(f"Control thread error: {e}")

# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Pre-loading models...")
    get_whisper_model()
    get_piper_voice()

    audio_thread   = threading.Thread(target=audio_listener_thread,   daemon=True)
    control_thread = threading.Thread(target=control_listener_thread, daemon=True)
    audio_thread.start()
    control_thread.start()

    print("\nEcho-Bud Server running. Press button on device to start.\n")

    try:
        while True:
            if current_pc_state == PcState.PROCESSING:
                if audio_frames:
                    captured_wav = save_audio_recording(audio_frames)
                    audio_frames.clear()

                    if captured_wav:
                        transcript = transcribe_audio_file(captured_wav)
                        transcript = transcript.strip()
                        print(f"\nYou said: {transcript}")

                        if not transcript or len(transcript) < 3:
                            print("→ No meaningful speech detected")
                        else:
                            messages = [
                                {"role": "system", "content": SYSTEM_PROMPT},
                                {"role": "user",   "content": transcript},
                            ]
                            messages = run_llm_with_tools(messages)
                            last = messages[-1]
                            llm_reply = (
                                last.content if hasattr(last, "content")
                                else last.get("content", "")
                            ) or "Sorry, I couldn't process that right now."

                            response_wav = os.path.join(WAV_SAVE_DIR, f"resp_{int(time.time())}.wav")
                            tts_success = generate_tts_wav(llm_reply, response_wav)

                            if tts_success:
                                playback_file = force_16000_hz(response_wav)
                                play_response_to_echobud(playback_file)
                            else:
                                print("TTS failed → no response played")

                else:
                    print("No audio frames → skipping processing")

                transition_state(PcState.IDLE_WAIT)

            time.sleep(0.08)

    except KeyboardInterrupt:
        print("\nShutting down Echo-Bud Server...")
    finally:
        shutdown_flag.set()
        audio_thread.join(timeout=1.2)
        control_thread.join(timeout=1.2)
        audio_sock.close()
        control_sock.close()
        print("Shutdown complete.")
