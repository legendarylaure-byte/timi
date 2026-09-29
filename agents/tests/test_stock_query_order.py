"""The scene's own words must outrank the category vocabulary when searching stock.

This is a regression lock for a defect that was measured, not assumed. asset_router
used to send ", ".join(asset_keywords) as its FIRST query. That blob mixes the
scene's own title with the owner-approved CATEGORY_VISUAL_KEYWORDS, and Pexels
answers for the dominant theme: across 5 live audit scenes the focused title
query and the joined query shared zero clips on 3 of 5 (Jaccard 0.0, all 5
focused clips discarded), while the join matched the category vocabulary
instead. Every scene in a category therefore got near-identical footage.

The failure was invisible to _score_stock_relevance, which scores all five
candidates from one query identically (spread 0.0) because it compares a
candidate's query field against the very keyword we just sent. So the number
looked like it was ranking when it was not.

These tests assert the ORDER of attempted queries, which is the actual invariant.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils import asset_router


def _scene(**over):
    # Realistic shape: scene_parser._infer_keywords() returns
    # [title, tech[:3], visual[:3]] and _apply_category_style appends the
    # category vocabulary. A one-keyword scene would make kw_list[0] equal the
    # join and quietly make the whole ordering test meaningless.
    s = {
        "keyword": "Quantum Error Correction Reaches a Milestone",
        "description": "A logical qubit held long enough to run a full algorithm.",
        "asset_keywords": [
            "quantum error correction milestone",
            "quantum computing",
            "GPU",
            "training",
            "floating quantum particles over a processor",
            "futuristic laboratory",
            "glowing circuit macro",
        ],
        "render_type": "stock",
        "asset_type": "STOCK_FOOTAGE",
    }
    s.update(over)
    return s


@pytest.fixture
def calls(monkeypatch, tmp_path):
    """Record every query asset_router tries, and fail the FIRST one so the loop
    stops there. One hit is enough to prove which query wins."""
    seen = []
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")

    def fake(query, orientation="landscape", duration=8.0, video_id=""):
        seen.append(query)
        if len(seen) == 1:
            return str(clip)
        return None

    monkeypatch.setattr(asset_router, "_get_stock_clip", fake)
    return seen


def test_scene_words_are_tried_before_the_category_join(calls):
    asset_router._render_scene_inner(_scene(), "v1", 0, "long", 5.0)
    assert calls, "no stock search was attempted at all"
    joined = ", ".join(_scene()["asset_keywords"])
    assert calls[0] == _scene()["asset_keywords"][0], (
        f"first query was {calls[0]!r}, not the scene's own words -- the "
        f"category vocabulary is outranking the topic again"
    )
    assert calls[0] != joined, "the join is being sent first again"


def test_category_join_is_still_reachable_as_a_fallback(monkeypatch, tmp_path):
    """Owner-approved CATEGORY_VISUAL_KEYWORDS must survive as the look. This is
    not a deletion of the category vocabulary, it is a change of precedence --
    so the join has to remain a query we actually try."""
    seen = []
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"x")

    def only_join_answers(query, orientation="landscape", duration=8.0, video_id=""):
        seen.append(query)
        joined = ", ".join(_scene()["asset_keywords"])
        return str(clip) if query == joined else None

    monkeypatch.setattr(asset_router, "_get_stock_clip", only_join_answers)
    asset_router._render_scene_inner(_scene(), "v1", 0, "long", 5.0)
    assert seen[0] != ", ".join(_scene()["asset_keywords"])
    assert ", ".join(_scene()["asset_keywords"]) in seen, (
        "the category join is never tried, so the approved category look is lost "
        "whenever the scene's own words return nothing"
    )


def test_single_keyword_scene_is_not_searched_twice(monkeypatch):
    """The one duplicate that is actually reachable.

    clean_scene_keywords() already dedupes and preserves order, so a multi-keyword
    scene can never repeat -- which is why an earlier version of this test (using a
    scene with "ai" three times) passed with the dedupe removed. It asserted
    nothing. A scene whose only surviving keyword is X produces
    attempts == [X, "X", *empty], because ", ".join(["X"]) == "X".

    Costs a Pexels call and a rate-limit slot to search the same thing twice.
    """
    seen = []
    monkeypatch.setattr(asset_router, "get_video_model", lambda: None)
    monkeypatch.setenv("ENABLE_STOCK_FOOTAGE", "true")
    monkeypatch.setattr(
        asset_router, "_get_stock_clip",
        lambda q, orientation="landscape", duration=8.0, video_id="": seen.append(q) or None,
    )
    asset_router._render_scene_inner(
        _scene(asset_keywords=["kathmandu"]), "v1", 0, "long", 5.0)
    assert seen == ["kathmandu"], f"expected one query, got {seen}"
