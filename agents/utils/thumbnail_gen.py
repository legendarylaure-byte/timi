import os
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter

THUMBNAIL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "thumbnails")
os.makedirs(THUMBNAIL_DIR, exist_ok=True)

COLOR_SCHEMES = [
    {"bg1": (255, 107, 107), "bg2": (78, 205, 196), "accent": (255, 230, 109), "text": (255, 255, 255)},
    {"bg1": (108, 92, 231), "bg2": (253, 121, 168), "accent": (255, 234, 167), "text": (255, 255, 255)},
    {"bg1": (0, 206, 201), "bg2": (255, 159, 67), "accent": (255, 255, 255), "text": (255, 255, 255)},
    {"bg1": (46, 213, 115), "bg2": (255, 165, 2), "accent": (255, 255, 255), "text": (255, 255, 255)},
    {"bg1": (255, 118, 117), "bg2": (86, 180, 233), "accent": (255, 255, 255), "text": (255, 255, 255)},
    {"bg1": (162, 155, 254), "bg2": (0, 210, 211), "accent": (253, 203, 110), "text": (255, 255, 255)},
    {"bg1": (116, 185, 255), "bg2": (223, 230, 233), "accent": (255, 118, 117), "text": (45, 52, 54)},
    {"bg1": (255, 159, 67), "bg2": (255, 107, 107), "accent": (46, 213, 115), "text": (255, 255, 255)},
]


def extract_sdxl_prompt(thumbnail_text: str) -> str:
    patterns = [
        r'SDXL.*?[Pp]rompt[:\s]*[":\s]*["\'"]?(.+?)["\'"]',
        r'"([^"]{20,})"',
        r'Image.*?[Pp]rompt[:\s]*(.+?)(?:\n\n|\Z)',
    ]
    for pattern in patterns:
        match = re.search(pattern, thumbnail_text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
    return ""


def extract_text_overlay(thumbnail_text: str) -> str:
    patterns = [
        r'[Tt]ext.*?[Oo]verlay.*?["\':]\s*["\']?([^"\'\\n]+)["\']?',
        r'"([^"]{3,30}!)"',
        r'"([^"]{3,30}\?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, thumbnail_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:40]
    words = thumbnail_text.split()
    for i, word in enumerate(words):
        if len(word) > 3 and word[0].isupper():
            return " ".join(words[max(0, i - 2):i + 3])
    return ""


def generate_thumbnail_image(topic: str, thumbnail_text: str, format_type: str = "shorts", output_filename: str = None) -> dict:  # noqa: E501
    if format_type == "shorts":
        width, height = 1080, 1920
    else:
        width, height = 1280, 720

    scheme = COLOR_SCHEMES[hash(topic) % len(COLOR_SCHEMES)]
    img = Image.new("RGB", (width, height), scheme["bg1"])
    draw = ImageDraw.Draw(img)

    try:
        gradient_steps = 200
        for i in range(gradient_steps):
            ratio = i / gradient_steps
            r = int(scheme["bg1"][0] + (scheme["bg2"][0] - scheme["bg1"][0]) * ratio)
            g = int(scheme["bg1"][1] + (scheme["bg2"][1] - scheme["bg1"][1]) * ratio)
            b = int(scheme["bg1"][2] + (scheme["bg2"][2] - scheme["bg1"][2]) * ratio)
            if format_type == "shorts":
                y = int(height * ratio)
                draw.rectangle([(0, y), (width, y + height // gradient_steps + 1)], fill=(r, g, b))
            else:
                x = int(width * ratio)
                draw.rectangle([(x, 0), (x + width // gradient_steps + 1, height)], fill=(r, g, b))
    except Exception:
        pass

    for seed_val in range(hash(topic) % 100, hash(topic) % 100 + 5):
        rng = seed_val
        cx = (rng * 17) % width
        cy = (rng * 23) % height
        radius = 50 + (rng * 7) % 150
        color = COLOR_SCHEMES[(seed_val + 1) % len(COLOR_SCHEMES)]["accent"]
        blob = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
        blob_draw = ImageDraw.Draw(blob)
        blob_draw.ellipse([(0, 0), (radius * 2, radius * 2)], fill=color + (60,))
        blob = blob.filter(ImageFilter.GaussianBlur(radius=25))
        img.paste(blob, (cx - radius, cy - radius), blob)

    text_overlay = extract_text_overlay(thumbnail_text)
    if not text_overlay or len(text_overlay) < 3:
        words = topic.split()[:4]
        text_overlay = " ".join(words)

    try:
        font_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if not os.path.exists(font_path):
            font_path = "/System/Library/Fonts/Helvetica.ttc"
        title_font = ImageFont.truetype(font_path, 80 if format_type == "long" else 100)
        subtitle_font = ImageFont.truetype(font_path, 40 if format_type == "long" else 50)
    except Exception:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    if format_type == "long":
        text_y = height // 3
        title_max_width = width - 100
        title_lines = _wrap_text(text_overlay, title_font, title_max_width)
        for line in title_lines:
            _draw_text_shadow(draw, line, (width // 2, text_y), title_font, scheme["text"])
            text_y += title_font.size + 20

        topic_lines = _wrap_text(topic, subtitle_font, title_max_width - 50)
        topic_y = text_y + 20
        for line in topic_lines:
            _draw_text_shadow(draw, line, (width // 2, topic_y), subtitle_font, scheme["accent"])
            topic_y += subtitle_font.size + 10
    else:
        text_y = height // 3
        title_max_width = width - 100
        title_lines = _wrap_text(text_overlay, title_font, title_max_width)
        for line in title_lines:
            _draw_text_shadow(draw, line, (width // 2, text_y), title_font, scheme["text"])
            text_y += title_font.size + 15

        topic_lines = _wrap_text(topic, subtitle_font, title_max_width - 50)
        topic_y = text_y + 30
        for line in topic_lines:
            _draw_text_shadow(draw, line, (width // 2, topic_y), subtitle_font, scheme["accent"])
            topic_y += subtitle_font.size + 8

    for seed_val in range(hash(topic + "sparkles") % 100, hash(topic + "sparkles") % 100 + 10):
        x = (seed_val * 31) % width
        y = (seed_val * 37) % height
        size = 3 + (seed_val * 3) % 8
        draw.ellipse([(x, y), (x + size, y + size)], fill=scheme["accent"] + (150,))

    if output_filename is None:
        output_filename = f"thumb_{format_type}_{hash(topic) % 100000}.png"
    output_path = os.path.join(THUMBNAIL_DIR, output_filename)
    img.save(output_path, "PNG", quality=95)

    return {
        "success": True,
        "path": output_path,
        "dimensions": f"{width}x{height}",
        "format": format_type,
    }


def _wrap_text(text: str, font, max_width: int) -> list:
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        try:
            bbox = font.getbbox(test_line)
            text_width = bbox[2] - bbox[0]
        except Exception:
            text_width = len(test_line) * 10
        if text_width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _draw_text_shadow(draw, text, position, font, color, shadow_color=(0, 0, 0), offset=4):
    x, y = position
    try:
        bbox = font.getbbox(text)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except Exception:
        tw = len(text) * 10
        th = font.size if hasattr(font, "size") else 20
    anchor_x = x - tw // 2
    anchor_y = y - th // 2
    for dx, dy in [(-offset, -offset), (offset, -offset), (-offset, offset), (offset, offset), (0, -offset), (0, offset), (-offset, 0), (offset, 0)]:  # noqa: E501
        draw.text((anchor_x + dx, anchor_y + dy), text, font=font, fill=shadow_color)
    draw.text((anchor_x, anchor_y), text, font=font, fill=color)
