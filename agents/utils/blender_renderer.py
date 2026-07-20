import os
import sys
import json
import hashlib
import shutil
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

BLENDER_CACHE_DIR = Path(__file__).parent.parent / "tmp" / "blender_cache"
BLENDER_RENDER_DIR = Path(__file__).parent.parent / "tmp" / "blender_render"
os.makedirs(BLENDER_CACHE_DIR, exist_ok=True)
os.makedirs(BLENDER_RENDER_DIR, exist_ok=True)

from utils.subprocess_helper import register_temp_dir, safe_run, retry_with_backoff
register_temp_dir(str(BLENDER_RENDER_DIR))

TEMPLATE_DIR = Path(__file__).parent.parent / "blender_templates"


def _find_blender():
    blender = shutil.which("blender")
    if blender:
        return blender
    for candidate in ["/Applications/Blender.app/Contents/MacOS/blender",
                       "/usr/bin/blender", "/usr/local/bin/blender"]:
        if os.path.exists(candidate):
            return candidate
    return None


BLENDER_BIN = _find_blender()

if BLENDER_BIN:
    logger.info(f"[Blender] Using: {BLENDER_BIN}")
else:
    logger.warning("[Blender] No Blender binary found — Blender scenes will fall through to stock/LTX")


def _samples_for_format(format_type: str, tier: str = "") -> int:
    if tier == "documentary":
        return int(os.getenv("BLENDER_RENDER_SAMPLES_DOC", "256"))
    if format_type == "shorts":
        return int(os.getenv("BLENDER_RENDER_SAMPLES_SHORT", "64"))
    return int(os.getenv("BLENDER_RENDER_SAMPLES_LONG", "128"))


def _engine_for_template(template_name: str, format_type: str) -> str:
    from blender_templates import TEMPLATE_REGISTRY
    info = TEMPLATE_REGISTRY.get(template_name, {})
    preferred = info.get("engine", "eevee")
    if format_type == "shorts" and preferred == "cycles":
        return "cycles"
    if format_type == "shorts":
        return "eevee"
    return preferred


def _cache_key(template_name: str, params: dict) -> str:
    raw = template_name + json.dumps(params, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def render_blender_scene(scene: dict, video_id: str, scene_idx: int,
                          format_type: str = "long", tier: str = "",
                          quality: str = "h") -> str | None:
    if not BLENDER_BIN:
        logger.warning("[Blender] No binary — skipping scene")
        return None

    description = scene.get("description", "")
    render_type = scene.get("render_type", "")
    duration = scene.get("duration", 5.0)
    category = scene.get("category", "")

    from blender_templates import select_template
    template_name, engine, confidence = select_template(description, category)

    if not template_name or confidence < 0.3:
        logger.info(f"[Blender] No template matched (confidence={confidence:.2f}) — skipping")
        return None

    params = _build_params(scene, template_name, duration)
    ckey = _cache_key(template_name, params)
    cached = BLENDER_CACHE_DIR / f"{ckey}.mp4"
    if cached.exists() and os.path.getsize(cached) > 10000:
        logger.info(f"[Blender] Cache hit: {cached}")
        return str(cached)

    engine = _engine_for_template(template_name, format_type)
    samples = _samples_for_format(format_type, tier)

    template_py = TEMPLATE_DIR / f"{template_name}.py"
    if not template_py.exists():
        logger.warning(f"[Blender] Template not found: {template_py}")
        return None

    output_dir = BLENDER_RENDER_DIR / f"{video_id}_{scene_idx}"
    os.makedirs(str(output_dir), exist_ok=True)

    params.update({"duration": duration, "fps": 24, "samples": samples, "engine": engine})
    params["_output"] = str(output_dir)
    params_path = BLENDER_RENDER_DIR / f"params_{video_id}_{scene_idx}.json"
    with open(params_path, "w") as f:
        json.dump(params, f)

    cmd = [
        BLENDER_BIN, "--background", "--python", str(template_py), "--",
        "--params", str(params_path),
        "--output", str(output_dir / "frame_"),
    ]
    logger.info(f"[Blender] Rendering scene {scene_idx}: {template_name} ({engine}, {samples}smp)")

    try:
        result = safe_run(cmd, timeout=3600, capture_output=True)
        if result.returncode != 0:
            logger.warning(f"[Blender] Render failed (code {result.returncode})")
            return None
    except Exception as e:
        logger.warning(f"[Blender] Render exception: {e}")
        return None

    mp4_path = _assemble_frames(str(output_dir), video_id, scene_idx, duration)
    if mp4_path and os.path.getsize(mp4_path) > 10000:
        shutil.copy2(mp4_path, str(cached))
        logger.info(f"[Blender] Scene {scene_idx} rendered → {mp4_path}")
        return mp4_path

    logger.warning(f"[Blender] Output validation failed for scene {scene_idx}")
    return None


def _build_params(scene: dict, template_name: str, duration: float) -> dict:
    desc = scene.get("description", "")
    text_blocks = scene.get("text", [])
    title_text = text_blocks[0].get("text", "") if text_blocks else desc[:60]
    narration = scene.get("narration_text", "") or ""

    params = {
        "title": title_text[:80],
        "duration": duration,
        "narration": narration[:200],
    }
    return params


def _assemble_frames(frame_dir: str, video_id: str, scene_idx: int, duration: float) -> str | None:
    import glob
    frames = sorted(glob.glob(os.path.join(frame_dir, "frame_*.png")))
    if not frames:
        return None
    output = BLENDER_RENDER_DIR / f"{video_id}_{scene_idx}.mp4"
    fps = 24
    input_pattern = os.path.join(frame_dir, "frame_%04d.png")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps), "-i", input_pattern,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        str(output),
    ]
    try:
        r = safe_run(cmd, timeout=300, capture_output=True)
        if r.returncode == 0:
            return str(output) if output.exists() else None
    except Exception as e:
        logger.warning(f"[Blender] Frame assembly failed: {e}")
        import glob as g
        fallback_frames = sorted(g.glob(os.path.join(frame_dir, "frame_*.png")))
        if len(fallback_frames) < 2:
            return None
        fallback_out = BLENDER_RENDER_DIR / f"{video_id}_{scene_idx}_fallback.mp4"
        fc = [
            "ffmpeg", "-y", "-framerate", str(fps), "-i", input_pattern,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-r", str(fps), str(fallback_out),
        ]
        try:
            r2 = safe_run(fc, timeout=300, capture_output=True)
            return str(fallback_out) if r2.returncode == 0 and fallback_out.exists() else None
        except Exception:
            return None


def render_blender_block(scenes: list[dict], video_id: str,
                          format_type: str = "long", tier: str = "") -> str | None:
    clips = []
    for i, scene in enumerate(scenes):
        path = render_blender_scene(scene, video_id, i, format_type, tier)
        if path:
            clips.append(path)
    if not clips:
        return None
    concat_path = BLENDER_RENDER_DIR / f"blender_block_{video_id}.mp4"
    concat_file = BLENDER_RENDER_DIR / f"concat_{video_id}.txt"
    with open(concat_file, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", str(concat_path),
    ]
    try:
        r = safe_run(cmd, timeout=600, capture_output=True)
        return str(concat_path) if r.returncode == 0 and concat_path.exists() else None
    except Exception as e:
        logger.warning(f"[Blender] Block concat failed: {e}")
        return None
