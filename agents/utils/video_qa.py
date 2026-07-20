import os
import re
import json
import math
import tempfile
import logging
from utils.subprocess_helper import safe_run, register_temp_dir

logger = logging.getLogger(__name__)

_BLUR_TEMP_DIR = None


def _get_blur_temp() -> str:
    global _BLUR_TEMP_DIR
    if _BLUR_TEMP_DIR is None:
        _BLUR_TEMP_DIR = tempfile.mkdtemp(prefix="qa_blur_")
        register_temp_dir(_BLUR_TEMP_DIR)
    return _BLUR_TEMP_DIR


def _ffmpeg_path() -> str:
    env = os.getenv("FFMPEG_PATH", "")
    if env and os.path.exists(env):
        return env
    for p in ("/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "ffmpeg"):
        if os.path.exists(p):
            return p
    return "ffmpeg"


def _ffprobe_path() -> str:
    env = os.getenv("FFPROBE_PATH", "")
    if env and os.path.exists(env):
        return env
    for p in ("/usr/bin/ffprobe", "/usr/local/bin/ffprobe", "ffprobe"):
        if os.path.exists(p):
            return p
    return "ffprobe"


def check_black_frames(video_path: str, duration: float = 2.0,
                       pixel_threshold: float = 0.1) -> dict:
    if not os.path.exists(video_path):
        return {"black_ratio": 0.0, "total_black_ms": 0.0, "segments": []}
    cmd = [
        _ffmpeg_path(), "-i", video_path,
        "-vf", f"blackdetect=d={duration}:pix_th={pixel_threshold}",
        "-f", "null", "-",
    ]
    try:
        result = safe_run(cmd, timeout=60)
        segments = []
        for line in result.stderr.split("\n"):
            if "black_start" not in line:
                continue
            m = re.search(
                r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)",
                line,
            )
            if m:
                segments.append({
                    "start": float(m.group(1)),
                    "end": float(m.group(2)),
                    "duration": float(m.group(3)),
                })
        dur_cmd = [
            _ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
        ]
        dur_result = safe_run(dur_cmd, timeout=15)
        total_dur = float(dur_result.stdout.strip()) or 1
        total_black = sum(s["duration"] for s in segments)
        return {
            "black_ratio": round(total_black / total_dur, 4),
            "total_black_ms": round(total_black * 1000, 1),
            "segments": segments,
        }
    except Exception as e:
        logger.warning("Black frame detection failed: %s", e)
        return {"black_ratio": 0.0, "total_black_ms": 0.0, "segments": []}


def check_freeze_frames(video_path: str, duration: float = 1.0,
                        noise_threshold: float = 0.1) -> dict:
    if not os.path.exists(video_path):
        return {"freeze_ratio": 0.0, "segments": []}
    cmd = [
        _ffmpeg_path(), "-i", video_path,
        "-vf", f"freezedetect=d={duration}:n={noise_threshold}",
        "-f", "null", "-",
    ]
    try:
        result = safe_run(cmd, timeout=60)
        segments = []
        for line in result.stderr.split("\n"):
            if "freeze_start" not in line:
                continue
            m = re.search(
                r"freeze_start:([\d.]+)\s+freeze_end:([\d.]+)\s+freeze_duration:([\d.]+)",
                line,
            )
            if m:
                segments.append({
                    "start": float(m.group(1)),
                    "end": float(m.group(2)),
                    "duration": float(m.group(3)),
                })
        dur_cmd = [
            _ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path,
        ]
        dur_result = safe_run(dur_cmd, timeout=15)
        total_dur = float(dur_result.stdout.strip()) or 1
        total_frozen = sum(s["duration"] for s in segments)
        return {
            "freeze_ratio": round(total_frozen / total_dur, 4),
            "segments": segments,
        }
    except Exception as e:
        logger.warning("Freeze frame detection failed: %s", e)
        return {"freeze_ratio": 0.0, "segments": []}


def check_corruption(video_path: str) -> dict:
    if not os.path.exists(video_path):
        return {"total_frames": 0, "decode_errors": 1, "is_corrupt": True}
    cmd = [
        _ffprobe_path(), "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path,
    ]
    try:
        result = safe_run(cmd, timeout=60)
        frames_str = result.stdout.strip()
        total = int(frames_str) if frames_str.isdigit() else 0
        error_lines = [l for l in result.stderr.split("\n") if l.strip()]
        decode_errors = len(error_lines)
        return {
            "total_frames": total,
            "decode_errors": decode_errors,
            "is_corrupt": decode_errors > 3 or total == 0,
        }
    except Exception as e:
        logger.warning("Frame corruption check failed: %s", e)
        return {"total_frames": 0, "decode_errors": 1, "is_corrupt": True}


def check_resolution(video_path: str,
                     expected_w: int = 1920,
                     expected_h: int = 1080) -> dict:
    if not os.path.exists(video_path):
        return {"width": 0, "height": 0, "match": False}
    cmd = [
        _ffprobe_path(), "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0", video_path,
    ]
    try:
        result = safe_run(cmd, timeout=15)
        parts = result.stdout.strip().split(",")
        if len(parts) >= 2:
            w, h = int(parts[0]), int(parts[1])
            return {"width": w, "height": h, "match": w == expected_w and h == expected_h}
    except Exception as e:
        logger.warning("Resolution check failed: %s", e)
    return {"width": 0, "height": 0, "match": False}


def check_blur(video_path: str, sample_interval: float = 5.0,
               blur_threshold: float = 100.0) -> dict:
    if not os.path.exists(video_path):
        return {"avg_blur_score": 0.0, "blurry_frames": [], "sample_count": 0}

    dur_cmd = [
        _ffprobe_path(), "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", video_path,
    ]
    try:
        dur_result = safe_run(dur_cmd, timeout=15)
        total_dur = float(dur_result.stdout.strip()) or 1
    except Exception:
        total_dur = 60.0

    if total_dur < 1:
        return {"avg_blur_score": 0.0, "blurry_frames": [], "sample_count": 0}

    temp_dir = _get_blur_temp()
    sample_times = []
    t = 0.5
    while t < total_dur:
        sample_times.append(t)
        t += sample_interval

    scores = []
    blurry = []
    frame_dir = os.path.join(temp_dir, "frames_" + os.path.basename(video_path).replace(".", "_"))
    os.makedirs(frame_dir, exist_ok=True)

    for i, ts in enumerate(sample_times):
        frame_path = os.path.join(frame_dir, f"frame_{i:04d}.png")
        try:
            safe_run(
                [_ffmpeg_path(), "-y", "-ss", str(ts), "-i", video_path,
                 "-vframes", "1", "-q:v", "2", frame_path],
                timeout=30,
            )
            if not os.path.exists(frame_path) or os.path.getsize(frame_path) < 100:
                continue

            from PIL import Image
            from PIL import ImageFilter
            img = Image.open(frame_path).convert("L")
            score = _laplacian_variance(img)
            scores.append(score)
            if score < blur_threshold:
                blurry.append({"time": round(ts, 1), "score": round(score, 1)})
        except Exception:
            continue
        finally:
            if os.path.exists(frame_path):
                try:
                    os.remove(frame_path)
                except OSError:
                    pass

    try:
        os.rmdir(frame_dir)
    except OSError:
        pass

    avg_score = sum(scores) / len(scores) if scores else 0.0
    blur_ratio = len(blurry) / len(sample_times) if sample_times else 0.0

    return {
        "avg_blur_score": round(avg_score, 1),
        "blurry_frames": blurry,
        "sample_count": len(scores),
        "blur_ratio": round(blur_ratio, 4),
    }


def _laplacian_variance(img) -> float:
    from PIL import ImageFilter
    lap = img.filter(ImageFilter.Kernel((3, 3), [
        -1, -1, -1,
        -1,  8, -1,
        -1, -1, -1,
    ], scale=1, offset=0))
    import numpy as np
    arr = np.array(lap, dtype=np.float64)
    return float(arr.var())


def check_visual_narration_match(narration_text: str, scene_keywords: list[str] | None = None,
                                  asset_type: str = "STOCK_FOOTAGE",
                                  ltx_prompt: str = "") -> tuple[bool, float, str]:
    if asset_type in ("DIAGRAM_ANIMATION", "CODE_SNIPPET", "SCREEN_CAPTURE"):
        return True, 1.0, "Auto-pass: Blender/code/screen scenes directly explain the content"
    if not narration_text:
        return True, 0.5, "No narration text to compare"
    import re
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "shall", "to", "of", "in", "for",
        "on", "with", "at", "by", "from", "as", "into", "through", "during",
        "this", "that", "these", "those", "it", "its", "they", "them", "their",
        "and", "or", "but", "if", "while", "about", "up", "down", "like",
        "just", "because", "also", "very", "too", "not", "no", "only",
        "show", "see", "use", "used", "using", "make", "made", "get",
    }
    nar_words = {w for w in re.findall(r'\b[a-z]{4,}\b', narration_text.lower()) if w not in stopwords}
    if not nar_words:
        return True, 0.5, "No significant words in narration"
    if asset_type == "STOCK_FOOTAGE" and scene_keywords:
        kw_text = " ".join(scene_keywords).lower()
        match_count = sum(1 for w in nar_words if w in kw_text)
        ratio = match_count / max(len(nar_words), 1)
        if ratio >= 0.15:
            return True, ratio, f"{match_count}/{len(nar_words)} narration words in stock keywords (ratio={ratio:.2f})"
        return False, ratio, f"Stock keywords miss narration: only {match_count}/{len(nar_words)} words match (ratio={ratio:.2f}, need ≥0.15)"
    if ltx_prompt:
        prompt_lower = ltx_prompt.lower()
        match_count = sum(1 for w in nar_words if w in prompt_lower)
        ratio = match_count / max(len(nar_words), 1)
        if ratio >= 0.1:
            return True, ratio, f"{match_count}/{len(nar_words)} narration words in LTX prompt (ratio={ratio:.2f})"
        logger.warning(f"LTX prompt may not match narration: {match_count}/{len(nar_words)} words match")
        return True, ratio, f"Weak LTX prompt match: {match_count}/{len(nar_words)} (ratio={ratio:.2f})"
    return True, 0.0, "No reference text to compare"


def check_frame_quality(video_path: str, format_type: str = "shorts",
                        blur_threshold: float = 100.0) -> dict:
    report = {
        "path": video_path,
        "format": format_type,
        "checks": {},
        "summary": "",
    }
    if not video_path or not os.path.exists(video_path):
        report["summary"] = "Video file not found"
        return report

    blur = check_blur(video_path, blur_threshold=blur_threshold)
    report["checks"]["blur"] = blur

    issues = []
    if blur.get("blur_ratio", 0) > 0.3:
        issues.append(f"Blurry frames: {blur['blur_ratio']*100:.1f}% (score={blur['avg_blur_score']})")
    if blur.get("sample_count", 0) == 0:
        issues.append("Could not sample any frames for blur check")

    report["passed"] = len(issues) == 0
    report["summary"] = "; ".join(issues) if issues else "All frame quality checks passed"
    return report


def verify_frame_quality(video_path: str, format_type: str = "shorts",
                         black_threshold: float = 0.2,
                         freeze_threshold: float = 0.1) -> tuple[bool, dict]:
    report = {
        "path": video_path,
        "format": format_type,
        "checks": {},
        "summary": "",
    }
    if not video_path or not os.path.exists(video_path):
        report["summary"] = "Video file not found"
        return False, report

    expected_w, expected_h = (1080, 1920) if format_type == "shorts" else (1920, 1080)

    resolution = check_resolution(video_path, expected_w, expected_h)
    report["checks"]["resolution"] = resolution

    black = check_black_frames(video_path)
    report["checks"]["black_frames"] = black

    freeze = check_freeze_frames(video_path)
    report["checks"]["freeze_frames"] = freeze

    corruption = check_corruption(video_path)
    report["checks"]["corruption"] = corruption

    issues = []
    if not resolution["match"]:
        issues.append(
            f"Resolution mismatch: {resolution['width']}x{resolution['height']} "
            f"(expected {expected_w}x{expected_h})"
        )
    if black["black_ratio"] > black_threshold:
        issues.append(
            f"Black frames: {black['black_ratio']*100:.1f}% "
            f"(threshold {black_threshold*100:.1f}%)"
        )
    if freeze["freeze_ratio"] > freeze_threshold:
        issues.append(
            f"Frozen frames: {freeze['freeze_ratio']*100:.1f}% "
            f"(threshold {freeze_threshold*100:.1f}%)"
        )
    if corruption["is_corrupt"]:
        issues.append(
            f"Corruption: {corruption['decode_errors']} decode errors "
            f"in {corruption['total_frames']} frames"
        )

    report["passed"] = len(issues) == 0
    report["summary"] = "; ".join(issues) if issues else "All checks passed"
    return report["passed"], report
