import os
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()

logger = logging.getLogger(__name__)

MUSIC_DIR = Path(__file__).parent.parent / "tmp" / "music"
MUSIC_DIR.mkdir(parents=True, exist_ok=True)

SR = 44100
LOOP_SECONDS = 40.0

USE_MUSICGEN = os.getenv("USE_MUSICGEN", "false").lower() == "true"

MOOD_CONFIGS = {
    "focused": {"bpm": 85, "notes": [196.00, 220.00, 261.63, 329.63, 392.00, 440.00], "waveform": "sine"},
    "energetic": {"bpm": 130, "notes": [293.66, 329.63, 369.99, 440.00, 493.88, 587.33], "waveform": "triangle"},
    "cinematic": {"bpm": 75, "notes": [130.81, 164.81, 196.00, 261.63, 329.63, 392.00], "waveform": "sawtooth"},
    "ambient": {"bpm": 60, "notes": [174.61, 220.00, 261.63, 349.23, 440.00], "waveform": "sine"},
    "modern": {"bpm": 110, "notes": [261.63, 329.63, 392.00, 523.25, 659.25], "waveform": "triangle"},
    "uplifting": {"bpm": 120, "notes": [261.63, 293.66, 329.63, 349.23, 392.00, 440.00, 493.88], "waveform": "triangle"},
    "documentary": {"bpm": 55, "notes": [130.81, 164.81, 196.00, 220.00, 261.63, 329.63], "waveform": "sine"},
}

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
# Own-generator soundscapes (news / relaxing)
#
# Two license-free beds, rendered once each and cached. The bed is a SEAMLESS
# loop: every oscillator and LFO frequency is quantized to an integer number of
# cycles over LOOP_SECONDS, bell tails are wrapped to the buffer start, and the
# reverb is circular (FFT length == signal length). So sample[-1] -> sample[0]
# is continuous and mix_audio can repeat the bed to any video length with no
# seam. No edge fades here -- the compositor applies its own fade_in/fade_out.
# ---------------------------------------------------------------------------

BED_PEAK = 0.28
NEWS_MUSIC_CATEGORIES = {"World News (24hr)", "Nepal News"}
MUSIC_PROFILES = ("news", "relaxing")


def select_music_profile(category, tier: str = "") -> str:
    """Map a video's category (and tier) to one of the two beds.

    Exact category set, deliberately NOT a substring match: "AI News" must map
    to relaxing, only the two real news categories get the news bed.
    """
    if tier == "documentary":
        return "relaxing"
    if isinstance(category, (list, tuple)):
        category = category[0] if category else ""
    cat = str(category or "").strip()
    return "news" if cat in NEWS_MUSIC_CATEGORIES else "relaxing"


def _quant(f: float, period: float) -> float:
    """Snap a frequency to exactly `round(f*period)` cycles over the loop."""
    return round(f * period) / period


def _spectral_lowpass(x, fc):
    import numpy as np
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X = X / np.sqrt(1.0 + (f / fc) ** 2)
    return np.fft.irfft(X, len(x))


def _circular_reverb(x, tau, mix, seed):
    import numpy as np
    n = len(x)
    rng = np.random.default_rng(seed)
    m = int(SR * min(3.0, tau * 3))
    t = np.arange(m) / SR
    rir = rng.standard_normal(m) * np.exp(-t / tau)
    rir /= np.sqrt((rir ** 2).sum() + 1e-12)
    wet = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(rir, n), n)
    wet *= np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(wet ** 2)) + 1e-12)
    return x * (1 - mix) + wet * mix


def _pad(freqs, t, T, seed):
    import numpy as np
    rng = np.random.default_rng(seed)
    out = np.zeros_like(t)
    for f in freqs:
        det = rng.uniform(-0.25, 0.25)
        lfo_f = rng.uniform(0.04, 0.12)
        lfo_p = rng.uniform(0, 2 * np.pi)
        amp = 0.55 + 0.45 * np.sin(2 * np.pi * _quant(lfo_f, T) * t + lfo_p)
        out += np.sin(2 * np.pi * _quant(f + det, T) * t + rng.uniform(0, 2 * np.pi)) * amp
    return out / len(freqs)


def _bells(t, freqs, decay, seed, level, count, T):
    import numpy as np
    rng = np.random.default_rng(seed)
    n = len(t)
    out = np.zeros(n)
    for _ in range(count):
        start = int(rng.integers(0, n))
        f = _quant(float(rng.choice(freqs)), T)
        m = int(SR * decay * 3)
        tt = np.arange(m) / SR
        tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt / decay) * level
        idx = (start + np.arange(m)) % n        # wrap decay tail -> seamless
        out[idx] += tone
    return out


def _pulse(t, hz, sharp, T):
    import numpy as np
    ph = (t * _quant(hz, T)) % 1.0
    return np.exp(-ph * sharp)


def _synth_bed(profile: str, loop_seconds: float = LOOP_SECONDS):
    """Return a stereo float array (2, N) that loops seamlessly."""
    import numpy as np
    T = loop_seconds
    n = int(SR * T)
    t = np.arange(n) / SR
    A4 = 432.0

    def note(semis):
        return A4 * 2.0 ** (semis / 12.0)

    root = note(-24)                            # A2 ~108

    if profile == "news":
        minor = [root, root * 6 / 5, root * 1.5, root * 2]
        pad_l = _pad(minor, t, T, 31)
        pad_r = _pad(minor, t, T, 32)
        env = _pulse(t, 1.9, 7.0, T)
        sub = np.sin(2 * np.pi * _quant(root * 0.5, T) * t) * (0.25 + 0.55 * env)
        # soft newsroom tick; random noise (tiny seam at 0.05 amp, lowpassed away)
        tick = np.random.default_rng(41).standard_normal(n) * _pulse(t, 1.9, 40.0, T) * 0.05
        tick = _spectral_lowpass(tick, 6000)
        L = _spectral_lowpass(pad_l * 0.6 + sub + tick, 4800)
        R = _spectral_lowpass(pad_r * 0.6 + sub + np.roll(tick, 300), 4800)
        L = _circular_reverb(L, 0.9, 0.28, 51)
        R = _circular_reverb(R, 0.9, 0.28, 52)
        peak = 0.28
    else:                                       # relaxing
        pad_l = _pad([root, root * 1.5, root * 2, root * 3], t, T, 11)
        pad_r = _pad([root, root * 1.5, root * 2, root * 3], t, T, 12)
        sub = np.sin(2 * np.pi * _quant(root * 0.5, T) * t) * 0.55
        bel = _bells(t, [note(0), note(7), note(12), note(19)], 1.6, 13, 0.42, 12, T)
        L = _spectral_lowpass(pad_l * 0.55 + sub + bel, 3200)
        R = _spectral_lowpass(pad_r * 0.55 + sub + np.roll(bel, 900), 3200)
        L = _circular_reverb(L, 1.4, 0.38, 21)
        R = _circular_reverb(R, 1.4, 0.38, 22)
        peak = 0.30

    stereo = np.stack([L, R])
    stereo = stereo / (np.abs(stereo).max() + 1e-12) * peak
    return stereo


def _write_bed_wav(path: str, stereo) -> None:
    import numpy as np
    import wave
    pcm = (np.clip(stereo.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _ensure_bed(profile: str) -> str:
    """Render bed_{profile}.wav once and reuse it (cache lives in MUSIC_DIR)."""
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)
    path = MUSIC_DIR / f"bed_{profile}.wav"
    if path.exists() and path.stat().st_size > 10000:
        return str(path)
    _write_bed_wav(str(path), _synth_bed(profile))
    logger.info(f"[music_gen] Rendered '{profile}' bed -> {path}")
    return str(path)


# ---------------------------------------------------------------------------
# MusicGen integration (optional — requires MPS or CUDA; off by default)
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
    except ImportError:
        return False

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
    return _generate_musicgen_local(prompt, duration, output_path)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_background_music(category: str, duration: float = 60, output_filename: Optional[str] = None,
                              scene_moods: Optional[list[str]] = None, tier: str = "", video_id: str = "") -> dict:
    profile = select_music_profile(category, tier=tier)

    # Optional MusicGen (requires CUDA/MPS; USE_MUSICGEN defaults off).
    if USE_MUSICGEN:
        out = str(MUSIC_DIR / (output_filename or f"bg_{profile}_{video_id or 'x'}.wav"))
        if _try_musicgen(category, duration, scene_moods or [profile], out) and os.path.exists(out):
            try:
                audio = AudioSegment.from_file(out)
                return {"path": out, "duration": len(audio) / 1000.0, "mood": profile,
                        "success": True, "source": "musicgen"}
            except Exception as e:
                logger.warning(f"[music_gen] MusicGen file is corrupt: {e}")

    try:
        music_path = _ensure_bed(profile)
        audio = AudioSegment.from_file(music_path)
        return {"path": music_path, "duration": len(audio) / 1000.0, "mood": profile,
                "success": True, "source": "own-generator"}
    except Exception as e:
        logger.warning(f"[music_gen] Failed to render '{profile}' bed: {e}")
        return {"path": None, "duration": 0, "mood": profile, "success": False}
