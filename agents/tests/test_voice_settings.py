"""Guards for the channel voice lock (WS5 Phase 2).

The channel voice is one number that a human ear judges, so it is a profile
default (educational = Emma -4%/-1Hz) plus an optional override dial. These
pin both: the default the pipeline actually ships, and that the dial wins when
set -- including for a content type whose own profile differs, since the whole
point of the dial is channel-wide calibration.
"""
import os

import pytest

from utils.voice_gen import get_voice_settings

CHANNEL_VOICE = "en-US-EmmaMultilingualNeural"


@pytest.fixture(autouse=True)
def _clear_voice_env(monkeypatch):
    for k in ("VOICE_NAME", "VOICE_RATE", "VOICE_PITCH"):
        monkeypatch.delenv(k, raising=False)


def test_educational_profile_is_the_locked_channel_voice():
    # main.py:1432 passes content_type="educational" for both shorts and longs.
    s = get_voice_settings("educational")
    assert s["voice"] == CHANNEL_VOICE, s
    assert s["rate"] == "-4%", s
    assert s["pitch"] == "-1Hz", s


def test_env_dial_overrides_every_content_type(monkeypatch):
    monkeypatch.setenv("VOICE_NAME", "en-US-AriaNeural")
    monkeypatch.setenv("VOICE_RATE", "-7%")
    monkeypatch.setenv("VOICE_PITCH", "+2Hz")
    for ct in ("educational", "documentary", "storytelling", "general"):
        s = get_voice_settings(ct)
        assert s["voice"] == "en-US-AriaNeural", (ct, s)
        assert s["rate"] == "-7%", (ct, s)
        assert s["pitch"] == "+2Hz", (ct, s)


def test_partial_dial_leaves_the_other_fields_on_the_profile(monkeypatch):
    # Setting ONLY the rate must not blank the voice/pitch -- each field is its
    # own dial, not a package deal.
    monkeypatch.setenv("VOICE_RATE", "-9%")
    s = get_voice_settings("educational")
    assert s["rate"] == "-9%", s
    assert s["voice"] == CHANNEL_VOICE, s
    assert s["pitch"] == "-1Hz", s


def test_unknown_content_type_falls_back_without_crashing():
    s = get_voice_settings("not-a-real-type")
    assert s["voice"] == get_voice_settings("general")["voice"]


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
