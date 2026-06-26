"""
Animation engine — simplified for tech/AI content.
Generates single-frame previews with background color and text overlay.
No character sprites or 2D animation.
"""
import os
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

BACKGROUND_COLORS = {
    "solid_black": (12, 12, 24),
    "solid_white": (245, 245, 250),
    "solid_indigo": (28, 25, 75),
    "solid_slate": (30, 41, 59),
    "gradient_dark_tech": (10, 10, 40),
    "gradient_blueprint": (20, 30, 60),
    "gradient_neon": (15, 15, 35),
    "gradient_corporate": (240, 240, 248),
    "gradient_minimal": (250, 250, 252),
}


def render_single_frame(scene: dict, format_type: str = "shorts") -> Image.Image:
    width = 720 if format_type == "long" else 405
    height = 405 if format_type == "long" else 720

    bg = BACKGROUND_COLORS.get(scene.get("background", "solid_black"), (12, 12, 24))
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    text_data = scene.get("text", [])
    for t in text_data:
        txt = t.get("text", "")
        if not txt:
            continue
        style = t.get("style", "title")
        font_size = 48 if style == "title" else 28
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()
        color = (255, 255, 255) if sum(bg) < 384 else (12, 12, 24)
        bbox = draw.textbbox((0, 0), txt, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x = (width - tw) // 2
        y = (height - th) // 2
        draw.text((x, y), txt, fill=color, font=font)

    return img
