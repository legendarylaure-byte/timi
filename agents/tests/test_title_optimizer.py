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
