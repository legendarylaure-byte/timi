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
from utils.brand_palette import (
    GRADE_CURVES,
    GRADE_REFERENCE_YUV,
    ass,
    LICORICE,
    PURPLE,
    VIOLET,
    ORANGE,
    LIGHT_ORANGE,
    PINK,
    WHITE,
    AMBER,
    watermark_position,
)
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
# Deadband for "this scene is far enough off target to be worth a re-encode".
# Was 0.15, which was tuned when the reference was the fictional y=140 teal value.
# Against the measured target (y=92) a genuinely too-dark scene at y=43 shifts
# only 0.080, so 0.15 silently graded almost nothing. 0.05 leaves a real
# deadband around the target while catching the darkness we actually ship.
COLOR_GRADING_THRESHOLD = float(os.getenv("COLOR_GRADING_THRESHOLD", "0.05"))
# One dial for how far to move. 0 disables the grade entirely (everything passes
# through untouched); 1 is the full look. Exists because taste is not something
# that should need a code change plus a 16GB image rebuild to adjust.
GRADE_STRENGTH = max(0.0, min(1.0, float(os.getenv("GRADE_STRENGTH", "1.0"))))
# Saturation push. Default 0, deliberately.
#
# This was a flat 0.18 and it fought the goal. brand_palette says outright that
# "tinting every frame purple is what makes AI footage look cheap", and vibrance
# does not remove a cast -- it amplifies whatever cast the source already has.
# Shipped output measured u=142.9, i.e. visibly blue, so an 18% vibrance lift was
# making the slate-blue stronger. The brand is carried by the CTA, lower-third and
# watermark, so the footage needs no saturation help. Left as a dial because taste
# is not something that should need a code change plus an image rebuild to adjust.
GRADE_VIBRANCE = max(0.0, min(1.0, float(os.getenv("GRADE_VIBRANCE", "0.0"))))

# Brand palette reference (Licorice/Purple/Violet/Orange) — measured from real
# output by scripts/measure_grade.py, not freehand. See brand_palette.py for the
# measurements and why the target is a well-exposed look rather than a restatement
# of the near-black video the pipeline used to produce.
BRAND_YUV = dict(GRADE_REFERENCE_YUV)

# Subtitle palette. These are ASS (&HAABBGGRR&, BGR), so they go through
# ass() rather than being written by hand — '&H000088CC' and '#CC8800' are the
# same colour and this way the intent is readable. Subtitles deliberately stay
# amber: they must stay legible over unknown footage, and the brand is carried
# by the CTAs and lower-third instead.
SUBTITLE_ASS = ass(AMBER)              # &H003388CC& -> RGB(204,136,0) amber
SUBTITLE_OUTLINE_ASS = ass(LICORICE, alpha=0x40)   # soft dark halo
SUBTITLE_BORDER_ASS = ass(LICORICE, alpha=0x80)

# Documentary palette (cooler/desaturated — PBS NOVA / Branch Education style)
DOCUMENTARY_YUV = {"y_mean": 90.0, "u_mean": 128.0, "v_mean": 118.0}

ASPECT_RATIOS = {
    "shorts": {"w": 1080, "h": 1920, "ar": "9:16"},
    "long": {"w": OUTPUT_W, "h": OUTPUT_H, "ar": "16:9"},
}


OUTPUT_FPS = 24
# CRF is the final master quality dial. 17 is deliberately generous for shorts
# (seconds long, every frame is viewer attention). Longs render at CRF_LONG
# because a 5-minute master at 17 is ~390MB, which is re-encoded by all four
# platforms anyway -- the extra bits buy nothing visible but cost upload time
# and push TikTok from 4 chunks to 7.
CRF = "17"
CRF_LONG = os.getenv("CRF_LONG", "20")


def _final_crf(format_type: str) -> str:
    """Quality dial for the FINAL master, per format.

    Longs render at CRF_LONG: a 5-minute master at 17 is ~390MB, re-encoded by
    all four platforms anyway, and it pushes TikTok from 4 upload chunks to 7.
    Shorts stay at CRF -- they are seconds long, every frame is viewer attention,
    and the size saving is negligible.

    Named function so this is testable; it used to be an inline expression buried
    in a 270-line function where nothing could assert it.
    """
    return CRF_LONG if format_type == "long" else CRF


# Channel logo watermark opacity. 1.0 was a sticker competing with the footage.
LOGO_ALPHA = 0.6

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


def _subs_enabled_for(format_type: str) -> bool:
    """Whether subtitles should be burned into frames for this format."""
    try:
        from utils.subtitle_gen import should_burn_subtitles
        return should_burn_subtitles(format_type)
    except Exception:
        return True  # default to burning if the mode helper is unavailable


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


def resize_to_target(input_path: str, output_path: str, target_w: int, target_h: int, duration: float = 0, motion_seed: int = 0) -> bool:
    # A still held dead-still for a whole scene reads as a mistake. When we know the
    # duration (the still-image path), add a slow push-in so the frame is alive.
    if duration > 0:
        frames = max(2, int(duration * OUTPUT_FPS))
        # 1.0 -> 1.08 over the scene: slow enough not to be distracting, enough to move.
        direction = -1 if motion_seed % 2 else 1
        zoom_expr = f"min(1.08, 1+0.08*on/{frames})" if direction > 0 else f"min(1.08, 1.08-0.08*on/{frames})"
        vf = (
            f"scale={target_w * 2}:{target_h * 2}:flags=lanczos:force_original_aspect_ratio=increase,"
            f"crop={target_w * 2}:{target_h * 2},"
            f"zoompan=z='{zoom_expr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={target_w}x{target_h}:fps={OUTPUT_FPS}"
        )
    else:
        vf = f"scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=increase,crop={target_w}:{target_h}"
    cmd = [
        _ffmpeg_cmd(), "-y",
        *(["-loop", "1", "-t", str(duration)] if duration > 0 else []),
        "-i", input_path, *_sws_flags(),
        # ponytail: bound the OUTPUT too, and do not "simplify" this away. zoompan
        # d=N expands every INPUT frame into N output frames, and a still arrives as
        # `-loop 1 -t dur`, which the image2 demuxer feeds at 25fps -- so the input
        # already holds dur*25 frames and the output was dur*25*N/24, i.e. QUADRATIC
        # in the allotment. A 4.6s card rendered 527s; a 7.0s card rendered 1225s.
        # The input -t above cannot help, because zoompan re-expands every one of
        # those frames. This output -t stops ffmpeg pulling input once the duration
        # is reached -- and the first input frame alone already emits exactly N
        # frames, so what survives is one smooth push-in, not a stuttering loop.
        *(["-t", str(duration)] if duration > 0 else []),
        "-vf", vf,
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


def resize_portrait_to_target(input_path: str, output_path: str, target_w: int, target_h: int, duration: float = 0) -> bool:
    """Genuinely-portrait crop: slice the (typically landscape) source to the 9:16
    aspect and upscale to fill the portrait frame — no blurred-pad letterbox.
    A slow horizontal Ken Burns pan keeps the crop from looking static."""
    kb = 1.0 + 0.06  # mild ~6% zoom so the pan has headroom
    t_expr = duration if duration > 0 else 60
    vf = (
        f"crop=min(iw\\,ih*9/16):ih:(iw-min(iw\\,ih*9/16))/2:0,"
        f"scale=iw*{kb}:ih*{kb}:flags=lanczos,"
        f"crop=min(iw\\,ih*9/16):ih:(iw-min(iw\\,ih*9/16))*t/{t_expr}:0,"
        f"scale={target_w}:{target_h}:flags=lanczos"
    )
    cmd = [
        _ffmpeg_cmd(), "-y",
        "-i", input_path, *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def apply_ken_burns(input_path: str, output_path: str, target_w: int, target_h: int, duration: float, preset_idx: int = 0, vid: str = "") -> bool:
    # ponytail: this MUST NOT be named kb_trim_{vid}_{preset_idx}. _process_clip
    # creates its trimmed input at exactly that path and passes it in as
    # input_path, so the old name made this trim_clip(X, X) -- same file, -y.
    # That failed, and the fallback below silently swapped Ken Burns for a plain
    # scale/crop on every long-form clip. Hence "kb_in", not a shared name.
    trim_path = str(TEMP_DIR / f"kb_in_{vid}_{preset_idx:03d}.mp4")
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
                # Was fade_in(3000): three seconds of near-silence at the start of
                # every video, which is dead air in the exact window that decides
                # retention. Short, and long enough to avoid a click.
                music_raw = music_raw.fade_in(400).fade_out(1200)
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


def _process_clip(clip: dict, target_w: int, target_h: int, idx: int, format_type: str = "shorts", vid: str = "") -> str | None:
    src = clip["path"]
    dur = clip.get("duration", 8.0)
    out = str(TEMP_DIR / f"clip_{vid}_{idx:03d}.mp4")
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
        trimmed = str(TEMP_DIR / f"kb_trim_{vid}_{idx:03d}.mp4")
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
            portrait = os.getenv("ENABLE_PORTRAIT_SHORTS", "true").lower() != "false"
            if portrait:
                if not resize_portrait_to_target(trimmed, out, target_w, target_h, duration=dur):
                    return None
            elif not pad_with_blurred_background(trimmed, out, target_w, target_h):
                return None
        elif has_camera_effect:
            if not _apply_camera_motion(trimmed, out, target_w, target_h, dur, zoom, pan_x, pan_y):
                if not apply_ken_burns(trimmed, out, target_w, target_h, dur, idx, vid):
                    return None
        else:
            if not apply_ken_burns(trimmed, out, target_w, target_h, dur, idx, vid):
                return None
    else:
        if not resize_to_target(src, out, target_w, target_h, duration=dur, motion_seed=idx):
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


def _apply_camera_motion(input_path: str, output_path: str, target_w: int, target_h: int,
                         duration: float, zoom: float = 1.0, pan_x: float = 0, pan_y: float = 0) -> bool:
    if zoom > 1.25:
        zoom = 1.25
    zoom_pct = zoom * 100
    pan_x_px = int(pan_x * target_w * 0.2)
    pan_y_px = int(pan_y * target_h * 0.2)
    # ponytail: d=1, not d=dur*24, and do not "simplify" this back. zoompan d=N turns
    # every INPUT frame into N OUTPUT frames, so a dur-long input rendered
    # input_len*duration*24 -- measured 144s for a 2s slot, 288s for a 6s input. The
    # x=/y= terms below already divide `on` by duration*24, i.e. they were written
    # assuming exactly that many output frames, so d=1 is what they mean.
    vf = (
        f"zoompan=z='if(eq(on,1),{zoom_pct},min({zoom_pct},zoom+0.005))':"
        f"d=1:"
        f"x='iw/2-(iw/zoom/2)+{pan_x_px}*on/{int(duration*24)}':"
        f"y='ih/2-(ih/zoom/2)+{pan_y_px}*on/{int(duration*24)}':"
        f"s={target_w}x{target_h}:fps=24"
    )
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path, *_sws_flags(),
        # the output -t is belt-and-braces: with d=1 a source longer than the
        # allotment still over-runs, which is the half a d=1-only fix would miss.
        *(["-t", str(duration)] if duration > 0 else []),
        "-vf", vf,
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-r", str(OUTPUT_FPS), "-an", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


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
                              fontsize: int = 22, color: str = PURPLE,
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
        f"drawbox=x=(w-24)/2:y=h-116:w=4:h=22:color={color}:enable='between(t\\,{ts}+0.3\\,{te}-0.3)'",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    return safe_run_bool(cmd, timeout=120)


def add_logo_overlay(video_path: str, logo_path: str, output_path: str,
                     position: str = "safe", scale: float = 0.0,
                     width: int = 0, height: int = 0, format_type: str = "landscape") -> bool:
    """Burn the channel logo into a corner, inside the platform safe area.

    This had zero callers -- the channel has never shipped a watermark -- and a
    hardcoded 20px margin, which is nowhere near a real safe area: on 9:16 the
    bottom ~18% is covered by the platform's own caption and channel name, so a
    bottom-right logo is invisible on upload despite rendering perfectly locally.

    `position="safe"` resolves via watermark_position(): top-right on both
    formats, the only corner clear of the notch, the action rail and the caption
    band. Explicit corners still work for callers that want them.
    `scale=0` picks a width from the frame rather than a fraction of the logo's
    own pixels, so a 1024px source and a 180px source land the same size.
    """
    if not (os.path.exists(logo_path) and os.path.getsize(logo_path) > 0):
        logger.warning(f"[Logo] missing or empty logo asset, skipping: {logo_path}")
        return False

    if not (width and height):
        try:
            probe = safe_run([_ffmpeg_cmd(), "-i", video_path], timeout=60)
            blob = probe[1] if isinstance(probe, (list, tuple)) else str(probe)
            width = int(re.search(r"(\d{2,5})x(\d{2,5})", blob).group(1))
            height = int(re.search(r"(\d{2,5})x(\d{2,5})", blob).group(2))
        except Exception as e:
            logger.warning(f"[Logo] could not probe dimensions, skipping: {e}")
            return False

    if position == "safe":
        pos = watermark_position(width, height, format_type)
    else:
        m = round(height * 0.035)
        pos = {
            "bottom_right": f"main_w-overlay_w-{m}:main_h-overlay_h-{m}",
            "top_right": f"main_w-overlay_w-{m}:{m}",
            "bottom_left": f"{m}:main_h-overlay_h-{m}",
            "top_left": f"{m}:{m}",
        }.get(position, f"main_w-overlay_w-{m}:{m}")

    if scale <= 0:
        # ~6.5% of frame width at 0.6 alpha. This was 11% and fully opaque, which
        # the owner reviewed on real output and called a sticker rather than a
        # watermark — it competed with the shot instead of branding it. A
        # watermark has to yield to the frame; pass scale= to override.
        scale = round(width * 0.065)

    cmd = [
        _ffmpeg_cmd(), "-y", "-i", video_path, "-i", logo_path, *_sws_flags(),
        "-filter_complex",
        # -1 keeps the logo's own aspect ratio; scaling by width alone would
        # stretch a square icon into a rectangle. colorchannelmixer=aa scales
        # alpha so the mark sits behind the footage instead of on top of it.
        f"[1:v]scale={scale}:-1,format=rgba,colorchannelmixer=aa={LOGO_ALPHA:.2f}[logo];"
        f"[0:v][logo]overlay={pos}",
        "-c:v", "libx264", "-preset", PRESET, "-crf", CRF,
        "-c:a", "copy", "-pix_fmt", "yuv420p", output_path,
    ]
    if not safe_run_bool(cmd, timeout=180):
        return False
    # Reject a 0-byte result rather than reporting a watermark that isn't there.
    if not (os.path.exists(output_path) and os.path.getsize(output_path) > 1024):
        logger.error(f"[Logo] overlay produced no usable output: {output_path}")
        return False
    return True



def _subtitle_style_escaped(fontsize: int, margin_v: int = 60,
                            primary: str = "&H00FFFFFF&",
                            outline: str = "&H40000000&",
                            border_style: int = 1,
                            has_outline: int = 1,
                            back_colour: str = "") -> str:
    from utils.fonts import resolve_font_family
    parts = [
        f"FontSize={fontsize}",
        f"PrimaryColour={primary}",
        f"OutlineColour={outline}",
        f"Outline={has_outline}",
        "Shadow=0",
        f"BorderStyle={border_style}",
        f"Alignment=2",
        f"MarginV={margin_v}",
        # Was a hardcoded "Arial", which does not exist in the image and so
        # silently degraded to a Latin-only face. Resolve the real family.
        f"FontName={resolve_font_family()}",
    ]
    if back_colour:
        parts.append(f"BackColour={back_colour}")
    style = ",".join(parts)
    return style.replace(",", "\\,")


def burn_subtitles(video_path: str, subtitle_path: str, output_path: str,
                   fontsize: int = 12, tier: str = "") -> bool:
    abs_sub = os.path.abspath(subtitle_path)
    if tier == "documentary":
        sub_style = _subtitle_style_escaped(fontsize, 40, SUBTITLE_ASS, '&H00000000&', has_outline=2)
    else:
        sub_style = _subtitle_style_escaped(fontsize, 40, SUBTITLE_ASS, ass('#402B00', alpha=0x40), 3, 0, '&H40000000&')
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
    md_path = str(TEMP_DIR / f"chapters_metadata_{os.path.basename(output_path)}.txt")
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
    ref = target_ref or BRAND_YUV

    for i, curr in enumerate(processed):
        curr_hist = _extract_yuv_histogram(curr)
        if curr_hist is None:
            graded.append(curr)
            continue

        shift = _histogram_shift(ref, curr_hist)
        # No special case for scene 0. There used to be `or i == 0`, which
        # re-encoded the hook on every single video through a filter that
        # derived brightness=+0.000 -- a full generation-lossy pass, on the most
        # important scene, producing literally no change. The hook is the
        # retention frame; it should not be the frame we double-compress.
        if shift > threshold and GRADE_STRENGTH > 0:
            logger.info("[color_grade] Scene %d off target by %.3f (threshold %.3f), "
                        "grading y=%.1f -> %.1f", i, shift, threshold,
                        curr_hist.get("y_mean", 0), ref.get("y_mean", 0))
            corrected = str(TEMP_DIR / f"color_corrected_{video_id}_{i:03d}.mp4")
            if _apply_color_correction(curr, corrected, ref, curr_hist):
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
    """Mean YUV of a clip, in the units `_histogram_shift` expects.

    This used to shell out to ffprobe with
    `-show_entries frame=...:signalstats=YAVG,UAVG,VAVG`, which can never work:
    `signalstats` is an ffmpeg *video filter*, not an ffprobe metadata section,
    so ffprobe rejects the argument and exits non-zero. Every call returned
    None, `_color_grade_scenes` appended every scene unchanged, and colour
    grading was inert no matter what ENABLE_COLOR_GRADING said.

    ffmpeg's `metadata=print` filter is the supported way to read these.
    Frames are sampled at 2fps rather than measured one by one: signalstats on
    every frame of a 300s clip is thousands of rows for an average that does not
    change materially.
    """
    dump = TEMP_DIR / f"yuv_{os.getpid()}_{abs(hash(video_path)) % 10**8}.txt"
    cmd = [
        _ffmpeg_cmd(), "-v", "error", "-i", video_path,
        "-vf", f"fps=2,signalstats,metadata=print:file={dump}",
        "-f", "null", "-",
    ]
    try:
        result = safe_run(cmd, timeout=120, capture_output=True, text=True)
        if result.returncode != 0 or not dump.exists():
            logger.warning("[color_grade] signalstats failed (rc=%s) for %s",
                           result.returncode, os.path.basename(video_path))
            return None
        text = dump.read_text(errors="ignore")
    except Exception as e:
        logger.warning("[color_grade] Histogram extraction failed: %s", e)
        return None
    finally:
        try:
            dump.unlink()
        except OSError:
            pass

    acc = {"YAVG": 0.0, "UAVG": 0.0, "VAVG": 0.0}
    counts = dict.fromkeys(acc, 0)
    for line in text.splitlines():
        m = re.search(r"lavfi\.signalstats\.(YAVG|UAVG|VAVG)=([0-9.]+)", line)
        if m:
            acc[m.group(1)] += float(m.group(2))
            counts[m.group(1)] += 1
    if not counts["YAVG"]:
        logger.warning("[color_grade] signalstats produced no YAVG rows for %s",
                       os.path.basename(video_path))
        return None
    return {
        "y_mean": acc["YAVG"] / counts["YAVG"],
        "u_mean": acc["UAVG"] / counts["UAVG"],
        "v_mean": acc["VAVG"] / counts["VAVG"],
    }


def _histogram_shift(h1: dict, h2: dict) -> float:
    dy = abs(h1["y_mean"] - h2["y_mean"]) / 255.0
    du = abs(h1["u_mean"] - h2["u_mean"]) / 255.0
    dv = abs(h1["v_mean"] - h2["v_mean"]) / 255.0
    return (dy + du + dv) / 3.0


def _grade_filter(measured: dict | None, target: dict, strength: float) -> str:
    """Filter chain that moves `measured` toward `target`. Extracted so it can be
    unit-tested without running ffmpeg, and so the maths is readable in one place.

    Brightness is a DELTA, not an absolute. The old form was
    `brightness = (target_y - 0.5) * 0.3`, which pins neutral at target 0.5 and
    can therefore only ever nudge: against measured Y=43 it derived +0.000. A
    grader that structurally cannot express "make this brighter" cannot fix
    video that is measurably too dark, which is exactly what we were shipping.

    `vibrance` rather than `eq=saturation`, because vibrance boosts the
    undersaturated colours and leaves already-saturated ones (skin) alone --
    the difference between "rich" and "orange".
    """
    meas_y = (measured or {}).get("y_mean", target.get("y_mean", 92.0))
    dy = (target["y_mean"] - meas_y) / 255.0
    if strength <= 0:
        # An honest no-op. Returning the curve anyway would mean the dial lied:
        # brightness and vibrance scale to zero but `curves` does not, so
        # "off" would still re-encode and still change the picture.
        return "null"
    # ponytail: clamped, not unbounded. ffmpeg `eq` brightness is asymmetric --
    # a large negative is a *cut*, and overshooting a lift flattens highlights
    # long before it rescues the shadows. 0.22 was calibrated against real
    # output (p50 43 -> 78) and is ~56 luma levels of headroom below clipping,
    # so there is room but it is not free. Raise it only on evidence from
    # measure_grade --histogram.
    brightness = max(-0.12, min(0.22, dy * 0.85)) * strength
    contrast = 1.0 + (0.06 * strength)
    vibrance = GRADE_VIBRANCE * strength
    if vibrance <= 0:
        # Omit the filter rather than passing intensity=0: the grade is luma and
        # curve only, and saying so in the command line keeps "why is this frame
        # not tinted" answerable from the log.
        return (f"eq=brightness={brightness:+.4f}:contrast={contrast:.3f},"
                f"curves=all='{GRADE_CURVES}'")
    return (f"eq=brightness={brightness:+.4f}:contrast={contrast:.3f},"
            f"curves=all='{GRADE_CURVES}',"
            f"vibrance=intensity={vibrance:.3f}")


def _apply_color_correction(source: str, output: str, target_hist: dict,
                            measured_hist: dict | None = None) -> bool:
    # Luma + a filmic curve + vibrance. eq cannot touch chroma, and forcing U/V
    # toward a brand hue is what makes AI footage look tinted and cheap -- the
    # brand is carried by the CTA/lower-third/watermark instead. The reference's
    # u_mean is still meaningful: _histogram_shift uses it to flag chroma drift.
    vf = _grade_filter(measured_hist, target_hist, GRADE_STRENGTH)
    cmd = [
        _ffmpeg_cmd(), "-y", "-i", source,
        "-vf", vf,
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
                    tier: str = "") -> Optional[str]:
    target = ASPECT_RATIOS.get(format_type, ASPECT_RATIOS["long"])
    tw, th = target["w"], target["h"]
    # Final master quality only. The per-scene encodes above deliberately stay on
    # CRF: they are re-encoded into this pass, so their quality is transient and
    # CRF is the safe value going in.
    final_crf = _final_crf(format_type)

    processed = []
    for i, clip in enumerate(clips):
        out = _process_clip(clip, tw, th, i, format_type, video_id)
        if out is None:
            continue
        processed.append(out)
        requested_dur = clip.get("duration", 8.0)
        actual_dur = _get_duration(out) or requested_dur
        if actual_dur < requested_dur - 0.5:
            extended = str(TEMP_DIR / f"extended_{video_id}_{i:03d}.mp4")
            if _extend_clip(out, extended, requested_dur):
                processed[-1] = extended
                actual_dur = requested_dur
        elif actual_dur > requested_dur + 0.5:
            # A renderer that ignored target_duration and keeps the stale
            # `duration` emits one clip far longer than its slot. Nothing trimmed
            # it, so the concat overran the audio and `-shortest` silently chopped
            # the tail -- freezing whole videos on the first oversized clip.
            trimmed = str(TEMP_DIR / f"trimmed_{video_id}_{i:03d}.mp4")
            if trim_clip(out, trimmed, 0.0, requested_dur):
                processed[-1] = trimmed
                logger.warning(
                    "[compositor] Clip %d rendered %.1fs but was allotted %.1fs; trimmed. "
                    "Cause is a filter that expands frames: zoompan d=N turns every INPUT "
                    "frame into N OUTPUT frames, so the OUTPUT needs its own -t. "
                    "Check resize_to_target / _apply_camera_motion for a missing -t.",
                    i, actual_dur, requested_dur)
                actual_dur = requested_dur
        clip["duration"] = actual_dur

    if not processed:
        print("[compositor] No clips to composite")
        return None

    # No fade-from-black on the first clip: it opened every video on a black screen
    # for half a second, delaying the visual the viewer came for. Start on frame 1.

    if ENABLE_COLOR_GRADING:
        grade_ref = DOCUMENTARY_YUV if tier == "documentary" else BRAND_YUV
        processed = _color_grade_scenes(processed, video_id, COLOR_GRADING_THRESHOLD, target_ref=grade_ref)

    combined_video = str(TEMP_DIR / f"combined_{video_id}.mp4")
    if len(processed) == 1:
        combined_video = processed[0]
    else:
        # Hard cuts. D39 removed the xfade path: every call site already passed
        # force_concat=True (the xfade else-branch was dead), the cross-dissolve
        # washed out every scene change, and concat is the cheaper, proven filter.
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
                    f"drawtext=text='{escaped}':fontsize=28:fontcolor={PURPLE}:box=1:boxcolor=black@0.4:"
                    f"boxborderw=6:x={x_expr}:y=h-130:enable='between(t\\,{ts}\\,{te})'"
                )

        # ponytail: no text overlays in the video body. This plus the
        # `callout` annotations in scene_parser used to burn extracted keyterms
        # onto the frame twice (large at top, small teal at bottom-left) and
        # both collided with the burned subtitle track. Removed 09-28 after the
        # owner reviewed real output. The only text on screen is now the
        # subtitle track + the CTA/midroll graphics below.

        # Annotations — callouts, steps, definitions, arrows, highlights, counters
        if os.getenv("ENABLE_ANNOTATIONS", "true").lower() == "true":
            ann_filters = build_annotation_filters(scenes, clips, tw, th)
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
                f"drawtext=text='Subscribe for more':fontsize=28:fontcolor={ORANGE}:"
                f"box=1:boxcolor=black@0.7:boxborderw=10:"
                f"x={cta_x}:y=h*0.75:enable='between(t\\,{cta_time}\\,{cta_end})'"
            )

        # End LIKE CTA: "LIKE if this helped" pill in the final seconds before outro.
        if os.getenv("ENABLE_LIKE_CTA", "true").lower() != "false":
            total_dur = sum(c.get("duration", 8.0) for c in clips) if clips else 120
            like_start = max(0.0, total_dur - 4.0)
            like_end = total_dur - 0.2
            like_alpha = (
                f"if(lt(t\\,{like_start}+0.5)\\,(t-{like_start})/0.5\\,"
                f"if(gte(t\\,{like_end}-0.5)\\,({like_end}-t)/0.5\\,1))"
            )
            like_text = "LIKE if this helped!"
            like_escaped = like_text.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
            vf_parts.append(
                f"drawtext=text='{like_escaped}':fontsize=30:fontcolor=white:"
                f"box=1:boxcolor={VIOLET}@0.8:boxborderw=10:"
                f"x=(w-text_w)/2:y=h*0.70:alpha={like_alpha}:"
                f"text_align=C:enable='between(t\\,{like_start}\\,{like_end})'"
            )

    if subtitle_path and os.path.exists(subtitle_path) and _subs_enabled_for(format_type):
        abs_sub = os.path.abspath(subtitle_path)
        is_deep = category in (_DEEP_LESSON_CATS if _DEEP_LESSON_CATS else set())
        is_doc = tier == "documentary"
        if is_doc:
            sub_fs = 24
            margin_v = 60
            sub_primary = SUBTITLE_ASS
            sub_outline = "&H00000000&"
            sub_border = SUBTITLE_OUTLINE_ASS
            has_outline = 2
        elif is_deep:
            sub_fs = 26
            margin_v = 90
            sub_primary = SUBTITLE_ASS
            sub_outline = SUBTITLE_OUTLINE_ASS
            has_outline = 1
        elif format_type == "shorts":
            sub_fs = 28
            margin_v = 60
            sub_primary = SUBTITLE_ASS
            sub_outline = SUBTITLE_OUTLINE_ASS
            has_outline = 1
        else:
            # Long-form default. Was 24 with a hairline outline, which the owner
            # reviewed on real 1920x1080 output and called not properly
            # subtitled. 34 + a 2px outline keeps it readable on a phone without
            # crowding a wider frame.
            sub_fs = 34
            margin_v = 80
            sub_primary = SUBTITLE_ASS
            sub_outline = SUBTITLE_OUTLINE_ASS
            has_outline = 2
        vf_parts.append(
            f"subtitles=filename='{abs_sub}':force_style="
            f"{_subtitle_style_escaped(sub_fs, margin_v, sub_primary, sub_outline, has_outline=has_outline)}"
        )

    vf_filter = ",".join(vf_parts)

    # Audio is authoritative. `-shortest` below trims to it, but it used to hide
    # a 4.7x visual overrun: the output looked fine and the tail was simply gone.
    # Auto-trim and publish, but say so loudly -- silence is what let a frozen
    # video ship to YouTube.
    _vis = _get_duration(combined_video) or 0.0
    _aud = _get_duration(mixed_audio) or 0.0
    if _vis > 0 and _aud > 0:
        _drift = (_vis - _aud) / _aud
        if abs(_drift) > 0.10:
            msg = (f"[compositor] Duration drift {f'{_drift:+.0%}':>5} "
                   f"(visual {_vis:.1f}s vs audio {_aud:.1f}s) for {video_id}; "
                   f"auto-trimming to audio.")
            logger.warning(msg)
            print(msg, flush=True)
            try:  # lazy: keeps Firestore out of the hot path when there is no drift
                from utils.firebase_status import log_activity
                log_activity("editor", msg.lstrip("[compositor] "), "warn")
            except Exception:
                pass

    cmd = [
        _ffmpeg_cmd(), "-y", "-i", combined_video, "-i", mixed_audio, *_sws_flags(),
    ]
    cmd += ["-vf", vf_filter] if vf_filter else []
    cmd += [
        "-c:v", "libx264", "-preset", PRESET, "-crf", final_crf,
        "-r", str(OUTPUT_FPS),
        "-af", "acompressor=threshold=-24dB:ratio=2:attack=5:release=50,"
               "loudnorm=I=-14:LRA=11:TP=-1,"
               "alimiter=limit=-1.5dB:attack=0.1:release=1,"
               "firequalizer=gain='if(between(f,5500,7000), -3, if(gt(f,9000), -2, 0))'",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest", "-pix_fmt", "yuv420p", final_path,
    ]
    try:
        logger.info(f"Final mux cmd: {' '.join(str(a) for a in cmd)}")
        result = safe_run(cmd, timeout=300)
        if result.returncode == 0 and os.path.exists(final_path):
            logger.info(f"Final video: {final_path} ({os.path.getsize(final_path)} bytes)")
            # ponytail: hard trim safety net for shorts — enforce max duration
            if format_type == "shorts":
                _max_s = int(os.getenv("SHORTS_MAX_DURATION", "120"))
                _dur = _get_duration(final_path)
                if _dur and _dur > _max_s + 1:  # +1s tolerance
                    _trimmed = final_path.replace(".mp4", "_trimmed.mp4")
                    _tcmd = [_ffmpeg_cmd(), "-y", "-i", final_path, "-t", str(_max_s),
                              "-c:v", "copy", "-c:a", "copy", _trimmed]
                    _tres = safe_run(_tcmd, timeout=30)
                    if _tres.returncode == 0 and os.path.exists(_trimmed):
                        os.replace(_trimmed, final_path)
                        print(f"[compositor] Trimmed from {_dur:.1f}s to {_max_s}s")
            from utils.upscaler import upscale_video, is_available
            upscaled = final_path.replace(".mp4", "_2x.mp4")
            if is_available() and upscale_video(final_path, upscaled, scale=2):
                print(f"[compositor] Upscaled: {upscaled}")
                os.replace(upscaled, final_path)
                print(f"[compositor] Replaced original with upscaled: {final_path}")
            return final_path
        logger.error(f"Final mux rc={result.returncode}, stderr: {result.stderr[-500:]}")
    except Exception as e:
        logger.error(f"Final mux error: {e}")
    return None
