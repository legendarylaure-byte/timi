#!/usr/bin/env python3
"""Render Concepts C / D / E as real PNGs for owner visual review.

A review artifact, deliberately NOT wired into the pipeline. Concept B is already
live in _compose_thumbnail(); these three are alternatives to it, and they exist
only so a human can look at them side by side. When one is chosen it gets folded
into _compose_thumbnail() and this file is deleted.

MUST run in-container -- _find_font() resolves Linux font paths, and the macOS
host has none of them, so a host render would come out as tofu boxes:

    docker cp scripts/concept_cards.py timi-pipeline:/app/scripts/
    docker exec timi-pipeline python3 -m scripts.concept_cards --out /app/output/concepts
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter  # noqa: E402

from utils.brand_palette import (  # noqa: E402
    ACCENT_RAMP, LICORICE, PINK, PURPLE, VIOLET, WHITE, hex_to_rgb,
)
from utils.thumbnail_gen import _find_font, _wrap_text  # noqa: E402


def _field(w, h, tint, blur=False):
    """Soft brand-tinted field standing in for the AI background image.

    Deterministic on purpose: the real pipeline uses a Pollinations image here, so
    a second render would differ anyway and the reviewer could not compare. A
    fixed field isolates the *layout*, which is what is being decided.
    """
    img = Image.new("RGB", (w, h), hex_to_rgb(LICORICE))
    d = ImageDraw.Draw(img)
    for cx, cy, r, col in (
        (int(w * 0.72), int(h * 0.30), int(min(w, h) * 0.62), tint),
        (int(w * 0.22), int(h * 0.78), int(min(w, h) * 0.48), PINK),
    ):
        for i in range(14, 0, -1):
            rr = int(r * i / 14)
            lift = int(9 * (14 - i) / 3)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      fill=tuple(min(255, c + lift) for c in hex_to_rgb(col)))
    img = ImageEnhance.Color(img).enhance(1.15)
    return img.filter(ImageFilter.GaussianBlur(48)) if blur else img


def _scrim(img, frac, from_bottom=True, peak=185):
    w, h = img.size
    sh = int(h * frac)
    grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for i in range(sh):
        top = h - sh + i if from_bottom else i
        gd.rectangle([(0, top), (w, top + 1)], fill=(0, 0, 0, int(peak * i / max(1, sh - 1))))
    return Image.alpha_composite(img.convert("RGBA"), grad).convert("RGB")


def _rule(img, x, y, w, h):
    seg = max(1, w // len(ACCENT_RAMP))
    d = ImageDraw.Draw(img)
    for i, hexcol in enumerate(ACCENT_RAMP):
        x0 = x + i * seg
        x1 = x + (i + 1) * seg if i < len(ACCENT_RAMP) - 1 else x + w
        d.rectangle([(x0, y), (x1, y + h)], fill=hex_to_rgb(hexcol))
    return img


def _text(d, xy, s, font, fill=WHITE, anchor_center=False, width=0):
    if not s:
        return
    if anchor_center:
        for line in (_wrap_text(s, font, width) if width else [s]):
            d.text(xy, line, font=font, fill=hex_to_rgb(fill), anchor="mm")
            xy = (xy[0], xy[1] + int(font.size * 1.18))
        return
    d.text(xy, s, font=font, fill=hex_to_rgb(fill))


def concept_c(w, h):
    """Aurora Split -- headline upper-third, no bottom scrim. The image carries
    the lower two thirds and the split is the whole idea."""
    img = _scrim(_field(w, h, VIOLET), 0.30, from_bottom=False, peak=165)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.07)
    img = _rule(img, pad, int(h * 0.115), int(w * 0.34), max(5, h // 130))
    f = _find_font(int(h * 0.050), serif=True)
    _text(d, (pad, int(h * 0.17)), "Aurora", f)
    _text(d, (pad, int(h * 0.17) + int(f.size * 1.15)), "Split", f, VIOLET)
    return img


def concept_d(w, h):
    """Signal Break -- one enormous statistic, near-empty frame. The number is
    the composition; there is nothing else competing with it."""
    img = _field(w, h, PINK, blur=True)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.08)
    img = _rule(img, pad, int(h * 0.30), int(w * 0.20), max(6, h // 110))
    _text(d, (pad, int(h * 0.36)), "3.4x", _find_font(int(h * 0.135), serif=True))
    _text(d, (pad, int(h * 0.60)), "faster than last year", _find_font(int(h * 0.040)))
    return img


def concept_e(w, h):
    """Deep Field -- centred serif headline over a violet horizon. The calm
    counterweight to D's shout."""
    img = _field(w, h, PURPLE)
    d = ImageDraw.Draw(img)
    band = int(h * 0.54)
    d.rectangle([(0, band), (w, h)], fill=hex_to_rgb(LICORICE))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for i in range(60):
        gd.rectangle([(0, band - i), (w, band - i + 1)],
                     fill=hex_to_rgb(VIOLET) + (int(120 * (1 - i / 60)),))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    d = ImageDraw.Draw(img)
    _text(d, (w // 2, int(h * 0.30)), "A field,", _find_font(int(h * 0.052), serif=True),
          anchor_center=True)
    _text(d, (w // 2, int(h * 0.30) + int(h * 0.065)), "seen whole",
          _find_font(int(h * 0.052), serif=True), anchor_center=True)
    return _rule(img, (w - int(w * 0.30)) // 2, int(h * 0.48), int(w * 0.30), max(4, h // 170))


CONCEPTS = {"C": concept_c, "D": concept_d, "E": concept_e}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/app/output/concepts")
    ap.add_argument("--format", default="long", choices=["long", "shorts"])
    args = ap.parse_args()
    w, h = (1280, 720) if args.format == "long" else (1080, 1920)
    os.makedirs(args.out, exist_ok=True)
    for name, fn in CONCEPTS.items():
        p = os.path.join(args.out, f"concept_{name.lower()}_{args.format}.png")
        fn(w, h).save(p, "PNG")
        print(f"WROTE {p} ({os.path.getsize(p)} bytes)")


if __name__ == "__main__":
    main()
