"""Self-check for P3 hook rotation.

Run: python -m utils.hook_selfcheck

The old suggest_hook_formula() started at FORMULAS[0] and only replaced it when a
formula averaged views > 0, so on a channel where nearly every video has 0 views it
returned the same formula on every single run — every video opened identically.
"""
import json

import utils.hook_tester as ht


def _write(data):
    ht._save_results(data)


def test_returns_same_formula_for_a_known_category():
    _write({})
    a = ht.suggest_hook_formula("AI News")
    b = ht.suggest_hook_formula("AI News")
    assert a == b, f"rotation is not stable across calls: {a} vs {b}"


def test_rotation_varies_across_categories():
    _write({})
    picks = {ht.suggest_hook_formula(c) for c in
             ["AI News", "Nepal News", "Programming & Software", "Science & Technology"]}
    assert len(picks) > 1, f"every category got the same formula: {picks}"


def test_all_zero_views_does_not_collapse_to_one_formula():
    # Exactly the live situation: results exist, but every view count is 0.
    data = {c: {f: [{"views": 0, "retention": 0.2}] for f in ht.FORMULAS}
            for c in ["AI News", "Nepal News", "Programming & Software", "Science & Technology"]}
    _write(data)
    picks = {ht.suggest_hook_formula(c) for c in data}
    assert len(picks) > 1, f"zero-view data collapsed to one formula: {picks}"


def test_real_signal_wins():
    data = {"AI News": {
        "question": [{"views": 10}, {"views": 20}],        # avg 15
        "bold_claim": [{"views": 400}, {"views": 600}],    # avg 500
    }}
    _write(data)
    assert ht.suggest_hook_formula("AI News") == "bold_claim", \
        f"real signal ignored: got {ht.suggest_hook_formula('AI News')}"


def test_thin_signal_is_not_trusted():
    # One 5000-view video is not a trend; must not lock the category to that formula.
    data = {"AI News": {"bold_claim": [{"views": 5000}]}}
    _write(data)
    assert ht.suggest_hook_formula("AI News") != "bold_claim", \
        "a single video locked the formula"


def test_salt_varies_hook_across_videos_in_one_category():
    # The per-video rotation fix: without a salt every video in a category opened
    # the same way. Distinct video_ids must yield more than one formula.
    _write({})
    picks = {ht.suggest_hook_formula("AI News", salt=f"short-20260926-{i}")
             for i in range(10)}
    assert len(picks) > 1, f"salt did not vary the hook within a category: {picks}"


def test_salt_is_stable_for_the_same_video():
    # A retry/re-run of one video must not silently change its hook.
    _write({})
    a = ht.suggest_hook_formula("AI News", salt="short-20260926-1")
    b = ht.suggest_hook_formula("AI News", salt="short-20260926-1")
    assert a == b, f"same video_id produced two hooks: {a} vs {b}"


def test_salt_does_not_override_real_signal():
    # Rotation only applies when there's no usable signal. A real winner must win
    # regardless of which video is asking.
    data = {"AI News": {
        "question": [{"views": 10}, {"views": 20}],        # avg 15
        "bold_claim": [{"views": 400}, {"views": 600}],    # avg 500
    }}
    _write(data)
    picks = {ht.suggest_hook_formula("AI News", salt=f"short-{i}") for i in range(6)}
    assert picks == {"bold_claim"}, f"salt overrode real signal: {picks}"


if __name__ == "__main__":
    ht._save_results({})
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    ht._save_results({})
    print("hook selfcheck OK")
