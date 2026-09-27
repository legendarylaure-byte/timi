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


# ---------------------------------------------------------------------------
# Disclosure / assembly durability
#
# The defect: the AI-disclosure, copyright line, and affiliate links were
# appended *inside* the try block, so the except path returned a description
# without them. An LLM outage therefore silently un-disclosed every upload,
# which is a YouTube policy requirement, not a nicety.
# ---------------------------------------------------------------------------


def _boom(**kw):
    raise RuntimeError("llm down")


def test_disclosure_and_copyright_survive_an_llm_outage():
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion", _boom):
        fd = generate_description("How Transformers Work", "script text", "AI Explained")["full_description"]
    assert "AI-generated" in fd, "disclosure dropped on the fallback path"
    assert "© Vyom Ai Cloud" in fd, "copyright line dropped on the fallback path"


def test_disclosure_survives_unparseable_json():
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion", lambda **kw: "total garbage"):
        fd = generate_description("How Transformers Work", "s", "AI Explained")["full_description"]
    assert "AI-generated" in fd
    assert "© Vyom Ai Cloud" in fd


def test_disclosure_survives_a_valid_but_empty_body():
    """An empty body must not emit a suffix-only description."""
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion",
               lambda **kw: '{"description": "   ", "hashtags": ["#AI"]}'):
        r = generate_description("How Transformers Work", "s", "AI Explained")
    assert "AI-generated" in r["full_description"]
    assert "Learn about" in r["full_description"]


def test_body_fallback_keeps_the_llm_other_keys():
    """Regression lock: an earlier fix replaced the WHOLE result dict when the
    body was empty, which silently dropped the LLM's seo_title/tags. Two
    pre-existing tests caught it. Only the body may be substituted."""
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion",
               lambda **kw: '{"description": "", "seo_title": "Kept", "tags": ["kept"]}'):
        r = generate_description("T", "s", "AI Explained")
    assert r["seo_title"] == "Kept", "fallback must not discard the LLM's other keys"
    assert r["tags"] == ["kept"]
    assert "Learn about" in r["full_description"]


def test_affiliate_links_survive_an_llm_outage():
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion", _boom):
        fd = generate_description(
            "T", "s", "AI Explained",
            affiliate_links=[{"name": "Book", "url": "https://example.com/book"}],
        )["full_description"]
    assert "https://example.com/book" in fd, "affiliate links dropped on the fallback path"


def test_long_form_chapters_survive_an_llm_outage():
    from utils.description_gen import generate_description
    with patch("utils.description_gen.generate_completion", _boom):
        r = generate_description(
            "Deep Dive", "s", "Deep Tech", format_type="long",
            scenes=[{"target_duration": 65, "keyword": "Intro"},
                    {"target_duration": 30, "keyword": "Core"}],
        )
    fd = r["full_description"]
    assert "00:00 - Intro" in fd
    assert "01:05 - Core" in fd
    assert "AI-generated" in fd


def test_prompt_forbids_invented_links_and_asks_for_a_cta():
    src = open(description_gen_path()).read()
    assert "Do NOT invent links" in src, "prompt must forbid fabricated sources/citations"
    assert "subscribe" in src.lower(), "prompt must request a CTA"


def description_gen_path():
    import utils.description_gen as m
    return m.__file__
