import os
import random
import sys
import json
import requests
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment
from pydub.generators import Sine, Triangle

load_dotenv()

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).parent.parent / "tmp" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "")
USE_MUSICGEN = os.getenv("USE_MUSICGEN", "false").lower() == "true"

MOOD_TO_PIXABAY_QUERY = {
    "focused": "ambient electronic background study",
    "energetic": "upbeat motivational corporate technology",
    "cinematic": "cinematic orchestral epic trailer",
    "ambient": "ambient atmospheric meditation drone",
    "modern": "modern electronic rhythmic tech",
    "uplifting": "uplifting inspirational happy corporate",
    "documentary": "ambient documentary cinematic nature",
}

MOOD_CONFIGS = {
    "focused": {"bpm": 85, "notes": [196.00, 220.00, 261.63, 329.63, 392.00, 440.00], "waveform": "sine"},
    "energetic": {"bpm": 130, "notes": [293.66, 329.63, 369.99, 440.00, 493.88, 587.33], "waveform": "triangle"},
    "cinematic": {"bpm": 75, "notes": [130.81, 164.81, 196.00, 261.63, 329.63, 392.00], "waveform": "sawtooth"},
    "ambient": {"bpm": 60, "notes": [174.61, 220.00, 261.63, 349.23, 440.00], "waveform": "sine"},
    "modern": {"bpm": 110, "notes": [261.63, 329.63, 392.00, 523.25, 659.25], "waveform": "triangle"},
    "uplifting": {"bpm": 120, "notes": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88], "waveform": "triangle"},
    "documentary": {"bpm": 55, "notes": [130.81, 164.81, 196.00, 220.00, 261.63, 329.63], "waveform": "sine"},
}


def detect_mood(category: str, tier: str = "") -> str:
    if tier == "documentary":
        return "documentary"
    category = category.lower()
    mood_map = {
        "explained": "focused", "tutorial": "modern", "deep": "ambient",
        "breakdown": "focused", "analysis": "focused", "news": "energetic",
        "build": "uplifting", "code": "modern", "career": "uplifting",
        "industry": "cinematic",
    }
    for key, mood in mood_map.items():
        if key in category:
            return mood
    return "focused"


ENERGY_KEYWORDS = {
    "high": {"breakthrough", "crucially", "revolutionary", "game-changing",
             "amazing", "shocking", "incredible", "mind-blowing",
             "changes everything", "fundamentally", "massive", "huge",
             "unbelievable", "extraordinary", "remarkable", "transformative",
             "never before", "cutting-edge", "state-of-the-art", "pioneering"},
    "low": {"first", "let's", "imagine", "consider", "basically",
            "introduction", "welcome", "let me", "think about",
            "what is", "define", "start by", "begin with", "overview",
            "simply put", "in simple terms", "at its core"},
}

ENERGY_TO_MOOD = {
    "high": "energetic",
    "medium": "focused",
    "low": "ambient",
}


def score_scene_energy(text: str) -> str:
    if not text:
        return "medium"
    lower = text.lower()
    high = sum(1 for w in ENERGY_KEYWORDS["high"] if w in lower)
    low = sum(1 for w in ENERGY_KEYWORDS["low"] if w in lower)
    net = high - low
    if net >= 2:
        return "high"
    if net <= -1:
        return "low"
    return "medium"


# ---------------------------------------------------------------------------
# Pixabay music search (primary)
# ---------------------------------------------------------------------------

def _search_pixabay_music(query: str, duration: float) -> list[dict]:
    if not PIXABAY_API_KEY:
        return []
    params = {
        "key": PIXABAY_API_KEY,
        "q": query,
        "duration": f"0,{int(duration) + 60}",
        "per_page": 5,
    }
    try:
        resp = requests.get("https://pixabay.com/api/audio/", params=params, timeout=15)
        if resp.status_code == 403:
            logger.debug("[music_gen] Pixabay audio API returned 403 (key may not have audio scope)")
            return []
        resp.raise_for_status()
        data = resp.json()
        hits = []
        for track in data.get("hits", []):
            hits.append({
                "id": track.get("id"),
                "url": track.get("audio_url", ""),
                "duration": track.get("duration", 0),
                "tags": track.get("tags", ""),
                "title": track.get("title", ""),
            })
        return hits
    except Exception as e:
        logger.debug(f"[music_gen] Pixabay search failed: {e}")
        return []


def _download_pixabay_track(url: str, output_path: str) -> bool:
    try:
        resp = requests.get(url, timeout=60, stream=True)
        if resp.status_code == 403:
            logger.debug("[music_gen] Pixabay track download 403 (access denied)")
            return False
        resp.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        logger.debug(f"[music_gen] Pixabay download failed: {e}")
        return False


def _try_pixabay_music(category: str, mood: str, duration: float, output_path: str) -> bool:
    query = MOOD_TO_PIXABAY_QUERY.get(mood, "ambient electronic background")
    logger.info(f"[music_gen] Searching Pixabay: '{query}'")
    tracks = _search_pixabay_music(query, duration)
    if not tracks:
        logger.info("[music_gen] No Pixabay tracks found")
        return False

    best = tracks[0]
    logger.info(f"[music_gen] Downloading: {best.get('title', 'unknown')} ({best.get('duration', 0)}s)")
    if _download_pixabay_track(best["url"], output_path):
        logger.info(f"[music_gen] Pixabay track saved -> {output_path}")
        return True

    return False


# ---------------------------------------------------------------------------
# MusicGen integration (secondary — requires MPS or CUDA)
# ---------------------------------------------------------------------------

def _build_musicgen_prompt(category: str, scene_moods: list[str]) -> str:
    cat_lower = category.lower()
    style_keywords = []
    if any(k in cat_lower for k in ("explained", "tutorial", "basics", "intro")):
        style_keywords = ["clear", "educational", "modern electronic", "focused"]
    elif any(k in cat_lower for k in ("deep", "paper", "analysis", "architecture")):
        style_keywords = ["ambient", "thoughtful", "cinematic", "minimal"]
    elif any(k in cat_lower for k in ("industry", "news", "review")):
        style_keywords = ["energetic", "professional", "modern corporate", "upbeat"]
    elif any(k in cat_lower for k in ("code", "build", "tool")):
        style_keywords = ["modern", "rhythmic", "electronic", "productive"]
    elif any(k in cat_lower for k in ("career", "learning")):
        style_keywords = ["uplifting", "inspirational", "warm", "progressive"]
    else:
        style_keywords = ["modern", "educational", "electronic background"]

    unique_moods = []
    for m in scene_moods:
        if not unique_moods or unique_moods[-1] != m:
            unique_moods.append(m)

    arc = ""
    if unique_moods:
        mood_labels = {
            "focused": "focused and clear", "energetic": "energetic and driving",
            "cinematic": "epic and cinematic", "ambient": "ambient and atmospheric",
            "modern": "modern and rhythmic", "uplifting": "uplifting and inspiring",
        }
        arc_parts = [mood_labels.get(m, m) for m in unique_moods]
        total_dur = len(scene_moods) * 8
        if len(unique_moods) == 1:
            arc = f"The music has a consistent {arc_parts[0]} mood throughout."
        else:
            timed_parts = []
            current_time = 0
            prev_mood = scene_moods[0]
            for i, m in enumerate(scene_moods):
                if m != prev_mood or i == len(scene_moods) - 1:
                    if i > 0:
                        timed_parts.append(f"at {current_time}s it transitions to {mood_labels.get(prev_mood, prev_mood)}")
                    current_time = i * 8
                prev_mood = m
            if timed_parts:
                arc = f"The music starts {mood_labels.get(scene_moods[0], scene_moods[0])}, {' then '.join(timed_parts)}."

    bpm_hint = ""
    if unique_moods:
        bpms = [MOOD_CONFIGS.get(m, {}).get("bpm", 100) for m in unique_moods if m in MOOD_CONFIGS]
        if bpms:
            avg_bpm = sum(bpms) // len(bpms)
            bpm_hint = f"Tempo around {avg_bpm} BPM. "

    return (
        f"{' and '.join(style_keywords)} background music for an educational tech video. "
        f"{arc} "
        f"{bpm_hint}"
        f"Clean studio recording, no vocals, suitable for narration voiceover. "
        f"Professional, modern instrumental."
    )


def _generate_musicgen_local(prompt: str, duration_seconds: float, output_path: str) -> bool:
    try:
        import torch
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import scipy.io.wavfile as wavfile
        import numpy as np
    except ImportError:
        return False

    device = None
    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        return False

    try:
        logger.info(f"[music_gen] Loading MusicGen-small on {device}...")
        processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
        model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small").to(device)

        inputs = processor(text=[prompt], padding=True, return_tensors="pt").to(device)
        max_new_tokens = int(duration_seconds * 50)
        audio_values = model.generate(
            **inputs, max_new_tokens=max_new_tokens, guidance_scale=3.0,
        )

        sampling_rate = model.config.audio_encoder.sampling_rate
        audio = audio_values[0, 0].cpu().numpy()
        wavfile.write(output_path, sampling_rate, audio)
        logger.info(f"[music_gen] MusicGen generated -> {output_path}")
        return True
    except Exception as e:
        logger.warning(f"[music_gen] Local MusicGen failed: {e}")
        return False


def _try_musicgen(category: str, duration: float, scene_moods: list[str], output_path: str) -> bool:
    if not USE_MUSICGEN:
        return False
    prompt = _build_musicgen_prompt(category, scene_moods)
    logger.info(f"[music_gen] MusicGen prompt: {prompt}")
    if _generate_musicgen_local(prompt, duration, output_path):
        return True
    return False


# ---------------------------------------------------------------------------
# Procedural music generation (last resort)
# ---------------------------------------------------------------------------

def generate_melody(duration_seconds: float, mood: str = "focused", output_path: Optional[str] = None,
                    scene_moods: Optional[list[str]] = None) -> Optional[str]:
    if scene_moods and len(scene_moods) > 1:
        return _generate_mood_arc_melody(duration_seconds, scene_moods, output_path)
    config = MOOD_CONFIGS.get(mood, MOOD_CONFIGS["focused"])
    bpm = config["bpm"]
    notes = config["notes"]
    waveform = config["waveform"]
    beat_duration = 60.0 / bpm
    total_beats = int(duration_seconds / beat_duration)
    gen = Sine if waveform == "sine" else Triangle

    # Documentary/ambient: sustained chord pads instead of note-by-note melody
    if mood in ("documentary", "ambient", "cinematic"):
        chord_dur = int(beat_duration * 4 * 1000)
        pad = AudioSegment.silent(duration=0)
        for start_beat in range(0, total_beats, 4):
            freq = random.choice(notes)
            tone = gen(freq).to_audio_segment(duration=chord_dur)
            tone = tone - 20
            pad = pad.overlay(tone, position=int(start_beat * beat_duration * 1000))
        pad = pad[:int(duration_seconds * 1000)]
        pad = AudioSegment.from_mono_audiosegments(pad, pad)
        if output_path is None:
            output_path = str(MUSIC_DIR / f"music_{mood}_{random.randint(1000,9999)}.wav")
        pad.export(output_path, format="wav")
        return output_path

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


def _generate_mood_arc_melody(duration_seconds: float, scene_moods: list[str], output_path: str) -> str:
    n_moods = len(scene_moods)
    seg_duration = duration_seconds / n_moods
    segments = []
    for i, mood in enumerate(scene_moods):
        if mood not in MOOD_CONFIGS:
            mood = "focused"
        seg_path = str(MUSIC_DIR / f"mood_seg_{i:03d}.wav")
        generate_melody(seg_duration, mood=mood, output_path=seg_path, scene_moods=None)
        segments.append(seg_path)
    combined = AudioSegment.empty()
    for i, seg_path in enumerate(segments):
        if os.path.exists(seg_path):
            seg = AudioSegment.from_file(seg_path)
            seg_len = len(seg)
            if seg_len < 100:
                continue
            crossfade = min(100, seg_len // 4)
            crossfade = crossfade if combined else 0
            combined = combined.append(seg, crossfade=crossfade)
    combined.export(output_path, format="wav")
    return output_path


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_background_music(category: str, duration: float = 60, output_filename: Optional[str] = None, scene_moods: Optional[list[str]] = None, tier: str = "") -> dict:
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    mood = detect_mood(category, tier=tier)
    if output_filename is None:
        output_filename = f"bg_{mood}.wav"
    output_path = str(MUSIC_DIR / output_filename)

    source = None
    music_path = None

    # Try Pixabay first
    if _try_pixabay_music(category, mood, duration, output_path):
        source = "pixabay"
        music_path = output_path

    # Try MusicGen (if enabled)
    if not music_path:
        scene_moods = scene_moods or [mood]
        if _try_musicgen(category, duration, scene_moods, output_path):
            source = "musicgen"
            music_path = output_path

    # Fall back to procedural
    if not music_path:
        logger.info("[music_gen] All external music sources failed, using procedural fallback")
        music_path = generate_melody(duration, mood, output_path, scene_moods=scene_moods)
        source = "procedural"

    if music_path and os.path.exists(music_path):
        try:
            audio = AudioSegment.from_file(music_path)
            return {"path": music_path, "duration": len(audio) / 1000.0, "mood": mood, "success": True, "source": source}
        except Exception as e:
            logger.warning(f"[music_gen] Generated music file is corrupt: {e}")

    return {"path": None, "duration": 0, "mood": mood, "success": False}
