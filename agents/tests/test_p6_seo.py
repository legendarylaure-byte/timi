"""P6: the SEO pass must be able to act, not just report.

The bug these lock down: `score_description_seo()` had no effect on anything.
It ran, it logged "Description missing: hashtags", and the video published with
the same description anyway. A scorer with no caller that can change an outcome
is a log line, so every test here asserts on which description SURVIVES.
"""

import pytest

import main


GOOD = "Watch the full breakdown here. #AI #Shorts #Tech Subscribe for more https://vyomai.cloud"

BARE = "A short explainer about neural networks."

# A description that misses ONE check. Needed by the comparison tests below: an
# original that is already perfect short-circuits before the retry, so a test
# built on GOOD never reaches the branch it is meant to cover. That made an
# earlier version of test_a_worse_retry_never_replaces_a_better_original VACUOUS
# -- it passed with the score comparison deleted entirely, because the retry was
# never called in the first place.
PARTIAL = "A short explainer about neural networks. #AI #Shorts #Tech Subscribe for more."

# Same score as PARTIAL (one missing check, same length band) but different
# wording, so "which description survived" is observable as text rather than as
# a no-op string comparison.
PARTIAL_ALT = "Neural networks, explained simply. #AI #Shorts #ML Subscribe for more."


def _polish(monkeypatch, retry_body, fmt="shorts"):
    """Patch the retry's LLM call, return the list of seo_fixes it received.

    NOTE: the original description arrives as an argument, not as a call, so
    there is exactly ONE generate_description call per _seo_polish_description
    and it is always the retry. Asserting `calls == [None]` would be wrong --
    an empty list is what "no retry happened" looks like from here.
    """
    calls = []

    def fake(title, script, category, format_type="shorts", **kw):
        calls.append(kw.get("seo_fixes"))
        return {"full_description": retry_body}

    monkeypatch.setattr(main, "generate_description", fake)
    monkeypatch.setattr(main, "suggest_seo_improvements", lambda c, f: ["Add #Shorts in the first line"])
    return calls


def test_a_perfect_description_is_never_regenerated(monkeypatch):
    """The happy path must cost exactly ONE LLM call.

    This is the "do not add a second call per video for nothing" guard: the retry
    is bounded, and a description that already passes is the common case on the
    scripted paths that assemble their own CTA and hashtags.
    """
    calls = _polish(monkeypatch, GOOD)
    result, score = main._seo_polish_description(
        {"full_description": GOOD}, "script", "AI News", "shorts", "Title", "topic"
    )
    assert result["full_description"] == GOOD
    assert calls == [], "a passing description must not trigger a retry"
    assert score["missing"] == []


def test_a_missing_check_triggers_exactly_one_retry_that_wins(monkeypatch):
    calls = _polish(monkeypatch, GOOD)
    result, score = main._seo_polish_description(
        {"full_description": BARE}, "script", "AI News", "shorts", "Title", "topic"
    )
    assert result["full_description"] == GOOD
    assert score["missing"] == []
    # Exactly ONE call, and it is the retry. Zero would mean the finding was
    # ignored; more than one would mean the bound is not actually a bound.
    assert len(calls) == 1, "expected exactly one retry, not zero and not a loop"
    # The retry prompt must be told WHAT failed, or it is just a second roll of
    # the same dice.
    assert calls[0], "the retry must carry the scorer's findings"
    assert any("call to action" in f for f in calls[0])


def test_a_worse_retry_never_replaces_a_better_original(monkeypatch):
    """A retry that scores LOWER is discarded.

    Regression risk, not theory: the retry prompt asks for structure, and an LLM
    handed a "you failed these checks" instruction can easily satisfy them by
    padding the description with filler links. Shipping that is worse than
    shipping the original.
    """
    _polish(monkeypatch, BARE)
    result, score = main._seo_polish_description(
        {"full_description": PARTIAL}, "script", "AI News", "shorts", "Title", "topic"
    )
    assert result["full_description"] == PARTIAL
    assert score["missing"] == ["links"], "precondition: the retry must actually run"


def test_an_equal_scoring_retry_is_discarded(monkeypatch):
    """Equal score = no gain, and it cost a second LLM call. Keep the original.

    Ties are the common case, so this is the branch that decides whether the
    retry is cheap or expensive in practice.
    """
    _polish(monkeypatch, PARTIAL_ALT)
    result, _score = main._seo_polish_description(
        {"full_description": PARTIAL}, "script", "AI News", "shorts", "Title", "topic"
    )
    # Compared against PARTIAL, not against PARTIAL_ALT: an identical string
    # would pass whether the retry was kept or discarded.
    assert result["full_description"] == PARTIAL


def test_a_crashing_retry_keeps_the_original_and_does_not_raise(monkeypatch):
    """A description must not be able to fail the whole video."""
    monkeypatch.setattr(main, "score_description_seo", lambda d: {"score": 40, "missing": ["hashtags"]})
    monkeypatch.setattr(main, "suggest_seo_improvements", lambda c, f: [])

    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(main, "generate_description", boom)
    original = {"full_description": BARE}
    result, _ = main._seo_polish_description(original, "s", "AI News", "shorts", "T", "t")
    assert result is original


def test_a_crashing_scorer_keeps_the_description_and_does_not_raise(monkeypatch):
    """If the scorer itself throws we must NOT retry.

    A broken scorer is not a finding about the description. Retrying off a
    crashed scorer means regenerating descriptions for a bug in the audit, which
    is how a cheap fix turns into a bill.
    """
    def boom(_d):
        raise ValueError("bad regex")

    monkeypatch.setattr(main, "score_description_seo", boom)

    # The canary is a CALL LOG, not a raised error. An earlier version raised
    # AssertionError, which the helper's own `except Exception` around the retry
    # swallowed and logged as a retry failure -- so the test passed whether or
    # not the retry fired. A canary the code under test catches is not a canary.
    fired = []

    def record(*a, **k):
        fired.append(1)
        return {"full_description": GOOD}

    monkeypatch.setattr(main, "generate_description", record)
    original = {"full_description": BARE}
    result, _ = main._seo_polish_description(original, "s", "AI News", "shorts", "T", "t")
    assert fired == [], "retry must not fire when the scorer crashed"
    assert result["full_description"] == BARE


def test_tags_are_derived_from_the_chosen_title_not_the_raw_topic(monkeypatch):
    """Tags come from the published title's words, not the topic's.

    An earlier version of this test could not fail: it asserted on the helper's
    tag assignment, but the CALL SITE immediately overwrites `desc_result["tags"]`
    afterwards, so the helper's value never survives to be observed. The mutation
    it was written to catch (swapping `best_title` for `topic` at the call site)
    therefore passed. Assert on the call site instead, where the value is final.
    """
    import inspect

    body = inspect.getsource(main.generate_short_video) + inspect.getsource(main.generate_long_video)
    for fmt in ("shorts", "long"):
        assert f'get_optimized_tags(category, "{fmt}", best_title)' in body, (
            f"{fmt}: tags must be built from the chosen title"
        )
        assert f'get_optimized_tags(category, "{fmt}", topic)' not in body, (
            f"{fmt}: tags are still built from the raw topic"
        )


def test_the_title_is_chosen_before_the_description_is_written():
    """P6a, enforced on the SOURCE rather than by running a video.

    The ordering bug was structural: `generate_description(title=topic)` ran, and
    only ~60 lines later `_pick_best_title()` produced the title actually
    published. YouTube shows the description's first ~150 chars above "Show
    more", so the visible hook could contradict the real title. Asserting this on
    source order is what catches a future refactor that reorders them again --
    running a real pipeline to observe the order would cost an LLM call and a
    render to learn something a line count can prove.
    """
    import inspect

    src = inspect.getsource(main)
    for fn in (main.generate_short_video, main.generate_long_video):
        body = inspect.getsource(fn)
        assert body.count("_pick_best_title(") == 1, (
            f"{fn.__name__}: expected exactly one _pick_best_title call, "
            f"found {body.count('_pick_best_title(')}"
        )
        assert "title=best_title" in body, f"{fn.__name__}: description must use the chosen title"
        # No description may be written from the raw topic again.
        assert "title=topic,\n            script=script_text" not in body, (
            f"{fn.__name__}: description is still generated from the raw topic"
        )
    # Both call sites, not just one.
    assert src.count("desc_result, seo_score = _seo_polish_description(") == 2


# --- A winning retry replaces the WHOLE description, so everything assembled
# after generation has to be re-applied to it. Both of these were real bugs that
# survived because no test covered the "retry wins" branch for a category that
# has affiliate programs (9 live ones, matching AI Explained / Code & Build).

AFFILIATE_SCRIPT = "We use the OpenAI API and GPT models for this."
AFFILIATE_MARKER = "affiliate links"


def _winning_retry(monkeypatch, retry_body: str = GOOD) -> dict:
    """Force the retry branch to WIN by making the original score badly.

    Returned desc_result is what _seo_polish_description actually hands back, so
    the assertions run against the real post-retry object rather than a stub.
    """
    def fake_gen(**kw):
        assert kw.get("seo_fixes"), "retry must be told what the scorer found"
        return {"full_description": retry_body, "tags": []}
    monkeypatch.setattr(main, "generate_description", fake_gen)
    return {"full_description": BARE, "tags": []}


def test_a_winning_retry_keeps_the_affiliate_disclosure(monkeypatch):
    """The FTC disclosure is appended AFTER generation. A retry returns a fresh
    dict from generate_description, so without _assemble_description on the retry
    the disclosure silently disappears from published descriptions."""
    monkeypatch.setattr(main, "build_affiliate_section",
                        lambda script, category="": "\n\n*Some links are affiliate links.*")
    original = _winning_retry(monkeypatch)
    desc, _ = main._seo_polish_description(
        original, AFFILIATE_SCRIPT, "AI Explained", "shorts", "T", "topic")
    assert AFFILIATE_MARKER in desc["full_description"], (
        "a winning SEO retry dropped the affiliate disclosure"
    )


def test_a_winning_retry_is_sanitized(monkeypatch):
    """sanitize_description() is what stops YouTube's 400 invalidDescription.
    A retry that skips it can ship control characters the API rejects."""
    monkeypatch.setattr(main, "build_affiliate_section", lambda script, category="": "")
    original = _winning_retry(monkeypatch, retry_body=GOOD + "\x00\x07 control chars")
    desc, _ = main._seo_polish_description(
        original, AFFILIATE_SCRIPT, "AI Explained", "shorts", "T", "topic")
    assert "\x00" not in desc["full_description"] and "\x07" not in desc["full_description"], (
        "a winning SEO retry shipped unsanitized control characters"
    )


def test_the_long_retry_keeps_chapter_timestamps(monkeypatch):
    """generate_description only emits chapters when it is given `scenes`, and
    only for long format. A retry without scenes drops the whole chapter list."""
    import inspect
    body = inspect.getsource(main.generate_long_video)
    assert body.count("parse_scenes_from_storyboard(str(storyboard), \"long\")") == 2, (
        "the long SEO retry must be passed scenes, or it drops every chapter stamp"
    )
