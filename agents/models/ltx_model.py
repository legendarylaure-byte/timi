import os
import sys
import json
import time
import hashlib
import logging
import tempfile
import importlib.util
from pathlib import Path
from collections import OrderedDict

from utils.subprocess_helper import safe_run, register_temp_dir
from models.base_video_model import BaseVideoModel

logger = logging.getLogger(__name__)

NEGATIVE_PROMPT = "distorted faces, glitchy motion, flickering lights, inconsistent lighting, warped geometry, artifacts, blurry, low quality, watermark, text"

QUALITY_SUFFIX = "cinematic lighting, volumetric god rays, smooth camera motion, consistent color palette, 24fps, high quality"

_LTX_MODULE_AVAILABLE = None

_MAX_CACHE_ENTRIES = 50
_CACHE_DIR = Path(tempfile.gettempdir()) / "ltx_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
register_temp_dir(str(_CACHE_DIR))

_prompt_cache = OrderedDict()
_cache_meta_path = _CACHE_DIR / "cache_meta.json"


def _load_cache_meta():
    global _prompt_cache
    if _cache_meta_path.exists():
        try:
            with open(_cache_meta_path) as f:
                data = json.load(f)
            _prompt_cache = OrderedDict(data.get("entries", {}))
            logger.info("[LTX-cache] Loaded %d cached prompts", len(_prompt_cache))
        except Exception as e:
            logger.warning("[LTX-cache] Failed to load cache meta: %s", e)
            _prompt_cache = OrderedDict()


def _save_cache_meta():
    try:
        with open(_cache_meta_path, "w") as f:
            json.dump({"entries": list(_prompt_cache.items())}, f)
    except Exception as e:
        logger.warning("[LTX-cache] Failed to save cache meta: %s", e)


def _cache_key(prompt: str, width: int = 704, height: int = 480, num_frames: int = 65) -> str:
    return hashlib.sha256(f"{prompt}|{width}x{height}|{num_frames}".encode()).hexdigest()[:16]


def _check_cache(prompt: str, width: int = 704, height: int = 480, num_frames: int = 65) -> str | None:
    key = _cache_key(prompt, width, height, num_frames)
    if key in _prompt_cache:
        cached_path = _prompt_cache[key]
        if os.path.exists(cached_path) and os.path.getsize(cached_path) > 1000:
            logger.info("[LTX-cache] HIT: %s -> %s", prompt[:40], cached_path)
            _prompt_cache.move_to_end(key)
            return cached_path
        else:
            del _prompt_cache[key]
    return None


def _update_cache(prompt: str, path: str, width: int = 704, height: int = 480, num_frames: int = 65):
    key = _cache_key(prompt, width, height, num_frames)
    _prompt_cache[key] = path
    _prompt_cache.move_to_end(key)
    while len(_prompt_cache) > _MAX_CACHE_ENTRIES:
        _prompt_cache.popitem(last=False)
    _save_cache_meta()


_load_cache_meta()


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
                      output_path: str | None = None,
                      seed: int = -1, prev_colors: str | None = None,
                      format_type: str = "long") -> str | None:
        if not self.is_available():
            return None

        continuity = ""
        if prev_colors:
            continuity = f", consistent with previous scene's palette of {prev_colors}"

        built_prompt = self._build_prompt(prompt + continuity)

        min_frames = max(9, min(65, int(os.getenv("LTX_MIN_FRAMES", "65"))))
        max_frames = max(65, min(481, int(os.getenv("LTX_MAX_FRAMES", "145"))))
        num_frames = max(min_frames, min(max_frames, int(duration * 24)))
        num_frames = ((num_frames - 1) // 8) * 8 + 1

        if format_type == "short":
            width, height = 544, 960
        else:
            width, height = 960, 544

        cached = _check_cache(built_prompt, width, height, num_frames)
        if cached:
            return cached

        if output_path is None:
            tmp = tempfile.mkdtemp()
            output_path = os.path.join(tmp, f"ltx_{int(time.time())}.mp4")

        try:
            logger.info("[LTX] Generating clip: '%s' (%d frames, %ds, %dx%d, seed=%d)",
                        prompt[:60], num_frames, duration, width, height, seed)
            ok = self._run_mlx_pipeline(built_prompt, num_frames, output_path, width, height, seed=seed)
            if ok and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                size = os.path.getsize(output_path)
                logger.info("[LTX] Done: %s (%d MB)", output_path, size // 1024 // 1024)
                _update_cache(built_prompt, output_path, width, height, num_frames)
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

        results = [None] * len(scenes)
        shared_seed = abs(hash(video_id)) % (2**31 - 1)
        prev_colors = None
        from models.gpu_prep import prepare_gpu_for_generation, check_memory_pressure
        mp = check_memory_pressure()
        if mp.get("pressure") == "critical":
            logger.warning("[LTX] Memory pressure CRITICAL (%.1f GB free) — early exiting, all scenes will fall back",
                           mp.get("available_gb", -1))
            return results
        elif mp.get("pressure") == "warning":
            logger.info("[LTX] Memory pressure warning (%.1f GB free) — proceeding carefully",
                        mp.get("available_gb", -1))

        for i, scene in enumerate(scenes):
            base_prompt = (
                scene.get("ltx_prompt", "")
                or scene.get("description", "")
                or ", ".join(scene.get("asset_keywords", ["technology"]))
            )
            continuity = ""
            if prev_colors:
                continuity = f", maintaining consistent color palette from previous scene ({prev_colors})"
            prompt = self._build_prompt(base_prompt + continuity)

            duration = scene.get("target_duration", scene.get("duration", 8.0))
            out_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "tmp", "asset_router"
            )
            os.makedirs(out_dir, exist_ok=True)
            output_path = os.path.join(out_dir, f"ltx_scene_{video_id}_{i}.mp4")
            scene_prompt = base_prompt + continuity
            result = self.generate_clip(
                prompt=scene_prompt,
                duration=int(duration),
                output_path=output_path,
                seed=shared_seed + i,
                prev_colors=None,
                format_type=format_type,
            )
            results[i] = result
            if result:
                prev_colors = "violet, magenta, dark gray"

        logger.info("[LTX] Per-scene generation done: %d/%d generated",
                    sum(1 for r in results if r), len(scenes))
        return results

    def _build_prompt(self, raw_prompt: str) -> str:
        word_count = raw_prompt.count(" ") + 1
        if word_count < 12:
            return f"{raw_prompt}, cinematic lighting, smooth camera motion, 24fps, high quality, negative: {NEGATIVE_PROMPT}"
        return f"{raw_prompt}, 24fps, high quality, negative: {NEGATIVE_PROMPT}"

    def _run_mlx_pipeline(self, ltx_prompt: str, num_frames: int, output_path: str,
                          width: int = 704, height: int = 480, seed: int = -1) -> bool:

        gemma_id = os.getenv("LTX_GEMMA_MODEL", "mlx-community/gemma-3-12b-it-4bit")

        pipeline_mode = os.getenv("LTX_PIPELINE_MODE", "distilled")
        cmd = [
            sys.executable, "-m", "ltx_pipelines_mlx", "generate",
            f"--{pipeline_mode}",
            "--model", self.model_dir,
            "--gemma", gemma_id,
            "--prompt", ltx_prompt,
            "--output", output_path,
            "--frames", str(num_frames),
            "--frame-rate", "24",
            "--width", str(width),
            "--height", str(height),
            "--seed", str(seed),
            "--quiet",
            "--low-ram",
        ]

        if num_frames > 97:
            cmd.extend(["--tile-frames", "2", "--tile-overlap", "4"])

        try:
            logger.info("[LTX] Running MLX pipeline: '%s' (%d frames, %ds, %dx%d)",
                        ltx_prompt[:60], num_frames, int(num_frames / 24), width, height)
            result = safe_run(
                cmd, timeout=1800, capture_output=True, text=True,
            )
            if result.returncode == 0:
                logger.info("[LTX] MLX pipeline succeeded: %s", output_path)
                return True
            stderr_clean = result.stderr[:500] if result.stderr else ""
            logger.warning("[LTX] Failed (rc=%d): %s",
                           result.returncode, stderr_clean[:200])
        except Exception as e:
            logger.warning("[LTX] Error: %s", e)

        return False
