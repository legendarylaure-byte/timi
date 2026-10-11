"""Multi-shot B-roll (WS3): one scene = several hard-cut shots, not one loop.

The "slideshow" look had a structural cause: a scene was exactly one clip, and
when that clip was shorter than the scene's slot, `_extend_clip` looped its tail
(10s scene on a 4s clip = the same 4s twice). The fix fetches 2-3 distinct stock
clips per scene and hard-cuts between them so the scene is filled by different
footage instead of repetition.

Two independent invariants, because they fail differently:

* `_collect_stock_shots` decides HOW MANY shots (and must never hand back two of
  the same clip, and must leave a short scene single-shot). Pure, no ffmpeg.
* `_process_clip` turns N shots into ONE file of the scene's full duration, so
  chapter/annotation/CTA timing (keyed on clip["duration"]) keeps working. This
  half needs ffmpeg, so it skips cleanly without it.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import asset_router


# ---------------------------------------------------------------------------
# 1. How many shots -- pure decision logic, no encoding
# ---------------------------------------------------------------------------

@pytest.fixture
def distinct_clips(monkeypatch, tmp_path):
    """_get_stock_clip returns a fresh real file per query, so nothing is deduped."""
    made = {}

    def fake(query, orientation="landscape", duration=8.0, video_id=""):
        p = tmp_path / f"{abs(hash(query))}.mp4"
        p.write_bytes(b"x" * 2000)
        made[query] = str(p)
        return str(p)

    monkeypatch.setattr(asset_router, "_get_stock_clip", fake)
    return made


def test_short_scene_degrades_to_single_shot(distinct_clips):
    """A ~2.5s short scene must NOT be chopped -- 2 shots would be < 2s each."""
    shots = asset_router._collect_stock_shots(
        ["a", "b", "c"], "portrait", 2.5, "v1")
    assert shots == [], (
        "a 2.5s scene was split into sub-2s shots; the floor is not enforced"
    )


def test_long_scene_gets_multiple_distinct_shots(distinct_clips):
    shots = asset_router._collect_stock_shots(
        ["a", "b", "c"], "landscape", 7.5, "v1")
    assert len(shots) >= 2, shots
    paths = [s["path"] for s in shots]
    assert len(set(paths)) == len(paths), "the same clip was returned twice"


def test_identical_clip_from_two_queries_is_deduped(monkeypatch, tmp_path):
    """_get_stock_clip caches per keyword -- two queries can yield one clip."""
    same = tmp_path / "same.mp4"
    same.write_bytes(b"x" * 2000)
    monkeypatch.setattr(asset_router, "_get_stock_clip",
                        lambda *a, **k: str(same))
    shots = asset_router._collect_stock_shots(["a", "b", "c"], "landscape", 8.0, "v1")
    assert len(shots) == 1, "one clip was counted as two shots"


def test_shot_count_is_capped(monkeypatch, tmp_path):
    monkeypatch.setenv("STOCK_SHOTS_PER_SCENE", "2")
    counter = {"n": 0}

    def fake(query, orientation="landscape", duration=8.0, video_id=""):
        counter["n"] += 1
        p = tmp_path / f"c{counter['n']}.mp4"
        p.write_bytes(b"x" * 2000)
        return str(p)

    monkeypatch.setattr(asset_router, "_get_stock_clip", fake)
    shots = asset_router._collect_stock_shots(["a", "b", "c", "d", "e"], "landscape", 20.0, "v1")
    assert len(shots) == 2, f"cap ignored: {shots}"


def test_there_are_no_shots_when_stock_is_unavailable(monkeypatch):
    monkeypatch.setattr(asset_router, "_get_stock_clip", lambda *a, **k: None)
    assert asset_router._collect_stock_shots(["a", "b"], "landscape", 8.0, "v1") == []


# ---------------------------------------------------------------------------
# 2. The compositor must cut N shots into ONE full-duration file (needs ffmpeg)
# ---------------------------------------------------------------------------

def _ffmpeg() -> str | None:
    try:
        from utils.video_qa import _ffmpeg_path
        return _ffmpeg_path()
    except Exception:
        return shutil.which("ffmpeg")


def _make_clip(path: str, source: str, seconds: float) -> str | None:
    ff = _ffmpeg()
    if not ff:
        return None
    subprocess.run(
        [ff, "-y", "-f", "lavfi", "-i", source, "-t", str(seconds),
         "-r", "24", "-pix_fmt", "yuv420p", path],
        capture_output=True, check=True,
    )
    return path


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_n_shots_produce_one_scene_length_file():
    from utils.video_compositor import _process_clip, _get_duration

    with tempfile.TemporaryDirectory() as td:
        shots = []
        # testsrc2 is high-detail, so each clip is >10KB and takes the real
        # video path in _process_single_shot (a flat `color=` source compresses
        # to a few KB and wrongly takes the still-image branch).
        for i in range(3):
            p = os.path.join(td, f"shot{i}.mp4")
            _make_clip(p, "testsrc2=s=640x480:r=24", 3.0)
            shots.append({"path": p})

        clip = {"path": shots[0]["path"], "duration": 6.0, "shots": shots}
        out = _process_clip(clip, 640, 480, 0, "long", "ws3")

        assert out and os.path.exists(out), "multi-shot render produced no file"
        dur = _get_duration(out)
        # 3 shots filling a 6s slot -> ~6s. A single slice is 2s, so anything
        # near 2s means the shots were NOT concatenated (the regression).
        assert abs(dur - 6.0) < 0.8, (
            f"expected ~6s from 3x2s shots, got {dur:.2f}s -- shots not concatenated"
        )


@pytest.mark.skipif(_ffmpeg() is None, reason="ffmpeg not available")
def test_single_shot_clip_still_renders():
    """The no-shots path must be untouched by the multi-shot branch."""
    from utils.video_compositor import _process_clip, _get_duration

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "one.mp4")
        _make_clip(p, "testsrc2=s=640x480:r=24", 4.0)
        clip = {"path": p, "duration": 4.0}
        out = _process_clip(clip, 640, 480, 0, "long", "ws3")
        assert out and os.path.exists(out)
        assert abs(_get_duration(out) - 4.0) < 0.8
