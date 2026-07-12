# LTX 16GB Optimization — Implementation Plan

## Overview
Upgrade the LTX video generation pipeline to work on 16GB Apple Silicon Macs by fixing the `low_ram_streaming` bug, reducing resolution/frame counts, adding GPU memory prep, and adding a Replicate cloud fallback.

## Files to Modify/Create

### 1. `models/ltx_batch.py` — Fix critical bug
- **Line 23-27**: Change `DistilledPipeline(..., low_memory=True)` to add `low_ram_streaming=True`
- **Lines 38-39**: Reduce `height=448, width=704` → `height=384, width=512`
- **No frame count change needed here** — handled by caller

### 2. `models/ltx_model.py` — Major tuning

#### `generate_clip()` (single scene, line 112):
- **Line 131**: Change `max(121, min(481, int(duration * 24)))` → `max(65, min(145, int(duration * 24)))`
- **Line 132**: Keep snap to `8k+1`
- Pass `format_type` to `_run_mlx_pipeline()` for resolution selection

#### `_run_mlx_pipeline()` (CLI subprocess, line 288):
- **Lines 305-306**: Change `--width 832 --height 512` to format-aware selection:
  - Long: `--width 704 --height 480`
  - Short: `--width 480 --height 832`
- **Line 309**: Keep `--low-ram`
- **Line 296**: Change `--distilled` → `--two-stage` (better quality, same memory with `--low-ram`)
- **Add after line 303**: `"--tile-frames", "2", "--tile-overlap", "4"` when `num_frames > 97`

#### `generate_clips()` (batch, line 153):
- **Remove the batch subprocess approach entirely** (lines 191-270)
- Instead: iterate scenes and call `self.generate_clip()` individually
- This ensures GPU memory is freed between scenes

#### Cache key fix (around line 122-125):
- Change `_check_cache(built_prompt)` to include resolution and frame count:
  ```python
  cache_key = f"{built_prompt}|{width}x{height}|{num_frames}"
  ```
- Same for `_update_cache()`

### 3. `models/gpu_prep.py` — NEW file

```python
"""GPU memory preparation for LTX generation on 16GB Macs."""

import os
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)

GPU_WIRED_LIMIT = 14000  # MB


def prepare_gpu_for_generation():
    """Raise GPU wired memory limit for large model inference.
    
    On 16GB Macs, the default wired limit (~10.5GB) is too small for
    the 10.54GB LTX transformer + activations. Raising to 14GB gives headroom.
    """
    try:
        result = subprocess.run(
            ["sudo", "sysctl", "-w", f"iogpu.wired_lwm_mb={GPU_WIRED_LIMIT}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            logger.info("[GPU] Wired limit raised to %d MB", GPU_WIRED_LIMIT)
            return True
        else:
            logger.warning("[GPU] Could not raise wired limit (not using sudo?): %s",
                           result.stderr.strip())
            return False
    except FileNotFoundError:
        logger.warning("[GPU] sysctl not available — not on macOS?")
        return False
    except Exception as e:
        logger.warning("[GPU] Unexpected error: %s", e)
        return False


def check_memory_pressure() -> dict:
    """Check system memory pressure before generation.
    
    Returns dict with 'pressure' (str) and 'available_gb' (float) keys.
    """
    try:
        result = subprocess.run(
            ["memory_pressure"], capture_output=True, text=True, timeout=5,
        )
        if "System is memory pressure-relieved" in result.stdout:
            return {"pressure": "ok", "available_gb": -1}
        elif "memory-pressure" in result.stdout:
            return {"pressure": "warning", "available_gb": -1}
        else:
            return {"pressure": "unknown", "available_gb": -1}
    except FileNotFoundError:
        pass
    
    # Fallback: parse vm_stat
    try:
        result = subprocess.run(
            ["vm_stat"], capture_output=True, text=True, timeout=5,
        )
        stats = {}
        for line in result.stdout.split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                val = val.strip().rstrip(".")
                if val.isdigit():
                    stats[key.strip()] = int(val)
        
        page_size = 16384  # Apple Silicon default
        free_pages = stats.get("Pages free", 0)
        inactive_pages = stats.get("Pages inactive", 0)
        available_bytes = (free_pages + inactive_pages) * page_size
        available_gb = available_bytes / (1024**3)
        
        if available_gb < 2.0:
            return {"pressure": "critical", "available_gb": round(available_gb, 1)}
        elif available_gb < 4.0:
            return {"pressure": "warning", "available_gb": round(available_gb, 1)}
        else:
            return {"pressure": "ok", "available_gb": round(available_gb, 1)}
    except Exception:
        return {"pressure": "unknown", "available_gb": -1}
```

### 4. `models/replicate_model.py` — NEW file

```python
"""Replicate.com cloud API fallback for video generation.

Implements BaseVideoModel so it drops into the existing model registry fallback chain.
"""

import os
import time
import json
import logging
import tempfile
from models.base_video_model import BaseVideoModel

logger = logging.getLogger(__name__)

FAL_MODEL = "fal-ai/ltx-video"
REPLICATE_MODEL = "luma/ray:2e7e5c4d8c5fb7d73c3e8c3d9b8e0e8f5c4d8c5fb7d73c3e8c3d9b8e0e8f"


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
        """Generate via fal.ai (fastest, ~10-30s per scene, ~$0.05/video)."""
        try:
            import fal_client
            
            logger.info("[Replicate] FAL generating: '%s' (%d frames)", prompt[:40], frames)
            
            result = fal_client.run(
                FAL_MODEL,
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
        """Generate via Replicate."""
        try:
            import replicate
            
            logger.info("[Replicate] generating: '%s' (%d frames)", prompt[:40], frames)
            
            # Use the ltx-video model on Replicate
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
```

### 5. `models/__init__.py` — Register Replicate model
- After line 9, add:
  ```python
  try:
      from models.replicate_model import ReplicateVideoModel
      register("replicate", ReplicateVideoModel)
  except ImportError:
      pass
  ```

### 6. `.env` — Add new env vars
```
# LTX Memory Tuning
LTX_LOW_RAM=true
LTX2_DIT_EVAL_EVERY=12
LTX2_GEMMA_EVAL_EVERY=2
LTX_MIN_FRAMES=65
LTX_MAX_FRAMES=145

# Cloud Video Fallback
REPLICATE_API_KEY=
FAL_KEY=
CLOUD_VIDEO_PROVIDER=replicate
```

### 7. Sudoers setup (run once manually)
```bash
echo 'Ai Mark ALL=(root) NOPASSWD: /usr/sbin/sysctl iogpu.wired_lwm_mb=14000' | sudo tee /etc/sudoers.d/timi-gpu
sudo chmod 440 /etc/sudoers.d/timi-gpu
```

## Testing

### Step 1: Quick smoke test
```bash
cd /Users/Ai\ Mark/timi/agents
source .venv/bin/activate

# Single scene, 65 frames, low-res, block streaming
python3 -m ltx_pipelines_mlx generate \
  --distilled --model ~/ltx-models \
  --prompt "A glowing neural network with data flowing through it" \
  -o /tmp/test_ltx.mp4 \
  --frames 65 --height 384 --width 512 \
  --frame-rate 24 --low-ram
```

### Step 2: Full pipeline test
```bash
cd /Users/Ai\ Mark/timi/agents
SLOT=morning FORMAT=short CATEGORY="AI Explained" \
  USE_ANIMATION_ENGINE=true python3 run_pipeline.py
```

### Step 3: Check output
- Verify video was generated without swap thrashing
- Check `memory_pressure` during generation
- Verify quality is acceptable

## Deployment

### Commit
```bash
cd /Users/Ai\ Mark/timi
git add agents/models/ltx_batch.py agents/models/ltx_model.py \
        agents/models/gpu_prep.py agents/models/replicate_model.py \
        agents/models/__init__.py agents/.env
git commit -m "LTX 16GB optimization: low_ram_streaming, reduced res/frames, GPU prep, Replicate fallback"
```

### Docker
- No rebuild needed — LTX runs on host, Docker runs scheduler only
- Verify container is still running: `docker ps | grep timi-pipeline`
