"""Self-check for the P6 title_tester fixes.

Run: python -m utils.title_selfcheck
"""
import os
import tempfile

import utils.title_tester as tt


def test_starts_at_the_published_variant():
    """The old code hardcoded current_index=0 while seeding results with
    initial_title, so a video published as variants[2] advanced to variants[1]."""
    variants = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    d = tempfile.mkdtemp()
    old = tt.TEST_DATA_DIR
    tt.TEST_DATA_DIR = d
    try:
        test = tt.start_title_test("vid1", variants, "C")
        assert test["current_index"] == 2, f"started at {test['current_index']}, want 2"
        assert tt._test_path("vid1").endswith("vid1.json")
    finally:
        tt.TEST_DATA_DIR = old


def test_unknown_initial_title_does_not_crash():
    d = tempfile.mkdtemp()
    old = tt.TEST_DATA_DIR
    tt.TEST_DATA_DIR = d
    try:
        test = tt.start_title_test("vid2", [{"title": "A"}], "something else")
        assert test["current_index"] == 0
    finally:
        tt.TEST_DATA_DIR = old


def test_winner_is_never_fabricated():
    """All-None results used to return a 'first_available' winner with ctr 0,
    which reads as a real experimental outcome."""
    out = tt._pick_winner({"results": {"A": None, "B": None}, "views_at_stage_start": {}})
    assert out["method"] == "insufficient_data", out
    assert out["title"] is None, f"invented a winner: {out}"


def test_winner_picks_highest_views_per_hour():
    test = {
        "results": {"A": 100, "B": 400, "C": 200},
        "views_at_stage_start": {"A": 0, "B": 100, "C": 0},
    }
    out = tt._pick_winner(test)
    assert out["title"] == "B", out
    assert out["method"] == "highest_views_per_hour", out
    assert out["views_per_hour"] > 0, out


def test_sync_needs_no_impressions_key():
    """fetch_video_stats() never returns impressions/title/ctr, so the old guard
    skipped every video. The new one only needs viewCount."""
    import inspect
    src = inspect.getsource(tt.sync_title_ctr_from_youtube)
    # Match actual code, not the docstring that explains the old behaviour.
    assert 'stats.get("impressions")' not in src, "still gating on impressions (always absent)"
    assert 'stats.get("title"' not in src, "still reading a title key that never exists"
    assert "record_title_ctr" not in src, "still writing CTR we cannot obtain"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    print("title selfcheck OK")
