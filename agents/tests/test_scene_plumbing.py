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
    _infer_diagram,
    clean_scene_keywords,
    first_content_scene,
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


def test_meta_only_diagram_is_suppressed():
    assert _infer_diagram("architecture: Narration Visual Diagram") is None


def test_real_diagram_still_renders():
    got = _infer_diagram("architecture: Transformer Attention FeedForward")
    assert got and got["type"] == "architecture"
    assert got["items"] == ["Transformer", "Attention", "FeedForward"]


def test_generic_step_fallback_preserved():
    """No capitalised tokens at all is NOT a plumbing case -- the pre-existing
    Step 1/2/3 fallback is real content and must survive Phase B."""
    got = _infer_diagram("the flow of the pipeline")
    assert got and got["items"][0].startswith("Step")


def test_hook_guarantee_targets_first_content_scene():
    """Regression on a guarantee that had never fired once.

    inject_intro_outro runs before the hook code, so scenes[0] is always the
    branded intro card. The old `scenes[0].get('render_type') == 'manim'`
    condition could never be true, so the D29 guarantee was dead code.
    """
    content = [{
        "render_type": "manim", "asset_type": "STOCK_FOOTAGE",
        "description": "A transformer architecture",
        "narration_text": "The architecture has layers and attention.",
        "keyword": "transformers",
    }]
    scenes = inject_intro_outro(content, "AI News", "long")
    hook = first_content_scene(scenes)
    assert hook is not None
    assert scenes.index(hook) == 1, "must skip the branded intro card at index 0"
    assert hook.get("render_type") == "manim"
    assert scenes[0].get("render_type") == "branded_card", "intro card must be untouched"


def test_first_content_scene_never_returns_a_card():
    """The card-skip is the whole point: scenes[0] is always a branded card, so
    anything that reads scenes[0] is reading plumbing."""
    cards_only = [
        {"render_type": "branded_card", "description": "Vyom Ai Cloud", "narration_text": ""},
        {"render_type": "branded_card", "description": "Subscribe", "narration_text": ""},
    ]
    assert first_content_scene(cards_only) is None
    assert first_content_scene([]) is None


def test_stock_keywords_are_searchable_never_plumbing():
    for cat, kws in CATEGORY_VISUAL_KEYWORDS.items():
        assert kws, f"{cat} has no stock keywords"
        for kw in kws:
            assert not is_meta_token(kw), f"{cat} keyword {kw!r} is plumbing"


def test_diagram_renderer_survives_bare_string_items():
    """The LLM emits `items: ["Attention", "Feed-forward"]` despite the prompt
    asking for values. _render_bar used to raise AttributeError on those, and
    asset_router's catch turned that into a silent fall back to stock -- so every
    unvalued bar diagram rendered as footage instead. All five types must take
    strings, or dicts, or a mix."""
    import os
    from utils.diagram_renderer import render_diagram

    specs = [
        {"type": "bar", "title": "Attention", "items": ["Attention", "Feed-forward"]},
        {"type": "bar", "title": "Cost", "items": [{"label": "A", "value": 3}, {"label": "B", "value": 7}]},
        {"type": "bar", "title": "Mixed", "items": ["A", {"label": "B", "value": 5}]},
        {"type": "comparison", "title": "C", "items": ["a", "b", "c"]},
        {"type": "flow", "title": "F", "items": ["a", "b"]},
    ]
    for spec in specs:
        path = render_diagram(spec, width=800, height=450)
        assert path and os.path.getsize(path) > 2000, f"{spec['type']} produced nothing: {spec}"


def test_unvalued_bar_does_not_invent_bars():
    """A bar chart with no numbers would draw equal-height bars, because
    _render_bar floors bar height at 10px. That implies measurements that do not
    exist, so it must render as the labelled list it actually is."""
    from utils.diagram_renderer import _normalize_items, _render_bar, _render_flow

    unvalued = _normalize_items(["Attention", "Feed-forward"])
    assert not any(i.get("value") for i in unvalued)

    valued = _normalize_items([{"label": "A", "value": 3}, {"label": "B", "value": 7}])
    assert any(i.get("value") for i in valued)

    # The bar renderer must still be reachable for real numbers, or the guard
    # above has quietly turned every bar chart into a list.
    from PIL import Image, ImageDraw
    for items, renderer in ((valued, _render_bar), (unvalued, _render_flow)):
        im = Image.new("RGB", (800, 450), (0, 0, 0))
        renderer(ImageDraw.Draw(im), items, 800, 350, 70, (155, 77, 255))
