#!/usr/bin/env python3
"""Render Concepts F / G / H as real PNGs for owner visual review.

A review artifact, deliberately NOT wired into the pipeline. Concept B is already
live in _compose_thumbnail(); these three are alternatives to it, and they exist
only so a human can look at them side by side. When one is chosen it gets folded
into _compose_thumbnail() and this file is deleted.

Concepts C / D / E were the previous dark-field round and were rejected by the
owner as too dark; their PNGs are left on disk for reference. Their `_field` /
`_scrim` helpers are gone because every concept here has a light ground.

Colour is not a taste call here, it is arithmetic. On a light surface only two
brand colours are safe as text -- LICORICE 18.4:1 and VIOLET 5.6:1 both clear
AA for body text, PURPLE 4.3:1 clears only the 3:1 large-text bar, and PINK /
ORANGE / LIGHT_ORANGE / AMBER are decorative only (1.7-3.1:1). So PURPLE is
confined to display type and the ramp to non-text rules, and `--report` prints
the measured ratio for every pair actually used.

MUST run in-container -- _find_font() resolves Linux font paths and the macOS
host has none of them, so a host render comes out as tofu boxes. Bind-mount the
tree rather than `docker cp` (a `cp` patch silently reverts on any container
recreate, which is what cost days of drift before):

    docker run --rm -v "$PWD/agents:/app/agents" -w /app/agents \\
      --entrypoint python3 timi-pipeline:phaseb \\
      -m scripts.concept_cards --out /app/output/concepts --report
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from utils.brand_palette import (  # noqa: E402
    ACCENT_RAMP, AMBER, LICORICE, LIGHT_ORANGE, ORANGE, PINK, PURPLE, VIOLET,
    WHITE, hex_to_rgb, lerp,
)
from utils.thumbnail_gen import _find_font, _wrap_text  # noqa: E402

# The only brand colours permitted as text, keyed by the WCAG bar they clear.
# Enforced by assertion in _text() so a concept cannot quietly ship unreadable type.
_BODY_SAFE = {LICORICE, VIOLET}
_DISPLAY_SAFE = _BODY_SAFE | {PURPLE}

KICKER = "AI EXPLAINED"
TITLE = "How Transformers Actually Work"
FOOTER = "Vyom Ai Cloud"


# ---------------------------------------------------------------- colour maths
def _luminance(rgb):
    out = []
    for v in rgb:
        v /= 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def contrast(a, b):
    """WCAG 2.x ratio between two hex colours."""
    la, lb = _luminance(hex_to_rgb(a)), _luminance(hex_to_rgb(b))
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def lerp_hex(a, b, t):
    """lerp() returns an RGB tuple; the contrast report needs a hex to measure."""
    return "#%02X%02X%02X" % lerp(a, b, t)


# ---------------------------------------------------------------- primitives
def light_field(w, h, base, t):
    """A pale surface derived from the palette, not a new colour.

    `lerp` returns an RGB tuple, so this feeds PIL's fill= directly.
    """
    img = Image.new("RGB", (w, h), lerp(WHITE, base, t))
    return img


def soft_blob(img, cx, cy, r, col, t):
    """A brand-coloured wash. Decorative only -- never behind body text."""
    base = img.copy()
    wash = Image.new("RGB", img.size, lerp(WHITE, col, t))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return Image.composite(wash, base, mask.filter(ImageFilter.GaussianBlur(max(2, r // 3))))


def rule(img, x, y, w, h):
    seg = max(1, w // len(ACCENT_RAMP))
    d = ImageDraw.Draw(img)
    for i, hexcol in enumerate(ACCENT_RAMP):
        x0 = x + i * seg
        x1 = x + (i + 1) * seg if i < len(ACCENT_RAMP) - 1 else x + w
        d.rectangle([(x0, y), (x1, y + h)], fill=hex_to_rgb(hexcol))
    return img


def text(d, xy, s, font, fill, ground, width=0, center=False, display=False):
    if not s:
        return
    allowed = _DISPLAY_SAFE if display else _BODY_SAFE
    assert fill in allowed, (
        f"{fill} is not text-safe on a light ground "
        f"(contrast {contrast(fill, ground):.2f}:1) -- it is decorative only"
    )
    rgb = hex_to_rgb(fill)
    if center:
        for line in (_wrap_text(s, font, width) if width else [s]):
            d.text(xy, line, font=font, fill=rgb, anchor="mm")
            xy = (xy[0], xy[1] + int(font.size * 1.16))
        return
    for i, line in enumerate((_wrap_text(s, font, width) if width else [s])):
        d.text((xy[0], xy[1] + i * int(font.size * 1.16)), line, font=font, fill=rgb)


def tofu_chars(font, s):
    """Characters that render as .notdef boxes.

    A .notdef box is bit-identical to an unmapped codepoint, so U+E000 (private
    use, guaranteed absent from every font) is the reference. A PNG-size
    assertion cannot catch this -- a card full of boxes is exactly as large as a
    real glyph -- so the glyph itself has to be compared.
    """
    def bitmap(ch):
        box = int(font.size * 1.8)
        im = Image.new("L", (box, box), 0)
        ImageDraw.Draw(im).text((box * 0.1, box * 0.1), ch, font=font, fill=255)
        return im.tobytes()

    ref = bitmap("\ue000")
    return [c for c in s if not c.isspace() and bitmap(c) == ref]


# ---------------------------------------------------------------- concepts
def concept_f(w, h):
    """Lavender Editorial -- pale lavender ground, violet serif headline, one
    orange rule. Closest to the current structure, just inverted to light."""
    ground = lerp(WHITE, PURPLE, 0.07)
    img = soft_blob(light_field(w, h, PURPLE, 0.07), int(w * 0.86), int(h * 0.80),
                    int(min(w, h) * 0.46), VIOLET, 0.30)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.075)
    img = rule(img, pad, int(h * 0.20), int(w * 0.26), max(5, h // 150))
    d = ImageDraw.Draw(img)
    text(d, (pad, int(h * 0.25)), KICKER, _find_font(int(h * 0.030), serif=False),
         VIOLET, "#F8F3FF")
    f = _find_font(int(h * 0.082), serif=True)
    text(d, (pad, int(h * 0.33)), TITLE, f, VIOLET, "#F8F3FF", width=int(w * 0.78))
    d.rectangle([(pad, int(h * 0.86)), (pad + int(w * 0.10), int(h * 0.86) + max(4, h // 200))],
                fill=hex_to_rgb(ORANGE))
    text(d, (pad, int(h * 0.89)), FOOTER, _find_font(int(h * 0.028), serif=False),
         LICORICE, "#F8F3FF")
    return img


def concept_g(w, h):
    """White Grid -- pure white, licorice sans headline, one purple display word
    (large enough to clear the 3:1 bar that PURPLE fails for body), full
    ACCENT_RAMP hairline. The most 'brand manual' of the three."""
    img = light_field(w, h, WHITE, 0.0)
    d = ImageDraw.Draw(img)
    pad = int(w * 0.075)
    blk = int(min(w, h) * 0.085)
    d.rectangle([(pad, int(h * 0.16)), (pad + blk, int(h * 0.16) + blk)],
                fill=hex_to_rgb(PURPLE))
    text(d, (pad + blk + int(w * 0.025), int(h * 0.16) + blk // 2), KICKER,
         _find_font(int(h * 0.032), serif=False), LICORICE, WHITE, center=False)
    f = _find_font(int(h * 0.090), serif=False)
    lines = _wrap_text(TITLE, f, int(w * 0.80))
    y = int(h * 0.34)
    for i, line in enumerate(lines):
        # the last word carries the brand colour, at display size where PURPLE clears 3:1
        if i == len(lines) - 1 and " " in line:
            head, _, tail = line.rpartition(" ")
            d.text((pad, y + i * int(f.size * 1.14)), head + " ", font=f, fill=hex_to_rgb(LICORICE))
            d.text((pad + d.textlength(head + " ", font=f), y + i * int(f.size * 1.14)), tail,
                   font=f, fill=hex_to_rgb(PURPLE))
        else:
            d.text((pad, y + i * int(f.size * 1.14)), line, font=f, fill=hex_to_rgb(LICORICE))
    img = rule(img, pad, int(h * 0.72), int(w * 0.855), max(4, h // 200))
    text(d, (pad, int(h * 0.77)), FOOTER, _find_font(int(h * 0.030), serif=False),
         LICORICE, WHITE)
    text(d, (w - pad, int(h * 0.77)), "AI Made Simple", _find_font(int(h * 0.030), serif=False),
         LICORICE, WHITE)
    return img


def concept_h(w, h):
    """Warm Split -- cream ground with a pink side panel and an orange wash. The
    warmest and least 'tech-purple' of the three."""
    img = light_field(w, h, ORANGE, 0.08)
    img = soft_blob(img, int(w * 0.10), int(h * 0.88), int(min(w, h) * 0.52), ORANGE, 0.34)
    panel_w = int(w * 0.30)
    d = ImageDraw.Draw(img)
    d.rectangle([(0, 0), (panel_w, h)], fill=lerp(WHITE, PINK, 0.16))
    d.rectangle([(panel_w, 0), (panel_w + max(5, w // 400), h)], fill=hex_to_rgb(ORANGE))
    text(d, (int(panel_w * 0.18), int(h * 0.42)), KICKER, _find_font(int(h * 0.030), serif=True),
         VIOLET, lerp_hex(WHITE, PINK, 0.16))
    text(d, (int(panel_w * 0.18), int(h * 0.42) + int(h * 0.09)), "01", _find_font(int(h * 0.11), serif=True),
         PURPLE, lerp_hex(WHITE, PINK, 0.16), display=True)
    f = _find_font(int(h * 0.078), serif=True)
    tx = panel_w + int(w * 0.055)
    text(d, (tx, int(h * 0.30)), TITLE, f, LICORICE, lerp_hex(WHITE, ORANGE, 0.08),
         width=int(w - tx - int(w * 0.075)))
    d.rectangle([(tx, int(h * 0.72)), (tx + int(w * 0.09), int(h * 0.72) + max(4, h // 200))],
                fill=hex_to_rgb(PINK))
    text(d, (tx, int(h * 0.76)), FOOTER, _find_font(int(h * 0.028), serif=False),
         LICORICE, lerp_hex(WHITE, ORANGE, 0.08))
    return img


CONCEPTS = {"F": concept_f, "G": concept_g, "H": concept_h}


def _report(ground_hex, ink_hex, display_hex):
    rows = [
        ("LICORICE", LICORICE, True), ("VIOLET", VIOLET, True), ("PURPLE", PURPLE, False),
        ("PINK", PINK, False), ("ORANGE", ORANGE, False), ("LIGHT_ORANGE", LIGHT_ORANGE, False),
        ("AMBER", AMBER, False),
    ]
    print(f"\nsurface {ground_hex}   (header ink {ink_hex}, display ink {display_hex})")
    print(f"  {'colour':<14}{'ratio':>8}   verdict")
    for name, hexcol, body_ok in rows:
        r = contrast(hexcol, ground_hex)
        bar = "body text OK" if r >= 4.5 else ("LARGE text only" if r >= 3 else "decorative only")
        mark = "" if body_ok == (r >= 4.5) else "  <-- unexpected"
        print(f"  {name:<14}{r:>7.2f}:1   {bar}{mark}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/app/output/concepts")
    ap.add_argument("--format", default="long", choices=["long", "shorts"])
    ap.add_argument("--report", action="store_true",
                    help="print measured contrast per concept and run the tofu check")
    args = ap.parse_args()
    w, h = (1280, 720) if args.format == "long" else (1080, 1920)
    os.makedirs(args.out, exist_ok=True)
    made = []
    for name, fn in CONCEPTS.items():
        p = os.path.join(args.out, f"concept_{name.lower()}_{args.format}.png")
        fn(w, h).save(p, "PNG")
        made.append(p)
        print(f"WROTE {p} ({os.path.getsize(p)} bytes)")
        if args.report:
            f_disp = _find_font(int(h * 0.090), serif=False)
            f_body = _find_font(int(h * 0.045), serif=True)
            for lbl, fnt in (("display", f_disp), ("body", f_body)):
                bad = tofu_chars(fnt, TITLE + KICKER + FOOTER)
                print(f"  glyph check {lbl} ({fnt.getname()}): "
                      f"{'OK - no tofu' if not bad else 'TOFU in ' + repr(bad)}")
    if args.report:
        _report(lerp_hex(WHITE, PURPLE, 0.07), VIOLET, PURPLE)
        _report(WHITE, LICORICE, PURPLE)
        _report(lerp_hex(WHITE, ORANGE, 0.08), LICORICE, PURPLE)
    print(f"\n{len(made)} concepts in {args.out}")


if __name__ == "__main__":
    main()
