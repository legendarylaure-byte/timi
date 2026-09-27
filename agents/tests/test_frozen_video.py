"""Regression tests for the frozen-video incident (2026-09-26, long-20260926-n3).

Symptom: a 257s long video was published that was one static title card for its
whole runtime, with 14 clips where clip 0 was 400s and clip 13 was 625s, and the
final `-shortest` mux cut the video inside the first clip.

These tests pin the two independent causes:

  1. `normalize_scene_durations` copied an unbounded parser `duration` into
     `target_duration`, so a renderer could be told to build a 400s clip.
  2. Nothing checked that the concatenated visuals matched the audio, so the
     overrun was discovered by a human on YouTube.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.scene_schema import (
    MAX_SCENE_DURATION,
    MIN_SCENE_DURATION,
    clamp_scene_duration,
)
from utils.scene_parser import normalize_scene_durations


# --------------------------------------------------------------------------
# 1. The bound itself
# --------------------------------------------------------------------------

def test_clamp_bounds_over_long_scene():
    """The 400s / 625s scenes must be impossible to express."""
    assert clamp_scene_duration(400.0) == MAX_SCENE_DURATION
    assert clamp_scene_duration(625.0) == MAX_SCENE_DURATION
    assert clamp_scene_duration(9999) == MAX_SCENE_DURATION


def test_clamp_bounds_under_short_scene():
    assert clamp_scene_duration(0.0) == MIN_SCENE_DURATION
    assert clamp_scene_duration(-5) == MIN_SCENE_DURATION
    assert clamp_scene_duration(0.4) == MIN_SCENE_DURATION


def test_clamp_passes_through_valid_value():
    assert clamp_scene_duration(18.4) == 18.4
    assert clamp_scene_duration("12.5") == 12.5


def test_clamp_survives_junk_without_raising():
    """A renderer must never die because a scene carried a string or None."""
    for junk in (None, "", "abc", float("nan"), float("inf"), [], {}):
        out = clamp_scene_duration(junk)
        assert MIN_SCENE_DURATION <= out <= MAX_SCENE_DURATION, f"{junk!r} -> {out}"


# --------------------------------------------------------------------------
# 2. normalize_scene_durations -- the actual regression
# --------------------------------------------------------------------------

def test_normalize_clamps_the_over_long_durations_that_caused_the_bug():
    """This is the exact payload shape from the incident: two runaway scenes.

    Before the fix, `target_duration` inherited 400 and 625 verbatim, and
    `render_manim_scene`/`render_manim_scene` sized the render from that value.
    """
    scenes = [{"duration": 400.0, "narration": "a"}] + [
        {"duration": 18.0, "narration": f"b{i}"} for i in range(5)
    ] + [{"duration": 625.0, "narration": "z"}]

    normalize_scene_durations(scenes)

    for scene in scenes:
        assert scene["target_duration"] <= MAX_SCENE_DURATION
        assert MIN_SCENE_DURATION <= scene["target_duration"]
        # Both fields must agree -- two names for one value is what let chapters,
        # asset_router and the renderers disagree about a scene's length.
        assert scene["duration"] == scene["target_duration"], scene


def test_normalize_preserves_valid_durations():
    scenes = [{"duration": 18.4}, {"duration": 7.0}, {"target_duration": 22.0}]
    normalize_scene_durations(scenes)
    assert [s["duration"] for s in scenes] == [18.4, 7.0, 22.0]
    assert [s["target_duration"] for s in scenes] == [18.4, 7.0, 22.0]


def test_normalize_fills_a_missing_duration():
    scenes = [{"narration": "no duration at all"}]
    normalize_scene_durations(scenes)
    assert MIN_SCENE_DURATION <= scenes[0]["target_duration"] <= MAX_SCENE_DURATION
    assert scenes[0]["duration"] == scenes[0]["target_duration"]


# --------------------------------------------------------------------------
# 3. Alignment paths cannot leave an over-long scene
# --------------------------------------------------------------------------

def _import_main():
    import main
    return main


def test_align_clamps_every_scene_to_the_bound():
    main = _import_main()
    # phrase timings present, but wildly longer than the audio: the aligner's own
    # compression pass must still land inside the bound.
    scenes = [{"target_duration": 400.0, "duration": 400.0, "narration": "x" * 50} for _ in range(3)]
    phrase_timings = [
        {"text": "word", "start": float(i), "end": float(i) + 1} for i in range(300)
    ]
    main._align_scenes_to_audio(scenes, phrase_timings, 257.16)
    for s in scenes:
        assert s["target_duration"] <= MAX_SCENE_DURATION, s
        assert s["duration"] == s["target_duration"], s


def test_align_without_phrase_timings_falls_back_to_proportional():
    """The incident path: empty phrase timings returned scenes untouched, silently.

    Now it must scale them into the bound instead of going quiet.
    """
    main = _import_main()
    scenes = [{"target_duration": 400.0, "duration": 400.0, "narration": "x" * 50} for _ in range(3)]
    out = main._align_scenes_to_audio(scenes, [], 257.16)
    assert out is scenes
    for s in out:
        assert s["target_duration"] <= MAX_SCENE_DURATION, s
        assert s["duration"] == s["target_duration"], s


def test_proportional_scale_respects_the_bound():
    main = _import_main()
    scenes = [{"target_duration": 400.0, "duration": 400.0} for _ in range(4)]
    main._proportional_scale(scenes, 300.0)
    for s in scenes:
        assert s["target_duration"] <= MAX_SCENE_DURATION
        assert s["duration"] == s["target_duration"]


# --------------------------------------------------------------------------
# 4. The static-video detector (needs ffmpeg; skipped without it)
# --------------------------------------------------------------------------

def _ffmpeg() -> str:
    from utils.video_qa import _ffmpeg_path
    return _ffmpeg_path()


def _make_video(path: str, frames: str, seconds: int) -> str:
    subprocess.run(
        [_ffmpeg(), "-y", "-f", "lavfi", "-i", frames, "-t", str(seconds),
         "-r", "24", "-pix_fmt", "yuv420p", path],
        capture_output=True, check=True,
    )
    return path


def test_static_detector_flags_a_frozen_card():
    from utils.video_qa import check_static_video

    with tempfile.TemporaryDirectory() as td:
        # A still image held for 20s: exactly the shape of the published bug.
        path = _make_video(
            os.path.join(td, "static.mp4"),
            "color=c=0x1B1212:s=320x180:r=24", 20,
        )
        report = check_static_video(path)
        assert report.get("is_static") is True, report
        assert report["motion_score"] < 1.5, report


def test_static_detector_does_not_flag_real_motion():
    from utils.video_qa import check_static_video

    with tempfile.TemporaryDirectory() as td:
        path = _make_video(
            os.path.join(td, "moving.mp4"),
            "testsrc=s=320x180:r=24", 20,
        )
        report = check_static_video(path)
        assert report.get("is_static") is False, report
        assert report["motion_score"] > 1.5, report


def test_frame_quality_report_fails_a_static_video():
    """The detector must be reachable as a gate, not just a helper."""
    from utils.video_qa import check_frame_quality

    with tempfile.TemporaryDirectory() as td:
        path = _make_video(
            os.path.join(td, "static.mp4"),
            "color=c=0x1B1212:s=320x180:r=24", 20,
        )
        report = check_frame_quality(path)
        assert report["passed"] is False, report["summary"]
        assert "STATIC" in report["summary"], report["summary"]


def test_frame_quality_report_passes_real_motion():
    from utils.video_qa import check_frame_quality

    with tempfile.TemporaryDirectory() as td:
        path = _make_video(
            os.path.join(td, "moving.mp4"),
            "testsrc=s=320x180:r=24", 20,
        )
        report = check_frame_quality(path)
        assert report["passed"] is True, report["summary"]


def test_static_detector_reports_instead_of_raising_on_missing_file():
    from utils.video_qa import check_static_video

    report = check_static_video("/nope/does-not-exist.mp4")
    assert report["is_static"] is False
    assert "error" in report


# --------------------------------------------------------------------------
# 5. The compositor trim (defence in depth)
# --------------------------------------------------------------------------

def test_trim_clip_bounds_an_over_long_renderer_output():
    """The compositor must be able to cut a renderer that ignored its slot.

    `composite_video` now trims any processed clip longer than the scene asked
    for. Before that, an over-long file went straight into xfade (so the offsets
    were computed from the real, huge duration) and the final `-shortest` mux cut
    the video wherever the audio happened to end.
    """
    from utils.subprocess_helper import safe_run
    from utils.video_compositor import trim_clip

    with tempfile.TemporaryDirectory() as td:
        src = os.path.join(td, "overlong.mp4")
        subprocess.run(
            [_ffmpeg(), "-y", "-f", "lavfi", "-i", "testsrc=s=320x180:r=24",
             "-t", "40", "-pix_fmt", "yuv420p", src],
            capture_output=True, check=True,
        )

        out = os.path.join(td, "trimmed.mp4")
        trim_clip(src, out, 0, 12.0)

        probe = safe_run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", out], timeout=30,
        )
        assert abs(float(probe.stdout.strip()) - 12.0) < 1.0, "trim did not honour the slot"
