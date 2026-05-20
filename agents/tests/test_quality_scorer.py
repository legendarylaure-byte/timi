"""Tests for quality_scorer.py"""
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_groq():
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
            "feedback": "Good content for kids"
        }
        """
        yield m


@pytest.fixture
def mock_firebase():
    with patch("utils.quality_scorer.update_agent_status"), \
         patch("utils.quality_scorer.log_activity"):
        yield


def test_score_content_returns_all_keys(mock_groq, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Test script about apples", "Red Apple", "Colors & Shapes", "shorts")
    assert "overall_score" in result
    assert "breakdown" in result
    assert "recommendation" in result
    assert "feedback" in result


def test_score_content_breakdown_has_all_dimensions(mock_groq, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Test script", "Title", "Science", "shorts")
    dims = ["age_appropriateness", "educational_value", "engagement_potential",
            "language_safety", "creativity", "pacing"]
    for d in dims:
        assert d in result["breakdown"], f"Missing dimension: {d}"


def test_score_content_numeric_range(mock_groq, mock_firebase):
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


def test_score_content_empty_script(mock_groq, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("", "Empty", "General", "shorts")
    assert isinstance(result, dict)


def test_score_content_long_format(mock_groq, mock_firebase):
    from utils.quality_scorer import score_content
    result = score_content("Long script " * 50, "Long Video", "Bedtime Stories", "long")
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
    result = predict_performance("Red Apple", "Colors & Shapes", "shorts", "Script text")
    assert "predicted_views_7d" in result
    assert "predicted_views_30d" in result
    assert "virality_score" in result
