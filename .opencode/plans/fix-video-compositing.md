# Fix: Video Compositing Pipeline Failure

## Problem

Error: `pipeline FAILED at long_video_pipeline: [video_pipeline] Video compositing failed.`

The animation engine `render_scenes()` in `agents/utils/animation_engine.py` returns `None`, causing the pipeline to abort.

## Root Cause

Phase F (commit `c6d5ca25`) flipped `USE_ANIMATION_ENGINE` from `"false"` → `"true"` by default. The animation engine renders long videos frame-by-frame with PIL at 1080p, producing thousands of ~6MB PPM frames. This is slow, disk-intensive, and the hardcoded 300s FFmpeg timeout is too tight for long videos.

## Changes Required

### File: `agents/utils/animation_engine.py`

#### 1. Add diagnostic logging before every `return None`
**`render_scenes()` function — 4 locations:**

a) Line 522 — "No frames rendered" → add scene count info
b) Line 538 — "FFmpeg stitch error" → already prints stderr, add "returning None"
c) Line 541 — "FFmpeg stitch exception" → already prints, add "returning None"  
d) Line 593 — "Final mux error" → add "returning None"
e) Line 601 — Add log before bare `return None`

#### 2. Scale FFmpeg timeout by format
**Line 535, 585** — Change hardcoded `timeout=300` to variable based on format:
```python
_ffmpeg_timeout = 600 if format_type == "long" else 300
```

#### 3. Clean old frames dir before rendering
**Before line 420** — Remove stale frames from prior failed runs:
```python
if frames_dir.exists():
    import shutil
    shutil.rmtree(str(frames_dir), ignore_errors=True)
```

#### 4. Guard `characters.json` load against I/O errors
**Lines 416-417** — Wrap in try/except so a missing/malformed file doesn't crash:
```python
try:
    with open(os.path.join(ASSETS_DIR, "characters.json")) as f:
        characters_config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"[ANIMATION] Failed to load characters.json: {e}")
    characters_config = {}
```

#### 5. Fix `_render_effects` double-processing bug
**Line 506** — Change `_render_effects(draw, effects, w, h, fi)` to `_render_effects(draw, effect, w, h, fi)` (pass single effect, not full list)

## Verification

1. Run the pipeline manually:
   ```bash
   cd agents && FORMAT=long TOPIC="test story" CATEGORY="Bedtime Stories" python run_pipeline.py
   ```

2. Check debug prints for `[ANIMATION]` prefix to identify which step fails

3. Verify output MP4 exists at `agents/output/{video_id}_long.mp4`

4. Check disk usage doesn't spike during rendering (intermediate PPM frames should be cleaned up)
