import os
import json
from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
CHARACTERS_DIR = os.path.join(ASSETS_DIR, "characters")
SPRITE_SIZE = 512


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def _draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def _draw_eye(draw, cx, cy, size, pupil_color="#000000", eye_color="#FFFFFF", expression="neutral"):
    eye_half = size // 2
    draw.ellipse([cx - eye_half, cy - eye_half, cx + eye_half, cy + eye_half], fill=eye_color, outline="#333333", width=2)
    if expression in ("sleep", "peaceful"):
        draw.arc([cx - eye_half, cy, cx + eye_half, cy + eye_half * 2], 0, 180, fill=pupil_color, width=3)
    elif expression == "surprised":
        draw.ellipse([cx - eye_half, cy - eye_half, cx + eye_half, cy + eye_half], fill=eye_color)
        pupil_r = max(3, eye_half * 2 // 3)
        draw.ellipse([cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r], fill=pupil_color)
    elif expression == "curious":
        draw.ellipse([cx - eye_half, cy - eye_half, cx + eye_half, cy + eye_half], fill=eye_color)
        pupil_r = eye_half // 2
        draw.ellipse([cx + 1, cy - pupil_r, cx + eye_half, cy + pupil_r], fill=pupil_color)
    else:
        pupil_r = max(2, eye_half * 2 // 5)
        draw.ellipse([cx - pupil_r, cy - pupil_r, cx + pupil_r, cy + pupil_r], fill=pupil_color)


def _draw_mouth(draw, cx, cy, width, expression="neutral", openness="closed"):
    hw = width // 2
    if openness == "open":
        draw.ellipse([cx - hw // 2, cy - hw // 4, cx + hw // 2, cy + hw // 2], fill="#333333")
        return
    if openness == "half":
        draw.ellipse([cx - hw // 2, cy - 1, cx + hw // 2, cy + hw // 4], fill="#333333")
        return
    if expression in ("happy", "excited", "silly"):
        draw.arc([cx - hw, cy - hw // 2, cx + hw, cy + hw], 0, 180, fill="#333333", width=3)
    elif expression == "sad":
        draw.arc([cx - hw, cy, cx + hw, cy + hw], 180, 360, fill="#333333", width=3)
    elif expression == "surprised":
        draw.ellipse([cx - hw // 2, cy - 2, cx + hw // 2, cy + hw // 2], fill="#333333")
    elif expression in ("calm", "dreamy", "peaceful"):
        draw.arc([cx - hw // 2, cy - hw // 4, cx + hw // 2, cy + hw // 4], 0, 180, fill="#333333", width=2)
    elif expression == "neutral":
        draw.line([cx - hw // 2, cy, cx + hw // 2, cy], fill="#333333", width=3)


OUTLINE_COLOR = "#222222"
OUTLINE_WIDTH = 6
HIGHLIGHT_COLOR = "#FFFFFF"


def _radial_gradient(size: int, center_color, edge_color) -> Image.Image:
    """Create a radial gradient image from center_color to edge_color."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cx = cy = size // 2
    max_dist = cx
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            dist = min((dx * dx + dy * dy) ** 0.5 / max_dist, 1.0)
            r = int(center_color[0] + (edge_color[0] - center_color[0]) * dist)
            g = int(center_color[1] + (edge_color[1] - center_color[1]) * dist)
            b = int(center_color[2] + (edge_color[2] - center_color[2]) * dist)
            a = int(255 - dist * 80)
            img.putpixel((x, y), (r, g, b, a))
    return img


def _draw_outlined_ellipse(draw, bbox, fill, outline=OUTLINE_COLOR, outline_width=OUTLINE_WIDTH):
    outer = [bbox[0] - outline_width, bbox[1] - outline_width,
             bbox[2] + outline_width, bbox[3] + outline_width]
    draw.ellipse(outer, fill=outline)
    draw.ellipse(bbox, fill=fill)


def _draw_outlined_circle(draw, cx, cy, r, fill, outline=OUTLINE_COLOR, outline_width=OUTLINE_WIDTH):
    _draw_outlined_ellipse(draw, [cx - r, cy - r, cx + r, cy + r], fill, outline, outline_width)


def _draw_outlined_line(draw, x1, y1, x2, y2, fill, outline=OUTLINE_COLOR, width=OUTLINE_WIDTH):
    draw.line([x1, y1, x2, y2], fill=outline, width=width + 4)
    draw.line([x1, y1, x2, y2], fill=fill, width=width)


def _draw_outlined_arc(draw, bbox, start, end, fill, outline=OUTLINE_COLOR, width=OUTLINE_WIDTH):
    draw.arc(bbox, start, end, fill=outline, width=width + 4)
    draw.arc(bbox, start, end, fill=fill, width=width)


def _draw_ground_shadow(draw, cx, cy, width, height):
    shadow = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([cx - width // 2, cy + height - 10, cx + width // 2, cy + height + 15],
               fill=(0, 0, 0, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
    draw.bitmap((0, 0), shadow)


def _draw_eye_upgraded(draw, cx, cy, size, expression="neutral"):
    """Draw cartoon eye with outline, catchlight, and expression variation."""
    r = size // 2
    # White of eye with outline
    _draw_outlined_circle(draw, cx, cy, r, "#FFFFFF")
    # Pupil
    pupil_r = int(r * 0.55)
    pupil_color = "#333333"
    if expression == "surprised":
        pupil_r = int(r * 0.75)
    elif expression == "curious":
        pupil_r = int(r * 0.45)
    elif expression == "happy":
        pupil_color = "#444444"
    draw.ellipse([cx - pupil_r, cy - pupil_r + 1, cx + pupil_r, cy + pupil_r + 1], fill=pupil_color)
    # Catchlight (white sparkle)
    cl_r = max(2, pupil_r // 3)
    draw.ellipse([cx + pupil_r // 2, cy - pupil_r // 2 - cl_r // 2,
                  cx + pupil_r // 2 + cl_r * 2, cy - pupil_r // 2 + cl_r // 2], fill="#FFFFFF")
    # Eyelid for sleep
    if expression in ("sleep", "peaceful", "calm"):
        draw.arc([cx - r - 2, cy - 2, cx + r + 2, cy + r // 2], 0, 180, fill=OUTLINE_COLOR, width=3)


def _draw_mouth_upgraded(draw, cx, cy, width, expression="neutral", openness="closed"):
    """Draw cartoon mouth with outline and expression."""
    hw = width // 2
    if openness == "open":
        _draw_outlined_ellipse(draw, [cx - hw // 2, cy - hw // 4, cx + hw // 2, cy + hw // 2],
                               "#CC3333", OUTLINE_COLOR, 3)
        return
    if openness == "half":
        _draw_outlined_ellipse(draw, [cx - hw // 2, cy - 1, cx + hw // 2, cy + hw // 3],
                               "#CC3333", OUTLINE_COLOR, 3)
        return
    if expression in ("happy", "excited", "silly"):
        _draw_outlined_arc(draw, [cx - hw, cy - hw // 3, cx + hw, cy + hw // 2],
                           0, 180, "#CC3333")
    elif expression == "sad":
        _draw_outlined_arc(draw, [cx - hw, cy - hw // 4, cx + hw, cy + hw // 2],
                           180, 360, "#CC3333")
    elif expression == "surprised":
        _draw_outlined_ellipse(draw, [cx - hw // 3, cy - 2, cx + hw // 3, cy + hw // 3],
                               "#CC3333", OUTLINE_COLOR, 3)
    elif expression in ("calm", "dreamy", "peaceful"):
        draw.line([cx - hw // 2, cy, cx + hw // 2, cy], fill="#CC3333", width=3)
    elif expression == "neutral":
        draw.line([cx - hw // 2, cy, cx + hw // 2, cy], fill="#CC3333", width=3)


def _apply_gradient_overlay(img, body_bbox, light_color, dark_color):
    """Apply radial gradient overlay to body region for 3D depth."""
    x1, y1, x2, y2 = body_bbox
    w, h = x2 - x1, y2 - y1
    gradient = _radial_gradient(max(w, h), light_color, dark_color)
    gradient = gradient.resize((w, h), Image.LANCZOS)
    alpha = gradient.split()[3]
    gradient = gradient.convert("RGBA")
    gradient.putalpha(alpha.point(lambda a: int(a * 0.3)))
    img.paste(gradient, (x1, y1), gradient)


def generate_pixel(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#FF69B4")
    body_dark = c("#E05590")
    screen_color = c("#E6E6FA")
    pupil_color = c("#4B0082")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    body_r = 120

    _draw_ground_shadow(draw, cx, cy, body_r * 1.5, body_r)

    # Antenna
    antenna_top = cy - body_r - 70
    draw.line([cx, cy - body_r - 5, cx, antenna_top], fill=c("#888888"), width=6)
    _draw_outlined_circle(draw, cx, antenna_top - 5, 16, c("#FF69B4"))

    # Body
    body_bbox = [cx - body_r, cy - body_r, cx + body_r, cy + body_r]
    _draw_outlined_ellipse(draw, body_bbox, body_color)

    # Screen/face area
    screen_r = body_r - 25
    screen_bbox = [cx - screen_r, cy - screen_r - 5, cx + screen_r, cy + screen_r - 5]
    _draw_outlined_ellipse(draw, screen_bbox, screen_color)

    if pose == "sleep":
        draw.arc([cx - 25, cy - 10, cx - 5, cy + 10], 0, 180, fill=pupil_color, width=5)
        draw.arc([cx + 5, cy - 10, cx + 25, cy + 10], 0, 180, fill=pupil_color, width=5)
        _draw_mouth_upgraded(draw, cx, cy + 35, 24, "calm", "closed")
        draw.text((cx + 35, cy - body_r + 10), "z Z", fill=pupil_color, font=None)
    else:
        _draw_eye_upgraded(draw, cx - 24, cy - 8, 20, expression)
        _draw_eye_upgraded(draw, cx + 24, cy - 8, 20, expression)
        _draw_mouth_upgraded(draw, cx, cy + 35, 32, expression, mouth)

    # Cheek blush
    draw.ellipse([cx - 38, cy + 8, cx - 18, cy + 20], fill=c("#FFB6C1") + (100,))
    draw.ellipse([cx + 18, cy + 8, cx + 38, cy + 20], fill=c("#FFB6C1") + (100,))

    # Arms
    if pose == "wave":
        _draw_outlined_line(draw, cx + body_r - 5, cy - 15, cx + body_r + 50, cy - 65, body_color)
        _draw_outlined_circle(draw, cx + body_r + 50, cy - 65, 14, body_color)
        _draw_outlined_line(draw, cx - body_r + 5, cy - 15, cx - body_r - 35, cy + 15, body_color)
    elif pose == "point":
        _draw_outlined_line(draw, cx + body_r - 5, cy - 15, cx + body_r + 55, cy - 25, body_color)
        _draw_outlined_circle(draw, cx + body_r + 55, cy - 25, 12, body_color)
        _draw_outlined_line(draw, cx - body_r + 5, cy - 15, cx - body_r - 35, cy + 15, body_color)
    elif pose == "happy":
        _draw_outlined_line(draw, cx + body_r - 10, cy - 25, cx + body_r + 45, cy - 65, body_color)
        _draw_outlined_circle(draw, cx + body_r + 45, cy - 65, 14, body_color)
        _draw_outlined_line(draw, cx - body_r + 10, cy - 25, cx - body_r - 45, cy - 65, body_color)
        _draw_outlined_circle(draw, cx - body_r - 45, cy - 65, 14, body_color)
    elif pose == "surprised":
        _draw_outlined_line(draw, cx + body_r - 10, cy - 20, cx + body_r + 40, cy - 50, body_color)
        _draw_outlined_line(draw, cx - body_r + 10, cy - 20, cx - body_r - 40, cy - 50, body_color)
    elif pose == "thinking":
        _draw_outlined_line(draw, cx + body_r - 5, cy - 10, cx + body_r + 40, cy - 30, body_color)
        _draw_outlined_circle(draw, cx + body_r + 45, cy - 35, 10, body_color)
    else:
        _draw_outlined_line(draw, cx + body_r - 5, cy - 5, cx + body_r + 35, cy + 20, body_color)
        _draw_outlined_circle(draw, cx + body_r + 35, cy + 20, 12, body_color)
        _draw_outlined_line(draw, cx - body_r + 5, cy - 5, cx - body_r - 35, cy + 20, body_color)
        _draw_outlined_circle(draw, cx - body_r - 35, cy + 20, 12, body_color)

    return img


def generate_nova(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#FFD700")
    body_dark = c("#DAA520")
    face_color = c("#FFEFD5")
    pupil_color = c("#8B4513")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    outer_r = 150
    inner_r = 120

    _draw_ground_shadow(draw, cx, cy, outer_r * 1.4, outer_r)

    # Glow halo
    for i in range(3):
        alpha = 60 - i * 15
        r = outer_r + 25 + i * 10
        halo = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        hd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 248, 220, alpha))
        halo = halo.filter(ImageFilter.GaussianBlur(radius=6))
        img.paste(halo, (0, 0), halo)

    # Star body with outline
    import math
    star_outer = []
    star_inner = []
    for i in range(10):
        angle = i * 36 - 90
        rad = math.radians(angle)
        sox = cx + outer_r * math.cos(rad)
        soy = cy + outer_r * math.sin(rad)
        star_outer.append((sox, soy))
        six = cx + inner_r * math.cos(rad)
        siy = cy + inner_r * math.sin(rad)
        star_inner.append((six, siy))

    star_points = []
    for i in range(10):
        star_points.append(star_outer[i])
        star_points.append(star_inner[(i + 1) % 10])

    draw.polygon(star_points, fill=c("#333333"))
    draw.polygon(star_points, fill=body_color)

    # Face circle
    center_r = 50
    _draw_outlined_circle(draw, cx, cy, center_r, face_color)

    if pose == "sleep":
        draw.arc([cx - 18, cy - 8, cx - 2, cy + 8], 0, 180, fill=pupil_color, width=5)
        draw.arc([cx + 2, cy - 8, cx + 18, cy + 8], 0, 180, fill=pupil_color, width=5)
        _draw_mouth_upgraded(draw, cx, cy + 22, 22, "calm", "closed")
    else:
        _draw_eye_upgraded(draw, cx - 18, cy - 5, 16, expression)
        _draw_eye_upgraded(draw, cx + 18, cy - 5, 16, expression)
        _draw_mouth_upgraded(draw, cx, cy + 25, 26, expression, mouth)

    # Cheek blush
    draw.ellipse([cx - 30, cy + 8, cx - 12, cy + 18], fill=c("#FFB6C1") + (80,))
    draw.ellipse([cx + 12, cy + 8, cx + 30, cy + 18], fill=c("#FFB6C1") + (80,))

    # Arms based on pose
    if pose == "wave":
        _draw_outlined_line(draw, cx + outer_r - 15, cy - 10, cx + outer_r + 35, cy - 55, body_color)
        _draw_outlined_circle(draw, cx + outer_r + 35, cy - 55, 14, body_color)
    elif pose == "point":
        _draw_outlined_line(draw, cx + outer_r - 15, cy - 5, cx + outer_r + 30, cy - 20, body_color)
        _draw_outlined_circle(draw, cx + outer_r + 30, cy - 20, 12, body_color)
    elif pose == "happy":
        _draw_outlined_line(draw, cx + outer_r - 15, cy - 20, cx + outer_r + 30, cy - 55, body_color)
        _draw_outlined_circle(draw, cx + outer_r + 30, cy - 55, 14, body_color)
        _draw_outlined_line(draw, cx - outer_r + 15, cy - 20, cx - outer_r - 30, cy - 55, body_color)
        _draw_outlined_circle(draw, cx - outer_r - 30, cy - 55, 14, body_color)
    elif pose == "thinking":
        _draw_outlined_line(draw, cx + outer_r - 15, cy - 5, cx + outer_r + 25, cy - 25, body_color)
        _draw_outlined_circle(draw, cx + outer_r + 30, cy - 30, 10, body_color)

    # Sparkle dots
    for _ in range(8):
        import random
        sx = cx + random.randint(-outer_r - 10, outer_r + 10)
        sy = cy + random.randint(-outer_r - 10, outer_r + 10)
        if abs(sx - cx) > outer_r * 0.5 or abs(sy - cy) > outer_r * 0.5:
            draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=c("#FFF8DC"))

    return img


def generate_ziggy(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    body_r = 130

    _draw_ground_shadow(draw, cx, cy, body_r * 1.5, body_r)

    rainbow_colors = [c("#FF4444"), c("#FF8C00"), c("#FFD700"), c("#44CC44"), c("#4488FF"), c("#9932CC")]

    # Rainbow rings with outline
    for i, color in enumerate(rainbow_colors):
        offset = i * 7
        r = body_r - offset
        _draw_outlined_circle(draw, cx + offset // 2, cy + offset // 3, r, color)

    # Face center
    center_r = body_r - 35
    _draw_outlined_circle(draw, cx, cy, center_r, c("#FFE4B5"))

    if pose == "sleep":
        draw.arc([cx - 20, cy - 8, cx - 4, cy + 8], 0, 180, fill=c("#333333"), width=5)
        draw.arc([cx + 4, cy - 8, cx + 20, cy + 8], 0, 180, fill=c("#333333"), width=5)
        _draw_mouth_upgraded(draw, cx, cy + 25, 24, "calm", "closed")
    else:
        _draw_eye_upgraded(draw, cx - 20, cy - 5, 18, expression)
        _draw_eye_upgraded(draw, cx + 20, cy - 5, 18, expression)
        _draw_mouth_upgraded(draw, cx, cy + 30, 30, expression, mouth)

    # Cheek blush
    draw.ellipse([cx - 34, cy + 8, cx - 16, cy + 20], fill=c("#FFB6C1") + (80,))
    draw.ellipse([cx + 16, cy + 8, cx + 34, cy + 20], fill=c("#FFB6C1") + (80,))

    # Arms
    if pose == "dance":
        import math
        for i, color in enumerate(rainbow_colors):
            angle = math.radians(i * 60 + 30)
            sx = cx + int(body_r * 0.85 * math.cos(angle))
            sy = cy + int(body_r * 0.85 * math.sin(angle))
            _draw_outlined_circle(draw, sx, sy, 14, color)
    elif pose == "wave":
        _draw_outlined_line(draw, cx + body_r - 10, cy - 10, cx + body_r + 40, cy - 55, c("#FFD700"))
        _draw_outlined_circle(draw, cx + body_r + 40, cy - 55, 14, c("#FFD700"))
    elif pose == "happy":
        _draw_outlined_line(draw, cx + body_r - 10, cy - 20, cx + body_r + 35, cy - 60, c("#FFD700"))
        _draw_outlined_circle(draw, cx + body_r + 35, cy - 60, 14, c("#FFD700"))
        _draw_outlined_line(draw, cx - body_r + 10, cy - 20, cx - body_r - 35, cy - 60, c("#FFD700"))
        _draw_outlined_circle(draw, cx - body_r - 35, cy - 60, 14, c("#FFD700"))
    elif pose == "point":
        _draw_outlined_line(draw, cx + body_r - 10, cy - 10, cx + body_r + 45, cy - 25, c("#FFD700"))
        _draw_outlined_circle(draw, cx + body_r + 45, cy - 25, 12, c("#FFD700"))

    return img


def generate_boop(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#87CEEB")
    body_dark = c("#5BA3C7")
    belly_color = c("#B0E0E6")
    pupil_color = c("#191970")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2 + 10
    body_rx = 140
    body_ry = 155

    _draw_ground_shadow(draw, cx, cy, body_rx * 1.4, body_ry + 10)

    # Body
    _draw_outlined_ellipse(draw, [cx - body_rx, cy - body_ry, cx + body_rx, cy + body_ry], body_color)

    # Belly
    belly_rx = body_rx - 25
    belly_ry = body_ry - 20
    _draw_outlined_ellipse(draw, [cx - belly_rx, cy - belly_ry + 15, cx + belly_rx, cy + belly_ry + 15],
                           belly_color)

    # Legs
    legs_y = cy + body_ry - 5
    _draw_outlined_ellipse(draw, [cx - 40, legs_y - 10, cx - 10, legs_y + 25], body_color)
    _draw_outlined_ellipse(draw, [cx + 10, legs_y - 10, cx + 40, legs_y + 25], body_color)

    if pose == "sleep":
        eye_y = cy - 20
        draw.arc([cx - 22, eye_y - 8, cx - 6, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        draw.arc([cx + 6, eye_y - 8, cx + 22, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        _draw_mouth_upgraded(draw, cx, cy + 32, 22, "calm", "closed")
    else:
        eye_y = cy - 20
        _draw_eye_upgraded(draw, cx - 22, eye_y, 22, expression)
        _draw_eye_upgraded(draw, cx + 22, eye_y, 22, expression)
        _draw_mouth_upgraded(draw, cx, cy + 34, 32, expression, mouth)

    # Cheek blush
    draw.ellipse([cx - 38, cy, cx - 16, cy + 18], fill=c("#FFB6C1") + (100,))
    draw.ellipse([cx + 16, cy, cx + 38, cy + 18], fill=c("#FFB6C1") + (100,))

    # Arms
    if pose == "wave":
        _draw_outlined_line(draw, cx + body_rx - 10, cy - 25, cx + body_rx + 45, cy - 80, body_color)
        _draw_outlined_circle(draw, cx + body_rx + 45, cy - 80, 16, body_color)
    elif pose == "happy":
        _draw_outlined_line(draw, cx + body_rx - 15, cy - 35, cx + body_rx + 40, cy - 75, body_color)
        _draw_outlined_circle(draw, cx + body_rx + 40, cy - 75, 16, body_color)
        _draw_outlined_line(draw, cx - body_rx + 15, cy - 35, cx - body_rx - 40, cy - 75, body_color)
        _draw_outlined_circle(draw, cx - body_rx - 40, cy - 75, 16, body_color)
    elif pose == "point":
        _draw_outlined_line(draw, cx + body_rx - 10, cy - 20, cx + body_rx + 50, cy - 30, body_color)
        _draw_outlined_circle(draw, cx + body_rx + 50, cy - 30, 14, body_color)
    elif pose == "surprised":
        _draw_outlined_line(draw, cx + body_rx - 10, cy - 30, cx + body_rx + 35, cy - 55, body_color)
        _draw_outlined_line(draw, cx - body_rx + 10, cy - 30, cx - body_rx - 35, cy - 55, body_color)

    return img


def generate_sprout(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#90EE90")
    body_dark = c("#55BB55")
    face_color = c("#98FB98")
    flower_color = c("#FF69B4")
    flower_center = c("#FFD700")
    leaf_color = c("#32CD32")
    pupil_color = c("#006400")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2 + 20
    body_r = 100 if pose == "growing" else 115

    _draw_ground_shadow(draw, cx, cy, body_r * 1.5, body_r + 10)

    # Body
    _draw_outlined_ellipse(draw, [cx - body_r, cy - body_r + 15, cx + body_r, cy + body_r + 15], body_color)

    # Face area
    center_r = body_r - 20
    _draw_outlined_ellipse(draw, [cx - center_r, cy - center_r + 20, cx + center_r, cy + center_r + 20], face_color)

    # Stem
    stem_top = cy - body_r - 10
    draw.line([cx, stem_top + 10, cx, stem_top - 55], fill=c("#228B22"), width=8)

    # Leaves
    leaf_positions = [(cx - 28, stem_top - 25), (cx + 28, stem_top - 40)]
    for lx, ly in leaf_positions:
        _draw_outlined_ellipse(draw, [lx - 16, ly - 8, lx + 16, ly + 8], leaf_color, c("#228B22"), 3)

    # Flower
    flower_y = stem_top - 55
    for angle in range(0, 360, 60):
        import math
        px = cx + int(20 * 1.5 * math.cos(math.radians(angle)))
        py = flower_y + int(20 * 1.5 * math.sin(math.radians(angle)))
        _draw_outlined_circle(draw, px, py, 20, flower_color)
    _draw_outlined_circle(draw, cx, flower_y, 16, flower_center)

    if pose == "sleep":
        eye_y = cy - 5
        draw.arc([cx - 18, eye_y - 8, cx - 4, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        draw.arc([cx + 4, eye_y - 8, cx + 18, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        _draw_mouth_upgraded(draw, cx, cy + 22, 20, "calm", "closed")
    else:
        _draw_eye_upgraded(draw, cx - 18, cy - 5, 16, expression)
        _draw_eye_upgraded(draw, cx + 18, cy - 5, 16, expression)
        _draw_mouth_upgraded(draw, cx, cy + 26, 26, expression, mouth)

    # Cheek blush
    draw.ellipse([cx - 30, cy + 6, cx - 14, cy + 18], fill=c("#FFB6C1") + (80,))
    draw.ellipse([cx + 14, cy + 6, cx + 30, cy + 18], fill=c("#FFB6C1") + (80,))

    # Arms
    if pose == "wave":
        _draw_outlined_line(draw, cx + body_r - 5, cy - 5, cx + body_r + 40, cy - 50, body_color)
        _draw_outlined_circle(draw, cx + body_r + 40, cy - 50, 14, body_color)
    elif pose == "point":
        _draw_outlined_line(draw, cx + body_r - 5, cy - 5, cx + body_r + 35, cy - 20, body_color)
        _draw_outlined_circle(draw, cx + body_r + 35, cy - 20, 12, body_color)
    elif pose == "happy":
        _draw_outlined_line(draw, cx + body_r - 8, cy - 15, cx + body_r + 35, cy - 50, body_color)
        _draw_outlined_circle(draw, cx + body_r + 35, cy - 50, 14, body_color)
        _draw_outlined_line(draw, cx - body_r + 8, cy - 15, cx - body_r - 35, cy - 50, body_color)
        _draw_outlined_circle(draw, cx - body_r - 35, cy - 50, 14, body_color)

    return img


CHARACTER_GENERATORS = {
    "pixel": generate_pixel,
    "nova": generate_nova,
    "ziggy": generate_ziggy,
    "boop": generate_boop,
    "sprout": generate_sprout,
}

ALL_POSES = ["idle", "happy", "wave", "point", "surprised", "thinking", "sleep"]
ALL_EXPRESSIONS = ["neutral", "happy", "excited", "curious", "calm", "dreamy", "silly", "sad", "surprised", "peaceful"]
ALL_MOUTH = ["closed", "half", "open"]

# Mouth overlay pixel offsets (relative to character center) for each character
CHARACTER_MOUTH_OFFSETS = {
    "pixel": (0, 30),
    "nova": (0, 25),
    "ziggy": (0, 28),
    "boop": (0, 32),
    "sprout": (0, 25),
}


def generate_all_sprites(output_dir: str = None):
    if output_dir is None:
        output_dir = CHARACTERS_DIR
    os.makedirs(output_dir, exist_ok=True)

    total = 0
    for char_name, generator in CHARACTER_GENERATORS.items():
        char_dir = os.path.join(output_dir, char_name)
        os.makedirs(char_dir, exist_ok=True)

        for pose in ALL_POSES:
            for expr in ALL_EXPRESSIONS:
                for mouth in ALL_MOUTH:
                    try:
                        img = generator(pose, expr, mouth)
                        filename = f"{pose}_{expr}_{mouth}.png"
                        filepath = os.path.join(char_dir, filename)
                        img.save(filepath, "PNG")
                        total += 1
                    except Exception as e:
                        print(f"  Failed {char_name}/{pose}_{expr}_{mouth}: {e}")

        print(f"  {char_name}: generated {total//5} sprites")

    print(f"Total: {total} sprites generated")
    return total


def _generate_mouth_only(generator_fn, char_name: str, mouth: str) -> Image.Image:
    """Generate a mouth-only overlay by masking everything but the mouth area."""
    center = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    mx, my = CHARACTER_MOUTH_OFFSETS.get(char_name, (0, 30))

    full = generator_fn("idle", "neutral", mouth)
    mask = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    mouth_box = (
        center[0] + mx - 30,
        center[1] + my - 20,
        center[0] + mx + 30,
        center[1] + my + 20,
    )
    mouth_region = full.crop(mouth_box)
    mask.paste(mouth_region, (mouth_box[0], mouth_box[1]))
    return mask


def generate_character_parts(output_dir: str = None):
    """Generate multi-part character sprites for Synctoon-style compositing.

    Produces per character:
    - body_{pose}_{expression}.png  (body without mouth)
    - mouth_closed.png / mouth_half.png / mouth_open.png (mouth overlays)
    """
    if output_dir is None:
        output_dir = CHARACTERS_DIR
    os.makedirs(output_dir, exist_ok=True)

    total = 0
    for char_name, generator_fn in CHARACTER_GENERATORS.items():
        char_dir = os.path.join(output_dir, char_name)
        os.makedirs(char_dir, exist_ok=True)

        for pose in ALL_POSES:
            for expr in ALL_EXPRESSIONS:
                try:
                    body_img = generator_fn(pose, expr, "closed")
                    body_path = os.path.join(char_dir, f"body_{pose}_{expr}.png")
                    body_img.save(body_path, "PNG")
                    total += 1
                except Exception as e:
                    print(f"  Failed body {char_name}/{pose}_{expr}: {e}")

        for mouth in ALL_MOUTH:
            try:
                mouth_img = _generate_mouth_only(generator_fn, char_name, mouth)
                mouth_path = os.path.join(char_dir, f"mouth_{mouth}.png")
                mouth_img.save(mouth_path, "PNG")
                total += 1
            except Exception as e:
                print(f"  Failed mouth {char_name}/{mouth}: {e}")

        print(f"  {char_name}: generated {total} parts")

    print(f"Total: {total} parts generated")
    return total


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode == "monolithic" or mode == "all":
        print("Generating monolithic sprites...")
        generate_all_sprites()
    if mode == "parts" or mode == "all":
        print("Generating multi-part sprites...")
        generate_character_parts()
    print("Done!")
