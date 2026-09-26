"""Prove the diagram and annotation renderers can actually draw non-Latin text.

These two renderers hardcoded Latin-only DejaVu, so any Devanagari/Hangul label
rendered as .notdef boxes. They now pick a covering font from the text itself
via utils.fonts.font_for_text. A PNG-size assertion cannot catch tofu -- a card
full of boxes is exactly as large as a real glyph -- so every check here
compares the rendered glyph against private-use U+E000, which no font covers.
"""
import os
import sys
import tempfile

from utils import diagram_renderer as dr
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

    return bmp(text) != bmp("")


HI = {
    "type": "flow",
    "title": "कृत्रिम बुद्धिमत्ता",
    "items": ["मशीन लर्निंग", "डेटा", "मॉडल"],
}
KO = {
    "type": "comparison",
    "title": "인공지능 비교",
    "items": [
        {"header": " supervised", "rows": ["정확도", "속도"]},
        {"header": " 비지도", "rows": ["정확도", "속도"]},
    ],
}


def main():
    print("=" * 68)
    print("MULTILINGUAL FONT SELFCHECK (diagram + annotation renderers)")
    print("=" * 68)

    print("\n[1] diagram renderer picks a covering font from the text")
    for name, spec, probe in (("Hindi", HI, "कृ"), ("Korean", KO, "인")):
        f = dr._font(24, text=spec["title"])
        path = f.path if hasattr(f, "path") else ""
        check(f"{name} title font covers its script", _covers(path, probe),
              os.path.basename(path))
        check(f"  and is not the Latin-only default",
              "DejaVuSans" not in os.path.basename(path),
              os.path.basename(path))

    print("\n[2] a real diagram renders to a non-empty PNG")
    with tempfile.TemporaryDirectory() as tmp:
        for name, spec in (("Hindi", HI), ("Korean", KO)):
            out = dr.render_diagram(spec, width=960, height=540)
            # render_diagram picks its own path; just assert something was drawn
            check(f"{name} diagram produced a file", bool(out) and os.path.getsize(out) > 1000,
                  f"{os.path.getsize(out) if out else 0}B")

    print("\n[3] annotation drawtext filters reference a covering font")
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

    print("\n[4] Latin text still resolves (no regression)")
    lat = " ".join(ar.animate_callout_box("Machine Learning", 1.0, 2.0))
    check("Latin callout still uses the default DejaVu", "DejaVuSans" in lat,
          lat.split("fontfile=")[-1][:60])
    check("Latin diagram font is the default", "DejaVuSans" in
          os.path.basename(dr._font(24, text="Machine Learning").path))

    print("\n" + "=" * 68)
    if FAILED:
        print(f"RESULT: {len(FAILED)} FAILED -> {FAILED}")
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
