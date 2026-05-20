from dotenv import load_dotenv
from typing import Optional
from pydub.generators import Sine, Triangle
from pydub import AudioSegment
import os
import random
import sys
import json
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

USE_MUSICGEN = os.getenv("USE_MUSICGEN", "true").lower() == "true"

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


# ---------------------------------------------------------------------------
# MusicGen integration (AI-generated music)
# ---------------------------------------------------------------------------

def _build_musicgen_prompt(category: str, scene_moods: list[str]) -> str:
    """Build a descriptive prompt for MusicGen from category + per-scene moods."""
    cat_lower = category.lower()
    style_keywords = []
    if any(k in cat_lower for k in ("bedtime", "lullaby", "sleep", "calm")):
        style_keywords = ["gentle", "soothing", "lullaby", "soft piano and strings"]
    elif any(k in cat_lower for k in ("adventure", "explore", "journey", "action")):
        style_keywords = ["epic", "adventurous", "orchestral", "uplifting"]
    elif any(k in cat_lower for k in ("science", "learn", "tech", "discover")):
        style_keywords = ["curious", "playful", "electronic", "upbeat"]
    elif any(k in cat_lower for k in ("song", "rhyme", "dance", "color", "shape")):
        style_keywords = ["bouncy", "fun", "catchy melody", "children's music box"]
    elif any(k in cat_lower for k in ("story", "fable", "mythology", "fairy")):
        style_keywords = ["whimsical", "magical", "storytelling", "gentle"]
    elif any(k in cat_lower for k in ("emotion", "friend", "social", "feel")):
        style_keywords = ["warm", "heartfelt", "gentle acoustic"]
    else:
        style_keywords = ["playful", "cheerful", "cartoon background music"]

    # Build arc description from scene moods
    unique_moods = []
    for m in scene_moods:
        if not unique_moods or unique_moods[-1] != m:
            unique_moods.append(m)

    if unique_moods:
        mood_labels = {
            "happy": "cheerful and bright",
            "calm": "calm and gentle",
            "adventure": "exciting and adventurous",
            "sad": "soft and emotional",
            "exciting": "energetic and thrilling",
            "bedtime": "peaceful and dreamy",
            "playful": "bouncy and fun",
            "dreamy": "dreamy and whimsical",
        }
        arc_parts = [mood_labels.get(m, m) for m in unique_moods]
        arc = ", then transitions to ".join(arc_parts)
        arc = f"The music starts {arc}."
    else:
        arc = ""

    prompt = (
        f"{' and '.join(style_keywords)} background music for a children's cartoon. "
        f"{arc} "
        f"Clean studio recording, no vocals, suitable for narration voiceover. "
        f"Cheerful, warm, child-friendly instrumental."
    )
    return prompt


def _generate_musicgen_local(prompt: str, duration_seconds: float, output_path: str) -> bool:
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import scipy.io.wavfile as wavfile
        import numpy as np
    except ImportError:
        print("[music_gen] torch/transformers not installed, cannot run MusicGen locally")
        return False

    if not torch.cuda.is_available():
        print("[music_gen] No GPU available for local MusicGen")
        return False

    try:
        print(f"[music_gen] Loading MusicGen-small on GPU...")
        device = "cuda"
        processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small").to(device)

        inputs = processor(text=[prompt], padding=True, return_tensors="pt").to(device)
        max_new_tokens = int(duration_seconds * 50)
        audio_values = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            guidance_scale=3.0,
        )

        sampling_rate = model.config.audio_encoder.sampling_rate
        audio = audio_values[0, 0].cpu().numpy()
        wavfile.write(output_path, sampling_rate, audio)
        print(f"[music_gen] MusicGen generated -> {output_path}")
        return True
    except Exception as e:
        print(f"[music_gen] Local MusicGen failed: {e}")
        return False


def _generate_musicgen_modal(prompt: str, duration_seconds: float, output_path: str) -> bool:
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "pipeline"))
        from gpu.musicgen import generate_music
        result_path = generate_music.remote(prompt, int(duration_seconds))
        if result_path and os.path.exists(result_path):
            import shutil
            shutil.copy(result_path, output_path)
            print(f"[music_gen] Modal MusicGen generated -> {output_path}")
            return True
    except Exception as e:
        print(f"[music_gen] Modal MusicGen failed: {e}")
    return False


def _try_musicgen(category: str, duration: float, scene_moods: list[str], output_path: str) -> bool:
    if not USE_MUSICGEN:
        return False

    prompt = _build_musicgen_prompt(category, scene_moods)
    print(f"[music_gen] MusicGen prompt: {prompt}")

    if _generate_musicgen_local(prompt, duration, output_path):
        return True
    if _generate_musicgen_modal(prompt, duration, output_path):
        return True

    print("[music_gen] All MusicGen methods failed, falling back to procedural")
    return False


# ---------------------------------------------------------------------------
# Procedural music generation (fallback / default)
# ---------------------------------------------------------------------------

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


def generate_background_music(category: str, duration: float = 60, output_filename: Optional[str] = None, scene_moods: Optional[list[str]] = None) -> dict:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    mood = detect_mood(category)
    if output_filename is None:
        output_filename = f"bg_{mood}.wav"
    output_path = str(MUSIC_DIR / output_filename)

    scene_moods = scene_moods or [mood]

    # Try MusicGen first (if enabled)
    musicgen_ok = _try_musicgen(category, duration, scene_moods, output_path)

    if not musicgen_ok:
        # Fall back to procedural
        music_path = generate_melody(duration, mood, output_path)
    else:
        music_path = output_path

    if music_path and os.path.exists(music_path):
        try:
            audio = AudioSegment.from_file(music_path)
            return {"path": music_path, "duration": len(audio) / 1000.0, "mood": mood, "success": True, "source": "musicgen" if musicgen_ok else "procedural"}
        except Exception:
            pass
    return {"path": None, "duration": 0, "mood": mood, "success": False}
