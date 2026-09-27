"""Tests for title_optimizer.is_garbage_title -- guards against publishing raw
news-feed / debug debris as a video title.

Live precedent: "long-20260925-1" published on YouTube/TikTok/FB/IG as
  "AI News Update: GRIEF 97%x2, 91% \U0001F534 75%+ x55 \U0001F534 STREAM 392"
which is a rolling live-blog headline, not a title.
"""
import pytest

from utils.title_optimizer import is_garbage_title


# The exact string that shipped. If this ever passes, the guard regressed.
REAL_GARBAGE = "AI News Update: GRIEF 97%x2, 91% \U0001F534 75%+ x55 \U0001F534 STREAM 392"


@pytest.mark.parametrize("title", [
    REAL_GARBAGE,
    "GRIEF 97%x2 and rising",          # repetition counter
    "Breaking: 91% surge x55",          # counter with a space
    "Live STREAM 392 coverage",         # live-blog ticker token
    "Neural nets \U0001F680 explained",  # emoji -> renders as .notdef boxes
    "50% 60% 70% 80%",                 # stat soup, no prose
    "",                                 # empty
    "   ",                              # whitespace only
])
def test_rejects_garbage_titles(title):
    assert is_garbage_title(title) is True


@pytest.mark.parametrize("title", [
    "How Neural Networks Actually Learn",
    "Pixel 2 Camera Review: Why It Still Wins",
    "GPT-4 vs Claude: A Practical Comparison",
    "3D Printing: 5 Facts You Did Not Know",
    "Kubernetes Crash Course For Beginners",
    "The 5 Most Common Python Mistakes",
])
def test_accepts_real_titles(title):
    assert is_garbage_title(title) is False


def test_pixel_2_is_not_mistaken_for_counter_x2():
    """The neg lookbehind must not read the 'x' inside 'Pixel' as a counter."""
    assert is_garbage_title("Pixel 2 Camera Review: Why It Still Wins") is False


def test_none_is_garbage():
    assert is_garbage_title(None) is True


def test_pick_best_title_falls_back_to_topic_when_all_variants_garbage():
    """End-to-end on the real choke point: every LLM variant echoing the live
    blog must be dropped, leaving the topic the script was written from."""
    from main import _pick_best_title
    garbage = [REAL_GARBAGE, "GRIEF 97%x2 x55 \U0001F534", {"title": "Live STREAM 392"}]
    topic = "How Neural Networks Actually Learn"
    assert _pick_best_title(garbage, topic, "AI News") == topic


def test_pick_best_title_keeps_good_variant_among_garbage():
    """A real variant must still win when mixed with debris."""
    from main import _pick_best_title
    variants = [REAL_GARBAGE, "How Neural Networks Actually Learn"]
    assert _pick_best_title(variants, "fallback topic", "AI News") == "How Neural Networks Actually Learn"


# --------------------------------------------------------------------------
# Per-format length caps
#
# Shorts and longs have different display surfaces. A Shorts title is read on a
# phone above a vertical video and is cut off in the feed past ~60 chars; a
# long-form title loses its second half past ~40. Both were unconstrained and
# the 100-char YouTube API cap was the only limit, so titles routinely ran long.
# --------------------------------------------------------------------------

def _pad(word: str, n: int) -> str:
    return " ".join([word] * n)


def test_short_title_is_capped_at_60():
    from main import _pick_best_title
    long_one = _pad("quantum", 14)          # 96 chars
    assert len(long_one) > 60
    out = _pick_best_title([long_one], "fallback", "AI News", "short")
    assert len(out) <= 60, f"shorts title {len(out)} chars: {out!r}"


def test_long_title_is_capped_at_40():
    from main import _pick_best_title
    long_one = _pad("transformer", 10)      # 111 chars
    assert len(long_one) > 40
    out = _pick_best_title([long_one], "fallback", "AI News", "long")
    assert len(out) <= 40, f"long title {len(out)} chars: {out!r}"


def test_unknown_format_keeps_the_100_char_api_cap():
    """Backwards compatible: no fmt means the original 100-char behaviour."""
    from main import _pick_best_title
    long_one = _pad("model", 30)            # 149 chars
    out = _pick_best_title([long_one], "fallback", "AI News")
    assert len(out) <= 100, f"{len(out)} chars"
    assert len(out) > 60, "unknown format should not inherit the short cap"


def test_fitting_variant_beats_longer_higher_scoring_one():
    """A truncated winner is worse than a slightly lower-scoring title that fits.

    The scorer rewards power words and length; without a length shortlist the
    top-scored variant always won and then got chopped mid-word.
    """
    from main import _pick_best_title
    long_scoring = "The SHOCKING Truth About AI That Nobody Tells You About Transformers"
    short_fitting = "Why AI Transformers Fail"
    assert len(long_scoring) > 60
    out = _pick_best_title([long_scoring, short_fitting], "fallback", "AI News", "short")
    assert out == short_fitting, f"picked {out!r}"


def test_truncation_never_leaves_a_dangling_word():
    from main import _pick_best_title
    filler = " ".join(["alpha"] * 20)       # no spaces near the boundary to test
    out = _pick_best_title([filler], "fallback", "AI News", "long")
    assert out == out.strip()
    assert not out.endswith(" ") and len(out) <= 40
