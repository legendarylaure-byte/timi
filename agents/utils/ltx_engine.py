import os
import sys
import time
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

LTX_MODEL_DIR = os.getenv("LTX_MODEL_DIR", os.path.expanduser("~/ltx-models"))
LTX_ENGINE = os.getenv("LTX_ENGINE", "mlx")
LTX_LOW_RAM = os.getenv("LTX_LOW_RAM", "true").lower() == "true"


def is_available() -> bool:
    if LTX_ENGINE == "disabled":
        return False
    model_path = Path(LTX_MODEL_DIR)
    if not model_path.exists():
        logger.warning("[LTX] Model dir not found: %s", LTX_MODEL_DIR)
        return False
    return True


def generate_clip(prompt: str, duration: int = 10,
                  output_path: str | None = None) -> str | None:
    if not is_available():
        return None

    if output_path is None:
        tmp = tempfile.mkdtemp()
        output_path = os.path.join(tmp, f"ltx_{int(time.time())}.mp4")

    num_frames = max(121, min(241, int(duration * 24)))
    num_frames = ((num_frames - 1) // 8) * 8 + 1

    try:
        logger.info("[LTX] Generating clip: '%s' (%d frames, %ds)",
                    prompt[:60], num_frames, duration)
        ok = _run_mlx_pipeline(prompt, num_frames, output_path)
        if ok and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            size = os.path.getsize(output_path)
            logger.info("[LTX] Done: %s (%d MB)", output_path, size // 1024 // 1024)
            return output_path
    except Exception as e:
        logger.error("[LTX] Generation failed: %s", e)

    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except OSError:
            pass
    return None


def _run_mlx_pipeline(prompt: str, num_frames: int, output_path: str) -> bool:
    ltx_prompt = (
        f"Tech educational animation, clean professional style, "
        f"{prompt}, smooth camera motion, "
        f"cinematic lighting, consistent color palette, 24fps, high quality"
    )

    attempts = [
        # Try ltx-video-mlx (appautomaton) first
        {
            "module": "ltx_video_mlx.cli",
            "args": [
                sys.executable, "-m", "ltx_video_mlx.cli", "generate",
                "--model-dir", LTX_MODEL_DIR,
                "--prompt", ltx_prompt,
                "--output", output_path,
                "--num-frames", str(num_frames),
                "--fps", "24",
                "--width", "768",
                "--height", "448",
            ],
        },
        # Fall back to ltx-pipelines-mlx (dgrauet)
        {
            "module": "ltx_pipelines_mlx.text_to_video",
            "args": [
                sys.executable, "-m", "ltx_pipelines_mlx.text_to_video",
                "--model", LTX_MODEL_DIR,
                "--prompt", ltx_prompt,
                "--output", output_path,
                "--num-frames", str(num_frames),
                "--fps", "24",
                "--width", "768",
                "--height", "448",
            ],
        },
    ]

    for attempt in attempts:
        cmd = list(attempt["args"])
        if LTX_LOW_RAM:
            cmd.append("--low-ram")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )
            if result.returncode == 0:
                return True
            logger.warning("[LTX] %s failed (rc=%d): %s",
                           attempt["module"], result.returncode,
                           result.stderr[:200])
        except FileNotFoundError:
            logger.warning("[LTX] %s not installed, trying next", attempt["module"])
        except Exception as e:
            logger.warning("[LTX] %s error: %s", attempt["module"], e)

    return False
