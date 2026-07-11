import logging
import tempfile
import os
from models.base_video_model import BaseVideoModel

logger = logging.getLogger(__name__)


class WanVideoModel(BaseVideoModel):
    """Wan2.1-1.3B video generation model.

    Uses diffusers pipeline when CUDA is available (GPU).
    Falls back gracefully to unavailable on Mac/CPU.
    """

    def __init__(self):
        self.engine = os.getenv("WAN_ENGINE", "diffusers")
        self._available = None

    def name(self) -> str:
        return "wan2.1"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if self.engine == "disabled":
            self._available = False
            return False
        try:
            import torch
            if torch.cuda.is_available():
                self._available = True
                return True
        except ImportError:
            pass
        try:
            import mlx.core as mx
            if mx.metal.is_available():
                logger.info("[Wan] MLX metal available, but Wan2.1 MLX port not yet available")
        except ImportError:
            pass
        self._available = False
        logger.info("[Wan] No CUDA GPU or MLX port available — Wan2.1 disabled, falling back to LTX")
        return False

    def generate_clip(self, prompt: str, duration: int = 10,
                      output_path: str | None = None) -> str | None:
        if not self.is_available():
            return None
        if output_path is None:
            tmp = tempfile.mkdtemp()
            output_path = os.path.join(tmp, f"wan_{id(self)}.mp4")
        try:
            from diffusers import WanPipeline
            import torch
            pipe = WanPipeline.from_pretrained(
                "Wan-AI/Wan2.1-1.3B",
                torch_dtype=torch.bfloat16,
            )
            pipe.to("cuda")
            num_frames = min(81, max(16, duration * 8))
            video_frames = pipe(
                prompt,
                num_frames=num_frames,
                guidance_scale=5.0,
            ).frames[0]
            import numpy as np
            import imageio
            frames_np = [np.array(frame) for frame in video_frames]
            imageio.mimwrite(output_path, frames_np, fps=8, codec="libx264")
            logger.info("[Wan] Generated %s (%d frames)", output_path, len(frames_np))
            return output_path
        except Exception as e:
            logger.error("[Wan] Generation failed: %s", e)
            return None

    def generate_clips(self, scenes: list[dict], video_id: str,
                       format_type: str = "long") -> list[str | None]:
        results = []
        for scene in scenes:
            prompt = scene.get("ltx_prompt", "") or scene.get("description", "")
            dur = scene.get("target_duration", scene.get("duration", 8.0))
            path = self.generate_clip(prompt, int(dur))
            results.append(path)
        return results
