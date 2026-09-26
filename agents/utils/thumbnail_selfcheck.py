"""Self-check for P2 thumbnail selection.

Run: python -m utils.thumbnail_selfcheck

Catches the two original defects:
  1. _score_thumbnail derived every metric from hash(loop_index), so it scored the
     same every run and never looked at the image.
  2. pick_best_thumbnail ignored the generated variants and always returned a
     blurred video frame.
"""
import os
import tempfile

from utils.thumbnail_gen import _measure_image, _score_thumbnail, fit_under_2mb


def _blank(w, h, color):
    from PIL import Image
    p = os.path.join(tempfile.gettempdir(), f"tb_{w}x{h}_{color[0]}.png")
    Image.new("RGB", (w, h), color).save(p)
    return p


def _photo_like():
    """Noisy, colourful image — should measure as high interest."""
    from PIL import Image
    import random
    random.seed(1)
    im = Image.new("RGB", (640, 360))
    px = im.load()
    for y in range(360):
        for x in range(640):
            px[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    p = os.path.join(tempfile.gettempdir(), "tb_photolike.png")
    im.save(p)
    return p


def test_scoring_reflects_the_image_not_a_hash():
    flat = _blank(640, 360, (128, 128, 128))          # featureless grey
    busy = _photo_like()                               # colourful + detailed
    s_flat = _score_thumbnail({"measured": _measure_image(flat), "text_length": 20})
    s_busy = _score_thumbnail({"measured": _measure_image(busy), "text_length": 20})
    assert s_busy > s_flat, f"busy photo {s_busy} should beat flat grey {s_flat}"


def test_scoring_is_deterministic_for_the_same_image():
    p = _photo_like()
    a = _score_thumbnail({"measured": _measure_image(p), "text_length": 20})
    b = _score_thumbnail({"measured": _measure_image(p), "text_length": 20})
    assert a == b, f"scoring not stable: {a} != {b}"


def test_shorter_text_scores_higher_than_wall_of_text():
    m = _measure_image(_photo_like())
    short = _score_thumbnail({"measured": m, "text_length": 25})
    wall = _score_thumbnail({"measured": m, "text_length": 120})
    assert short > wall, f"short {short} should beat wall-of-text {wall}"


def test_pick_best_keeps_generated_variant_over_video_frame():
    from utils.thumbnail_gen import pick_best_thumbnail
    gen = _photo_like()
    # No video_path -> must return the generated variant, unchanged.
    got = pick_best_thumbnail(gen, "", "a real title", "long")
    assert got == gen, f"expected the generated variant {gen}, got {got}"
    assert os.path.getsize(got) <= 2 * 1024 * 1024, "exceeds YouTube 2MB limit"


def test_fit_under_2mb_shrinks_an_oversized_file():
    from PIL import Image
    import random
    random.seed(2)
    # 2560x1440 of pure noise at q100 — comfortably over YouTube's 2MB cap.
    w, h = 2560, 1440
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            v = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            px[x, y] = v
            if x + 1 < w:
                px[x + 1, y] = v
            if y + 1 < h:
                px[x, y + 1] = v
                if x + 1 < w:
                    px[x + 1, y + 1] = v
    p = os.path.join(tempfile.gettempdir(), "tb_huge.jpg")
    im.save(p, "JPEG", quality=100)
    before = os.path.getsize(p)
    assert before > 2 * 1024 * 1024, f"test image not actually oversized: {before}"
    fit_under_2mb(p)
    after = os.path.getsize(p)
    assert after < before, f"file not shrunk: {before} -> {after}"
    assert after <= 2 * 1024 * 1024, f"still over limit: {after}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  PASS {name}")
    print("thumbnail selfcheck OK")
