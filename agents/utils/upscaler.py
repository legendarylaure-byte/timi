import os
import subprocess
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

UPSCALER_BIN = os.getenv("UPSCALER_BIN", os.path.expanduser("~/timi/agents/bin/realesrgan-ncnn-vulkan"))
UPSCALER_MODEL = os.getenv("UPSCALER_MODEL", "realesrgan-x4plus")
UPSCALER_MODEL_DIR = os.getenv("UPSCALER_MODEL_DIR", os.path.expanduser("~/timi/agents/bin"))
UPSCALE_ENABLED = os.getenv("ENABLE_UPSCALE", "false").lower() == "true"
TEMP_DIR = Path(__file__).parent.parent / "tmp" / "upscaler"


def is_available() -> bool:
    if not UPSCALE_ENABLED:
        return False
    return os.path.exists(UPSCALER_BIN)


def upscale_frame(input_path: str, output_path: str, scale: int = 4) -> bool:
    cmd = [
        UPSCALER_BIN,
        "-i", input_path,
        "-o", output_path,
        "-s", str(scale),
        "-n", UPSCALER_MODEL,
        "-m", UPSCALER_MODEL_DIR,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        if result.returncode != 0:
            logger.warning("upscale frame failed (rc=%d): %s", result.returncode, result.stderr[:200])
    except Exception as e:
        logger.warning("upscale frame error: %s", e)
    return False


def upscale_video(input_path: str, output_path: str, scale: int = 2) -> bool:
    if not is_available():
        return False
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    frames_dir = str(TEMP_DIR / "frames_in")
    upscaled_dir = str(TEMP_DIR / "frames_out")
    os.makedirs(frames_dir, exist_ok=True)
    os.makedirs(upscaled_dir, exist_ok=True)

    try:
        extract = [
            "ffmpeg", "-y", "-i", input_path,
            "-qscale:v", "1", "-qmin", "1", "-qmax", "1",
            os.path.join(frames_dir, "frame_%06d.png"),
        ]
        if subprocess.run(extract, capture_output=True, text=True, timeout=120).returncode != 0:
            logger.warning("upscale video: frame extraction failed")
            return False

        for f in sorted(os.listdir(frames_dir)):
            if f.endswith(".png"):
                inp = os.path.join(frames_dir, f)
                out = os.path.join(upscaled_dir, f)
                if not upscale_frame(inp, out, scale):
                    logger.warning("upscale video: frame %s failed", f)
                    return False

        reencode = [
            "ffmpeg", "-y", "-i", os.path.join(upscaled_dir, "frame_%06d.png"),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", output_path,
        ]
        if subprocess.run(reencode, capture_output=True, text=True, timeout=120).returncode != 0:
            logger.warning("upscale video: re-encode failed")
            return False

        return os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception as e:
        logger.warning("upscale video error: %s", e)
        return False
    finally:
        import shutil
        for d in [frames_dir, upscaled_dir]:
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
