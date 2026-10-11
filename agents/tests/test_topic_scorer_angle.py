"""Niche-angle guard for topic selection (WS5 Phase 4).

The channel over-produced generic "What is X" overviews. Phase 4 makes the
scorer rank a broad opener BELOW a specific-angle title in the same category,
so rank_topics() sends the specific one to the pipeline first. Pure function,
no LLM.
"""
from utils.topic_scorer import (
    GENERIC_OPENERS,
    _score_viral_potential,
    score_topic,
)


def test_generic_opener_scores_below_specific_angle():
    generic = _score_viral_potential("What is quantum computing?")
    specific = _score_viral_potential("Why quantum computers fail at simple math")
    assert generic < specific, f"generic {generic} should rank below specific {specific}"


def test_generic_penalty_is_bounded():
    # A generic title must still clear the 30/100 rank_topics floor: penalty
    # must not turn a producible topic into a dropped one.
    ts = score_topic("Introduction to neural networks", "Science & Technology")
    assert ts.total >= 30, f"penalised generic topic dropped below floor: {ts.total}"
    assert "generic overview title" in ts.reasoning


def test_specific_titles_are_unaffected():
    # None of these start with a generic opener, so none take the penalty.
    for title in ("RAG Architecture Explained Simply",
                  "Build a RAG App in 10 Minutes",
                  "The GPU Bottleneck Nobody Talks About"):
        assert not title.lower().startswith(GENERIC_OPENERS), title
