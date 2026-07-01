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


NEGATIVE_PROMPT = "distorted faces, glitchy motion, flickering lights, inconsistent lighting, warped geometry, artifacts, blurry, low quality, watermark, text"

QUALITY_SUFFIX = "cinematic lighting, volumetric god rays, smooth camera motion, consistent color palette, 24fps, high quality"


def _build_prompt(raw_prompt: str) -> str:
    lower = raw_prompt.lower()
    word_count = raw_prompt.count(" ") + 1

    if word_count < 12:
        return f"Tech educational animation, clean professional style, {raw_prompt}, smooth camera motion, cinematic lighting, consistent color palette, 24fps, high quality, negative: {NEGATIVE_PROMPT}"

    if any(w in lower for w in ["circuit", "chip", "processor", "server", "data center", "infrastructure"]):
        return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"

    if any(w in lower for w in ["neural", "network", "brain", "synapse", "digital", "data"]):
        return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"

    return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"


def _run_mlx_pipeline(prompt: str, num_frames: int, output_path: str) -> bool:
    ltx_prompt = _build_prompt(prompt)

    gemma_id = os.getenv("LTX_GEMMA_MODEL", "mlx-community/gemma-3-12b-it-4bit")
    distilled_lora = os.getenv("LTX_DISTILLED_LORA",
                               "ltx-2.3-22b-distilled-lora-384-1.1.safetensors")

    cmd = [
        sys.executable, "-m", "ltx_pipelines_mlx", "generate",
        "--distilled",
        "--model", LTX_MODEL_DIR,
        "--gemma", gemma_id,
        "--distilled-lora", distilled_lora,
        "--prompt", ltx_prompt,
        "--output", output_path,
        "--frames", str(num_frames),
        "--frame-rate", "24",
        "--width", "704",
        "--height", "448",
        "--seed", "-1",
        "--quiet",
        "--low-ram",
    ]

    try:
        logger.info("[LTX] Generating: '%s' (%d frames, %ds)",
                     prompt[:60], num_frames, int(num_frames / 24))
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800
        )
        if result.returncode == 0:
            return True
        logger.warning("[LTX] Failed (rc=%d): %s",
                       result.returncode, result.stderr[:300])
    except Exception as e:
        logger.warning("[LTX] Error: %s", e)

    return False
