import os
import json
import logging
import shutil
import tempfile
from pathlib import Path
from utils.subprocess_helper import register_temp_dir, safe_run_bool
from utils.video_compositor import _subtitle_style_escaped

logger = logging.getLogger(__name__)

_TEMP_DIR = None
OUTPUT_DIR = Path(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "repurposed"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _get_temp_dir() -> Path:
    global _TEMP_DIR
    if _TEMP_DIR is None:
        _TEMP_DIR = Path(tempfile.mkdtemp(prefix="shorts_render_"))
        register_temp_dir(str(_TEMP_DIR))
    return _TEMP_DIR


def _ffmpeg_cmd() -> str:
    return os.getenv("FFMPEG_PATH", "ffmpeg")


def _ffprobe_cmd() -> str:
    return os.getenv("FFPROBE_PATH", "ffprobe")


def _sws_flags() -> list[str]:
    return ["-sws_flags", "lanczos+accurate_rnd"]


def compute_scene_timestamps(scenes: list[dict]) -> list[dict]:
    current = 0.0
    result = []
    for i, scene in enumerate(scenes):
        dur = scene.get("duration", scene.get("target_duration", 8.0))
        result.append({
            "index": i,
            "start": current,
            "end": current + dur,
            "duration": dur,
            "keyword": scene.get("keyword") or (scene.get("asset_keywords") or [None])[0] or scene.get("description", "") or "",
        })
        current += dur
    return result


def _find_scenes_for_times(scene_timestamps: list[dict], start_sec: float, end_sec: float) -> list[str]:
    keywords = []
    for st in scene_timestamps:
        if st["start"] < end_sec and st["end"] > start_sec:
            if st["keyword"]:
                keywords.append(st["keyword"])
    return keywords


def chop_segment(input_video: str, start_sec: float, duration: float, output_path: str) -> bool:
    cmd = [
        _ffmpeg_cmd(), "-y",
        "-ss", str(start_sec),
        "-i", input_video,
        "-t", str(duration),
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    if not safe_run_bool(cmd, timeout=120):
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def reformat_to_shorts(input_path: str, hook_text: str, output_path: str,
                       subtitle_path: str | None = None,
                       clip_duration: float = 60.0) -> bool:
    target_w, target_h = 1080, 1920

    scale_filter = (
        f"scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=decrease,"
        f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black@0,"
        f"split[main][bg];"
        f"[bg]scale={target_w}:{target_h}:flags=lanczos:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},boxblur=20:5[bg];"
        f"[bg][main]overlay=(W-w)/2:(H-h)/2"
    )

    hook_escaped = hook_text.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
    hook_duration = 2.0
    hook_filter = (
        f"drawtext=text='{hook_escaped}':"
        f"fontsize=42:fontcolor=white:box=1:boxcolor=black@0.5:"
        f"x=(w-text_w)/2:y=h*0.15:"
        f"alpha=if(lt(t\\,{hook_duration})\\,t/{hook_duration}\\,1):"
        f"fontfile={os.getenv('FONT_PATH', '/System/Library/Fonts/Helvetica.ttc')}"
    )

    cta_start = max(0, clip_duration - 4.0)
    cta_text = "Subscribe for more \\nAI content"
    cta_escaped = cta_text.replace("'", "\u2019").replace(":", "\\:").replace("-", "\\-")
    cta_filter = (
        f"drawtext=text='{cta_escaped}':"
        f"fontsize=38:fontcolor=white:box=1:boxcolor=#8a50e8@0.7:"
        f"x=(w-text_w)/2:y=(h-text_h)/2:"
        f"alpha=if(lt(t\\,{cta_start + 1})\\,0\\,if(lt(t\\,{cta_start + 3})\\,(t-{cta_start})/2\\,1)):"
        f"fontfile={os.getenv('FONT_PATH', '/System/Library/Fonts/Helvetica.ttc')}:"
        f"text_align=C:line_spacing=8"
    )

    quality_filters = "eq=saturation=1.25:contrast=1.1,unsharp=5:5:0.8:3:3:0.4"

    subtitle_filter = ""
    if subtitle_path and os.path.exists(subtitle_path):
        abs_sub = os.path.abspath(subtitle_path)
        subtitle_filter = (
            f",subtitles=filename='{abs_sub}':force_style="
            f"{_subtitle_style_escaped(28, primary='&H000088CC&')}"
        )

    vf = f"{scale_filter},{hook_filter},{cta_filter},{quality_filters}{subtitle_filter}"

    cmd = [
        _ffmpeg_cmd(), "-y", "-i", input_path,
        *_sws_flags(),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "17",
        "-r", "24",
        "-af", "acompressor=threshold=-24dB:ratio=2:attack=5:release=50,"
               "loudnorm=I=-14:LRA=11:TP=-1,"
               "alimiter=limit=-1.5dB:attack=0.1:release=1",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-pix_fmt", "yuv420p", output_path,
    ]
    if not safe_run_bool(cmd, timeout=300):
        return False
    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def _generate_segment_subtitles(phrase_timings: list[dict], start_ms: float, end_ms: float,
                                 output_srt: str) -> str | None:
    import re
    segments_in_range = []
    for pt in phrase_timings:
        pt_start = pt.get("start_ms", 0)
        pt_end = pt.get("end_ms", 0)
        if pt_start >= start_ms and pt_end <= end_ms:
            segments_in_range.append(pt)
        elif pt_start < end_ms and pt_end > start_ms:
            segments_in_range.append({
                "text": pt.get("text", ""),
                "start_ms": max(pt_start, start_ms) - start_ms,
                "end_ms": min(pt_end, end_ms) - start_ms,
            })

    if not segments_in_range:
        return None

    def _ms_to_srt(ms: float) -> str:
        h = int(ms // 3600000)
        m = int((ms % 3600000) // 60000)
        s = int((ms % 60000) // 1000)
        ml = int(ms % 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ml:03d}"

    lines = []
    for i, seg in enumerate(segments_in_range):
        lines.append(str(i + 1))
        lines.append(f"{_ms_to_srt(seg['start_ms'])} --> {_ms_to_srt(seg['end_ms'])}")
        lines.append(seg["text"])
        lines.append("")

    with open(output_srt, "w") as f:
        f.write("\n".join(lines))
    return output_srt


def _generate_hook_from_keywords(keywords: list[str]) -> str:
    if not keywords:
        return "This is how it works \U0001f525"
    primary = keywords[0].strip()
    if len(primary) > 50:
        primary = " ".join(primary.split()[:7])
    hooks = [
        f"{primary} \u2014 explained",
        f"How {primary} works",
        f"{primary} \U0001f525",
        f"You won't believe how {primary.lower()} works",
    ]
    import random
    return random.choice(hooks)


def render_repurposed_shorts(long_video_path: str, scenes: list[dict],
                              phrase_timings: list[dict], category: str,
                              video_id: str, script_text: str = "") -> list[dict]:
    import utils.shorts_renderer as _sr
    from utils.thumbnail_gen import generate_thumbnail_variants

    scene_timestamps = compute_scene_timestamps(scenes)
    total_duration = scene_timestamps[-1]["end"] if scene_timestamps else 180.0

    clip_count = min(3, max(1, int(total_duration // 60)))
    segment_duration = total_duration / clip_count

    results = []
    for i in range(clip_count):
        start = segment_duration * i + 5
        end = segment_duration * (i + 1)
        if i == clip_count - 1:
            end = total_duration - 2
        clip_dur = end - start
        if clip_dur < 20:
            continue

        keywords = _find_scenes_for_times(scene_timestamps, start, end)
        hook = _generate_hook_from_keywords(keywords)

        clip_id = f"{video_id}_short_{i+1}"
        temp_dir = _get_temp_dir()
        chopped = str(temp_dir / f"{clip_id}_chopped.mp4")
        reformatted = str(OUTPUT_DIR / f"{clip_id}.mp4")

        if not chop_segment(long_video_path, start, clip_dur, chopped):
            logger.warning("Failed to chop segment %d for %s", i, video_id)
            continue

        srt_path = None
        if phrase_timings:
            srt_path = str(temp_dir / f"{clip_id}.srt")
            _generate_segment_subtitles(phrase_timings, start * 1000, end * 1000, srt_path)
            if not os.path.exists(srt_path):
                srt_path = None

        if not reformat_to_shorts(chopped, hook, reformatted, subtitle_path=srt_path, clip_duration=clip_dur):
            logger.warning("Failed to reformat segment %d for %s", i, video_id)
            continue

        thumb_result = generate_thumbnail_variants(topic=hook, thumbnail_text=hook, format_type="shorts")
        thumb_path = thumb_result.get("best", "")

        results.append({
            "clip_id": clip_id,
            "video_path": reformatted,
            "thumbnail_path": thumb_path,
            "title": hook,
            "start_time": start,
            "end_time": end,
            "duration": clip_dur,
            "keywords": keywords,
            "hook": hook,
        })
        logger.info("Repurposed short %d/%d: %s (%.0fs-%.0fs)", i + 1, clip_count, hook, start, end)

    if _sr._TEMP_DIR is not None:
        try:
            shutil.rmtree(str(_sr._TEMP_DIR), ignore_errors=True)
            _sr._TEMP_DIR = None
        except Exception:
            logger.warning("Failed to clean up temp dir")

    return results
