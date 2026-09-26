"""Tests for the pure publish helpers in utils/youtube_upload.py.

This file used to assert nothing about the application: it compared stdlib
`datetime` values and re-implemented the publish_at guard inline, so it kept
passing even with the guard deleted from youtube_upload.py. It now imports the
real functions, so a regression in either helper fails here.

The guards were extracted from upload_video_to_youtube specifically so they can be
tested without a YouTube client or credentials.
"""
from datetime import datetime, timedelta, timezone

from utils.youtube_upload import _caption_body, _resolve_publish_at


def _iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


# --- _resolve_publish_at -----------------------------------------------------

def test_future_publish_at_is_kept():
    """A scheduled time in the future must survive, or the upload defers forever."""
    future = _iso(datetime.now(timezone.utc) + timedelta(days=1))
    assert _resolve_publish_at(future) == future


def test_past_publish_at_becomes_none_so_it_goes_public():
    """The original bug this guards: a past schedule used to be sent to the API."""
    past = _iso(datetime.now(timezone.utc) - timedelta(days=1))
    assert _resolve_publish_at(past) is None


def test_empty_publish_at_is_none():
    assert _resolve_publish_at(None) is None
    assert _resolve_publish_at("") is None


def test_unparseable_publish_at_is_passed_through_unchanged():
    """Documented ceiling: junk is forwarded, not silently turned into 'publish now'.
    Nulling it here would convert a mistyped schedule into an immediate public upload."""
    assert _resolve_publish_at("not-a-date") == "not-a-date"


# --- _caption_body -----------------------------------------------------------

def test_caption_defaults_to_english():
    """No default_language => English source track (unchanged pre-dub behaviour)."""
    assert _caption_body("vid1") == {
        "snippet": {
            "videoId": "vid1",
            "language": "en",
            "name": "English",
            "isDraft": False,
        }
    }


def test_dubbed_caption_uses_the_dubbed_language():
    """The real bug: every dubbed long was uploaded with language='en'/'English'
    while the SRT was Hindi. YouTube then mislabels its own track."""
    for code, name in (("hi", "Hindi"), ("ko", "Korean"),
                       ("es", "Spanish"), ("de", "German")):
        snippet = _caption_body("vid2", code)["snippet"]
        assert snippet["language"] == code
        assert snippet["name"] == name
        assert snippet["videoId"] == "vid2"
        assert snippet["isDraft"] is False


def test_caption_language_is_normalised():
    assert _caption_body("vid3", "KO")["snippet"]["language"] == "ko"
    assert _caption_body("vid4", " hi ")["snippet"]["language"] == "hi"


def test_unknown_caption_language_does_not_crash():
    """An unmapped code falls back to the code itself rather than raising mid-upload."""
    snippet = _caption_body("vid5", "xx")["snippet"]
    assert snippet["language"] == "xx"
    assert snippet["name"] == "xx"
