from pydub import AudioSegment
from pydub.generators import Sine, Square, Sawtooth, WhiteNoise
from pydub.playback import play
import os
import json
import math
import random
from pathlib import Path

SFX_DIR = Path(__file__).parent.parent / "tmp" / "sfx"
SFX_DIR.mkdir(parents=True, exist_ok=True)

ASSETS_SFX_DIR = Path(__file__).parent / "assets" / "sfx"
ASSETS_SFX_DIR.mkdir(parents=True, exist_ok=True)

SFX_MAP = {
    "sparkle": {"generator": "sine_freq_sweep", "duration_ms": 400, "params": {"freq_start": 2000, "freq_end": 4000}},
    "pop": {"generator": "short_burst", "duration_ms": 150, "params": {"freq": 800}},
    "boing": {"generator": "bounce", "duration_ms": 500, "params": {"freq_start": 400, "freq_end": 200}},
    "swoosh": {"generator": "noise_sweep", "duration_ms": 600, "params": {"freq_start": 200, "freq_end": 2000}},
    "zip": {"generator": "sine_freq_sweep", "duration_ms": 200, "params": {"freq_start": 500, "freq_end": 3000}},
    "ding": {"generator": "sine_decay", "duration_ms": 800, "params": {"freq": 2500}},
    "twinkle": {"generator": "sine_freq_sweep", "duration_ms": 300, "params": {"freq_start": 3000, "freq_end": 5000}},
    "zap": {"generator": "square_burst", "duration_ms": 300, "params": {"freq": 1000}},
    "poof": {"generator": "noise_burst", "duration_ms": 200, "params": {}},
    "laugh": {"generator": "laugh", "duration_ms": 1000, "params": {"freq": 600}},
    "giggle": {"generator": "laugh", "duration_ms": 600, "params": {"freq": 800}},
    "aww": {"generator": "sine_decay", "duration_ms": 800, "params": {"freq": 500}},
    "sigh": {"generator": "noise_sweep", "duration_ms": 1000, "params": {"freq_start": 800, "freq_end": 100}},
    "gasp": {"generator": "short_burst", "duration_ms": 200, "params": {"freq": 1200}},
    "chirp": {"generator": "chirp", "duration_ms": 200, "params": {"freq": 2000}},
    "wind": {"generator": "noise_sweep", "duration_ms": 2000, "params": {"freq_start": 100, "freq_end": 500}},
    "bubble": {"generator": "short_burst", "duration_ms": 100, "params": {"freq": 600}},
    "chime": {"generator": "sine_decay", "duration_ms": 1500, "params": {"freq": 1000}},
    "bell": {"generator": "sine_decay", "duration_ms": 2000, "params": {"freq": 800}},
    "drum_roll": {"generator": "noise_burst", "duration_ms": 800, "params": {}},
    "cymbal": {"generator": "noise_burst", "duration_ms": 1500, "params": {}},
    "slide": {"generator": "sine_freq_sweep", "duration_ms": 500, "params": {"freq_start": 300, "freq_end": 100}},
    "bounce": {"generator": "bounce", "duration_ms": 600, "params": {"freq_start": 500, "freq_end": 200}},
    "crash": {"generator": "noise_burst", "duration_ms": 500, "params": {}},
    "magic": {"generator": "sine_freq_sweep", "duration_ms": 1000, "params": {"freq_start": 1000, "freq_end": 4000}},
    "water_drop": {"generator": "sine_decay", "duration_ms": 300, "params": {"freq": 1500}},
    "thunder": {"generator": "noise_burst", "duration_ms": 2000, "params": {}},
    "applause": {"generator": "noise_burst", "duration_ms": 3000, "params": {}},
    "snap": {"generator": "short_burst", "duration_ms": 50, "params": {"freq": 2000}},
    "click": {"generator": "short_burst", "duration_ms": 30, "params": {"freq": 1500}},
}

EFFECT_TO_SFX = {
    "sparkle": "sparkle",
    "star_rain": "twinkle",
    "rainbow_burst": "magic",
    "fade_in": "swoosh",
    "fade_out": "swoosh",
    "pop": "pop",
    "boing": "boing",
    "zip": "zip",
    "ding": "ding",
    "zap": "zap",
    "poof": "poof",
    "laugh": "laugh",
    "giggle": "giggle",
    "aww": "aww",
    "sigh": "sigh",
    "gasp": "gasp",
    "chirp": "chirp",
    "wind": "wind",
    "bubble": "bubble",
    "chime": "chime",
    "bell": "bell",
    "drum_roll": "drum_roll",
    "cymbal": "cymbal",
    "slide": "slide",
    "bounce": "bounce",
    "crash": "crash",
    "magic": "magic",
    "water_drop": "water_drop",
    "thunder": "thunder",
    "applause": "applause",
    "snap": "snap",
    "click": "click",
    "whoosh": "swoosh",
    "reveal": "swoosh",
    "transition_in": "swoosh",
    "transition_out": "swoosh",
    "emphasis": "ding",
    "highlight": "chime",
    "chapter_break": "bell",
    "list_item": "click",
    "bullet_point": "pop",
    "conclusion": "chime",
    "intro": "drum_roll",
    "outro": "chime",
}

TRANSITION_TO_SFX = {
    "dissolve": "chime",
    "fade": "swoosh",
    "slide_left": "swoosh",
    "slide_right": "swoosh",
    "zoom": "zip",
    "cut": "click",
    "circle_open": "whoosh",
    "circle_close": "whoosh",
    "pixelize": "zap",
    "wipe_left": "swoosh",
    "wipe_right": "swoosh",
    "wipe_up": "swoosh",
    "wipe_down": "swoosh",
    "smooth_left": "slide",
    "smooth_right": "slide",
    "fade_gradual": "chime",
    "squeeze_h": "bounce",
    "squeeze_v": "bounce",
}


def _sine_freq_sweep(duration_ms: int, freq_start: float, freq_end: float, volume_db: int = -10) -> AudioSegment:
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    sweep = AudioSegment.silent(duration=duration_ms)
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        freq = freq_start + (freq_end - freq_start) * progress
        sample = int(32767 * 0.3 * math.sin(2 * math.pi * freq * t))
        b = bytearray([(sample >> 8) & 0xFF, sample & 0xFF])
        sweep = sweep.overlay(AudioSegment(b, frame_rate=sample_rate, sample_width=2, channels=1),
                              times=0)
    sweep = sweep[:duration_ms]
    return sweep.fade_in(max(5, duration_ms // 20)).fade_out(max(5, duration_ms // 10)) + volume_db


def _short_burst(duration_ms: int, freq: float, volume_db: int = -8) -> AudioSegment:
    gen = Sine(freq)
    tone = gen.to_audio_segment(duration=duration_ms)
    return (tone.fade_in(2).fade_out(5) + volume_db)


def _sine_decay(duration_ms: int, freq: float, volume_db: int = -10) -> AudioSegment:
    gen = Sine(freq)
    tone = gen.to_audio_segment(duration=duration_ms)
    decay = AudioSegment.silent(duration=0)
    for i in range(100):
        pos = int(duration_ms * i / 100)
        seg_len = int(duration_ms / 100)
        if pos + seg_len > duration_ms:
            seg_len = duration_ms - pos
        if seg_len <= 0:
            break
        amp = 1.0 - (i / 100.0) ** 1.5
        segment = tone[pos:pos + seg_len] - abs(-10 - int(20 * (1 - amp)))
        decay = decay.append(segment, crossfade=0)
    return decay.fade_in(5) + volume_db


def _noise_burst(duration_ms: int, volume_db: int = -12) -> AudioSegment:
    noise = WhiteNoise().to_audio_segment(duration=duration_ms)
    env = AudioSegment.silent(duration=0)
    for i in range(100):
        pos = int(duration_ms * i / 100)
        seg_len = int(duration_ms / 100)
        if pos + seg_len > duration_ms:
            seg_len = duration_ms - pos
        if seg_len <= 0:
            break
        amp = math.exp(-3 * i / 100)
        segment = noise[pos:pos + seg_len] - abs(-10 - int(20 * (1 - amp)))
        env = env.append(segment, crossfade=0)
    return env.fade_in(5).fade_out(10) + volume_db


def _square_burst(duration_ms: int, freq: float, volume_db: int = -10) -> AudioSegment:
    gen = Square(freq)
    tone = gen.to_audio_segment(duration=duration_ms)
    return tone.fade_in(2).fade_out(duration_ms // 4) + volume_db


def _noise_sweep(duration_ms: int, freq_start: float, freq_end: float, volume_db: int = -12) -> AudioSegment:
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    noise = bytearray()
    for i in range(num_samples):
        progress = i / num_samples
        cutoff = freq_start + (freq_end - freq_start) * progress
        white = random.uniform(-1, 1)
        filtered = white * min(1.0, cutoff / 4000)
        sample = int(32767 * 0.2 * filtered)
        noise.extend([(sample >> 8) & 0xFF, sample & 0xFF])
    seg = AudioSegment(bytes(noise), frame_rate=sample_rate, sample_width=2, channels=1)
    return seg.fade_in(10).fade_out(duration_ms // 4) + volume_db


def _bounce(duration_ms: int, freq_start: float, freq_end: float, volume_db: int = -10) -> AudioSegment:
    sample_rate = 44100
    num_samples = int(sample_rate * duration_ms / 1000)
    bounce = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        progress = i / num_samples
        freq = freq_start + (freq_end - freq_start) * math.sin(progress * math.pi * 3) ** 2
        amp = max(0, 1 - progress) * 0.3
        sample = int(32767 * amp * math.sin(2 * math.pi * freq * t))
        bounce.extend([(sample >> 8) & 0xFF, sample & 0xFF])
    seg = AudioSegment(bytes(bounce), frame_rate=sample_rate, sample_width=2, channels=1)
    return seg.fade_in(5).fade_out(duration_ms // 3) + volume_db


def _chirp(duration_ms: int, freq: float, volume_db: int = -8) -> AudioSegment:
    gen = Sine(freq)
    base = gen.to_audio_segment(duration=duration_ms)
    chirped = AudioSegment.silent(duration=0)
    for i in range(5):
        seg = base[int(i * duration_ms / 5):int((i + 1) * duration_ms / 5)]
        chirped = chirped.append(seg, crossfade=0)
    return chirped.fade_in(2).fade_out(10) + volume_db


def _laugh(duration_ms: int, freq: float, volume_db: int = -8) -> AudioSegment:
    gen = Sine(freq)
    base = gen.to_audio_segment(duration=duration_ms)
    laugh = AudioSegment.silent(duration=0)
    num_ha = int(duration_ms / 150)
    for i in range(num_ha):
        ha_start = int(i * duration_ms / num_ha)
        ha_dur = int(duration_ms / num_ha * 0.6)
        ha = base[ha_start:ha_start + ha_dur]
        amp = 1.0 - (i / num_ha) * 0.5
        ha = ha - abs(int(10 * (1 - amp)))
        silence = AudioSegment.silent(duration=int(duration_ms / num_ha * 0.4))
        laugh = laugh.append(ha, crossfade=0).append(silence, crossfade=0)
    return laugh.fade_in(10).fade_out(30) + volume_db


GENERATORS = {
    "sine_freq_sweep": _sine_freq_sweep,
    "short_burst": _short_burst,
    "sine_decay": _sine_decay,
    "noise_burst": _noise_burst,
    "square_burst": _square_burst,
    "noise_sweep": _noise_sweep,
    "bounce": _bounce,
    "chirp": _chirp,
    "laugh": _laugh,
}


def generate_sfx(name: str, output_dir: str = None) -> str | None:
    if output_dir is None:
        output_dir = str(ASSETS_SFX_DIR)
    os.makedirs(output_dir, exist_ok=True)

    config = SFX_MAP.get(name)
    if not config:
        print(f"[sfx_generator] Unknown SFX: {name}")
        return None

    generator_fn = GENERATORS.get(config["generator"])
    if not generator_fn:
        print(f"[sfx_generator] Unknown generator: {config['generator']}")
        return None

    try:
        params = dict(config["params"])
        audio = generator_fn(duration_ms=config["duration_ms"], volume_db=-10, **params)
        audio = audio.set_frame_rate(44100).set_channels(1)

        output_path = os.path.join(output_dir, f"{name}.wav")
        audio.export(output_path, format="wav")
        print(f"[sfx_generator] Generated SFX: {name} -> {output_path}")
        return output_path
    except Exception as e:
        print(f"[sfx_generator] Error generating {name}: {e}")
        return None


def generate_all_sfx(output_dir: str = None) -> dict:
    results = {}
    for name in SFX_MAP:
        path = generate_sfx(name, output_dir)
        if path:
            results[name] = path
    print(f"[sfx_generator] Generated {len(results)}/{len(SFX_MAP)} sound effects")
    return results


def get_sfx_path(name: str) -> str | None:
    path = os.path.join(str(ASSETS_SFX_DIR), f"{name}.wav")
    if os.path.exists(path):
        return path
    return generate_sfx(name)


def map_effect_to_sfx(effect_name: str) -> str | None:
    return EFFECT_TO_SFX.get(effect_name)


def get_transition_sfx(transition_name: str) -> dict | None:
    """Return an SFX dict for a transition name, or None if no mapping."""
    sfx_name = TRANSITION_TO_SFX.get(transition_name)
    if not sfx_name:
        return None
    sfx_path = get_sfx_path(sfx_name)
    if not sfx_path:
        return None
    return {"name": sfx_name, "path": sfx_path, "type": "transition"}


def compute_scene_timestamps(scenes: list[dict]) -> list[dict]:
    """Compute start_time and end_time for each scene from cumulative durations."""
    current = 0.0
    for scene in scenes:
        dur = scene.get("duration", scene.get("target_duration", 8.0))
        scene["start_time"] = current
        scene["end_time"] = current + dur
        current += dur
    return scenes


def load_sfx_scene_assignments(scenes: list[dict]) -> list[dict]:
    scenes = compute_scene_timestamps(scenes)
    for i, scene in enumerate(scenes):
        effects = scene.get("effects", [])
        scene_sfx = []
        for effect in effects:
            sfx_name = map_effect_to_sfx(effect)
            if sfx_name:
                sfx_path = get_sfx_path(sfx_name)
                if sfx_path:
                    scene_sfx.append({"name": sfx_name, "path": sfx_path, "type": "effect"})
        # Add transition SFX for the incoming transition (except first scene)
        if i > 0:
            prev_transition = scene.get("transition", "dissolve")
            tsfx = get_transition_sfx(prev_transition)
            if tsfx:
                scene_sfx.append(tsfx)
        if scene_sfx:
            scene["sfx"] = scene_sfx
    return scenes


if __name__ == "__main__":
    generate_all_sfx()
    print("All SFX generated successfully!")
