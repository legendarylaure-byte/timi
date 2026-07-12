import os
import time
import json
import logging
import tempfile
from models.base_video_model import BaseVideoModel

logger = logging.getLogger(__name__)


class ReplicateVideoModel(BaseVideoModel):
    """Cloud video generation via Replicate or fal.ai APIs."""

    def __init__(self):
        self.provider = os.getenv("CLOUD_VIDEO_PROVIDER", "replicate")
        self.replicate_key = os.getenv("REPLICATE_API_KEY", "")
        self.fal_key = os.getenv("FAL_KEY", "")
        self._available = None

    def name(self) -> str:
        return "replicate"

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        if self.provider == "replicate" and self.replicate_key:
            self._available = True
            logger.info("[Replicate] API key found — cloud fallback available")
        elif self.provider == "fal" and self.fal_key:
            self._available = True
            logger.info("[Replicate] FAL key found — cloud fallback available")
        else:
            self._available = False
            logger.info("[Replicate] No API key set — cloud fallback disabled")
        return self._available

    def generate_clip(self, prompt: str, duration: int = 10,
                      output_path: str | None = None) -> str | None:
        if not self.is_available():
            return None

        if output_path is None:
            tmp = tempfile.mkdtemp()
            output_path = os.path.join(tmp, f"replicate_{int(time.time())}.mp4")

        num_frames = max(65, min(145, int(duration * 24)))
        num_frames = ((num_frames - 1) // 8) * 8 + 1
        width = 704
        height = 480

        if self.provider == "fal":
            return self._generate_fal(prompt, num_frames, width, height, output_path)
        else:
            return self._generate_replicate(prompt, num_frames, width, height, output_path)

    def _generate_fal(self, prompt: str, frames: int, width: int, height: int,
                      output_path: str) -> str | None:
        try:
            import fal_client

            logger.info("[Replicate] FAL generating: '%s' (%d frames)", prompt[:40], frames)

            result = fal_client.run(
                "fal-ai/ltx-video",
                arguments={
                    "prompt": prompt,
                    "num_frames": frames,
                    "fps": 24,
                    "width": width,
                    "height": height,
                    "guidance_scale": 3.0,
                    "num_inference_steps": 8,
                },
            )

            video_url = result.get("video", {}).get("url")
            if not video_url:
                logger.error("[Replicate] No video URL in FAL response")
                return None

            import requests
            resp = requests.get(video_url, timeout=120)
            with open(output_path, "wb") as f:
                f.write(resp.content)

            size = os.path.getsize(output_path)
            logger.info("[Replicate] FAL done: %s (%d MB)", output_path, size // 1024 // 1024)
            return output_path

        except ImportError:
            logger.error("[Replicate] fal_client not installed. Run: pip install fal-client")
            return None
        except Exception as e:
            logger.error("[Replicate] FAL generation failed: %s", e)
            return None

    def _generate_replicate(self, prompt: str, frames: int, width: int, height: int,
                            output_path: str) -> str | None:
        try:
            import replicate

            logger.info("[Replicate] generating: '%s' (%d frames)", prompt[:40], frames)

            output = replicate.run(
                "luma/ray:2e7e5c4d8c5fb7d73c3e8c3d9b8e0e8f",
                input={
                    "prompt": prompt,
                    "num_frames": frames,
                    "fps": 24,
                    "width": width,
                    "height": height,
                },
            )

            if isinstance(output, str):
                video_url = output
            elif isinstance(output, list):
                video_url = output[0] if output else None
            else:
                video_url = str(output) if output else None

            if not video_url:
                logger.error("[Replicate] No output from Replicate")
                return None

            import requests
            resp = requests.get(video_url, timeout=120)
            with open(output_path, "wb") as f:
                f.write(resp.content)

            size = os.path.getsize(output_path)
            logger.info("[Replicate] done: %s (%d MB)", output_path, size // 1024 // 1024)
            return output_path

        except ImportError:
            logger.error("[Replicate] replicate not installed. Run: pip install replicate")
            return None
        except Exception as e:
            logger.error("[Replicate] generation failed: %s", e)
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
