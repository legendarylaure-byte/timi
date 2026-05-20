"""Tests for description_gen.py"""
import pytest
from unittest.mock import patch


@pytest.fixture
def mock_groq():
    with patch("utils.description_gen.generate_completion") as m:
        m.return_value = """
        {
            "seo_title": "Red Apple Song for Kids",
            "full_description": "Learn all about red apples in this fun video!",
            "tags": ["apples", "colors", "kids"],
            "category": "Education"
        }
        """
        yield m


def test_generate_description_returns_keys(mock_groq):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Red Apple",
        script="Look at this red apple! It is yummy.",
        category="Colors & Shapes",
        format_type="shorts",
    )
    assert "seo_title" in result
    assert "full_description" in result
    assert isinstance(result, dict)


def test_generate_description_with_chapters(mock_groq):
    from utils.description_gen import generate_description
    scenes = [
        {"keyword": "Apple Intro", "target_duration": 8},
        {"keyword": "Apple Color", "target_duration": 10},
    ]
    result = generate_description(
        title="Red Apple",
        script="Script text here",
        category="Colors & Shapes",
        format_type="long",
        scenes=scenes,
    )
    assert isinstance(result, dict)
    assert "seo_title" in result


def test_generate_description_with_merch(mock_groq):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Red Apple",
        script="Script text",
        category="Colors & Shapes",
        format_type="shorts",
        merch_links={"T-Shirt": "https://example.com/tshirt"},
    )
    assert isinstance(result, dict)


def test_generate_description_with_affiliate(mock_groq):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Red Apple",
        script="Script text",
        category="Colors & Shapes",
        format_type="shorts",
        affiliate_links=[{"name": "Apple Toy", "url": "https://example.com/toy"}],
    )
    assert isinstance(result, dict)


def test_generate_description_short_script(mock_groq):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Hi",
        script="Hello",
        category="General",
        format_type="shorts",
    )
    assert isinstance(result, dict)


def test_generate_description_channel_name(mock_groq):
    from utils.description_gen import generate_description
    result = generate_description(
        title="Test",
        script="Test content",
        category="Science",
        format_type="long",
        channel_name="My Channel",
    )
    assert isinstance(result, dict)


def test_generate_description_fallback(mock_groq):
    """When LLM returns unparseable, fallback should still work."""
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion") as m:
        m.return_value = "NOT JSON"
        result = generate_description("Test", "Script", "General")
    assert isinstance(result, dict)
