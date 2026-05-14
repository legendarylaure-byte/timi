from dotenv import load_dotenv
from typing import Optional
from pydub.generators import Sine, Triangle
from pydub import AudioSegment
import os
import random
from pathlib import Path

_FFMPEG_BIN = None
for _candidate in ["/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/bin", "/usr/bin"]:
    if os.path.exists(os.path.join(_candidate, "ffmpeg")):
        _FFMPEG_BIN = _candidate
        break
if _FFMPEG_BIN and _FFMPEG_BIN not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_BIN + ":" + os.environ.get("PATH", "")


load_dotenv()

MUSIC_DIR = Path(__file__).parent.parent / "tmp" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

MOOD_CONFIGS = {
    "happy": {"bpm": 120, "notes": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88], "waveform": "triangle"},
    "calm": {"bpm": 70, "notes": [196.00, 220.00, 246.94, 293.66, 329.63, 392.00], "waveform": "sine"},
    "adventure": {"bpm": 140, "notes": [293.66, 329.63, 369.99, 440.00, 493.88, 587.33], "waveform": "triangle"},
    "sad": {"bpm": 60, "notes": [220.00, 261.63, 329.63, 349.23, 440.00], "waveform": "sine"},
    "exciting": {"bpm": 160, "notes": [329.63, 369.99, 415.30, 493.88, 554.37, 659.25], "waveform": "triangle"},
    "bedtime": {"bpm": 50, "notes": [174.61, 220.00, 261.63, 349.23, 440.00], "waveform": "sine"},
    "playful": {"bpm": 130, "notes": [261.63, 329.63, 392.00, 523.25, 659.25], "waveform": "triangle"},
}


def detect_mood(category: str) -> str:
    category = category.lower()
    mood_map = {
        "lullaby": "bedtime", "bedtime": "bedtime", "sleep": "bedtime", "calm": "calm",
        "adventure": "adventure", "explore": "adventure", "journey": "adventure",
        "happy": "happy", "fun": "happy", "play": "playful", "friendship": "happy",
        "exciting": "exciting", "action": "exciting", "superhero": "exciting",
        "sad": "sad", "emotional": "calm",
    }
    for key, mood in mood_map.items():
        if key in category:
            return mood
    return "playful"


def generate_melody(duration_seconds: float, mood: str = "playful", output_path: Optional[str] = None) -> Optional[str]:
    config = MOOD_CONFIGS.get(mood, MOOD_CONFIGS["playful"])
    bpm = config["bpm"]
    notes = config["notes"]
    waveform = config["waveform"]
    beat_duration = 60.0 / bpm
    total_beats = int(duration_seconds / beat_duration)
    gen = Sine if waveform == "sine" else Triangle

    melody = AudioSegment.silent(duration=0)
    for _ in range(total_beats):
        freq = random.choice(notes)
        note_duration = random.choice([beat_duration * 0.5, beat_duration, beat_duration * 1.5])
        note_ms = int(note_duration * 1000)
        tone = gen(freq).to_audio_segment(duration=note_ms - 50)
        tone = tone.fade_in(20).fade_out(30) - 15
        melody += tone

    melody = melody[:int(duration_seconds * 1000)]
    melody = AudioSegment.from_mono_audiosegments(melody, melody)

    if output_path is None:
        output_path = str(MUSIC_DIR / f"music_{mood}_{random.randint(1000,9999)}.wav")

    melody.export(output_path, format="wav")
    return output_path


def generate_background_music(category: str, duration: float = 60, output_filename: Optional[str] = None) -> dict:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    mood = detect_mood(category)
    if output_filename is None:
        output_filename = f"bg_{mood}.wav"
    output_path = str(MUSIC_DIR / output_filename)
    music_path = generate_melody(duration, mood, output_path)
    if music_path and os.path.exists(music_path):
        try:
            audio = AudioSegment.from_file(music_path)
            return {"path": music_path, "duration": len(audio) / 1000.0, "mood": mood, "success": True}
        except Exception:
            pass
    return {"path": None, "duration": 0, "mood": mood, "success": False}
