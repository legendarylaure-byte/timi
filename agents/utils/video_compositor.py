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

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = Path(__file__).parent.parent / "tmp" / "compositor"
TEMP_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(TEMP_DIR))

OUTPUT_4K = os.getenv("OUTPUT_4K", "false").lower() == "true"
OUTPUT_W = 3840 if OUTPUT_4K else 1920
OUTPUT_H = 2160 if OUTPUT_4K else 1080

ENABLE_COLOR_GRADING = os.getenv("ENABLE_COLOR_GRADING", "false").lower() == "true"
COLOR_GRADING_THRESHOLD = float(os.getenv("COLOR_GRADING_THRESHOLD", "0.15"))

ASPECT_RATIOS = {
    "shorts": {"w": 1080, "h": 1920, "ar": "9:16"},
    "long": {"w": OUTPUT_W, "h": OUTPUT_H, "ar": "16:9"},
}

FFMPEG_XFADE_MAP = {
    "dissolve": "dissolve",
    "fade": "fade",
    "slide_left": "slideleft",
    "slide_right": "slideright",
    "zoom": "zoompan",
    "cut": "cut",
    "circle_open": "circleopen",
    "circle_close": "circleclose",
    "pixelize": "pixelize",
    "wipe_left": "wipeleft",
    "wipe_right": "wiperight",
    "wipe_up": "wipeup",
    "wipe_down": "wipedown",
    "smooth_left": "smoothleft",
    "smooth_right": "smoothright",
    "fade_gradual": "fadegradual",
    "squeeze_h": "squeezeh",
    "squeeze_v": "squeezev",
}

OUTPUT_FPS = 24
CRF = "20"

logger = logging.getLogger(__name__)
PRESET = "medium"

SFX_VOLUME_DB = float(os.getenv("SFX_VOLUME_DB", "-12"))
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
    """Loop a clip to fill target_dur seconds if it's shorter than requested."""
    current = _get_duration(input_path)
    if current >= target_dur - 0.5:
        return True
    cmd = [
        _ffmpeg_cmd(), "-y", "-stream_loop", "-1", "-i", input_path,
        *_sws_flags(),
        "-c:v", "libx264", "-preset", "fast", "-crf", CRF,
        "-t", str(target_dur),
        "-pix_fmt", "yuv420p",
        "-an", output_path,
    ]
    return safe_run_bool(cmd, timeout=300)


def resize_to_target(input_path: str, output_path: str, target_w: int, target_h: int) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, *_sws_flags(),
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

    # Pan across the wider dimension over the clip's duration
    if src_w * target_h > src_h * target_w:
        # Source is wider — pan horizontally
        max_x = max(0, src_w - crop_w)
        x_expr = f"{max_x}*t/{duration}" if max_x > 0 else "0"
        y_expr = f"({src_h} - {crop_h}) / 2"
    else:
        # Source is taller — pan vertically
        max_y = max(0, src_h - crop_h)
        x_expr = f"({src_w} - {crop_w}) / 2"
        y_expr = f"{max_y}*t/{duration}" if max_y > 0 else "0"

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


MUSIC_FADE_MS = 800
SFX_EMPHASIS_VOLUME_DB = -10


def _generate_emphasis_tone(duration_ms: int = 200, freq: int = 440) -> AudioSegment:
    import math
    import array
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms / 1000)
    samples = [int(8192 * math.sin(2 * math.pi * freq * t / sample_rate)) for t in range(n_samples)]
    for t in range(min(50, n_samples)):
        samples[t] = int(samples[t] * t / 50)
        samples[-(t + 1)] = int(samples[-(t + 1)] * t / 50)
    raw = array.array('h', samples).tobytes()
    return AudioSegment(raw, frame_rate=sample_rate, sample_width=2, channels=1)


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


def mix_audio(voice_path: str, music_path: Optional[str], output_path: str,
              voice_volume_db: float = 0, music_volume_db: float = -18,
              duck_db: float = -6, sfx_scenes: Optional[list] = None,
              duration_ms: Optional[int] = None) -> bool:
    try:
        voice = AudioSegment.from_file(voice_path) + voice_volume_db
        if duration_ms:
            voice = voice[:duration_ms]

        if music_path and os.path.exists(music_path):
            music_raw = (AudioSegment.from_file(music_path) + music_volume_db)
            music_raw = (music_raw * (len(voice) // len(music_raw) + 1))[:len(voice)]
            if len(music_raw) > MUSIC_FADE_MS * 2:
                music_raw = music_raw.fade_in(MUSIC_FADE_MS).fade_out(MUSIC_FADE_MS)
            music_raw = _apply_ducking(music_raw, voice, duck_db=duck_db)
            mixed = voice.overlay(music_raw)
        else:
            mixed = voice

        ambient_pad = _generate_ambient_pad(len(mixed))
        ambient_pad = ambient_pad + _AMBIENT_VOLUME_DB
        mixed = mixed.overlay(ambient_pad)

        if sfx_scenes:
            sfx_track = AudioSegment.silent(duration=len(mixed))
            cumulative_ms = 0
            emphasis_markers = []
            for si, scene in enumerate(sfx_scenes):
                dur = scene.get("duration", scene.get("target_duration", 8.0))
                scene_sfx = scene.get("sfx", [])
                for sfx in scene_sfx:
                    sfx_path = sfx.get("path", "")
                    if os.path.exists(sfx_path):
                        try:
                            sfx_audio = AudioSegment.from_file(sfx_path) + SFX_VOLUME_DB
                            sfx_track = sfx_track.overlay(sfx_audio, position=cumulative_ms)
                        except Exception:
                            pass
                scene_mood = scene.get("music_mood", "focused")
                if scene_mood == "transition" or si > 0 and si % 3 == 0:
                    emphasis_markers.append(cumulative_ms + int(dur * 500))
                cumulative_ms += int(dur * 1000)

            for pos_ms in emphasis_markers:
                tone = _generate_emphasis_tone(120, 660)
                tone = tone + SFX_EMPHASIS_VOLUME_DB
                sfx_track = sfx_track.overlay(tone, position=min(pos_ms, len(sfx_track) - len(tone)))

            if len(mixed) > 1000:
                cta_pos = max(0, len(mixed) - 3000)
                cta_tone = _generate_emphasis_tone(300, 880)
                cta_tone = cta_tone.fade_in(50).fade_out(100) + SFX_EMPHASIS_VOLUME_DB
                sfx_track = sfx_track.overlay(cta_tone, position=min(cta_pos, len(sfx_track) - len(cta_tone)))

            mixed = mixed.overlay(sfx_track)

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
        if not trim_clip(src, trimmed, 0, dur):
            return None

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
        if not resize_to_target(src, out, target_w, target_h):
            return None

    return out if os.path.exists(out) and os.path.getsize(out) > 1000 else None


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
        "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def _xfade_duration_for_scene(duration: float) -> float:
    if duration < 5:
        return 0.5
    if duration > 15:
        return 1.5
    return 1.0


def _build_xfade_filter(processed: list[str], transitions: list[str], durations: list[float]) -> tuple[str, str]:
    n = len(processed)
    if n == 0:
        return "", ""
    if n == 1:
        return f"[0:v]format=yuv420p[out]", "out"

    labels = []
    filter_parts = []
    had_none = False

    for i in range(n):
        label = f"v{i}"
        labels.append(label)
        filter_parts.append(f"[{i}:v]setpts=PTS-STARTPTS,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709[{label}]")

    prev_label = labels[0]
    cumulative = durations[0]
    for i in range(1, n):
        raw = transitions[i] if i < len(transitions) else "dissolve"
        if raw == "none":
            had_none = True
            out_label = prev_label
            cumulative += durations[i]
            continue
        xfade = FFMPEG_XFADE_MAP.get(raw, "dissolve")
        xfade_dur = _xfade_duration_for_scene(durations[i])
        out_label = f"xf{i}"
        offset = max(0, cumulative - xfade_dur)
        filter_parts.append(
            f"[{prev_label}][{labels[i]}]xfade=transition={xfade}:duration={xfade_dur}:offset={offset}[{out_label}]"
        )
        prev_label = out_label
        cumulative += durations[i] - xfade_dur

    result = ";".join(filter_parts)
    if had_none:
        result = result.replace("none", "dissolve")
    return result, prev_label


def add_text_overlay(video_path: str, text: str, output_path: str,
                     fontsize: int = 48, color: str = "white",
                     position: str = "center", start_time: float = 0,
                     duration: float = 3) -> bool:
    positions = {"center": "(w-text_w)/2:(h-text_h)/2",
                 "bottom": "(w-text_w)/2:(h-text_h)-50",
                 "top": "(w-text_w)/2:50"}
    pos = positions.get(position, positions["center"])
    escaped = text.replace("'", "\\'").replace(":", "\\:").replace("-", "\\-")
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, *_sws_flags(),
        "-vf", f"drawtext=text='{escaped}':fontsize={fontsize}:fontcolor={color}:x={pos}:enable='between(t,{start_time},{start_time+duration})'",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def add_animated_lower_third(video_path: str, text: str, output_path: str,
                              fontsize: int = 22, color: str = "#00CCCC",
                              start_time: float = 0, duration: float = 5) -> bool:
    escaped = text.replace("'", "\\'").replace(":", "\\:").replace("-", "\\-")
    ts = start_time
    te = start_time + duration
    x_expr = (
        f"if(lt(t,{ts}+0.3),-text_w+(w+text_w)*(t-{ts})/0.3,"
        f"if(gte(t,{te}-0.3),(w-text_w)/2-(w+text_w)*(t-({te}-0.3))/0.3,"
        f"(w-text_w)/2))"
    )
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, *_sws_flags(),
        "-vf",
        f"drawtext=text='{escaped}':fontsize={fontsize}:fontcolor={color}:"
        f"box=1:boxcolor=black@0.5:boxborderw=8:"
        f"x={x_expr}:y=h-100:enable='between(t,{ts},{te})',"
        f"drawbox=x=(w-text_w)/2-12:y=h-116:w=4:h=22:color={color}:enable='between(t,{ts}+0.3,{te}-0.3)'",
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


def burn_subtitles(video_path: str, subtitle_path: str, output_path: str,
                   fontsize: int = 28) -> bool:
    abs_sub = os.path.abspath(subtitle_path)
    vf = (
        f"subtitles=filename='{abs_sub}':force_style="
        f"'FontSize={fontsize},PrimaryColour=&HFF00CCCC&,OutlineColour=&H40002B00&,"
        f"Outline=0,Shadow=0,BorderStyle=3,BackColour=&H40000000&,"
        f"Alignment=2,MarginV=40,FontName=Arial'"
    )
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


def _color_grade_scenes(processed: list[str], video_id: str, threshold: float = 0.15) -> list[str]:
    if not ENABLE_COLOR_GRADING or len(processed) < 2:
        return processed

    graded = [processed[0]]

    for i in range(1, len(processed)):
        prev = graded[-1]
        curr = processed[i]

        prev_hist = _extract_yuv_histogram(prev)
        curr_hist = _extract_yuv_histogram(curr)

        if prev_hist is None or curr_hist is None:
            graded.append(curr)
            continue

        shift = _histogram_shift(prev_hist, curr_hist)
        if shift > threshold:
            logger.info("[color_grade] Scene %d→%d color shift=%.3f > %.3f, correcting",
                        i - 1, i, shift, threshold)
            corrected = str(TEMP_DIR / f"color_corrected_{video_id}_{i:03d}.mp4")
            if _apply_color_correction(curr, corrected, prev_hist):
                graded.append(corrected)
            else:
                graded.append(curr)
        else:
            graded.append(curr)

    corrected_count = sum(1 for idx in range(1, len(processed)) if graded[idx] != processed[idx])
    logger.info("[color_grade] Checked %d scene transitions, corrected %d",
                len(processed) - 1, corrected_count)
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
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", source,
        "-vf", (
            f"colorbalance=rs={1.0 - target_hist['y_mean'] / 255.0:.3f}:"
            f"gs={1.0 - target_hist['u_mean'] / 255.0:.3f}:"
            f"bs={1.0 - target_hist['v_mean'] / 255.0:.3f}"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", CRF,
        "-pix_fmt", "yuv420p", output,
    ]
    try:
        result = safe_run(cmd, timeout=120)
        return result.returncode == 0 and os.path.exists(output) and os.path.getsize(output) > 1000
    except Exception:
        return False


def composite_video(clips: list[dict], voice_path: str, music_path: Optional[str] = None,
                    format_type: str = "shorts", video_id: str = "output",
                    subtitle_path: Optional[str] = None, chapters: Optional[list] = None,
                    category: str = "", scenes: Optional[list] = None,
                    force_concat: bool = False) -> Optional[str]:
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

    if ENABLE_COLOR_GRADING:
        processed = _color_grade_scenes(processed, video_id, COLOR_GRADING_THRESHOLD)

    combined_video = str(TEMP_DIR / f"combined_{video_id}.mp4")
    if len(processed) == 1:
        combined_video = processed[0]
    elif force_concat:
        print("[compositor] force_concat=True, skipping xfade")
        combined_video = _concat_only(processed, video_id)
        if not combined_video:
            return None
    else:
        filter_str, out_label = _build_xfade_filter(processed, transitions, durations)
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
                print(f"[compositor] Xfade failed (rc={result.returncode}), full stderr: {result.stderr[-500:]}")
                print("[compositor] Falling back to concat")
                combined_video = _concat_only(processed, video_id)
                if not combined_video:
                    print(f"[compositor] Concat also failed")
                    return None
        except Exception as e:
            print(f"[compositor] Xfade error: {e}")
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
    if not mix_audio(voice_path, music_path, mixed_audio, sfx_scenes=sfx_scenes):
        print("[compositor] Audio mix failed")
        return None

    final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
    vf_parts = []

    if scenes:
        for i, s in enumerate(scenes):
            if i >= len(clips):
                break
            title = s.get("keyword") or s.get("description") or ""
            if title:
                escaped = title.replace("'", "\\'").replace(":", "\\:").replace("-", "\\-")
                ts = sum(c.get("duration", 8.0) for c in clips[:i])
                te = ts + clips[i].get("duration", 8.0) - 0.5
                x_expr = (
                    f"if(lt(t,{ts}+0.3),-text_w+(w+text_w)*(t-{ts})/0.3,"
                    f"if(gte(t,{te}-0.3),(w-text_w)/2-(w+text_w)*(t-({te}-0.3))/0.3,"
                    f"(w-text_w)/2))"
                )
                vf_parts.append(
                    f"drawtext=text='{escaped}':fontsize=20:fontcolor=#00CCCC:box=1:boxcolor=black@0.4:"
                    f"boxborderw=6:x={x_expr}:y=h-130:enable='between(t,{ts},{te})'"
                )

    if subtitle_path and os.path.exists(subtitle_path):
        abs_sub = os.path.abspath(subtitle_path)
        sub_fs = 18
        vf_parts.append(
            f"subtitles=filename='{abs_sub}':force_style="
            f"'FontSize={sub_fs},PrimaryColour=&HFF00CCCC&,OutlineColour=&H40002B00&,"
            f"Outline=0,Shadow=0,BorderStyle=3,BackColour=&H40000000&,"
            f"Alignment=2,MarginV=40,FontName=Arial'"
        )

    vf_parts.extend(["eq=saturation=1.25:contrast=1.1", "unsharp=5:5:0.8:3:3:0.4"])
    vf_filter = ",".join(vf_parts)

    cmd = [
        _ffmpeg_cmd(), "-y", "-i", combined_video, "-i", mixed_audio, *_sws_flags(),
    ]
    cmd += ["-vf", vf_filter] if vf_filter else []
    cmd += [
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS),
        "-af", "compand=attacks=0.1:decays=0.3:points=-80/-80|-30/-18|-10/-5|0/-3:gain=3,loudnorm=I=-16:LRA=11:TP=-1.5",
        "-c:a", "aac", "-b:a", "192k", "-shortest", "-pix_fmt", "yuv420p", final_path,
    ]
    try:
        result = safe_run(cmd, timeout=300)
        if result.returncode == 0 and os.path.exists(final_path):
            print(f"[compositor] Final video: {final_path} ({os.path.getsize(final_path)} bytes)")
            return final_path
        print(f"[compositor] Final mux error: {result.stderr[-200:]}")
    except Exception as e:
        print(f"[compositor] Final mux error: {e}")
    return None
