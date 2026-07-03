import os
import sys
import json
import time
import logging
import subprocess
import tempfile
import importlib.util
from pathlib import Path

from models.base_video_model import BaseVideoModel

logger = logging.getLogger(__name__)

NEGATIVE_PROMPT = "distorted faces, glitchy motion, flickering lights, inconsistent lighting, warped geometry, artifacts, blurry, low quality, watermark, text"

QUALITY_SUFFIX = "cinematic lighting, volumetric god rays, smooth camera motion, consistent color palette, 24fps, high quality"

_LTX_MODULE_AVAILABLE = None


def _check_ltx_module() -> bool:
    global _LTX_MODULE_AVAILABLE
    if _LTX_MODULE_AVAILABLE is None:
        _LTX_MODULE_AVAILABLE = importlib.util.find_spec("ltx_pipelines_mlx") is not None
        if not _LTX_MODULE_AVAILABLE:
            logger.warning("[LTX] ltx_pipelines_mlx module not found — LTX disabled")
    return _LTX_MODULE_AVAILABLE


class LtxVideoModel(BaseVideoModel):

    def __init__(self):
        self.model_dir = os.getenv("LTX_MODEL_DIR", os.path.expanduser("~/ltx-models"))
        self.engine = os.getenv("LTX_ENGINE", "mlx")
        self.low_ram = os.getenv("LTX_LOW_RAM", "true").lower() == "true"

    def name(self) -> str:
        return "ltx"

    def is_available(self) -> bool:
        if self.engine == "disabled":
            return False
        if not _check_ltx_module():
            return False
        model_path = Path(self.model_dir)
        if not model_path.exists():
            logger.warning("[LTX] Model dir not found: %s", self.model_dir)
            return False
        return True

    def generate_clip(self, prompt: str, duration: int = 10,
                      output_path: str | None = None) -> str | None:
        if not self.is_available():
            return None

        if output_path is None:
            tmp = tempfile.mkdtemp()
            output_path = os.path.join(tmp, f"ltx_{int(time.time())}.mp4")

        num_frames = max(121, min(241, int(duration * 24)))
        num_frames = ((num_frames - 1) // 8) * 8 + 1

        try:
            logger.info("[LTX] Generating clip: '%s' (%d frames, %ds)",
                        prompt[:60], num_frames, duration)
            ok = self._run_mlx_pipeline(prompt, num_frames, output_path)
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

    def generate_clips(self, scenes: list[dict], video_id: str, format_type: str = "long") -> list[str | None]:
        if not self.is_available():
            return [None] * len(scenes)

        batch = []
        for scene in scenes:
            prompt = self._build_prompt(
                scene.get("ltx_prompt", "")
                or scene.get("description", "")
                or ", ".join(scene.get("asset_keywords", ["technology"]))
            )
            duration = scene.get("target_duration", scene.get("duration", 8.0))
            num_frames = max(121, min(241, int(duration * 24)))
            num_frames = ((num_frames - 1) // 8) * 8 + 1
            out_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "tmp", "asset_router"
            )
            os.makedirs(out_dir, exist_ok=True)
            output_path = os.path.join(out_dir, f"ltx_batch_{video_id}_{len(batch)}.mp4")
            batch.append({
                "prompt": prompt,
                "frames": num_frames,
                "output": output_path,
            })

        config = {
            "model_dir": self.model_dir,
            "gemma_id": os.getenv("LTX_GEMMA_MODEL", "mlx-community/gemma-3-12b-it-4bit"),
            "scenes": batch,
        }

        config_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tmp", "asset_router"
        )
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, f"ltx_batch_config_{video_id}.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        worker_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "ltx_batch.py"
        )

        try:
            logger.info("[LTX] Batch generating %d scenes (model loads once)", len(scenes))
            result = subprocess.run(
                [sys.executable, worker_path, config_path],
                capture_output=True, text=True, timeout=7200,
            )
            if result.returncode == 0:
                outputs = []
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        if r.get("status") == "ok" and os.path.exists(r["path"]):
                            outputs.append(r["path"])
                        else:
                            logger.warning("[LTX] Batch scene failed: %s", r.get("message", "unknown"))
                            outputs.append(None)
                    except json.JSONDecodeError:
                        outputs.append(None)
                while len(outputs) < len(scenes):
                    outputs.append(None)
                logger.info("[LTX] Batch done: %d/%d succeeded",
                            sum(1 for o in outputs if o), len(scenes))
                return outputs[:len(scenes)]
            else:
                logger.warning("[LTX] Batch process failed (rc=%d): %s",
                               result.returncode, result.stderr[:300])
        except subprocess.TimeoutExpired:
            logger.error("[LTX] Batch generation timed out (7200s)")
        except Exception as e:
            logger.error("[LTX] Batch generation error: %s", e)
        finally:
            try:
                os.remove(config_path)
            except OSError:
                pass

        return [None] * len(scenes)

    def _build_prompt(self, raw_prompt: str) -> str:
        lower = raw_prompt.lower()
        word_count = raw_prompt.count(" ") + 1

        if word_count < 12:
            return f"Tech educational animation, clean professional style, {raw_prompt}, smooth camera motion, cinematic lighting, consistent color palette, 24fps, high quality, negative: {NEGATIVE_PROMPT}"

        if any(w in lower for w in ["circuit", "chip", "processor", "server", "data center", "infrastructure"]):
            return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"

        if any(w in lower for w in ["neural", "network", "brain", "synapse", "digital", "data"]):
            return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"

        return f"{raw_prompt}, {QUALITY_SUFFIX}, negative: {NEGATIVE_PROMPT}"

    def _run_mlx_pipeline(self, prompt: str, num_frames: int, output_path: str) -> bool:
        ltx_prompt = self._build_prompt(prompt)

        gemma_id = os.getenv("LTX_GEMMA_MODEL", "mlx-community/gemma-3-12b-it-4bit")
        distilled_lora = os.getenv("LTX_DISTILLED_LORA",
                                   "ltx-2.3-22b-distilled-lora-384-1.1.safetensors")

        cmd = [
            sys.executable, "-m", "ltx_pipelines_mlx", "generate",
            "--distilled",
            "--model", self.model_dir,
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
                cmd, capture_output=True, text=True, timeout=1800,
                close_fds=True,
            )
            if result.returncode == 0:
                return True
            stderr_clean = result.stderr.replace("I0701", "").replace("ev_poll_posix.cc", "")[:300]
            logger.warning("[LTX] Failed (rc=%d): %s",
                           result.returncode, stderr_clean[:200])
        except Exception as e:
            logger.warning("[LTX] Error: %s", e)

        return False
