"""Regression tests for the still-image duration blowout (found 2026-10-03).

Symptom: `[compositor] Clip 0 rendered 527.1s but was allotted 4.6s` -- 77 such
lines in the logs, allotments 2-7s against renders of 100-1225s.

The old AGENTS.md note blamed `_process_clip` for reading `duration` instead of
`target_duration`. That was wrong, and acting on it would have "fixed" correct
code: `asset_router` already reads `target_duration` first (lines 219 and 360),
and `_process_clip` reads the same field the composite loop compares against.

The actual cause is `resize_to_target`'s zoompan. `zoompan d=N` expands every
INPUT frame into N OUTPUT frames. A still image is fed as `-loop 1 -t dur`, which
the image2 demuxer delivers at 25fps, so the input already holds `dur*25` frames
and the output became `dur*25*N/24` -- quadratic in the allotment. Predicted from
that formula and matched exactly against all six logged samples:

    allotted 4.6s -> 527.1s    allotted 5.2s -> 671.7s
    allotted 5.3s -> 703.8s    allotted 5.4s -> 725.6s
    allotted 3.7s -> 341.0s    allotted 7.0s -> 1225.0s

Only the still-image path shows it (code snippets, branded cards). Real .mp4
footage is trimmed by `trim_clip` first, which is why video clips never tripped it.

The second defect is a caller/callee naming contract: `apply_ken_burns` trimmed
to `kb_trim_{vid}_{preset_idx}.mp4`, which is exactly the path `_process_clip`
creates and passes in as `input_path` -- so it ran `trim_clip(X, X)` on the same
file. That failed and fell back to a plain scale/crop with duration=0, which also
dropped the `-t` bound and emitted the clip's FULL source length, which is how an
oversized clip reaches the concat at all.

Both tests therefore go through `_process_clip`, NOT through the helpers directly.
Testing `apply_ken_burns` in isolation cannot see the collision at all, because
the collision requires `_process_clip` to be the caller -- mutation-confirmed:
reverting the filename leaves an isolated helper test green.

Needs ffmpeg. The host ffmpeg is broken (missing libx265), so these run in the
container via agents/scripts/verify.sh, which is the gate anyway.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


def _ffmpeg() -> str:
    from utils.video_compositor import _ffmpeg_cmd
    return _ffmpeg_cmd()


def _require_ffmpeg() -> None:
    exe = _ffmpeg()
    if not exe or not (shutil.which(exe) or Path(exe).exists()):
        pytest.skip(f"ffmpeg not available: {exe!r}")
    try:
        subprocess.run([exe, "-version"], capture_output=True, timeout=60, check=True)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ffmpeg not runnable here: {exc}")


def _make_still(path: str, w: int = 640, h: int = 360) -> str:
    from PIL import Image
    Image.new("RGB", (w, h), (30, 42, 56)).save(path)
    return path


def _make_video(path: str, seconds: float) -> str:
    subprocess.run(
        [_ffmpeg(), "-y", "-f", "lavfi", "-i", "testsrc=s=640x360:r=24",
         "-t", str(seconds), "-r", "24", "-pix_fmt", "yuv420p", path],
        capture_output=True, check=True, timeout=300,
    )
    return path


def test_still_image_respects_its_allotment(tmp_path, monkeypatch):
    """A still allotted N seconds must render N seconds, not N^2 * 25.

    Routed as a shorts scene (portrait target) because that is how code snippets
    and branded cards actually reach the compositor.
    """
    _require_ffmpeg()
    from utils import video_compositor as mpp

    monkeypatch.setattr(mpp, "TEMP_DIR", tmp_path)
    still = _make_still(str(tmp_path / "card.png"))
    allotted = 1.0

    out = mpp._process_clip(
        {"path": still, "duration": allotted, "asset_type": "STATIC_IMAGE",
         "source": "branded_card"},
        target_w=360, target_h=640, idx=0, format_type="shorts", vid="t",
    )
    assert out is not None, "still card failed to render at all"

    got = mpp._get_duration(out)
    # Without the output-side -t this is ~25s (25 input frames x 24 zoompan
    # frames / 24fps). Anything past 2s means the bound is gone again.
    assert got < 2.0, f"still rendered {got:.1f}s for a {allotted}s allotment -- zoompan re-expansion is back"
    assert got > allotted * 0.5, f"still rendered only {got:.1f}s for a {allotted}s allotment -- over-trimmed"


def test_long_clip_trim_never_overwrites_its_own_input(tmp_path, monkeypatch):
    """The long-form Ken Burns path must not trim a file in place.

    `_process_clip` creates `kb_trim_{vid}_{idx}.mp4` and passes it to
    `apply_ken_burns`, which then trimmed to that same path -- `trim_clip(X, X)`,
    which fails and leaves the file untouched, so every long clip silently fell
    back to a plain scale/crop with no Ken Burns.

    Measured, not assumed: `trim_clip(X, X, 0, 1.5)` returns False and leaves
    10.00s at 60217 bytes. It does NOT corrupt the file -- so the damage is a
    silent loss of motion, not a duration blowout, which is why this asserts the
    self-trim itself. A duration assertion cannot see it: `_process_clip` already
    trimmed upstream, so the fallback still lands near the right length.

    The test must drive `_process_clip`, not the helper directly -- the collision
    only exists when the caller's `input_path` happens to equal the helper's
    internal `kb_trim_{vid}_{idx}.mp4`. Mutation-confirmed: reverting the
    filename with either shape of this test leaves it green.
    """
    _require_ffmpeg()
    from utils import video_compositor as mpp

    monkeypatch.setattr(mpp, "TEMP_DIR", tmp_path)
    src = _make_video(str(tmp_path / "footage.mp4"), seconds=10)

    calls = []
    real_trim = mpp.trim_clip

    def spy(s, d, start, duration):
        calls.append((str(s), str(d)))
        return real_trim(s, d, start, duration)

    monkeypatch.setattr(mpp, "trim_clip", spy)

    allotted = 2.0
    out = mpp._process_clip(
        {"path": src, "duration": allotted, "asset_type": "STOCK_FOOTAGE", "source": "stock"},
        target_w=640, target_h=360, idx=0, format_type="long", vid="t",
    )
    assert out is not None, "long clip failed to render at all"
    assert calls, "trim_clip was never called -- the long path did not run"

    self_trims = [(a, b) for a, b in calls if os.path.abspath(a) == os.path.abspath(b)]
    assert not self_trims, f"trim_clip called with one path as both input and output: {self_trims}"

    got = mpp._get_duration(out)
    # _process_clip drops a 0.5s lead, so ~allotted-0.5 is the healthy value.
    assert got < allotted, f"clip rendered {got:.1f}s for a {allotted}s allotment -- overran its slot"
    assert got > allotted * 0.4, f"clip rendered only {got:.1f}s for a {allotted}s allotment -- over-trimmed"
