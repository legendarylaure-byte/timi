"""Guards for the two own-generator music beds (news / relaxing).

The whole point is that background music is now deterministic and license-free
and that the bed is a SEAMLESS loop, so anything that reintroduces the Pixabay
download path, maps a category to the wrong profile, or breaks the loop seam
must fail here.
"""
import os
import wave

import numpy as np


def test_category_maps_to_profile():
    from utils.music_gen import select_music_profile
    assert select_music_profile("World News (24hr)") == "news"
    assert select_music_profile("Nepal News") == "news"
    assert select_music_profile("AI News") == "relaxing"
    assert select_music_profile("Science & Technology") == "relaxing"
    assert select_music_profile("Programming & Software") == "relaxing"
    # "AI News" must never match the news bed via substring -- it shares the word.
    assert "News" in "AI News"
    assert select_music_profile(["World News (24hr)"]) == "news"
    assert select_music_profile(None) == "relaxing"
    assert select_music_profile("World News (24hr)", tier="documentary") == "relaxing"


def test_each_profile_renders_stereo_loop():
    from utils.music_gen import _synth_bed, SR, LOOP_SECONDS
    for profile in ("news", "relaxing"):
        bed = _synth_bed(profile)
        assert bed.shape[0] == 2, f"{profile} is not stereo"
        assert bed.shape[1] == int(SR * LOOP_SECONDS), f"{profile} wrong loop length"
        peak = float(np.abs(bed).max())
        assert peak > 0.05, f"{profile} is silent"
        # Loop seam: the step from last -> first sample must be an ordinary step,
        # not a click. A non-seamless render (edge fade removed, LFO un-quantized,
        # linear reverb) leaves a discontinuity here.
        seam = float(np.abs(bed[:, 0] - bed[:, -1]).max())
        # Measured: circular seam ratio ~0.006-0.008; a linear (tail-cut) reverb
        # pushes it to ~0.10-0.13. 0.03 sits an order of magnitude above the
        # correct render and well below the broken one.
        assert seam < 0.03 * peak, f"{profile} has a click at the loop seam ({seam:.3f})"


def test_beds_cache_and_are_real_files():
    from utils.music_gen import _ensure_bed
    for profile in ("news", "relaxing"):
        path = _ensure_bed(profile)
        assert os.path.exists(path) and os.path.getsize(path) > 10000
        with wave.open(path, "rb") as w:
            assert w.getnchannels() == 2
            assert w.getframerate() == 44100


def test_generate_background_music_returns_real_beds():
    from utils.music_gen import generate_background_music
    news = generate_background_music("Nepal News", duration=30, video_id="t1")
    assert news["success"] is True
    assert news["source"] == "own-generator"
    assert news["mood"] == "news"
    assert news["path"] and os.path.exists(news["path"])

    relaxing = generate_background_music("Programming & Software", duration=30, video_id="t2")
    assert relaxing["success"] is True
    assert relaxing["mood"] == "relaxing"
    # Two distinct beds are served, not one shared track.
    assert news["path"] != relaxing["path"]