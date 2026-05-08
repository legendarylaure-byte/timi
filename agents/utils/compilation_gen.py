import os
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

COMPILATION_DIR = Path(__file__).parent.parent / "output" / "compilations"
COMPILATION_DIR.mkdir(parents=True, exist_ok=True)

TEMP_DIR = Path(__file__).parent.parent / "tmp" / "compilation"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def create_compilation(
    video_paths: list[str],
    titles: list[str],
    output_filename: Optional[str] = None,
    intro_text: str = "",
    outro_text: str = "",
    target_format: str = "long",
) -> dict:
    if not video_paths:
        return {"success": False, "error": "No video paths provided"}

    processed_paths = []
    chapter_markers = []
    current_time = 0.0

    for i, video_path in enumerate(video_paths):
        if not os.path.exists(video_path):
            print(f"[compilation] Skipping missing file: {video_path}")
            continue

        clip_duration = _get_duration(video_path)
        if clip_duration <= 0:
            continue

        trimmed_path = str(TEMP_DIR / f"comp_clip_{i:03d}.mp4")
        if _ensure_format(video_path, trimmed_path, target_format):
            processed_paths.append(trimmed_path)
            chapter_markers.append({
                "start_time": current_time,
                "end_time": current_time + clip_duration,
                "title": titles[i] if i < len(titles) else f"Clip {i+1}",
            })
            current_time += clip_duration + 0.5

    if not processed_paths:
        return {"success": False, "error": "No valid videos to compile"}

    concat_list = str(TEMP_DIR / "compilation_concat.txt")
    with open(concat_list, "w") as f:
        for i, path in enumerate(processed_paths):
            f.write(f"file '{path}'\n")
            if i < len(processed_paths) - 1:
                f.write(f"file '{_generate_transition(TEMP_DIR, i)}'\n" if _generate_transition(TEMP_DIR, i) else "")

    if output_filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"compilation_{timestamp}.mp4"

    output_path = str(COMPILATION_DIR / output_filename)
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list,
           "-c:v", "libx264", "-preset", "fast", "-crf", "23",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", output_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and os.path.exists(output_path):
            duration = _get_duration(output_path)
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"[compilation] Created: {output_path} ({duration:.1f}s, {size_mb:.1f}MB)")
            return {
                "success": True,
                "path": output_path,
                "duration": duration,
                "size_mb": round(size_mb, 1),
                "clips_count": len(processed_paths),
                "chapters": chapter_markers,
                "is_above_8min": duration >= 480,
            }
        else:
            print(f"[compilation] FFmpeg error: {result.stderr[-300:]}")
            return {"success": False, "error": "FFmpeg concatenation failed"}
    except Exception as e:
        print(f"[compilation] Error: {e}")
        return {"success": False, "error": str(e)}


def _get_duration(file_path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", file_path],
            capture_output=True, text=True, timeout=10
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _ensure_format(input_path: str, output_path: str, target_format: str) -> bool:
    target = {"long": ("1920", "1080"), "shorts": ("1080", "1920")}
    w, h = target.get(target_format, ("1920", "1080"))
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p", output_path,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=120).returncode == 0
    except Exception:
        return False


def _generate_transition(temp_dir: Path, idx: int) -> str:
    transition_path = str(temp_dir / f"transition_{idx:03d}.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:d=0.5",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p", "-an", transition_path,
    ]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if os.path.exists(transition_path):
            return transition_path
    except Exception:
        pass
    return ""


def create_compilation_from_shorts(
    shorts_data: list[dict],
    category: str,
    title: str = "",
    min_duration_seconds: int = 480,
) -> dict:
    eligible = [s for s in shorts_data if os.path.exists(s.get("path", ""))]

    if not eligible:
        return {"success": False, "error": "No valid shorts found"}

    eligible.sort(key=lambda s: s.get("views", 0), reverse=True)

    total_duration = 0
    selected = []
    selected_titles = []
    for short in eligible:
        if total_duration >= min_duration_seconds:
            break
        selected.append(short["path"])
        selected_titles.append(short.get("title", f"Clip {len(selected)}"))
        total_duration += short.get("duration", 30)

    if not selected:
        return {"success": False, "error": "Could not select enough clips"}

    if not title:
        title = f"Best {category} Compilation - {datetime.now().strftime('%B %Y')}"

    intro_text = f"Welcome to {category}!"
    outro_text = "Thanks for watching! Subscribe for more!"

    return create_compilation(
        video_paths=selected,
        titles=selected_titles,
        intro_text=intro_text,
        outro_text=outro_text,
        target_format="long",
    )
