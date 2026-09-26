"""Tests for quality_scorer.py"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_llm():
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = """
        {
            "overall_score": 78,
            "breakdown": {
                "age_appropriateness": 85,
                "educational_value": 72,
                "engagement_potential": 80,
                "language_safety": 90,
                "creativity": 65,
                "pacing": 75
            },
            "flags": [],
            "recommendation": "approve",
            "feedback": "Good tech educational content"
        }
        """
        yield m


@pytest.fixture
def mock_firebase():
    with patch("utils.quality_scorer.update_agent_status"), \
         patch("utils.quality_scorer.log_activity"):
        yield


def test_score_content_returns_all_keys(mock_llm, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Test script about AI", "Red Apple", "AI Explained", "shorts")
    assert "overall_score" in result
    assert "breakdown" in result
    assert "recommendation" in result
    assert "feedback" in result


def test_score_content_breakdown_has_all_dimensions(mock_llm, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Test script", "Title", "Science", "shorts")
    dims = ["age_appropriateness", "educational_value", "engagement_potential",
            "language_safety", "creativity", "pacing"]
    for d in dims:
        assert d in result["breakdown"], f"Missing dimension: {d}"


def test_score_content_numeric_range(mock_llm, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Test", "Title", "General", "shorts")
    assert 0 <= result["overall_score"] <= 100


def test_score_content_fallback_on_parse_failure(mock_firebase):
    """When LLM returns unparseable JSON, fallback should still return valid dict."""
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = "NOT JSON AT ALL"
    from utils.quality_scorer import score_content
    result = score_content("Test script here", "Title", "Category", "shorts")
    assert isinstance(result, dict)
    assert "overall_score" in result
    assert result["overall_score"] >= 0


def test_score_content_empty_script(mock_llm, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("", "Empty", "General", "shorts")
    assert isinstance(result, dict)


def test_score_content_valid_json_missing_overall_score(mock_firebase):
    """Regression: 2026-09-25 "FAILED at long_video_pipeline: [quality_scoring]
    'overall_score'". extract_json() does no schema validation, so an LLM that
    returns well-formed JSON missing a key used to raise an uncaught KeyError at
    `result['overall_score']` (quality_scorer.py) / `quality["overall_score"]`
    (main.py save_checkpoint) and kill the whole video pipeline.
    Must fall back, not crash."""
    from utils.quality_scorer import score_content
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = '{"breakdown": {"clarity": 80}, "feedback": "partial"}'
        result = score_content("A reasonably long script about neural networks.", "Title", "AI", "long")
    assert isinstance(result, dict)
    for key in ("overall_score", "breakdown", "flags", "recommendation"):
        assert key in result, f"fallback dropped required key: {key}"
    assert 0 <= result["overall_score"] <= 100


def test_score_content_valid_json_missing_breakdown(mock_firebase):
    """Partial dict missing a different key must also fall back."""
    from utils.quality_scorer import score_content
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = '{"overall_score": 91}'
        result = score_content("A reasonably long script about neural networks.", "Title", "AI", "shorts")
    assert "breakdown" in result
    assert "flags" in result
    assert "recommendation" in result


def test_score_content_complete_json_is_not_discarded(mock_llm, mock_firebase):
    """Guard against over-correcting: a schema-complete LLM answer must be
    used as-is, not silently replaced by the heuristic fallback."""
    from utils.quality_scorer import score_content
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = """
        {"overall_score": 77, "breakdown": {"clarity": 70, "accuracy": 80},
         "flags": [], "recommendation": "approve", "feedback": "good"}
        """
        result = score_content("A reasonably long script about neural networks.", "Title", "AI", "long")
    assert result["overall_score"] == 77
    assert "Local heuristic score" not in str(result.get("feedback", ""))


def test_score_content_long_format(mock_llm, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Long script " * 50, "Long Video", "Deep Tech", "long")
    assert result["overall_score"] > 0


def test_check_repetition_returns_dict():
    from utils.quality_scorer import check_repetition
    result = check_repetition("Script about apples", "Red Apple")
    assert "max_similarity" in result
    assert "similarity_scores" in result


def test_evaluate_publish_decision_auto_approve():
    from utils.quality_scorer import evaluate_publish_decision
    quality = {"overall_score": 85, "breakdown": {}, "recommendation": "approve"}
    repetition = {"max_similarity": 0.1, "similar_titles": []}
    decision = evaluate_publish_decision(quality, repetition, 80)
    assert decision["action"] in ("auto_approve", "manual_review", "block")


def test_evaluate_publish_decision_block_low_score():
    from utils.quality_scorer import evaluate_publish_decision
    quality = {"overall_score": 30, "breakdown": {}, "recommendation": "block"}
    repetition = {"max_similarity": 0.1, "similar_titles": []}
    decision = evaluate_publish_decision(quality, repetition, 80)
    assert decision["action"] in ("auto_approve", "manual_review", "block")


def test_evaluate_publish_decision_block_high_similarity():
    from utils.quality_scorer import evaluate_publish_decision
    quality = {"overall_score": 85, "breakdown": {}, "recommendation": "approve"}
    repetition = {"max_similarity": 0.95, "similar_titles": ["Previous Video"]}
    decision = evaluate_publish_decision(quality, repetition, 80)
    assert decision["action"] in ("auto_approve", "manual_review", "block")


def test_predict_performance_returns_keys(mock_firebase):
    with patch("utils.quality_scorer.generate_completion") as m:
        m.return_value = """
        {"predicted_views_7d": 5000, "predicted_views_30d": 25000, "virality_score": 65}
        """
    from utils.quality_scorer import predict_performance
    result = predict_performance("Red Apple", "AI Explained", "shorts", "Script text")
    assert "predicted_views_7d" in result
    assert "predicted_views_30d" in result
    assert "virality_score" in result
