"""Phase B: pipeline plumbing must never reach the screen.

The owner review found videos "buried under text". Two of those words were not
content at all -- they were the pipeline's own field names and routing labels
reaching the frame, which is what these tests lock down.

Each test is negative-tested: revert the fix and it fails.
"""
import sys
import pathlib

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from utils.scene_parser import (  # noqa: E402
    CATEGORY_VISUAL_KEYWORDS,
    clean_scene_keywords,
    is_meta_token,
)
from utils.series_router import inject_intro_outro  # noqa: E402


def test_plumbing_tokens_are_recognised():
    for tok in ("intro", "channel_brand", "narration", "Narration_Text", "manim", "MANIM"):
        assert is_meta_token(tok), f"{tok} should be treated as plumbing"
    for tok in ("data center", "neon network", "transformer", "kathmandu"):
        assert not is_meta_token(tok), f"{tok} is real content, must survive"


def test_clean_scene_keywords_keeps_order_and_drops_plumbing():
    got = clean_scene_keywords(["intro", "data center", "channel_brand", "neon network", "manim"])
    assert got == ["data center", "neon network"]
    # all-plumbing returns empty so the caller picks its own honest default
    # rather than silently keeping a meta word
    assert clean_scene_keywords(["intro", "channel_brand"]) == []


def test_plumbing_never_becomes_the_ltx_prompt():
    """The actual leak. asset_router falls back to joining asset_keywords when a
    scene has no ltx_prompt and no description, so an all-plumbing keyword list
    used to become the render prompt verbatim."""
    import utils.asset_router as ar

    captured = {}
    original = ar._render_scene_inner

    def spy(scene, *a, **k):
        captured["kw"] = list(scene.get("asset_keywords", []))
        return None  # force the fallback path, we only care what it was handed

    ar._render_scene_inner = spy
    try:
        ar.dispatch_scene(
            {
                "render_type": "stock",
                "asset_type": "STOCK_FOOTAGE",
                # no ltx_prompt, no description -> this list IS the prompt
                "asset_keywords": ["intro", "channel_brand", "narration"],
                "narration_text": "some words",
            },
            "vid_test", 0, "long", "AI News",
        )
    finally:
        ar._render_scene_inner = original

    leaked = [k for k in captured["kw"] if is_meta_token(k)]
    assert not leaked, f"plumbing reached the prompt fallback: {leaked}"
    assert captured["kw"], "keyword list should have been replaced with a real default, not emptied"


def test_series_router_does_not_inject_plumbing_keywords():
    scenes = inject_intro_outro(
        [{"render_type": "stock", "description": "d", "narration_text": "n"}],
        "AI News", "long",
    )
    for s in (scenes[0], scenes[-1]):  # intro card + outro card
        assert not [k for k in s.get("asset_keywords", []) if is_meta_token(k)], (
            f"card injects plumbing: {s.get('asset_keywords')}"
        )
    # the card's real text still comes from description -- we did not break it
    assert scenes[0].get("description") == "Vyom Ai Cloud"


def test_stock_keywords_are_searchable_never_plumbing():
    for cat, kws in CATEGORY_VISUAL_KEYWORDS.items():
        assert kws, f"{cat} has no stock keywords"
        for kw in kws:
            assert not is_meta_token(kw), f"{cat} keyword {kw!r} is plumbing"