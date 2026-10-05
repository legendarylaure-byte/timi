"""D1-D4 regression checks.

One test per defect, each negative-tested by mutating the source back. These exist
because the four defects were all *silently* wrong: D1 was believed to have no
enforcement at all when one existed untested, D2 and D3 were docstrings/behaviour
mismatches, and D4 was a scorer that could not rank anything.
"""
import ast
import inspect
import sys
from pathlib import Path

import pytest

AGENTS = Path(__file__).resolve().parents[1]


def _calls_named(src: str, name: str) -> bool:
    """True if `src` contains a real call to `name`.

    AST-based on purpose: docstrings and comments are not code, and this repo's
    convention is to name a retired thing in prose while explaining its removal.
    A substring check would report the explanation as the bug.
    """
    for node in ast.walk(ast.parse(src)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == name
        ):
            return True
    return False


def _module(name):
    """Import a module that needs the container's dependency set.

    Same rule as the other container-only tests: skip visibly on the host rather
    than add one more `ModuleNotFoundError` to the known-failing host list.
    """
    try:
        return __import__(name, fromlist=["*"])
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"{name} needs container deps: {e}")


# ---------------------------------------------------------------- D1: scene cap


def test_scene_cap_clamps_and_rescales_duration():
    """`_limit_scenes` was believed not to exist. It does, and it has no test.

    Two halves, because they can fail independently: the count is capped at the
    per-format ceiling, and each surviving scene's target_duration is scaled so
    the total runtime does not shrink when scenes are dropped.
    """
    main = _module("main")
    scenes = [{"target_duration": 4.0} for _ in range(12)]

    shorts = main._limit_scenes([dict(s) for s in scenes], "shorts")
    assert len(shorts) == 12, "12 is exactly the shorts ceiling; must pass through whole"

    longs = main._limit_scenes([dict(s) for s in scenes], "long")
    assert len(longs) == 12, "12 scenes is under the long ceiling; nothing dropped"

    over = [{"target_duration": 4.0} for _ in range(33)]
    clamped = main._limit_scenes(over, "long")
    assert len(clamped) == 20
    # 33 scenes dropped to 20 -> each must stretch by 33/20 to preserve runtime.
    assert clamped[0]["target_duration"] == pytest.approx(6.6, abs=0.05)


def test_scene_cap_is_not_silently_removed():
    """Negative test: with `_limit_scenes` neutered, 40 scenes would flow through.

    Guards the AGENTS.md lesson that a documented mechanism needs its own test --
    the clamp existed before this file did, untested the whole time.
    """
    main = _module("main")
    src = inspect.getsource(main._limit_scenes)
    assert "max_scenes" in src, "_limit_scenes lost its ceiling"

    ast.parse((AGENTS / "main.py").read_text())  # must stay importable


# ------------------------------------------------------- D2: strict title caps


def test_title_caps_are_strict_for_our_own_limits():
    """`<= cap` accepted a title of exactly the cap; the directive was strict.

    Also pins the deliberate exception: YouTube's own 100-char API cap stays
    inclusive, because that one is the platform's limit, not our display rule.
    """
    main = _module("main")
    pick = main._pick_best_title

    exactly_60 = "A" * 60
    assert len(pick([exactly_60], "fallback", "AI News", fmt="short")) < 60

    exactly_40 = "B" * 40
    assert len(pick([exactly_40], "fallback", "AI News", fmt="long")) < 40

    # 59 / 39 must survive untouched -- strict, not off-by-one-too-far.
    assert pick(["C" * 59], "fallback", "AI News", fmt="short") == "C" * 59
    assert pick(["D" * 39], "fallback", "AI News", fmt="long") == "D" * 39

    # No fmt -> the inclusive 100 cap, so exactly 100 is allowed.
    assert pick(["E" * 100], "fallback", "AI News") == "E" * 100


def test_title_truncation_cannot_loop_on_a_word_boundary():
    """The word-boundary cut can land exactly on the cap; the hard slice is the
    fallback that is guaranteed shorter. Without this the truncate step can
    return a title that `fits` still rejects.
    """
    main = _module("main")
    # One unbroken 200-char token: rsplit finds no space, so the cut must fall
    # back to the hard slice rather than returning a still-too-long title.
    out = main._pick_best_title(["F" * 200], "fallback", "AI News", fmt="short")
    assert len(out) < 60


# ------------------------------------------------- D3: watermark margin honesty


def test_watermark_margin_is_a_flat_margin_not_the_safe_band():
    """The docstring claimed "inside the safe box" while the band was discarded.

    A test that only reads the docstring would pass on the original bug, so this
    pins the actual arithmetic: a flat 3.5% of height, independent of format.
    """
    bp = _module("utils.brand_palette")

    for fmt in ("shorts", "long"):
        for height in (1080, 1920):
            pos = bp.watermark_position(1080, height, fmt)
            expected = round(height * 0.035)
            assert f"-{expected}:{expected}" in pos, (
                f"{fmt}@{height} margin is not the flat 3.5% it documents: {pos}"
            )

    # The dead call is gone. Checked via AST, not a substring: the docstring
    # deliberately NAMES safe_band() while explaining that it used to be called
    # and discarded, so a substring match on the source would flag the
    # explanation as the bug. Prose is excluded for the same reason
    # test_legacy_hexes_are_gone_from_runtime_source walks the AST.
    assert not _calls_named(inspect.getsource(bp.watermark_position), "safe_band"), (
        "watermark_position still calls safe_band (and discards it)"
    )
    # Positive check on the headline claim, not an absence check on a literal.
    # The absence form was broken twice by this file's own prose: the docstring
    # quotes the old wording to explain that it was removed, so "assert the old
    # phrase is absent" reports the explanation as the bug. Assert what the
    # first line now promises instead.
    first_line = (bp.watermark_position.__doc__ or "").strip().split("\n")[0]
    assert "fixed margin" in first_line, (
        f"docstring headline still promises something the code does not do: {first_line!r}"
    )

    # The helper itself must survive: content_box() and the existing brand tests
    # are its real consumers.
    assert callable(bp.safe_band)


# -------------------------------------------- D4: no ranking-incapable relevance


def test_stock_sort_has_no_ranking_incapable_relevance_term():
    """Every candidate from one search scored identically, so the term ranked
    nothing and ordering was pure jitter. Pin the deletion so it cannot return
    as a decorator.
    """
    sv = _module("utils.stock_video")

    assert not hasattr(sv, "_score_stock_relevance"), (
        "the per-query-constant relevance scorer is back; it cannot rank anything"
    )
    # AST, not substring: the ponytail comment above the sort deliberately
    # describes the removed scorer in prose.
    assert not _calls_named(
        (AGENTS / "utils" / "stock_video.py").read_text(), "_score_stock_relevance"
    )

    # The two live terms must remain: repeat penalty and per-video jitter are what
    # actually keep footage from repeating across videos.
    assert hasattr(sv, "_repeat_penalty")
    assert hasattr(sv, "_stable_jitter")


def test_relevance_scorer_could_not_rank_its_own_candidates():
    """Kept as a spec, not a behaviour: three candidates from ONE search all got
    the same score, so any ordering was the jitter's. This documents why the term
    was removed rather than tuned.
    """
    text = "ai art intelligence"
    keyword = "ai art intelligence"
    queries = ["ai art intelligence", "ai art intelligence", "ai art intelligence"]
    scores = {
        len(
            {w for w in text.split() if len(w) > 3} & set(q.split())
        ) / max(len({w for w in text.split() if len(w) > 3}), 1)
        for q in queries
    }
    assert scores == {1.0}, "one query -> one score -> nothing to rank"
    assert keyword == text


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))