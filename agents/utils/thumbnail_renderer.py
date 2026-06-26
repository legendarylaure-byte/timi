import os
import random
import math
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")
os.makedirs(FONT_DIR, exist_ok=True)

COLORS = {
    "bg_dark": (10, 10, 15),
    "indigo": (99, 102, 241),
    "cyan": (34, 211, 238),
    "violet": (167, 139, 250),
    "white": (255, 255, 255),
    "gray": (156, 163, 175),
    "accent_gradient_start": (99, 102, 241),
    "accent_gradient_end": (34, 211, 238),
}


def _find_font(size: int = 48):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Helvetica.ttf",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_gradient_bar(draw: ImageDraw, width: int, height: int, bar_height: int = 6):
    for x in range(width):
        ratio = x / width
        r = int(COLORS["accent_gradient_start"][0] * (1 - ratio) + COLORS["accent_gradient_end"][0] * ratio)
        g = int(COLORS["accent_gradient_start"][1] * (1 - ratio) + COLORS["accent_gradient_end"][1] * ratio)
        b = int(COLORS["accent_gradient_start"][2] * (1 - ratio) + COLORS["accent_gradient_end"][2] * ratio)
        draw.line([(x, height - bar_height), (x, height)], fill=(r, g, b))


def _draw_grid(draw: ImageDraw, width: int, height: int, spacing: int = 60, opacity: int = 15):
    grid_color = (255, 255, 255, opacity)
    for x in range(0, width, spacing):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, spacing):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)


def _draw_circle_decoration(draw: ImageDraw, width: int, height: int, count: int = 3):
    for _ in range(count):
        cx = random.randint(50, width - 50)
        cy = random.randint(50, height - 50)
        r = random.randint(40, 120)
        color = random.choice([COLORS["indigo"], COLORS["cyan"], COLORS["violet"]])
        color = (*color[:3], 30)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=None)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bb = font.getbbox(test_line)
        w = bb[2] - bb[0]
        if w <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def _apply_glow(draw: ImageDraw, text: str, x: int, y: int, font: ImageFont.FreeTypeFont, color: tuple, glow_strength: int = 3):
    for dx in range(-glow_strength, glow_strength + 1):
        for dy in range(-glow_strength, glow_strength + 1):
            if dx == 0 and dy == 0:
                continue
            draw.text((x + dx, y + dy), text, font=font, fill=(color[0], color[1], color[2], 80))
    draw.text((x, y), text, font=font, fill=color)


def generate_thumbnail(
    title: str,
    category: str = "",
    output_path: str = "",
    width: int = 1280,
    height: int = 720,
    variant: str = "comparison",
) -> str:
    img = Image.new("RGBA", (width, height), COLORS["bg_dark"])
    draw = ImageDraw.Draw(img)

    _draw_grid(draw, width, height, spacing=80, opacity=10)
    _draw_circle_decoration(draw, width, height, count=4)
    _draw_gradient_bar(draw, width, height)

    title_font_size = 64 if len(title) < 30 else 52 if len(title) < 50 else 40
    title_font = _find_font(title_font_size)
    sub_font = _find_font(28)

    max_text_width = width - 120
    title_lines = _wrap_text(title.upper(), title_font, max_text_width)
    line_height = title_font_size + 8
    total_text_height = len(title_lines) * line_height
    start_y = (height - total_text_height) // 2 - 20

    for i, line in enumerate(title_lines):
        bb = title_font.getbbox(line)
        line_w = bb[2] - bb[0]
        x = (width - line_w) // 2
        y = start_y + i * line_height
        color = COLORS["indigo"] if i == 0 else COLORS["white"]
        _apply_glow(draw, line, x, y, title_font, color, glow_strength=4)

    category_label = category.upper() if category else "TECH"
    cat_bb = sub_font.getbbox(category_label)
    cat_w = cat_bb[2] - cat_bb[0]
    cat_x = (width - cat_w) // 2
    cat_y = start_y + total_text_height + 20
    draw.text((cat_x, cat_y), category_label, font=sub_font, fill=COLORS["cyan"])

    padding = 20
    border_color = COLORS["indigo"] + (40,)
    for i in range(2):
        draw.rectangle(
            [padding + i * 3, padding + i * 3, width - padding - i * 3, height - padding - i * 3],
            outline=border_color[:3] + (40 - i * 10,),
            width=2,
        )

    if not output_path:
        safe_title = "".join(c if c.isalnum() or c in " -_" else "_" for c in title)[:50].strip()
        thumb_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "thumbnails")
        os.makedirs(thumb_dir, exist_ok=True)
        output_path = os.path.join(thumb_dir, f"thumb_{safe_title}_{variant}.png")

    img.save(output_path, "PNG")
    return output_path


def generate_thumbnail_variants(title: str, category: str = "", count: int = 3) -> list:
    variants_config = [
        {"variant": "comparison", "subtitle": "VS"},
        {"variant": "question", "subtitle": "?"},
        {"variant": "list", "subtitle": "TOP 5"},
    ]
    paths = []
    for config in variants_config[:count]:
        display_title = f"{config['subtitle']} {title}" if len(f"{config['subtitle']} {title}") < 60 else title
        path = generate_thumbnail(display_title, category, variant=config["variant"])
        paths.append(path)
    return paths
