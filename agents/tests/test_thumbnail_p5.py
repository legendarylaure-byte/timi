"""P5 thumbnail checks.

The 160px gate is the one worth locking: a headline that cannot be read at the
width a mobile feed shows is a failed thumbnail, and nothing else in the
pipeline would notice.
"""
import os

import pytest

from PIL import Image, ImageDraw, ImageFont

from utils import thumbnail_gen as tg


def _img(path, size=(1280, 720), draw_band=None, text_color=(255, 255, 255)):
    img = Image.new("RGB", size, (30, 26, 40))
    if draw_band:
        draw_band(ImageDraw := __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).ImageDraw(img))
    img.save(path, "JPEG", quality=92)
    return path


def test_headline_is_capped_at_three_words():
    assert tg._headline("The Future Of Artificial Intelligence Explained") == "The Future Of"
    assert tg._headline("AI  is   here") == "AI is here"
    assert tg._headline("") == ""


def _headline_font(size):
    """A real sized face. PIL's load_default() is a 10px bitmap and a mock drawn
    with it would be testing an unreadable card, not a headline."""
    import glob
    for pat in ("/usr/share/fonts/**/DejaVuSerif-Bold.ttf", "/System/Library/Fonts/Supplemental/*.ttf"):
        hits = glob.glob(pat, recursive=True)
        if hits:
            return ImageFont.truetype(hits[0], size)
    return ImageFont.truetype(tg._find_font(size).path, size)


def test_mobile_gate_accepts_a_scrimmed_headline(tmp_path):
    """A dark scrim with light text must survive the 160px downscale."""
    path = str(tmp_path / "good.jpg")
    font = _headline_font(52)

    def band(d):
        d.rectangle([(0, 470), (1280, 720)], fill=(14, 12, 16))
        for i, line in enumerate(("THE", "FUTURE", "OF AI")):
            d.text((90, 500 + i * 56), line, font=font, fill=(255, 255, 255))

    _img(path, draw_band=band)
    assert tg._mobile_legible(path) is True


def test_real_composed_thumbnail_passes_its_own_gate(tmp_path):
    """The gate must not reject the design it was written for.

    This is the test that catches a threshold tuned against a hand-drawn mock
    rather than against what _compose_photo actually produces.
    """
    src = tmp_path / "photo.jpg"
    Image.new("RGB", (1920, 1080), (60, 66, 78)).save(src, "JPEG")
    out = str(tmp_path / "card.jpg")
    assert tg._compose_photo(src, "The Future Of AI", out, format_type="long")
    assert tg._mobile_legible(out) is True, "P5's own thumbnail failed its own 160px gate"


def test_mobile_gate_rejects_a_flat_card_with_no_text(tmp_path):
    """Negative case: the gate must fail on a card whose headline vanished."""
    path = str(tmp_path / "flat.jpg")
    _img(path)
    assert tg._mobile_legible(path) is False


def test_mobile_gate_rejects_text_at_the_wrong_size_to_read(tmp_path):
    """A headline rendered too small to survive downscaling is not legible."""
    path = str(tmp_path / "tiny.jpg")

    def band(d):
        d.rectangle([(0, 470), (1280, 720)], fill=(14, 12, 16))
        d.text((90, 590), "AI", font=_headline_font(9), fill=(255, 255, 255))  # ~1px after downscale

    _img(path, draw_band=band)
    assert tg._mobile_legible(path) is False


def test_crop_fill_never_letterboxes(tmp_path):
    """Cover-crop, not fit: a 4:3 source on a 9:16 canvas must fill it."""
    src = tmp_path / "src.png"
    Image.new("RGB", (1920, 1440), (10, 20, 30)).save(src)
    with Image.open(src) as im:
        out = tg._crop_fill(im.convert("RGB"), 1080, 1920)
    assert out.size == (1080, 1920)


def test_variants_fall_back_to_concept_f_when_the_image_round_is_dead(monkeypatch, tmp_path):
    """No image provider must still yield a usable thumbnail."""
    monkeypatch.setattr(tg, "THUMBNAIL_DIR", str(tmp_path))
    import utils.image_gen as ig
    monkeypatch.setattr(ig, "generate_variants", lambda *a, **k: [])

    res = tg.generate_thumbnail_variants("Quantum computing explained", "", "long")
    assert res["source"] == "concept_f"
    assert res["count"] == 1
    assert os.path.exists(res["best"])
    assert os.path.getsize(res["best"]) > 2000
