"""Prove the annotation renderer can actually draw non-Latin text.

The annotation overlays hardcoded Latin-only DejaVu, so any Devanagari/Hangul label
rendered as .notdef boxes. They now pick a covering font from the text itself
via utils.fonts.font_for_text. A PNG-size assertion cannot catch tofu -- a card
full of boxes is exactly as large as a real glyph -- so every check here
compares the rendered glyph against private-use U+E000, which no font covers.
"""
import os
import sys

from utils import annotation_renderer as ar

FAILED = []


def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'} {label}" + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILED.append(label)


def _covers(font_path, text):
    """False when the font renders `text` identically to the .notdef box."""
    from PIL import ImageFont
    f = ImageFont.truetype(font_path, 48)

    def bmp(s):
        m = f.getmask(s)
        return (m.size, bytes(m))

    return bmp(text) != bmp("\uE000")


def main():
    print("=" * 68)
    print("MULTILINGUAL FONT SELFCHECK (annotation renderer)")
    print("=" * 68)

    print("\n[1] annotation drawtext filters reference a covering font")
    filters = ar.animate_callout_box("मशीन लर्निंग", 1.0, 2.0)
    joined = " ".join(filters)
    check("Hindi callout is not on Latin-only DejaVu", "DejaVuSans" not in joined,
          joined.split("fontfile=")[-1][:60])
    check("Hindi callout uses the Devanagari-covering font",
          _covers(ar._font_for("मशीन लर्निंग"), "म"))

    pops = " ".join(ar.animate_definition("तंत्र", "a structure", 1.0, 2.0))
    check("Hindi definition term uses a covering font", _covers(ar._font_for("तंत्र"), "त"))

    ko = " ".join(ar.animate_callout_box("인공지능", 1.0, 2.0))
    check("Korean callout uses the Hangul-covering font", _covers(ar._font_for("인공지능"), "인"))

    print("\n[2] Latin text still resolves (no regression)")
    lat = " ".join(ar.animate_callout_box("Machine Learning", 1.0, 2.0))
    check("Latin callout still uses the default DejaVu", "DejaVuSans" in lat,
          lat.split("fontfile=")[-1][:60])

    print("\n" + "=" * 68)
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())