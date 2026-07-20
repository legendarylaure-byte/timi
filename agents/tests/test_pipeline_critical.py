import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.voice_gen import _wrap_ssml
from utils.shorts_renderer import compute_scene_timestamps
from utils.video_compositor import _subtitle_style_escaped


def test_wrap_ssml_no_ssml_tags():
    """_wrap_ssml should NOT emit <speak>, <emphasis>, or <break> tags.
    edge-tts XML-escapes all input, so SSML tags become literal text.
    """
    text = "Key concept: this is important. Think about it!"
    result = _wrap_ssml(text, voice_name="en-US-JennyNeural", rate="-5%", is_deep_lesson=False)
    assert "<speak" not in result, f"Should not contain <speak>: {result[:100]}"
    assert "<emphasis" not in result, f"Should not contain <emphasis>: {result[:100]}"
    assert "<break" not in result, f"Should not contain <break>: {result[:100]}"
    assert "<prosody" not in result, f"Should not contain <prosody>: {result[:100]}"
    assert result == text, f"Should return text unchanged (xml-escaped): {result} != {text}"


def test_wrap_ssml_xml_escapes():
    """_wrap_ssml should XML-escape &, <, > to prevent TTS parsing issues."""
    text = "C++ is > Java & < Python"
    result = _wrap_ssml(text)
    assert "&amp;" in result, f"Should escape &: {result}"
    assert "&gt;" in result or "&lt;" not in result, f"Should escape >: {result}"
    assert result == text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), \
        f"Should only apply basic XML escaping: {result}"


def test_wrap_ssml_deep_lesson_no_ssml():
    """Deep lesson mode should also not emit SSML tags."""
    text = "This is crucial for understanding. Imagine the possibilities!"
    result = _wrap_ssml(text, is_deep_lesson=True)
    assert "<speak" not in result
    assert "<emphasis" not in result
    assert "<break" not in result


def test_compute_scene_timestamps_fallsback_to_asset_keywords():
    """compute_scene_timestamps should prefer asset_keywords over description for keyword."""
    scenes = [
        {"duration": 10.0, "asset_keywords": ["Tokenization"], "description": "Then we dive into how tokens actually work step by step"},
        {"duration": 8.0, "description": "Fallback description only"},
    ]
    result = compute_scene_timestamps(scenes)
    assert result[0]["keyword"] == "Tokenization", \
        f"Should use asset_keywords[0], got: {result[0]['keyword']}"
    assert result[1]["keyword"] == "Fallback description only", \
        f"Should fallback to description, got: {result[1]['keyword']}"


def test_compute_scene_timestamps_keyword_precedence():
    """explicit keyword field should take precedence over asset_keywords."""
    scenes = [
        {"duration": 10.0, "keyword": "Explicit Keyword", "asset_keywords": ["Fallback"]},
    ]
    result = compute_scene_timestamps(scenes)
    assert result[0]["keyword"] == "Explicit Keyword"


def test_subtitle_style_builds_valid_string():
    """_subtitle_style_escaped should build a well-formed SUBTITLE style string."""
    style = _subtitle_style_escaped(fontsize=32, margin_v=60)
    assert "FontSize=32" in style, f"Should include FontSize: {style}"
    assert "MarginV=60" in style, f"Should include MarginV: {style}"
    assert "FontName=Arial" in style, f"Should include FontName: {style}"
    assert "\\," in style or "," not in style, \
        f"Commas should be escaped: {style}"
