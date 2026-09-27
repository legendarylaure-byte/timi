"""Tests for the brand palette and the Concept B social card.

The card carries the source click-through, so the two things worth locking are:
the palette maths (a bad blend silently darkens text) and the fact that a link
is always present when there is one, and never invented when there is not.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.brand_palette import (
    LICORICE,
    LIGHT_ORANGE,
    ORANGE,
    PINK,
    PURPLE,
    VIOLET,
    WHITE,
    hex_to_rgb,
    lerp,
)


# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

def test_every_brand_colour_is_six_digit_hex():
    """A typo'd literal here becomes an invisible or black element on the card."""
    for name in (LICORICE, PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE, WHITE):
        assert len(name) == 7 and name.startswith("#"), f"{name!r} is not #RRGGBB"
        int(name[1:], 16)  # raises if not hex


def test_hex_to_rgb():
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert hex_to_rgb("#000000") == (0, 0, 0)
    assert hex_to_rgb(PURPLE) == (155, 77, 255)


def test_hex_to_rgb_rejects_junk():
    for junk in ("#FFF", "#GGGGGG", "", "not-a-colour"):
        with pytest.raises(ValueError):
            hex_to_rgb(junk)


def test_hex_to_rgb_tolerates_a_missing_hash():
    """Lenient on the leading '#': no user input reaches this, and a bare hex
    literal is a normal way to write one."""
    assert hex_to_rgb("9B4DFF") == hex_to_rgb("#9B4DFF")


def test_lerp_endpoints_and_midpoint():
    assert lerp("#000000", "#FFFFFF", 0.0) == (0, 0, 0)
    assert lerp("#000000", "#FFFFFF", 1.0) == (255, 255, 255)
    mid = lerp("#000000", "#FFFFFF", 0.5)
    assert all(126 <= c <= 129 for c in mid), mid


def test_lerp_clamps_t_outside_zero_one():
    """The card passes a computed fraction; drift must not produce out-of-range RGB."""
    assert lerp("#000000", "#FFFFFF", -5.0) == (0, 0, 0)
    assert lerp("#000000", "#FFFFFF", 99.0) == (255, 255, 255)


# --------------------------------------------------------------------------
# Card rendering
# --------------------------------------------------------------------------

def _card(article, tmp_path, monkeypatch):
    from utils import viral_news_agent as va
    monkeypatch.setattr(va, "_TEMP_DIR", tmp_path)
    return va.generate_image(article, 0)


def _sample(path):
    from PIL import Image
    return Image.open(path).convert("RGB")


def test_card_is_square_and_full_size(tmp_path, monkeypatch):
    p = _card({"title": "Test headline", "source": "BBC World",
               "link": "https://bbc.com/news/1", "category": "World News (24hr)"},
              tmp_path, monkeypatch)
    assert _sample(p).size == (1080, 1080)


def test_top_strip_is_a_gradient_not_a_solid_bar(tmp_path, monkeypatch):
    """Concept B's signature. A solid bar means the ramp never got applied."""
    p = _card({"title": "Gradient check", "source": "X",
               "link": "https://x.com/a", "category": "News"}, tmp_path, monkeypatch)
    im = _sample(p)
    px = im.load()
    W = im.size[0]
    strip = {px[x, 8] for x in range(W)}
    assert len(strip) > 50, f"only {len(strip)} colours in the accent strip -- not a gradient"


def test_spotlight_blooms_in_the_upper_third(tmp_path, monkeypatch):
    """The glow must peak behind the headline, not at the top or the bottom."""
    p = _card({"title": "Spotlight check", "source": "X",
               "link": "https://x.com/a", "category": "News"}, tmp_path, monkeypatch)
    im = _sample(p)
    px = im.load()
    W, H = im.size

    def row_brightness(y):
        return sum(sum(px[x, y]) / 3 for x in range(0, W, 20)) / (W // 20)

    top = row_brightness(int(H * 0.05))
    peak = row_brightness(int(H * 0.34))
    bottom = row_brightness(int(H * 0.95))
    assert peak > top, f"no glow: top={top} peak={peak}"
    assert peak > bottom, f"glow not in the upper third: peak={peak} bottom={bottom}"


def test_card_renders_with_a_very_long_title(tmp_path, monkeypatch):
    """Long headlines must not crash, change the size, or lose the panel."""
    p = _card({"title": "Nepal Opens First Grid-Scale Battery Storage Plant In The "
                        "Middle East And Signs A Landmark Regional Energy Agreement "
                        "Covering Six Nations Across Three Continents Simultaneously",
               "source": "Onlinekhabar", "link": "https://ok.com/x",
               "category": "Nepal News"}, tmp_path, monkeypatch)
    assert _sample(p).size == (1080, 1080)


def test_card_renders_when_the_article_has_no_link(tmp_path, monkeypatch):
    p = _card({"title": "No link here", "source": "X", "link": "", "category": "News"},
              tmp_path, monkeypatch)
    assert _sample(p).size == (1080, 1080)


def test_card_renders_when_the_link_key_is_absent(tmp_path, monkeypatch):
    p = _card({"title": "Missing key", "source": "X", "category": "News"},
              tmp_path, monkeypatch)
    assert _sample(p).size == (1080, 1080)


# --------------------------------------------------------------------------
# The click-through
# --------------------------------------------------------------------------

def test_caption_carries_the_source_link(monkeypatch):
    """The image cannot be a hyperlink -- the caption is the only click surface."""
    from utils import viral_news_agent as va

    link = "https://english.onlinekhabar.com/2026/09/27/story"
    # Force the template path so the test never depends on an LLM being up.
    import utils.llm_helper as lh
    monkeypatch.setattr(lh, "get_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")))

    caption = va.generate_caption({"title": "T", "source": "Onlinekhabar",
                                   "link": link, "body": "b", "category": "Nepal News"})
    assert link in caption, f"caption lost the click-through link: {caption[-200:]}"
    assert "Onlinekhabar" in caption
    # Must be the LAST thing, so it is the last clickable element.
    assert caption.strip().endswith(link), f"link is not last: ...{caption[-120:]!r}"


def test_caption_never_invents_a_link_when_there_is_none(monkeypatch):
    """A fabricated URL sends readers to a page that does not exist."""
    from utils import viral_news_agent as va
    import utils.llm_helper as lh
    monkeypatch.setattr(lh, "get_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")))

    caption = va.generate_caption({"title": "T", "source": "X", "link": "",
                                   "body": "b", "category": "News"})
    assert "http" not in caption, f"invented a URL: {caption[-200:]}"
    assert "comments" in caption.lower()


def test_caption_survives_a_missing_link_key(monkeypatch):
    from utils import viral_news_agent as va
    import utils.llm_helper as lh
    monkeypatch.setattr(lh, "get_llm", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")))

    caption = va.generate_caption({"title": "T", "source": "X", "body": "b"})
    assert "http" not in caption
