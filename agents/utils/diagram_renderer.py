"""Render 2D diagrams (flow charts, bar charts, comparison tables, timelines)
as PNG frames using PIL, compositable into video via overlay or still image input.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

import math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # ponytail: PIL required, render returns None if missing

FONT_PATH = os.getenv("FONT_PATH") or "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = os.getenv("FONT_PATH_BOLD", FONT_PATH)
FONT_SIZE = 18

# Brand colours, derived from the single source of truth. These were local RGB
# tuples pinned to the pre-rebrand palette (teal #00CCCC, orange #FF6B35, purple
# #8a50e8, dark #1e1e1e), which is why diagrams kept rendering in retired teal
# after the rebrand landed.
from utils.brand_palette import (  # noqa: E402
    PURPLE as _PURPLE_HEX,
    ORANGE as _ORANGE_HEX,
    LICORICE as _DARK_HEX,
    WHITE as _WHITE_HEX,
    hex_to_rgb,
)

TEAL = hex_to_rgb(_PURPLE_HEX)   # retired teal slot, now brand purple
ORANGE = hex_to_rgb(_ORANGE_HEX)
PURPLE = hex_to_rgb(_PURPLE_HEX)
DARK = hex_to_rgb(_DARK_HEX)
WHITE = hex_to_rgb(_WHITE_HEX)
LIGHT_GRAY = (200, 200, 200)

# Default diagram accent: brand purple, not the retired teal.
DEFAULT_ACCENT = _PURPLE_HEX


_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _resolve_font(size: int, text: str = "") -> ImageFont.FreeTypeFont:
    """Find a TrueType font that covers `text`.

    The module-level FONT_PATH/_FONT_CANDIDATES are Latin-only DejaVu/Liberation,
    so non-Latin labels would render as .notdef boxes. When `text` is non-Latin
    the script is detected from the text itself and a covering font is used
    instead, so callers need no language context.
    """
    candidates = [FONT_PATH] + _FONT_CANDIDATES
    if text:
        from utils.fonts import font_for_text
        covering = font_for_text(text)
        if covering and os.path.exists(covering):
            candidates.insert(0, covering)
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _font(size: int = FONT_SIZE, bold: bool = False, text: str = "") -> ImageFont.FreeTypeFont:
    return _resolve_font(size, text)


def render_diagram(spec: dict, width: int = 1920, height: int = 1080) -> Optional[str]:
    """Render a diagram spec to a PNG file. Returns path or None.

    Spec format:
    {
        "type": "flow" | "bar" | "comparison" | "timeline" | "architecture",
        "title": "Optional title",
        "items": [...],    # type-specific
        "color": "#9B4DFF" # accent override
    }
    """
    if Image is None:
        return None
    img = Image.new("RGB", (width, height), DARK)
    draw = ImageDraw.Draw(img)

    diagram_type = spec.get("type", "flow")
    title = spec.get("title", "")
    # Default accent comes from the brand palette. This was hardcoded to the
    # retired teal #00CCCC, so every diagram that didn't override `color` was
    # drawn in pre-rebrand teal.
    accent = _parse_color(spec.get("color") or DEFAULT_ACCENT)
    items = spec.get("items", [])

    if title:
        tf = _font(32, bold=True, text=title)
        tw = draw.textlength(title, font=tf)
        draw.text(((width - tw) / 2, 20), title, fill=WHITE, font=tf)

    margin_top = 70 if title else 40
    body_h = height - margin_top - 40

    if diagram_type == "flow":
        _render_flow(draw, items, width, body_h, margin_top, accent)
    elif diagram_type == "bar":
        _render_bar(draw, items, width, body_h, margin_top, accent)
    elif diagram_type == "comparison":
        _render_comparison(draw, items, width, body_h, margin_top, accent)
    elif diagram_type == "timeline":
        _render_timeline(draw, items, width, body_h, margin_top, accent)
    elif diagram_type == "architecture":
        _render_architecture(draw, items, width, body_h, margin_top, accent)

    out = tempfile.mktemp(suffix=".png", dir=os.environ.get("TMPDIR", "/tmp"))
    img.save(out, "PNG")
    return out


def _parse_color(hex_str: str) -> tuple:
    h = hex_str.lstrip("#")
    if len(h) != 6:
        return TEAL
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _text_w(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont) -> int:
    return int(draw.textlength(text, font=font))


def _render_flow(draw: ImageDraw.Draw, items: list, width: int,
                 body_h: int, margin_top: int, accent: tuple):
    """Flow chart: horizontal boxes with arrows."""
    n = len(items)
    if n == 0:
        return
    bw = min(280, (width - 80) // n)
    bh = 60
    gap = min(40, (width - n * bw) // (n + 1))
    y = margin_top + (body_h - bh) // 2
    for i, item in enumerate(items):
        label = item if isinstance(item, str) else item.get("label", "")
        x = gap + i * (bw + gap)
        draw.rectangle([x, y, x + bw, y + bh], outline=accent, width=2, fill=(50, 50, 50))
        f = _font(14, text=label)
        tw = _text_w(draw, label, f)
        draw.text((x + (bw - tw) / 2, y + (bh - 20) / 2), label, fill=WHITE, font=f)
        if i < n - 1:
            ax = x + bw
            ay = y + bh / 2
            draw.line([ax, ay, ax + gap - 5, ay], fill=accent, width=2)
            _draw_arrowhead(draw, ax + gap - 5, ay, accent, "right")


def _render_bar(draw: ImageDraw.Draw, items: list, width: int,
                body_h: int, margin_top: int, accent: tuple):
    """Bar chart with labels."""
    n = len(items)
    if n == 0:
        return
    vals = [(item if isinstance(item, (int, float)) else item.get("value", 0)) for item in items]
    labels = [(str(item) if isinstance(item, (int, float)) else item.get("label", "")) for item in items]
    max_v = max(vals) if max(vals) > 0 else 1
    bar_w = min(60, (width - 120) // n - 10)
    gap = (width - 120 - n * bar_w) // (n - 1) if n > 1 else 0
    x0 = 60
    y0 = margin_top + body_h - 30
    draw.line([x0, y0, width - 60, y0], fill=LIGHT_GRAY, width=1)
    for i in range(n):
        bh = max(10, int((vals[i] / max_v) * (body_h - 60)))
        bx = x0 + i * (bar_w + gap)
        by = y0 - bh
        draw.rectangle([bx, by, bx + bar_w, y0], fill=accent, width=0)
        f = _font(12, text=labels[i])
        lbl = labels[i][:12]
        tw = _text_w(draw, lbl, f)
        draw.text((bx + (bar_w - tw) / 2, y0 + 5), lbl, fill=LIGHT_GRAY, font=f)
        val_str = str(vals[i])
        vw = _text_w(draw, val_str, f)
        draw.text((bx + (bar_w - vw) / 2, by - 18), val_str, fill=WHITE, font=f)


def _render_comparison(draw: ImageDraw.Draw, items: list, width: int,
                       body_h: int, margin_top: int, accent: tuple):
    """Side-by-side comparison table."""
    n = len(items)
    if n == 0:
        return
    cols = n
    col_w = (width - 120) // cols
    y = margin_top + 10
    rh = 30
    all_text = " ".join(
        str(x) for it in items
        for x in ([it.get("header", "") if isinstance(it, dict) else str(it)]
                 + [r if isinstance(r, str) else r.get("text", str(r))
                    for r in (it.get("rows", []) if isinstance(it, dict) else [])]))
    header_f = _font(16, bold=True, text=all_text)
    cell_f = _font(14, text=all_text)
    for c in range(cols):
        item = items[c] if isinstance(items[c], dict) else {"header": str(items[c])}
        header = item.get("header", str(items[c]))
        cx = 60 + c * col_w
        draw.rectangle([cx, y, cx + col_w - 4, y + rh], outline=accent, width=1, fill=(50, 50, 50))
        tw = _text_w(draw, header, header_f)
        draw.text((cx + (col_w - tw) / 2, y + 5), header, fill=accent, font=header_f)
        rows = item.get("rows", [])
        for r, row in enumerate(rows):
            ry = y + (r + 1) * rh + 4
            if ry > margin_top + body_h:
                break
            draw.rectangle([cx, ry, cx + col_w - 4, ry + rh - 2],
                           outline=DARK, width=0, fill=(45, 45, 45))
            rl = row if isinstance(row, str) else row.get("text", str(row))
            tw = _text_w(draw, rl, cell_f)
            draw.text((cx + (col_w - tw) / 2, ry + 5), rl, fill=WHITE, font=cell_f)


def _render_timeline(draw: ImageDraw.Draw, items: list, width: int,
                     body_h: int, margin_top: int, accent: tuple):
    """Horizontal timeline with milestones."""
    n = len(items)
    if n == 0:
        return
    y = margin_top + body_h // 2
    x0 = 80
    x1 = width - 80
    draw.line([x0, y, x1, y], fill=accent, width=2)
    for i, item in enumerate(items):
        x = x0 + (x1 - x0) * i // (n - 1) if n > 1 else (x0 + x1) // 2
        dot_r = 8
        draw.ellipse([x - dot_r, y - dot_r, x + dot_r, y + dot_r], fill=accent, width=0)
        label = item if isinstance(item, str) else item.get("label", "")
        desc = item if isinstance(item, str) else item.get("description", "")
        f = _font(14, text=label)
        tw = _text_w(draw, label, f)
        draw.text((x - tw / 2, y - 40), label, fill=WHITE, font=f)
        if desc:
            df = _font(12, text=desc)
            dw = _text_w(draw, desc, df)
            draw.text((x - dw / 2, y + 20), desc, fill=LIGHT_GRAY, font=df)


def _render_architecture(draw: ImageDraw.Draw, items: list, width: int,
                         body_h: int, margin_top: int, accent: tuple):
    """Architecture block diagram: boxes organized in layers."""
    if not items:
        return
    layers = items
    n_layers = len(layers)
    layer_h = body_h // n_layers - 10
    for li, layer in enumerate(layers):
        layer_label = layer.get("layer", "") if isinstance(layer, dict) else ""
        blocks = layer.get("blocks", layer) if isinstance(layer, dict) else layer
        if isinstance(blocks, str):
            blocks = [blocks]
        blocks = list(blocks) if not isinstance(blocks, list) else blocks
        nb = len(blocks)
        bw = min(200, (width - 80) // nb - 10)
        bh = min(layer_h - 10, 50)
        bx0 = (width - nb * bw - (nb - 1) * 10) // 2
        ly = margin_top + li * (layer_h + 10)
        for bi, block in enumerate(blocks):
            b_label = block if isinstance(block, str) else block.get("label", "")
            bx = bx0 + bi * (bw + 10)
            by = ly + (layer_h - bh) // 2
            draw.rectangle([bx, by, bx + bw, by + bh], outline=accent, width=2, fill=(50, 50, 50))
            f = _font(12, text=b_label)
            tw = _text_w(draw, b_label, f)
            draw.text((bx + (bw - tw) / 2, by + (bh - 16) / 2), b_label, fill=WHITE, font=f)
            if li < n_layers - 1 and bi < len(layers[li + 1].get("blocks", [])):
                dy = by + bh
                draw.line([bx + bw / 2, dy, bx + bw / 2, dy + 10], fill=accent, width=1)
                _draw_arrowhead(draw, bx + bw / 2, dy + 10, accent, "down")


def _draw_arrowhead(draw: ImageDraw.Draw, x: float, y: float,
                    color: tuple, direction: str = "right", size: int = 8):
    pts = []
    if direction == "right":
        pts = [(x, y), (x - size, y - size // 2), (x - size, y + size // 2)]
    elif direction == "down":
        pts = [(x, y), (x - size // 2, y - size), (x + size // 2, y - size)]
    elif direction == "left":
        pts = [(x, y), (x + size, y - size // 2), (x + size, y + size // 2)]
    elif direction == "up":
        pts = [(x, y), (x - size // 2, y + size), (x + size // 2, y + size)]
    draw.polygon(pts, fill=color)
