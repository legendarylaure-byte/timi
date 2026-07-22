import os
import re
import json
import logging
from utils.subprocess_helper import safe_run, safe_run_bool, register_temp_dir
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()

from utils.scene_schema import DEEP_LESSON_CATS as _DEEP_LESSON_CATS
from utils.annotation_renderer import build_annotation_filters

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = Path(__file__).parent.parent / "tmp" / "compositor"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(TEMP_DIR))

OUTPUT_4K = os.getenv("OUTPUT_4K", "false").lower() == "true"
OUTPUT_W = 3840 if OUTPUT_4K else 1920
OUTPUT_H = 2160 if OUTPUT_4K else 1080

ENABLE_COLOR_GRADING = os.getenv("ENABLE_COLOR_GRADING", "true").lower() == "true"
COLOR_GRADING_THRESHOLD = float(os.getenv("COLOR_GRADING_THRESHOLD", "0.15"))

# Brand palette reference (teal/dark/orange)
# YUV histogram target for consistent visual identity across all scenes
BRAND_TEAL_YUV = {"y_mean": 140.0, "u_mean": 160.0, "v_mean": 80.0}

# Documentary palette (cooler/desaturated — PBS NOVA / Branch Education style)
DOCUMENTARY_YUV = {"y_mean": 90.0, "u_mean": 128.0, "v_mean": 118.0}

ASPECT_RATIOS = {
    "shorts": {"w": 1080, "h": 1920, "ar": "9:16"},
    "long": {"w": OUTPUT_W, "h": OUTPUT_H, "ar": "16:9"},
}


OUTPUT_FPS = 24
CRF = "17"

logger = logging.getLogger(__name__)
PRESET = "medium"

_AMBIENT_VOLUME_DB = float(os.getenv("AMBIENT_VOLUME_DB", "-24"))


def _sws_flags() -> list:
    return ["-sws_flags", "lanczos+accurate_rnd+full_chroma_int"]


def _ffmpeg_cmd() -> str:
    env_path = os.getenv("FFMPEG_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path
    for p in ["/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"]:
        if os.path.exists(p):
            return p
    return "ffmpeg"


def _ffprobe_cmd() -> str:
    env_path = os.getenv("FFPROBE_PATH", "")
    if env_path and os.path.exists(env_path):
        return env_path
    for p in ["/opt/homebrew/opt/ffmpeg-full/bin/ffprobe", "/usr/local/bin/ffprobe", "/usr/bin/ffprobe"]:
        if os.path.exists(p):
            return p
    return "ffprobe"


def _get_duration(path: str) -> float:
    cmd = [_ffprobe_cmd(), "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", path]
    try:
        result = safe_run(cmd, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def trim_clip(input_path: str, output_path: str, start: float = 0, duration: float = 5) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, *_sws_flags(),
        "-ss", str(start), "-t", str(duration),
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def _extend_clip(input_path: str, output_path: str, target_dur: float) -> bool:
    """Loop the LAST 2 seconds of a clip to fill target_dur.
    Keeps the original clip unchanged, only loops the tail.
    Caps extension at 1.5x original to avoid obvious looping artifacts.
    """
    from pathlib import Path
    current = _get_duration(input_path)
    if current >= target_dur - 0.5:
        return True
    max_extend = current * 1.5
    capped = min(target_dur, max_extend)
    if capped < target_dur - 1.0:
        return False

    tail_dur = min(2.0, current * 0.3)
    stem = Path(input_path).stem
    tail_path = str(TEMP_DIR / f"tail_{stem}.mp4")

    cmd_cut = [
        _ffmpeg_cmd(), "-y", "-i", input_path,
        *("-ss", str(max(0, current - tail_dur))),
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-pix_fmt", "yuv420p", "-an", tail_path,
    ]
    if not safe_run_bool(cmd_cut, timeout=120):
        return False

    needed = capped - current
    loop_path = str(TEMP_DIR / f"loop_{stem}.mp4")
    cmd_loop = [
        _ffmpeg_cmd(), "-y", "-stream_loop", "-1", "-i", tail_path,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-t", str(needed),
        "-pix_fmt", "yuv420p", "-an", loop_path,
    ]
    if not safe_run_bool(cmd_loop, timeout=120):
        return False

    concat_list = str(TEMP_DIR / f"ext_concat_{stem}.txt")
    with open(concat_list, "w") as f:
        f.write(f"file '{input_path}'\n")
        f.write(f"file '{loop_path}'\n")

    cmd_cat = [
        _ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
        *_sws_flags(),
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-pix_fmt", "yuv420p", "-an", output_path,
    ]
    return safe_run_bool(cmd_cat, timeout=300)


def resize_to_target(input_path: str, output_path: str, target_w: int, target_h: int, duration: float = 0) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y",
        *(["-loop", "1", "-t", str(duration)] if duration > 0 else []),
        "-i", input_path, *_sws_flags(),
        "-vf", f"scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=increase,crop={target_w}:{target_h}",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def pad_with_blurred_background(input_path: str, output_path: str, target_w: int, target_h: int) -> bool:
    vf = (
        f"scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=increase,"
        f"split[fg][bg];"
        f"[bg]scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=increase,crop={target_w}:{target_h},"
        f"boxblur=20:5[bg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
    )
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def apply_ken_burns(input_path: str, output_path: str, target_w: int, target_h: int, duration: float, preset_idx: int = 0) -> bool:
    trim_path = str(TEMP_DIR / f"kb_trim_{preset_idx:03d}.mp4")
    if not trim_clip(input_path, trim_path, 0, duration):
        return resize_to_target(input_path, output_path, target_w, target_h)

    src_w, src_h = 0, 0
    try:
        probe = [_ffprobe_cmd(), "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height",
                 "-of", "csv=p=0", trim_path]
        result = safe_run(probe, timeout=15)
        src_w, src_h = map(int, result.stdout.strip().split(","))
    except Exception:
        return resize_to_target(trim_path, output_path, target_w, target_h)

    crop_w = min(target_w, src_w)
    crop_h = min(target_h, src_h)

    # ponytail: vary pan direction per scene using preset_idx % 4
    direction = preset_idx % 4
    if src_w * target_h > src_h * target_w:
        max_x = max(0, src_w - crop_w)
        if direction == 0:
            x_expr = f"{max_x}*t/{duration}" if max_x > 0 else "0"
        elif direction == 1:
            x_expr = f"{max_x}*(1-t/{duration})" if max_x > 0 else "0"
        elif direction == 2:
            x_expr = f"{max_x}*0.5+{max_x}*0.3*sin(2*pi*t/{duration})" if max_x > 0 else "0"
        else:
            x_expr = f"{max_x}*0.5" if max_x > 0 else "0"
        y_expr = f"({src_h} - {crop_h}) / 2"
    else:
        max_y = max(0, src_h - crop_h)
        x_expr = f"({src_w} - {crop_w}) / 2"
        if direction == 0:
            y_expr = f"{max_y}*t/{duration}" if max_y > 0 else "0"
        elif direction == 1:
            y_expr = f"{max_y}*(1-t/{duration})" if max_y > 0 else "0"
        elif direction == 2:
            y_expr = f"{max_y}*0.5+{max_y}*0.3*sin(2*pi*t/{duration})" if max_y > 0 else "0"
        else:
            y_expr = f"{max_y}*0.5" if max_y > 0 else "0"

    vf = f"crop={crop_w}:{crop_h}:{x_expr}:{y_expr},scale={target_w}:{target_h}:flags=lanczos"
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", trim_path, *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = safe_run(cmd, timeout=120)
        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True
    except Exception:
        pass
    return resize_to_target(trim_path, output_path, target_w, target_h)


def _generate_ambient_pad(duration_ms: int) -> AudioSegment:
    import math
    import random
    import array
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    samples = []
    for t in range(n_samples):
        env = 0.5 - 0.5 * math.cos(2 * math.pi * t / n_samples)
        chord = (math.sin(2 * math.pi * 110 * t / sample_rate) * 0.15 +
                 math.sin(2 * math.pi * 165 * t / sample_rate) * 0.10 +
                 math.sin(2 * math.pi * 220 * t / sample_rate) * 0.08)
        noise = (random.random() - 0.5) * 0.02
        samples.append(int(4096 * env * (chord + noise)))
    raw = array.array('h', samples).tobytes()
    return AudioSegment(raw, frame_rate=sample_rate, sample_width=2, channels=1)


def _generate_emphasis_tone(duration_ms: int = 150, freq: float = 880,
                             volume_db: float = -12) -> AudioSegment:
    """Short sine-wave tone for emphasis on key terms."""
    import array, math
    n = int(44100 * duration_ms / 1000)
    samples = array.array("h", [
        int(32767 * 0.3 * math.sin(2 * math.pi * freq * t / 44100)
            * min(1.0, t / max(1, n * 0.1)))  # fade in over first 10%
        for t in range(n)
    ])
    seg = AudioSegment(samples.tobytes(), frame_rate=44100, sample_width=2, channels=1) + volume_db
    return seg.fade_out(min(50, duration_ms))


def _generate_transition_whoosh(duration_ms: int = 300,
                                  volume_db: float = -18) -> AudioSegment:
    """Sweep tone for scene transitions (200Hz→2000Hz)."""
    import array, math
    n = int(44100 * duration_ms / 1000)
    samples = array.array("h", [
        int(32767 * 0.2 * math.sin(2 * math.pi * (200 + 1800 * t / n) * t / 44100)
            * min(1.0, t / max(1, n * 0.15)))
        for t in range(n)
    ])
    seg = AudioSegment(samples.tobytes(), frame_rate=44100, sample_width=2, channels=1) + volume_db
    return seg.fade_in(min(30, duration_ms)).fade_out(min(80, duration_ms))


def mix_audio(voice_path: str, music_path: Optional[str], output_path: str,
              voice_volume_db: float = 2, music_volume_db: float = -24,
              duck_db: float = -8, sfx_scenes: Optional[list] = None,
              duration_ms: Optional[int] = None) -> bool:
    try:
        voice = AudioSegment.from_file(voice_path) + voice_volume_db
        if len(voice) > 1000:
            voice = voice.high_pass_filter(80).compress_dynamic_range(threshold=-16.0, ratio=2.5, attack=5.0, release=50.0)
        if duration_ms:
            voice = voice[:duration_ms]

        if music_path and os.path.exists(music_path):
            music_raw = (AudioSegment.from_file(music_path) + music_volume_db)
            if len(music_raw) > 1000:
                music_raw = music_raw.high_pass_filter(100).low_pass_filter(8000)
            music_raw = (music_raw * (len(voice) // len(music_raw) + 1))[:len(voice)]
            if len(music_raw) > 4000:
                music_raw = music_raw.fade_in(3000).fade_out(4000)
            music_raw = _apply_ducking(music_raw, voice, duck_db=duck_db)
            mixed = voice.overlay(music_raw)
        else:
            mixed = voice

        # SFX: emphasis tones for scenes with key terms
        if sfx_scenes and os.getenv("ENABLE_SFX", "true").lower() == "true":
            for s in sfx_scenes:
                offset_ms = s.get("timing_offset_ms", 0)
                sfx_type = s.get("sfx_type", "emphasis")
                if sfx_type == "emphasis":
                    tone = _generate_emphasis_tone()
                    mixed = mixed.overlay(tone, position=offset_ms)
                elif sfx_type == "transition":
                    whoosh = _generate_transition_whoosh()
                    mixed = mixed.overlay(whoosh, position=offset_ms)

        # ponytail: ambient pad only when no music — avoids frequency clashing
        if not (music_path and os.path.exists(music_path)):
            ambient_pad = _generate_ambient_pad(len(mixed))
            ambient_pad = ambient_pad + _AMBIENT_VOLUME_DB
            mixed = mixed.overlay(ambient_pad)

        if len(mixed) > 400:
            mixed = mixed.fade_in(300).fade_out(400)

        mixed.export(output_path, format="wav")
        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        print(f"[compositor] Audio mix error: {e}")
        return False


def _apply_ducking(music: AudioSegment, voice: AudioSegment, duck_db: float = -6,
                   threshold_db: float = -30, window_ms: int = 50,
                   attack_ms: int = 100, release_ms: int = 200) -> AudioSegment:
    try:
        import math
        num_windows = max(1, len(voice) // window_ms)
        smoothed = AudioSegment.silent(duration=0)
        prev_gain = 0
        for i in range(num_windows):
            start = i * window_ms
            end = min(start + window_ms, len(music))
            chunk = music[start:end]
            voice_rms = voice[start:min(end, len(voice))].rms or 0
            voice_db = 20 * math.log10(max(voice_rms, 1) / 32768) if voice_rms > 0 else -60
            target_gain = duck_db if voice_db > threshold_db else 0
            if target_gain != prev_gain:
                crossfade = attack_ms if target_gain < prev_gain else release_ms
                chunk = chunk.apply_gain(prev_gain).append(
                    chunk[-crossfade:].apply_gain(target_gain) if crossfade < len(chunk) else chunk.apply_gain(target_gain),
                    crossfade=min(crossfade, len(chunk)))
            else:
                chunk = chunk.apply_gain(target_gain)
            smoothed = smoothed.append(chunk, crossfade=5)
            prev_gain = target_gain
        return smoothed[:len(music)]
    except Exception:
        return music


def _process_clip(clip: dict, target_w: int, target_h: int, idx: int, format_type: str = "shorts") -> str | None:
    src = clip["path"]
    dur = clip.get("duration", 8.0)
    out = str(TEMP_DIR / f"clip_{idx:03d}.mp4")
    camera = clip.get("camera", {}) or {}

    try:
        clip_size = os.path.getsize(src)
    except FileNotFoundError:
        print(f"[compositor] Clip file not found, skipping: {src}")
        return None
    except OSError as e:
        print(f"[compositor] Clip file error, skipping: {src} — {e}")
        return None

    if src.endswith(".mp4") and clip_size > 10000:
        trimmed = str(TEMP_DIR / f"kb_trim_{idx:03d}.mp4")
        # Skip leading dark frames (diffusion models produce near-black at boundaries)
        lead = 0.5 if not clip.get("is_static", False) else 0
        if not trim_clip(src, trimmed, lead, max(dur - lead, 1.0)):
            return None
        dur = dur - lead

        zoom = float(camera.get("zoom", 1.0))
        pan_x = float(camera.get("pan_x", 0))
        pan_y = float(camera.get("pan_y", 0))
        has_camera_effect = zoom != 1.0 or pan_x != 0 or pan_y != 0

        if format_type == "shorts" and target_h > target_w:
            if not pad_with_blurred_background(trimmed, out, target_w, target_h):
                return None
        elif has_camera_effect:
            if not _apply_camera_motion(trimmed, out, target_w, target_h, dur, zoom, pan_x, pan_y):
                if not apply_ken_burns(trimmed, out, target_w, target_h, dur, idx):
                    return None
        else:
            if not apply_ken_burns(trimmed, out, target_w, target_h, dur, idx):
                return None
    else:
        if not resize_to_target(src, out, target_w, target_h, duration=dur):
            return None

    # ponytail: light denoise on LTX clips
    denoised = out.replace(".mp4", "_dn.mp4")
    denoise_cmd = [
        _ffmpeg_cmd(), "-y", "-i", out,
        "-vf", "hqdn3d=1:0.5:2:1.5",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy",
        denoised,
    ]
    try:
        safe_run(denoise_cmd, timeout=120)
        if os.path.exists(denoised) and os.path.getsize(denoised) > 1000:
            os.replace(denoised, out)
    except Exception:
        pass

    return out if os.path.exists(out) and os.path.getsize(out) > 1000 else None


def _fade_in_first_clip(clip_path: str, idx: int, dur: float) -> str:
    """Add a 0.5s fade-in from black on the first video clip."""
    if idx != 0 or not clip_path or not os.path.exists(clip_path):
        return clip_path
    out = clip_path.replace(".mp4", "_fadein.mp4")
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", clip_path,
        "-vf", f"fade=t=in:st=0:d=0.5",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy",
        out
    ]
    try:
        safe_run(cmd, timeout=60)
        if os.path.exists(out) and os.path.getsize(out) > 1000:
            return out
    except Exception:
        pass
    return clip_path


def _apply_camera_motion(input_path: str, output_path: str, target_w: int, target_h: int,
                         duration: float, zoom: float = 1.0, pan_x: float = 0, pan_y: float = 0) -> bool:
    if zoom > 1.25:
        zoom = 1.25
    zoom_pct = zoom * 100
    pan_x_px = int(pan_x * target_w * 0.2)
    pan_y_px = int(pan_y * target_h * 0.2)
    vf = (
        f"zoompan=z='if(eq(on,1),{zoom_pct},min({zoom_pct},zoom+0.005))':"
        f"d={int(duration * 24)}:"
        f"x='iw/2-(iw/zoom/2)+{pan_x_px}*on/{int(duration*24)}':"
        f"y='ih/2-(ih/zoom/2)+{pan_y_px}*on/{int(duration*24)}':"
        f"s={target_w}x{target_h}:fps=24"
    )
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


XFADE_MAP = {
    "dissolve": "dissolve",
    "fade": "fade",
    "fade_gradual": "fadeslow",
    "wipe_left": "wipeleft",
    "wipe_right": "wiperight",
    "slide_left": "slideleft",
    "slide_right": "slideright",
    "smooth_left": "smoothleft",
    "smooth_right": "smoothright",
    "zoom": "zoomin",
    "circle_open": "circleopen",
    "circle_close": "circleclose",
    "pixelize": "pixelize",
    "radial": "radial",
    "squeeze": "squeezeh",
    "cover": "coverright",
    "reveal": "revealright",
}


def _build_xfade_transition(processed: list[str], durations: list[float],
                            transitions: list[str],
                            target_w: int = 1920, target_h: int = 1080,
                            xfade_dur: float = 0.4) -> tuple[str, str]:
    n = len(processed)
    if n == 0:
        return "", ""
    if n == 1:
        return (f"[0:v]fps=24,setpts=PTS-STARTPTS,scale={target_w}:{target_h}:flags=lanczos,"
                f"format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,"
                f"setsar=1,settb=1/24[out]"), "out"

    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]fps=24,setpts=PTS-STARTPTS,scale={target_w}:{target_h}:flags=lanczos,"
            f"format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709,"
            f"setsar=1,settb=1/24[raw{i}]"
        )

    cum_dur = [sum(durations[:i]) for i in range(n + 1)]
    prev_label = f"raw0"
    out_label = prev_label

    for i in range(1, n):
        raw_type = transitions[i - 1] if i - 1 < len(transitions) else "dissolve"
        xf_type = XFADE_MAP.get(raw_type, "dissolve")
        offset = max(0.0, cum_dur[i] - i * xfade_dur)
        out_label = f"x{i}"
        filter_parts.append(
            f"[{prev_label}][raw{i}]xfade=transition={xf_type}"
            f":duration={xfade_dur}:offset={offset}[{out_label}]"
        )
        prev_label = out_label

    return ";".join(filter_parts), out_label


def add_text_overlay(video_path: str, text: str, output_path: str,
                     fontsize: int = 48, color: str = "white",
                     position: str = "center", start_time: float = 0,
                     duration: float = 3) -> bool:
    positions = {"center": "(w-text_w)/2:(h-text_h)/2",
                 "bottom": "(w-text_w)/2:(h-text_h)-50",
                 "top": "(w-text_w)/2:50"}
    pos = positions.get(position, positions["center"])
    escaped = text.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, *_sws_flags(),
        "-vf", f"drawtext=text='{escaped}':fontsize={fontsize}:fontcolor={color}:x={pos}:enable='between(t,{start_time},{start_time+duration})'",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def add_animated_lower_third(video_path: str, text: str, output_path: str,
                              fontsize: int = 22, color: str = "#8a50e8",
                              start_time: float = 0, duration: float = 5) -> bool:
    escaped = text.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
    ts = start_time
    te = start_time + duration
    x_expr = (
        f"if(lt(t\\,{ts}+0.3)\\,-text_w+(w+text_w)*(t-{ts})/0.3\\,"
        f"if(gte(t\\,{te}-0.3)\\,(w-text_w)/2-(w+text_w)*(t-({te}-0.3))/0.3\\,"
        f"(w-text_w)/2))"
    )
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, *_sws_flags(),
        "-vf",
        f"drawtext=text='{escaped}':fontsize={fontsize}:fontcolor={color}:"
        f"box=1:boxcolor=black@0.5:boxborderw=8:"
        f"x={x_expr}:y=h-100:enable='between(t\\,{ts}\\,{te})',"
        f"drawbox=x=(w-text_w)/2-12:y=h-116:w=4:h=22:color={color}:enable='between(t\\,{ts}+0.3\\,{te}-0.3)'",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def add_logo_overlay(video_path: str, logo_path: str, output_path: str,
                     position: str = "bottom_right", scale: float = 0.1) -> bool:
    positions = {"bottom_right": "main_w-overlay_w-20:main_h-overlay_h-20",
                 "top_right": "main_w-overlay_w-20:20",
                 "bottom_left": "20:main_h-overlay_h-20",
                 "top_left": "20:20"}
    pos = positions.get(position, positions["bottom_right"])
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, "-i", logo_path, *_sws_flags(),
        "-filter_complex", f"[1:v]scale=iw*{scale}:ih*{scale}[logo];[0:v][logo]overlay={pos}",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def _subtitle_style_escaped(fontsize: int, margin_v: int = 60,
                            primary: str = "&H00FFFFFF&",
                            outline: str = "&H40000000&",
                            border_style: int = 1,
                            has_outline: int = 1,
                            back_colour: str = "") -> str:
    parts = [
        f"FontSize={fontsize}",
        f"PrimaryColour={primary}",
        f"OutlineColour={outline}",
        f"Outline={has_outline}",
        "Shadow=0",
        f"BorderStyle={border_style}",
        f"Alignment=2",
        f"MarginV={margin_v}",
        "FontName=Arial",
    ]
    if back_colour:
        parts.append(f"BackColour={back_colour}")
    style = ",".join(parts)
    return style.replace(",", "\\,")


def burn_subtitles(video_path: str, subtitle_path: str, output_path: str,
                   fontsize: int = 12, tier: str = "") -> bool:
    abs_sub = os.path.abspath(subtitle_path)
    if tier == "documentary":
        sub_style = _subtitle_style_escaped(fontsize, 40, '&H000088CC&', '&H00000000&', has_outline=2)
    else:
        sub_style = _subtitle_style_escaped(fontsize, 40, '&H000088CC&', '&H40002B00&', 3, 0, '&H40000000&')
    vf = f"subtitles=filename='{abs_sub}':force_style={sub_style}"
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        result = safe_run(cmd, timeout=300)
        if result.returncode == 0:
            return True
        print(f"[compositor] Subtitle burn error (fallback): {result.stderr[-200:]}")
        cmd[-2] = f"subtitles=filename='{abs_sub}'"
        return safe_run_bool(cmd, timeout=300)
    except Exception as e:
        print(f"[compositor] Subtitle burn error: {e}")
        return False


def add_chapter_markers(video_path: str, chapters: list[dict], output_path: str) -> bool:
    md_path = str(TEMP_DIR / "chapters_metadata.txt")
    with open(md_path, "w") as f:
        f.write(";FFMETADATA1\n")
        for ch in chapters:
            start_ms = int(ch.get("start_time", 0) * 1000)
            end_ms = int(ch.get("end_time", 0) * 1000)
            title = ch.get("title", "Chapter")
            f.write(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={start_ms}\nEND={end_ms}\ntitle={title}\n")
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, "-i", md_path,
        "-map_metadata", "1", "-c:v", "copy", "-c:a", "copy", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def _concat_only(processed: list[str], video_id: str) -> str | None:
    concat_list = str(TEMP_DIR / f"concat_{video_id}.txt")
    combined = str(TEMP_DIR / f"concat_only_{video_id}.mp4")
    try:
        with open(concat_list, "w") as f:
            for p in processed:
                f.write(f"file '{p}'\n")
        cmd = [
            _ffmpeg_cmd(), "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
            *_sws_flags(),
            "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
            "-pix_fmt", "yuv420p", combined,
        ]
        result = safe_run(cmd, timeout=300)
        return combined if result.returncode == 0 and os.path.exists(combined) else None
    except Exception as e:
        print(f"[compositor] _concat_only error: {e}")
        return None


def _color_grade_scenes(processed: list[str], video_id: str, threshold: float = 0.15, target_ref: dict = None) -> list[str]:
    if not ENABLE_COLOR_GRADING or not processed:
        return processed

    graded = []
    ref = target_ref or BRAND_TEAL_YUV

    for i, curr in enumerate(processed):
        curr_hist = _extract_yuv_histogram(curr)
        if curr_hist is None:
            graded.append(curr)
            continue

        shift = _histogram_shift(ref, curr_hist)
        if shift > threshold or i == 0:
            if i > 0 or shift > threshold:
                logger.info("[color_grade] Scene %d brand shift=%.3f > %.3f, correcting to brand palette",
                            i, shift, threshold)
            corrected = str(TEMP_DIR / f"color_corrected_{video_id}_{i:03d}.mp4")
            if _apply_color_correction(curr, corrected, ref):
                graded.append(corrected)
            else:
                graded.append(curr)
        else:
            graded.append(curr)

    corrected_count = sum(1 for i in range(len(processed)) if graded[i] != processed[i])
    logger.info("[color_grade] Graded %d scenes to brand palette, corrected %d",
                len(processed), corrected_count)
    return graded


def _extract_yuv_histogram(video_path: str) -> dict | None:
    cmd = [
        _ffprobe_cmd(), "-v", "error", "-f", "lavfi",
        "-i", f"movie={video_path},signalstats",
        "-show_entries", "frame=pts_time:signalstats=YAVG,UAVG,VAVG",
        "-of", "json", "-v", "quiet",
    ]
    try:
        result = safe_run(cmd, timeout=30, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        frames = data.get("frames", [])
        if not frames:
            return None
        y_vals, u_vals, v_vals = [], [], []
        for f in frames:
            ss = f.get("tags", {})
            if ss.get("YAVG") is not None:
                y_vals.append(float(ss["YAVG"]))
                u_vals.append(float(ss["UAVG"]))
                v_vals.append(float(ss["VAVG"]))
        if not y_vals:
            return None
        return {
            "y_mean": sum(y_vals) / len(y_vals),
            "u_mean": sum(u_vals) / len(u_vals),
            "v_mean": sum(v_vals) / len(v_vals),
        }
    except Exception as e:
        logger.warning("[color_grade] Histogram extraction failed: %s", e)
        return None


def _histogram_shift(h1: dict, h2: dict) -> float:
    dy = abs(h1["y_mean"] - h2["y_mean"]) / 255.0
    du = abs(h1["u_mean"] - h2["u_mean"]) / 255.0
    dv = abs(h1["v_mean"] - h2["v_mean"]) / 255.0
    return (dy + du + dv) / 3.0


def _apply_color_correction(source: str, output: str, target_hist: dict) -> bool:
    # ponytail: match luminance/saturation via eq filter (correct color science)
    target_y = target_hist.get("y_mean", 128) / 255.0
    target_u = target_hist.get("u_mean", 128) / 255.0
    target_v = target_hist.get("v_mean", 128) / 255.0
    brightness = (target_y - 0.5) * 0.3
    saturation = 0.9 + (target_v * 0.2)
    contrast = 0.95 + (target_y * 0.1)
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", source,
        "-vf", f"eq=brightness={brightness:.3f}:contrast={contrast:.3f}:saturation={saturation:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", CRF,
        "-pix_fmt", "yuv420p", output,
    ]
    try:
        result = safe_run(cmd, timeout=120)
        return result.returncode == 0 and os.path.exists(output) and os.path.getsize(output) > 1000
    except Exception:
        return False


def _extract_keyterms(scene: dict) -> list[str]:
    """Extract key terms from a scene for animated text overlays."""
    terms = scene.get("asset_keywords", [])
    if isinstance(terms, str):
        terms = [terms]
    terms = list(filter(None, terms[:3]))
    if not terms:
        narration = scene.get("narration_text", "") or scene.get("text", "")
        if isinstance(narration, str):
            words = narration.split()
            terms = [w for w in words if len(w) > 5 and w[0].isupper() and w.isalpha()][:2]
    kw = scene.get("keyword", "")
    if kw and kw not in terms:
        terms.insert(0, kw)
    return terms[:3]


def _build_keyterm_filters(scenes: list[dict], clips: list[dict]) -> list[str]:
    """Build drawtext filters for animated key-term overlays synced to scenes.
    
    Each key term appears at the top of the frame with a fade-in animation,
    matching how 3Blue1Brown and Universal Resilience highlight concepts.
    The first content scene (hook) gets a larger, more prominent treatment.
    """
    filters = []
    first_content_idx = None
    for i, s in enumerate(scenes):
        if i >= len(clips):
            break
        terms = _extract_keyterms(s)
        if not terms:
            continue
        if first_content_idx is None:
            first_content_idx = i

        ts = sum(c.get("duration", 8.0) for c in clips[:i])
        dur = clips[i].get("duration", 8.0)
        term_count = min(len(terms), 3)
        spacing = max(2.5, dur / (term_count + 1))

        is_hook = (i == first_content_idx)
        font_size = 48 if is_hook else 36
        font_color = "#e07040" if is_hook else "#8a50e8"
        fade_in_dur = 0.8 if is_hook else 0.4

        for j, term in enumerate(terms):
            escaped = term.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
            appear = ts + spacing * j
            hold = max(2.0, spacing - 0.8)
            disappear = appear + fade_in_dur + hold
            fade_out = 0.4
            end = disappear + fade_out
            x_expr = (
                f"if(lt(t\\,{appear}+{fade_in_dur})\\,"
                f"(-text_w-20)+(w+text_w+20)*(t-{appear})/{fade_in_dur}\\,"
                f"if(lt(t\\,{disappear})\\,"
                f"(w-text_w)/2\\,"
                f"if(lt(t\\,{disappear}+{fade_out})\\,"
                f"(w-text_w)/2*(1-(t-{disappear})/{fade_out})\\,"
                f"-text_w-20)))"
            )
            y_expr = "h*0.10" if is_hook else "h*0.12"
            filters.append(
                f"drawtext=text='{escaped}':fontsize={font_size}:fontcolor={font_color}:"
                f"x={x_expr}:y={y_expr}:"
                f"borderw=2:bordercolor=#1e1e1e@0.8:"
                f"enable='between(t\\,{appear}\\,{end})':"
                f"fontfile=/System/Library/Fonts/Helvetica.ttc"
            )
    return filters


def composite_video(clips: list[dict], voice_path: str, music_path: Optional[str] = None,
                    format_type: str = "shorts", video_id: str = "output",
                    subtitle_path: Optional[str] = None, chapters: Optional[list] = None,
                    category: str = "", scenes: Optional[list] = None,
                    force_concat: bool = False, tier: str = "") -> Optional[str]:
    target = ASPECT_RATIOS.get(format_type, ASPECT_RATIOS["long"])
    tw, th = target["w"], target["h"]

    processed = []
    transitions = []
    durations = []
    for i, clip in enumerate(clips):
        out = _process_clip(clip, tw, th, i, format_type)
        if out is None:
            continue
        processed.append(out)
        requested_dur = clip.get("duration", 8.0)
        actual_dur = _get_duration(out) or requested_dur
        if actual_dur < requested_dur - 0.5:
            extended = str(TEMP_DIR / f"extended_{i:03d}.mp4")
            if _extend_clip(out, extended, requested_dur):
                processed[-1] = extended
                actual_dur = requested_dur
        clip["duration"] = actual_dur
        transitions.append(clip.get("transition", "dissolve"))
        durations.append(actual_dur)

    if not processed:
        print("[compositor] No clips to composite")
        return None

    processed[0] = _fade_in_first_clip(processed[0], 0, durations[0] if durations else 8.0)

    if ENABLE_COLOR_GRADING:
        grade_ref = DOCUMENTARY_YUV if tier == "documentary" else BRAND_TEAL_YUV
        processed = _color_grade_scenes(processed, video_id, COLOR_GRADING_THRESHOLD, target_ref=grade_ref)

    combined_video = str(TEMP_DIR / f"combined_{video_id}.mp4")
    if len(processed) == 1:
        combined_video = processed[0]
    elif force_concat:
        print("[compositor] force_concat=True, skipping fade transition")
        combined_video = _concat_only(processed, video_id)
        if not combined_video:
            return None
    else:
        filter_str, out_label = _build_xfade_transition(processed, durations, transitions, tw, th)
        inputs = []
        for p in processed:
            inputs.extend(["-i", p])
        cmd = [
            _ffmpeg_cmd(), "-y", *inputs, *_sws_flags(),
            "-filter_complex", filter_str,
            "-map", f"[{out_label}]",
            "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
            "-pix_fmt", "yuv420p", combined_video,
        ]
        try:
            result = safe_run(cmd, timeout=600)
            if result.returncode != 0 or not os.path.exists(combined_video):
                print(f"[compositor] xfade transition failed (rc={result.returncode}), full stderr: {result.stderr[-500:]}")
                combined_video = _concat_only(processed, video_id)
                if not combined_video:
                    return None
        except Exception as e:
            print(f"[compositor] xfade transition error: {e}, falling back to concat")
            combined_video = _concat_only(processed, video_id)
            if not combined_video:
                return None

    if not os.path.exists(combined_video):
        return None

    if chapters and format_type == "long":
        with_chapters = str(TEMP_DIR / f"chapters_{video_id}.mp4")
        if add_chapter_markers(combined_video, chapters, with_chapters):
            combined_video = with_chapters

    mixed_audio = str(TEMP_DIR / f"audio_{video_id}.wav")
    sfx_scenes = [s for s in (scenes or []) if s.get("sfx")]
    n_clips = len(clips or [])
    for i in range(n_clips - 1):
        ts_ms = int(sum(clips[j].get("duration", 8.0) for j in range(i + 1)) * 1000)
        if ts_ms > 0:
            sfx_scenes.append({"timing_offset_ms": ts_ms, "sfx_type": "transition"})
    if not mix_audio(voice_path, music_path, mixed_audio, sfx_scenes=sfx_scenes):
        print("[compositor] Audio mix failed")
        return None

    final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
    # ponytail: lighter unsharp — only sharpens video content, not text overlays (which come after)
    vf_parts = ["unsharp=3:3:0.3:3:3:0.2"]

    if scenes:
        for i, s in enumerate(scenes):
            if i >= len(clips):
                break
            title = s.get("keyword") or s.get("description") or ""
            if title:
                escaped = title.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
                ts = sum(c.get("duration", 8.0) for c in clips[:i])
                te = ts + clips[i].get("duration", 8.0) - 0.5
                x_expr = (
                    f"if(lt(t\\,{ts}+0.3)\\,-text_w+(w+text_w)*(t-{ts})/0.3\\,"
                    f"if(gte(t\\,{te}-0.3)\\,(w-text_w)/2-(w+text_w)*(t-({te}-0.3))/0.3\\,"
                    f"(w-text_w)/2))"
                )
                vf_parts.append(
                    f"drawtext=text='{escaped}':fontsize=28:fontcolor=#8a50e8:box=1:boxcolor=black@0.4:"
                    f"boxborderw=6:x={x_expr}:y=h-130:enable='between(t\\,{ts}\\,{te})'"
                )

        # Key-term text overlays — show important terms animated on screen
        vf_parts.extend(_build_keyterm_filters(scenes, clips))

        # Annotations — callouts, steps, definitions, arrows, highlights, counters
        if os.getenv("ENABLE_ANNOTATIONS", "true").lower() == "true":
            ann_filters = build_annotation_filters(scenes, clips)
            if ann_filters:
                vf_parts.extend(ann_filters)

        # Mid-roll CTA: "Subscribe" prompt at 60% mark
        if os.getenv("ENABLE_MIDROLL_CTA", "true").lower() == "true":
            total_dur = sum(c.get("duration", 8.0) for c in clips) if clips else 120
            cta_time = total_dur * 0.6
            cta_end = cta_time + 4.0
            cta_x = (
                f"if(lt(t\\,{cta_time}+0.4)\\,(w-text_w)/2-20+(w+20)*(t-{cta_time})/0.4\\,"
                f"if(gte(t\\,{cta_end}-0.4)\\,(w+20)-(w+text_w+20)*(t-({cta_end}-0.4))/0.4\\,"
                f"(w-text_w)/2))"
            )
            vf_parts.append(
                f"drawtext=text='Subscribe for more':fontsize=28:fontcolor=#00CCCC:"
                f"box=1:boxcolor=black@0.7:boxborderw=10:"
                f"x={cta_x}:y=h*0.75:enable='between(t\\,{cta_time}\\,{cta_end})'"
            )

    if subtitle_path and os.path.exists(subtitle_path):
        abs_sub = os.path.abspath(subtitle_path)
        is_deep = category in (_DEEP_LESSON_CATS if _DEEP_LESSON_CATS else set())
        is_doc = tier == "documentary"
        if is_doc:
            sub_fs = 24
            margin_v = 60
            sub_primary = "&H000088CC&"
            sub_outline = "&H00000000&"
            sub_border = "&H80000000&"
            has_outline = 2
        elif is_deep:
            sub_fs = 26
            margin_v = 90
            sub_primary = "&H000088CC&"
            sub_outline = "&H80000000&"
            has_outline = 1
        elif format_type == "shorts":
            sub_fs = 28
            margin_v = 60
            sub_primary = "&H000088CC&"
            sub_outline = "&H80000000&"
            has_outline = 1
        else:
            sub_fs = 24
            margin_v = 80
            sub_primary = "&H000088CC&"
            sub_outline = "&H80000000&"
            has_outline = 1
        vf_parts.append(
            f"subtitles=filename='{abs_sub}':force_style="
            f"{_subtitle_style_escaped(sub_fs, margin_v, sub_primary, sub_outline, has_outline=has_outline)}"
        )

    vf_filter = ",".join(vf_parts)

    cmd = [
        _ffmpeg_cmd(), "-y", "-i", combined_video, "-i", mixed_audio, *_sws_flags(),
    ]
    cmd += ["-vf", vf_filter] if vf_filter else []
    cmd += [
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-af", "acompressor=threshold=-24dB:ratio=2:attack=5:release=50,"
               "loudnorm=I=-14:LRA=11:TP=-1,"
               "alimiter=limit=-1.5dB:attack=0.1:release=1,"
               "firequalizer=gain='if(between(f,5500,7000), -3, if(gt(f,9000), -2, 0))'",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-pix_fmt", "yuv420p", final_path,
    ]
    try:
        print(f"[compositor] Final mux cmd: {' '.join(str(a) for a in cmd)}")
        result = safe_run(cmd, timeout=300)
        if result.returncode == 0 and os.path.exists(final_path):
            print(f"[compositor] Final video: {final_path} ({os.path.getsize(final_path)} bytes)")
            from utils.upscaler import upscale_video, is_available
            upscaled = final_path.replace(".mp4", "_2x.mp4")
            if is_available() and upscale_video(final_path, upscaled, scale=2):
                print(f"[compositor] Upscaled: {upscaled}")
                os.replace(upscaled, final_path)
                print(f"[compositor] Replaced original with upscaled: {final_path}")
            return final_path
        print(f"[compositor] Final mux rc={result.returncode}, stderr: {result.stderr[-500:]}")
    except Exception as e:
        print(f"[compositor] Final mux error: {e}")
    return None
