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
    assert "FontName=" in style, f"Should include FontName: {style}"
    # Arial is not installed in the container; the style must name a font that
    # actually resolves, otherwise libass silently falls back to a Latin-only face.
    assert "FontName=Arial" not in style, f"Arial not installed in image: {style}"
    assert "\\," in style or "," not in style, \
        f"Commas should be escaped: {style}"


def test_auto_subtitle_mode_gives_longs_exactly_one_caption_track(monkeypatch):
    """SUBTITLE_MODE=auto must not burn AND upload captions for long form.

    Regression: auto returned "both" for longs, so every long video shipped two
    copies of the same line, and the dubbing clean master inherited burned
    English captions. One format, one caption track.
    """
    from utils import subtitle_gen

    monkeypatch.setenv("SUBTITLE_MODE", "auto")
    assert subtitle_gen.subtitle_mode_for("long") == "cc"
    assert subtitle_gen.should_upload_cc("long") is True
    assert subtitle_gen.should_burn_subtitles("long") is False

    assert subtitle_gen.subtitle_mode_for("shorts") == "burn"
    assert subtitle_gen.should_burn_subtitles("shorts") is True
    assert subtitle_gen.should_upload_cc("shorts") is False


def test_explicit_subtitle_modes_are_respected(monkeypatch):
    from utils import subtitle_gen

    monkeypatch.setenv("SUBTITLE_MODE", "both")
    assert subtitle_gen.should_burn_subtitles("long") is True
    assert subtitle_gen.should_upload_cc("long") is True

    monkeypatch.setenv("SUBTITLE_MODE", "cc")
    assert subtitle_gen.should_burn_subtitles("long") is False
    assert subtitle_gen.should_upload_cc("long") is True

    monkeypatch.setenv("SUBTITLE_MODE", "off")
    assert subtitle_gen.should_burn_subtitles("shorts") is False
    assert subtitle_gen.should_upload_cc("shorts") is False


# --- Meta temp-dir self-heal -------------------------------------------------
# The 04:00 UTC cleanup_local_files() rmdir's empty tmp/ subdirs, and both Meta
# temp dirs are always empty after an upload. makedirs at module import was
# therefore not enough: ffmpeg wrote to a deleted dir, the function fell back to
# the uncompressed original, and Facebook returned "Video Upload Time Out"
# (subcode 1363030). Mirror of the viral_news.generate_image() fix in D32.


def _stub_ffmpeg(monkeypatch, mpp):
    """Make safe_run report ffmpeg failure so both helpers return early,
    after the makedirs that we actually want to assert on."""
    class _Fail:
        returncode = 1
        stderr = "stubbed"
        stdout = ""
    monkeypatch.setattr(mpp, "safe_run", lambda *a, **k: _Fail())
    monkeypatch.setattr(mpp, "log_activity", lambda *a, **k: None)


def test_compress_for_facebook_recreates_deleted_temp_dir(monkeypatch, tmp_path):
    import shutil

    from utils import multi_platform_publisher as mpp

    src = tmp_path / "in.mp4"
    src.write_bytes(b"\x00" * 64)  # real file: _compress_for_facebook stats it

    shutil.rmtree(mpp._FACEBOOK_TEMP_DIR, ignore_errors=True)
    assert not Path(mpp._FACEBOOK_TEMP_DIR).exists(), "precondition: dir must be gone"

    _stub_ffmpeg(monkeypatch, mpp)
    mpp._compress_for_facebook(str(src))

    assert Path(mpp._FACEBOOK_TEMP_DIR).is_dir()


def test_trim_for_instagram_recreates_deleted_temp_dir(monkeypatch, tmp_path):
    import shutil

    from utils import multi_platform_publisher as mpp

    src = tmp_path / "in.mp4"
    src.write_bytes(b"\x00" * 64)

    shutil.rmtree(mpp._INSTAGRAM_TEMP_DIR, ignore_errors=True)
    assert not Path(mpp._INSTAGRAM_TEMP_DIR).exists(), "precondition: dir must be gone"

    monkeypatch.setattr(mpp, "_get_video_duration_ffprobe", lambda *a, **k: 9999.0)
    _stub_ffmpeg(monkeypatch, mpp)
    mpp._trim_for_instagram(str(src))

    assert Path(mpp._INSTAGRAM_TEMP_DIR).is_dir()
