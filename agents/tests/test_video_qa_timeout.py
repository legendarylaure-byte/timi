"""A ffprobe timeout is not corruption.

On the 2026-10-05 run, `check_corruption` called `ffprobe -count_frames` with a
60s timeout. Four scenes hit that timeout on clips that were perfectly fine --
`-count_frames` decodes the *entire* file, and the box was running two concurrent
pipeline workers. The bare `except` could not tell a timeout from a decode error,
so it returned `is_corrupt: True`, and the caller at
`utils/asset_router.py:249` reacted by demoting the scene to stock footage and
popping its `ltx_prompt`. A slow read silently downgraded an AI-generated visual,
after ~60s wasted per scene.

The counterweight matters as much as the fix: if a timeout merely stopped being
corruption, the check could be passing everything and nobody would notice. So
genuine decode errors and genuine unexpected failures must still read as corrupt.
`test_timeout_is_not_corruption` alone would not prove the check still works.
"""
import subprocess
import types

import pytest

from utils.video_qa import check_corruption


@pytest.fixture
def clip(tmp_path):
    """A real path: check_corruption short-circuits on os.path.exists."""
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00")
    return str(p)


def _completed(stdout="", stderr=""):
    return types.SimpleNamespace(stdout=stdout, stderr=stderr)


def test_timeout_is_not_corruption(clip, monkeypatch):
    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=60)

    monkeypatch.setattr("utils.video_qa.safe_run", boom)
    qa = check_corruption(clip)
    assert qa["timed_out"] is True
    assert qa["is_corrupt"] is False, "a slow read must not demote a healthy clip"


def test_many_decode_errors_is_still_corruption(clip, monkeypatch):
    """The fix must not blind the check -- >3 decode errors is real corruption."""
    monkeypatch.setattr(
        "utils.video_qa.safe_run",
        lambda *a, **k: _completed(stdout="0\n", stderr="err\n" * 5),
    )
    qa = check_corruption(clip)
    assert qa["is_corrupt"] is True
    assert qa["timed_out"] is False


def test_unexpected_failure_is_still_corruption(clip, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ffprobe missing")

    monkeypatch.setattr("utils.video_qa.safe_run", boom)
    qa = check_corruption(clip)
    assert qa["is_corrupt"] is True
    assert qa["timed_out"] is False


def test_healthy_clip_is_clean(clip, monkeypatch):
    monkeypatch.setattr(
        "utils.video_qa.safe_run", lambda *a, **k: _completed(stdout="240\n", stderr="")
    )
    qa = check_corruption(clip)
    assert qa == {
        "total_frames": 240,
        "decode_errors": 0,
        "is_corrupt": False,
        "timed_out": False,
    }


def test_missing_file_is_corruption(tmp_path):
    qa = check_corruption(str(tmp_path / "does-not-exist.mp4"))
    assert qa["is_corrupt"] is True