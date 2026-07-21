"""Render 2D diagrams (flow charts, bar charts, comparison tables, timelines)
as PNG frames using PIL, compositable into video via overlay or still image input.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

import math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None  # ponytail: PIL required, render returns None if missing

FONT_PATH = "/System/Library/Fonts/Helvetica.ttc"
FONT_BOLD = "/System/Library/Fonts/Helvetica.ttc"
FONT_SIZE = 18

TEAL = (0, 204, 204)
ORANGE = (255, 107, 53)
PURPLE = (138, 80, 232)
DARK = (30, 30, 30)
WHITE = (255, 255, 255)
LIGHT_GRAY = (200, 200, 200)


def _font(size: int = FONT_SIZE, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_PATH
    if not os.path.exists(path):
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)


def render_diagram(spec: dict, width: int = 1920, height: int = 1080) -> Optional[str]:
    """Render a diagram spec to a PNG file. Returns path or None.

    Spec format:
    {
        "type": "flow" | "bar" | "comparison" | "timeline" | "architecture",
        "title": "Optional title",
        "items": [...],    # type-specific
        "color": "#00CCCC" # accent override
    }
    """
    if Image is None:
        return None
    img = Image.new("RGB", (width, height), DARK)
    draw = ImageDraw.Draw(img)

    diagram_type = spec.get("type", "flow")
    title = spec.get("title", "")
    accent = _parse_color(spec.get("color", "#00CCCC"))
    items = spec.get("items", [])

    if title:
        tf = _font(32, bold=True)
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
        f = _font(14)
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
        f = _font(12)
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
    header_f = _font(16, bold=True)
    cell_f = _font(14)
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
        f = _font(14)
        tw = _text_w(draw, label, f)
        draw.text((x - tw / 2, y - 40), label, fill=WHITE, font=f)
        if desc:
            df = _font(12)
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
            f = _font(12)
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
