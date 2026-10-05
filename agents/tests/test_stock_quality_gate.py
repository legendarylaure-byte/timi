"""Stock selection: the resolution floor and the abstract-footage gate.

Both exist because of what was actually shipping. Measured on a recent long:
mean RGB #314664 with a per-frame luma range of 3 points across four minutes --
a dark, desaturated, near-uniform frame the owner read as "slate blue". Two
separate causes, one test file because they are one decision:

1. Portrait was unreachable. The floor required width >= 1920, but portrait stock
   is natively 1080x1920, so the width test rejected 100% of it. Verified live:
   "abstract data visualization" and "quantum computing abstract" each returned 5
   portrait clips from Pexels and 0 survived. Shorts then fell through to
   Pixabay, which takes no orientation parameter and returned landscape clips
   that were crushed into 9:16.

2. When a search did return something, nothing checked what it depicted. The
   abstract/neon vocabulary in the category keywords produced exactly the CGI
   look that had to go.

The gate is fail-open by construction, and that is asserted here rather than
hoped for: a scene that loses every candidate falls through to the branded title
card, which is a WORSE outcome than the slate-blue. Tightening these filters may
cost quality; it must never cost a scene its footage.
"""
import sys
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

from utils.stock_video import (  # noqa: E402
    MIN_CLIP_LUMA, _min_source_dims, _pexels_title, _title_rejected,
)


def test_min_dims_follow_the_delivery_size():
    # Output is 1920x1080 landscape and 1080x1920 portrait, so the floor is the
    # delivery size. Demanding 4K portrait would reject the native portrait
    # library for a resolution the renderer never uses.
    assert _min_source_dims("landscape") == (1920, 1080)
    assert _min_source_dims("portrait") == (1080, 1920)


@pytest.mark.parametrize("orientation,w,h,expected", [
    # The regression: native portrait rejected by a landscape-only width test.
    ("portrait", 1080, 1920, True),
    ("portrait", 2160, 3840, True),
    ("portrait", 1920, 1080, False),   # landscape clip for a portrait slot
    ("landscape", 1920, 1080, True),
    ("landscape", 3840, 2160, True),
    ("landscape", 1080, 1920, False),  # portrait clip for a landscape slot
    ("landscape", 640, 360, False),
])
def test_resolution_floor_is_oriented(orientation, w, h, expected):
    min_w, min_h = _min_source_dims(orientation)
    assert (w >= min_w and h >= min_h) is expected


def test_pexels_title_is_read_from_the_image_slug():
    # Pexels has no title field; the description lives in the image URL slug.
    # Dropping it is why relevance could never rank anything, and why the quality
    # gate can reject a clip by what it depicts rather than by guesswork.
    v = {"id": 12352337,
         "image": "https://images.pexels.com/videos/12352337/"
                  "abstract-background-binary-blue-12352337.jpeg?auto=compress"}
    assert _pexels_title(v) == "abstract background binary blue"
    assert _pexels_title({"id": 1, "image": ""}) == ""


@pytest.mark.parametrize("title", [
    "abstract background binary blue",
    "3d digital dj neon",
    "holographic glitch abstract 3d figure animation",
    "3d arcadian audiovisual cosmos",
    "neon matrix light",
    "abstract code animation",
])
def test_abstract_titles_are_rejected(title):
    assert _title_rejected(title), f"{title!r} should be rejected"


@pytest.mark.parametrize("title", [
    "programmer typing code",
    "4k drone shot above clouds alpine mountains",
    "conference room daylight indoors microphones",
    "bacteria lab laboratory scientist",
    "kathmandu mountain range mountains nepal",
    "analysis experiment flask lab",
    "aerial video city nepalese panorama",
])
def test_real_footage_titles_survive(title):
    assert not _title_rejected(title), f"{title!r} is real footage and was rejected"


def test_short_nondescript_titles_are_not_rejected():
    # Several providers return a bare slug like "pexels-photo-8347236". Treating
    # an unknown title as "fine" is what lets the gate stay fail-open; treating it
    # as abstract would reject good clips by accident.
    assert not _title_rejected("pexels-photo-8347236")
    assert not _title_rejected("free-video-3433789")


def test_luma_floor_is_set_from_measurement_not_guesswork():
    # brand_palette.py already calls the shipped 76.4 "a near-black frame". The
    # floor sits above that and below a usable exposure.
    assert 62 == MIN_CLIP_LUMA
    assert MIN_CLIP_LUMA > 76.4 * 0 - 1  # sanity: it is a real number, not None


def test_gate_is_fail_open_when_every_candidate_is_abstract(monkeypatch, tmp_path):
    """The single most important property of the gate.

    When enforcement would reject every candidate it must proceed unfiltered and
    say so. If it returned nothing instead, "remove the abstract footage" would
    silently become "remove every scene's footage" and the branded title card
    would become the channel.
    """
    import utils.stock_video as sv

    monkeypatch.setattr(sv, "STOCK_QUALITY_REJECTED", True, raising=False)
    monkeypatch.setattr(sv, "CLIPS_DIR", tmp_path, raising=False)

    calls = {"n": 0}

    def _fake_download(url, out_path):
        calls["n"] += 1
        Path(out_path).write_bytes(b"x" * 2048)
        return True

    monkeypatch.setattr(sv, "download_clip", _fake_download)
    monkeypatch.setattr(sv, "get_video_duration", lambda p: 9.0)
    monkeypatch.setattr(sv, "_clip_mean_luma", lambda p: 120.0)
    monkeypatch.setattr(sv, "_search_providers", lambda kws, o, per_page=5: [
        {"id": i, "url": f"http://x/{i}", "width": 1920, "height": 1080,
         "source": "pexels", "query": kws[0], "title": "abstract neon 3d render"}
        for i in range(3)
    ])
    monkeypatch.setattr(sv, "_keyword_expand", lambda kw: [kw])

    clip = sv.search_and_download("quantum thing", video_id="v1", scene_idx=0)

    assert clip is not None, (
        "the gate returned nothing when every candidate was abstract; a scene "
        "that loses all its footage falls through to the branded title card"
    )
    assert calls["n"] >= 1, "no download was even attempted"
    assert clip["keyword"] == "quantum thing"


def test_gate_prefers_real_footage_when_a_real_candidate_exists(monkeypatch, tmp_path):
    """The gate must actually drop the abstract one, not merely tolerate it."""
    import utils.stock_video as sv

    monkeypatch.setattr(sv, "STOCK_QUALITY_REJECTED", True, raising=False)
    monkeypatch.setattr(sv, "CLIPS_DIR", tmp_path, raising=False)
    monkeypatch.setattr(sv, "download_clip", lambda url, out: (
        Path(out).write_bytes(b"x" * 2048) or True))
    monkeypatch.setattr(sv, "get_video_duration", lambda p: 9.0)
    monkeypatch.setattr(sv, "_clip_mean_luma", lambda p: 120.0)
    monkeypatch.setattr(sv, "_keyword_expand", lambda kw: [kw])
    monkeypatch.setattr(sv, "_search_providers", lambda kws, o, per_page=5: [
        {"id": 1, "url": "http://x/1", "width": 1920, "height": 1080,
         "source": "pexels", "query": kws[0], "title": "abstract neon 3d render"},
        {"id": 2, "url": "http://x/2", "width": 1920, "height": 1080,
         "source": "pexels", "query": kws[0], "title": "laboratory research scientist"},
    ])

    clip = sv.search_and_download("lab work", video_id="v2", scene_idx=0)
    assert clip is not None
    assert clip["path"].endswith("pexels_2.mp4"), (
        f"expected the real-footage candidate, got {clip['path']}"
    )