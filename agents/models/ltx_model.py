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


def _cache_key(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:16]


def _check_cache(prompt: str) -> str | None:
    key = _cache_key(prompt)
    if key in _prompt_cache:
        cached_path = _prompt_cache[key]
        if os.path.exists(cached_path) and os.path.getsize(cached_path) > 1000:
            logger.info("[LTX-cache] HIT: %s -> %s", prompt[:40], cached_path)
            _prompt_cache.move_to_end(key)
            return cached_path
        else:
            del _prompt_cache[key]
    return None


def _update_cache(prompt: str, path: str):
    key = _cache_key(prompt)
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
                      seed: int = -1, prev_colors: str | None = None) -> str | None:
        if not self.is_available():
            return None

        continuity = ""
        if prev_colors:
            continuity = f", consistent with previous scene's palette of {prev_colors}"

        built_prompt = self._build_prompt(prompt + continuity)
        cached = _check_cache(built_prompt)
        if cached:
            return cached

        if output_path is None:
            tmp = tempfile.mkdtemp()
            output_path = os.path.join(tmp, f"ltx_{int(time.time())}.mp4")

        num_frames = max(121, min(481, int(duration * 24)))
        num_frames = ((num_frames - 1) // 8) * 8 + 1

        try:
            logger.info("[LTX] Generating clip: '%s' (%d frames, %ds, seed=%d)",
                        prompt[:60], num_frames, duration, seed)
            ok = self._run_mlx_pipeline(prompt, num_frames, output_path, seed=seed)
            if ok and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                size = os.path.getsize(output_path)
                logger.info("[LTX] Done: %s (%d MB)", output_path, size // 1024 // 1024)
                _update_cache(built_prompt, output_path)
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
        batch = []
        batch_indices = []
        shared_seed = abs(hash(video_id)) % (2**31 - 1)
        prev_colors = None

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

            cached = _check_cache(prompt)
            if cached:
                logger.info("[LTX-cache] Batch HIT scene %d: %s", i, prompt[:40])
                results[i] = cached
                if scene.get("ltx_prompt"):
                    prev_colors = "teal, cyan, dark gray"
                continue

            duration = scene.get("target_duration", scene.get("duration", 8.0))
            num_frames = max(121, min(481, int(duration * 24)))
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
                "seed": shared_seed + i,
                "scene_index": i,
                "scene_total": len(scenes),
            })
            batch_indices.append(i)
            prev_colors = "teal, cyan, dark gray"

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

        if not batch:
            logger.info("[LTX-cache] All %d scenes served from cache", len(scenes))
            return results

        try:
            logger.info("[LTX] Batch generating %d/%d scenes (cache hit: %d)",
                        len(batch), len(scenes), len(scenes) - len(batch))
            result = safe_run(
                [sys.executable, worker_path, config_path],
                timeout=7200, capture_output=True, text=True,
            )
            if result.returncode == 0:
                stdout = result.stdout
                batch_outputs = []
                for line in stdout.strip().split("\n"):
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        if r.get("status") == "ok" and os.path.exists(r["path"]):
                            batch_outputs.append(r["path"])
                        else:
                            logger.warning("[LTX] Batch scene failed: %s", r.get("message", "unknown"))
                            batch_outputs.append(None)
                    except json.JSONDecodeError:
                        batch_outputs.append(None)
                while len(batch_outputs) < len(batch):
                    batch_outputs.append(None)

                for idx, output in zip(batch_indices, batch_outputs):
                    results[idx] = output
                    if output:
                        _update_cache(batch[len([j for j in batch_indices if j < idx])]["prompt"], output)

                logger.info("[LTX-cache] Batch done: %d/%d new, %d cached",
                            sum(1 for o in batch_outputs if o),
                            len(batch), sum(1 for r in results if r) - sum(1 for o in batch_outputs if o))
                return results
            else:
                logger.warning("[LTX] Batch process failed (rc=%d): %s",
                               result.returncode, result.stderr[:300])
        except Exception as e:
            logger.error("[LTX] Batch generation error: %s", e)
        finally:
            try:
                os.remove(config_path)
            except OSError:
                pass

        return results

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

    def _run_mlx_pipeline(self, prompt: str, num_frames: int, output_path: str, seed: int = -1) -> bool:
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
            "--width", "832",
            "--height", "512",
            "--seed", str(seed),
            "--quiet",
            "--low-ram",
        ]

        try:
            logger.info("[LTX] Generating: '%s' (%d frames, %ds)",
                        prompt[:60], num_frames, int(num_frames / 24))
            result = safe_run(
                cmd, timeout=1800, capture_output=True, text=True,
            )
            if result.returncode == 0:
                return True
            stderr_clean = result.stderr.replace("I0701", "").replace("ev_poll_posix.cc", "")[:300]
            logger.warning("[LTX] Failed (rc=%d): %s",
                           result.returncode, stderr_clean[:200])
        except Exception as e:
            logger.warning("[LTX] Error: %s", e)

        return False
