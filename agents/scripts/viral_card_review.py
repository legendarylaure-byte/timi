"""Render competing viral-card type scales through the REAL generate_image().

Ponytail: this is the review mechanism, so it earns its place only by measuring
the shipped code rather than a copy of it. The P4 lesson was an audit that
called its own helper and kept printing the pre-fix answer after the fix landed
-- so every card here comes out of `viral_news_agent.generate_image()` with
`_CARD_SCALE` / `_CARD_SUMMARY_CHARS` patched. Nothing below re-implements the
drawing code, and if the layout changes this sheet changes with it.

Writes agents/output/viral_card_review/{contact_sheet.png,report.json}.
Those are evidence, not source: never commit them.

    python3 -m scripts.viral_card_review          # (run inside the container)
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from utils import viral_news_agent as vna  # noqa: E402

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output", "viral_card_review",
)

# The two scales that were compared on 09-29. B is now the shipped default in
# vna._CARD_SCALE (owner choice). A stays here because this script is the
# measurement, not the decision: if the type is ever retuned, re-render both and
# compare worst_gap_pct rather than eyeballing it. The module is the single
# source of truth for what actually ships.
#
# A is balanced: headline and body get equal billing. B is headline-led: it buys
# a 92px headline by spending body size and summary length. Both bottom-anchor
# the panel, because the measured problem was dead space, not the anchoring.
OPTIONS = {
    "A-balanced": {
        "title": 0.075, "body": 0.040, "body_line": 0.038, "chars": 230,
    },
    "B-headline-led": {
        "title": 0.085, "body": 0.037, "body_line": 0.036, "chars": 200,
    },
}


def _scale_for(spec: dict) -> dict:
    """Build a full _CARD_SCALE dict. Line spacing is derived from the title, so a
    bigger headline can never silently overlap the summary under it."""
    s = dict(vna._CARD_SCALE)
    s["title"] = spec["title"]
    s["line"] = spec["title"] * 1.20
    s["body"] = spec["body"]
    s["body_line"] = spec["body_line"]
    return s


# Real headline shapes. The 5-line case is the pathological tail that the
# no-overlap clamp exists for, not decoration.
LONG_BODY = (
    "Researchers will work on superconducting qubits and quantum error "
    "correction, and the site will train students and accept outside projects "
    "from 2027, according to officials at the ministry."
)
SHORT_BODY = "Nepal opened its first quantum computing research laboratory in Kathmandu."

SHAPES = [
    ("2-line headline, short summary", {
        "title": "Nepal Opens First Quantum Lab In Kathmandu",
        "body": SHORT_BODY, "source": "The Kathmandu Post",
    }),
    ("3-line headline, long summary", {
        "title": "Nepal Opens Its First Quantum Computing Research "
                 "Laboratory In Kathmandu",
        "body": LONG_BODY, "source": "The Kathmandu Post",
    }),
    ("4-line headline, long summary", {
        "title": "Nepal Opens Its First Quantum Computing Research "
                 "Laboratory In The Capital With Government Funding",
        "body": LONG_BODY, "source": "OnlineKhabar",
    }),
    ("5-line headline, long summary", {
        "title": "Nepal Opens Its First Quantum Computing Research Laboratory "
                 "In Kathmandu With Government Funding And Two Universities",
        "body": LONG_BODY, "source": "The Kathmandu Post",
    }),
    ("5-line headline, no summary", {
        "title": "Nepal Opens Its First Quantum Computing Research Laboratory "
                 "In Kathmandu With Government Funding And Two Universities",
        "body": "", "source": "Nepali Times",
    }),
]


def _article(spec: dict) -> dict:
    return {
        "title": spec["title"],
        "summary": spec["body"],
        "description": spec["body"],
        "content": spec["body"],
        "source": spec["source"],
        "link": "https://kathmandupost.com/nepal/quantum-lab-2026",
    }


def _ink_rows(card: Image.Image) -> list:
    """Rows that contain anything drawn on top of the background.

    Diffs against `_spotlight_background`, which is the exact function
    generate_image paints under the text. So "ink" is exact -- no brightness
    threshold guessing, which is how the P4 caption measurement lied (a luma>230
    'white text' proxy reported zero burned captions on amber text).
    """
    bg = vna._spotlight_background(card.width, card.height)
    w, h = card.size
    bgpx, cpx = bg.load(), card.load()
    rows = []
    for y in range(h):
        for x in range(0, w, 4):  # every 4th column is plenty to find ink
            if cpx[x, y][:3] != bgpx[x, y][:3]:
                rows.append(y)
                break
    return rows


def _measure(path: str, W: int, H: int) -> dict:
    """Balance, not just "how much ink".

    The first version of this reported `content_span_pct` (last ink row minus
    first), which was 99.1% on every card because the URL always sits at the
    bottom -- a metric that cannot distinguish a good card from a bad one is
    the same failure as a test that cannot fail. What actually matters for the
    "does this fill the card" complaint is the two empty bands: above the text
    block and below it (between the divider and the panel). Balanced bands read
    as padding; one large band reads as a hole.
    """
    card = Image.open(path).convert("RGB")
    rows = _ink_rows(card)
    bar_h = int(H * 0.035)
    panel_top = H - int(H * 0.075) - int(H * 0.105)
    # Skip the gradient accent strip: it spans the full width, so it is ink on
    # every row it touches and would otherwise read as the text block starting at
    # row 0 (which is how this first measured a negative top gap).
    above = [r for r in rows if bar_h < r < panel_top]
    if not above:
        return {"ink_rows": len(rows), "gap_top_pct": 100.0, "gap_bottom_pct": 100.0}
    gap_top = above[0] - bar_h                  # below the gradient strip
    gap_bottom = panel_top - above[-1]          # between divider and panel
    return {
        "ink_rows": len(rows),
        "gap_top_px": gap_top,
        "gap_top_pct": round(gap_top / H * 100, 1),
        "gap_bottom_px": gap_bottom,
        "gap_bottom_pct": round(gap_bottom / H * 100, 1),
        # One number for the sheet: the worse of the two bands.
        "worst_gap_pct": round(max(gap_top, gap_bottom) / H * 100, 1),
    }


def _label(img: Image.Image, text: str, sub: str = "") -> None:
    d = ImageDraw.Draw(img, "RGBA")
    try:
        f = ImageFont.truetype(vna._FONT_PATH, 22)
        fs = ImageFont.truetype(vna._FONT_PATH, 17)
    except Exception:
        f = fs = ImageFont.load_default()
    d.rectangle([0, 0, img.width, 56], fill=(10, 8, 18, 235))
    d.text((10, 6), text, fill=(255, 255, 255, 255), font=f)
    if sub:
        d.rectangle([0, 56, img.width, 78], fill=(10, 8, 18, 210))
        d.text((10, 58), sub, fill=(255, 190, 120, 255), font=fs)


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    W, H = vna._IMAGE_WIDTH, vna._IMAGE_HEIGHT
    report, cards, row_labels = [], [], []

    for name, spec in OPTIONS.items():
        orig_scale, orig_chars = dict(vna._CARD_SCALE), vna._CARD_SUMMARY_CHARS
        vna._CARD_SCALE = _scale_for(spec)
        vna._CARD_SUMMARY_CHARS = spec["chars"]
        try:
            for shape_name, art in SHAPES:
                path = vna.generate_image(_article(art), index=0)
                m = _measure(path, W, H)
                m.update(option=name, shape=shape_name,
                         title_px=int(H * spec["title"]),
                         fitted_px=int(H * vna._title_scale_for(
                             ImageDraw.Draw(Image.new("RGB", (W, H))),
                             art["title"], H, W, int(W * 0.075))),
                         body_px=int(H * spec["body"]),
                         chars=spec["chars"], file=os.path.basename(path))
                report.append(m)
                cards.append((name, shape_name, m, path))
                print(f"  {name:16s} {shape_name:34s} "
                      f"fit {m['fitted_px']:3d}px  top {m['gap_top_pct']:5.1f}%  "
                      f"bottom {m['gap_bottom_pct']:5.1f}%  worst {m['worst_gap_pct']:5.1f}%")
        finally:
            vna._CARD_SCALE, vna._CARD_SUMMARY_CHARS = orig_scale, orig_chars

    # Contact sheet: one row per shape, one column per option.
    TW, TH = 430, 430
    PAD, HDR = 14, 86
    sheet = Image.new("RGB",
                      (PAD + len(OPTIONS) * (TW + PAD), HDR + len(SHAPES) * (TH + PAD)),
                      (14, 12, 20))
    for r, shape_name in enumerate([s for s, _ in SHAPES]):
        y = HDR + r * (TH + PAD)
        for c, opt in enumerate(OPTIONS):
            hit = [k for k in cards if k[0] == opt and k[1] == shape_name]
            if not hit:
                continue
            _, _, m, path = hit[0]
            x = PAD + c * (TW + PAD)
            # Resize ONCE, label the thumbnail, then paste THAT. The original
            # version called _label() on a second, separate resize and pasted the
            # first -- so the per-card labels were drawn onto an image that was
            # then thrown away, and the sheet shipped with no labels at all.
            thumb = Image.open(path).convert("RGB").resize((TW, TH))
            _label(thumb, opt,
                   f"{m['title_px']}px title (fits {m['fitted_px']}px) / "
                   f"{m['body_px']}px body / {m['worst_gap_pct']:.0f}% worst gap")
            sheet.paste(thumb, (x, y))
    d = ImageDraw.Draw(sheet, "RGBA")
    try:
        hf = ImageFont.truetype(vna._FONT_PATH, 26)
    except Exception:
        hf = ImageFont.load_default()
    d.text((PAD, 14), "Viral card type-scale review — pick a column", fill=(255, 255, 255, 255), font=hf)
    d.text((PAD, 50), "rows = real headline shapes; worst gap = larger of the two empty bands",
           fill=(180, 170, 200, 255), font=hf)
    for r, shape_name in enumerate([s for s, _ in SHAPES]):
        d.text((PAD + len(OPTIONS) * (TW + PAD) + 8, HDR + r * (TH + PAD) + 12),
               shape_name.replace(", ", ",\n", 1), fill=(200, 195, 215, 255),
               font=ImageFont.load_default())

    sheet_path = os.path.join(OUT_DIR, "contact_sheet.png")
    sheet.save(sheet_path, "PNG")
    with open(os.path.join(OUT_DIR, "report.json"), "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nwrote {sheet_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
