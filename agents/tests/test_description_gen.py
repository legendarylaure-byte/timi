"""Tests for description_gen.py"""
import pytest
from unittest.mock import patch


@pytest.fixture
def mock_llm():
    with patch("utils.description_gen.generate_completion") as m:
        m.return_value = """
        {
            "seo_title": "Transformers Explained Simply",
            "full_description": "Learn how transformer neural networks work in this educational video!",
            "tags": ["transformers", "deep learning", "AI"],
            "category": "AI Explained"
        }
        """
        yield m


def test_generate_description_returns_keys(mock_llm):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Transformers Explained",
        script="Transformer models use self-attention mechanisms to process sequential data.",
        category="AI Explained",
        format_type="shorts",
    )
    assert "seo_title" in result
    assert "full_description" in result
    assert isinstance(result, dict)


def test_generate_description_with_chapters(mock_llm):
    from utils.description_gen import generate_description
    scenes = [
        {"keyword": "Attention Mechanism", "target_duration": 8},
        {"keyword": "Self-Attention", "target_duration": 10},
    ]
    result = generate_description(
        title="Transformers Explained",
        script="Script text here",
        category="AI Explained",
        format_type="long",
        scenes=scenes,
    )
    assert isinstance(result, dict)
    assert "seo_title" in result


def test_generate_description_with_merch(mock_llm):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Transformers Explained",
        script="Script text",
        category="AI Explained",
        format_type="shorts",
        merch_links={"T-Shirt": "https://example.com/tshirt"},
    )
    assert isinstance(result, dict)


def test_generate_description_with_affiliate(mock_llm):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Transformers Explained",
        script="Script text",
        category="AI Explained",
        format_type="shorts",
        affiliate_links=[{"name": "Deep Learning Book", "url": "https://example.com/book"}],
    )
    assert isinstance(result, dict)


def test_generate_description_short_script(mock_llm):
    from utils.description_gen import generate_description
    result = generate_description(
        title="AI",
        script="Hello",
        category="AI Explained",
        format_type="shorts",
    )
    assert isinstance(result, dict)


def test_generate_description_channel_name(mock_llm):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Test",
        script="Test content",
        category="Science",
        format_type="long",
        channel_name="My Channel",
    )
    assert isinstance(result, dict)


def test_generate_description_fallback(mock_llm):
    """When LLM returns unparseable, fallback should still work."""
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion") as m:
        m.return_value = "NOT JSON"
        result = generate_description("Test", "Script", "General")
    assert isinstance(result, dict)
