import os
import json
from PIL import Image, ImageDraw

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


def generate_pixel(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#FF69B4")
    body_secondary = c("#FF1493")
    face_color = c("#FFE4E1")
    screen_color = c("#E6E6FA")
    pupil_color = c("#4B0082")
    antenna_color = c("#C0C0C0")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    body_r = 120

    antenna_height = 60
    draw.line([cx, cy - body_r - 10, cx, cy - body_r - antenna_height], fill=antenna_color, width=6)
    draw.ellipse([cx - 12, cy - body_r - antenna_height - 20, cx + 12, cy - body_r - antenna_height + 5], fill=c("#FF69B4"))

    draw.ellipse([cx - body_r, cy - body_r, cx + body_r, cy + body_r], fill=body_color)

    screen_r = body_r - 30
    draw.ellipse([cx - screen_r, cy - screen_r - 10, cx + screen_r, cy + screen_r - 10], fill=screen_color)
    draw.ellipse([cx - screen_r, cy - screen_r - 10, cx + screen_r, cy + screen_r - 10], fill=None, outline=c("#D8BFD8"), width=3)

    if pose == "sleep":
        draw.arc([cx - 25, cy - 10, cx - 5, cy + 10], 0, 180, fill=pupil_color, width=4)
        draw.arc([cx + 5, cy - 10, cx + 25, cy + 10], 0, 180, fill=pupil_color, width=4)
        _draw_mouth(draw, cx, cy + 30, 24, "calm", "closed")
        draw.text((cx + 30, cy - body_r - 10), "z Z", fill=c("#4B0082"), font=None)
    else:
        _draw_eye(draw, cx - 22, cy - 10, 18, c("#4B0082"), c("#FFFFFF"), expression)
        _draw_eye(draw, cx + 22, cy - 10, 18, c("#4B0082"), c("#FFFFFF"), expression)
        _draw_mouth(draw, cx, cy + 30, 30, expression, mouth)

    arm_offset = body_r + 20
    if pose == "wave":
        draw.line([cx + body_r - 10, cy - 20, cx + body_r + 45, cy - 60], fill=body_color, width=16)
        draw.ellipse([cx + body_r + 35, cy - 70, cx + body_r + 55, cy - 50], fill=body_color)
        draw.line([cx - body_r + 10, cy - 20, cx - body_r - 30, cy + 20], fill=body_color, width=16)
    elif pose == "point":
        draw.line([cx + body_r - 10, cy - 20, cx + body_r + 50, cy - 30], fill=body_color, width=16)
        draw.line([cx - body_r + 10, cy - 20, cx - body_r - 30, cy + 20], fill=body_color, width=16)
    elif pose == "happy":
        draw.line([cx + body_r - 15, cy - 30, cx + body_r + 40, cy - 60], fill=body_color, width=16)
        draw.line([cx - body_r + 15, cy - 30, cx - body_r - 40, cy - 60], fill=body_color, width=16)
    else:
        draw.line([cx + body_r - 10, cy - 10, cx + body_r + 35, cy + 20], fill=body_color, width=16)
        draw.line([cx - body_r + 10, cy - 10, cx - body_r - 35, cy + 20], fill=body_color, width=16)

    return img


def generate_nova(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#FFD700")
    glow_color = c("#FFF8DC")
    pupil_color = c("#8B4513")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    outer_r = 150
    inner_r = 120

    glow_r = outer_r + 20
    draw.ellipse([cx - glow_r, cy - glow_r, cx + glow_r, cy + glow_r], fill=glow_color)

    star_points = []
    for i in range(10):
        angle = i * 36 - 90
        r = outer_r if i % 2 == 0 else inner_r
        import math
        x = cx + r * math.cos(math.radians(angle))
        y = cy + r * math.sin(math.radians(angle))
        star_points.append((x, y))
    draw.polygon(star_points, fill=body_color)

    center_r = 45
    draw.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=c("#FFEFD5"))

    if pose == "sleep":
        draw.arc([cx - 18, cy - 8, cx - 2, cy + 8], 0, 180, fill=pupil_color, width=4)
        draw.arc([cx + 2, cy - 8, cx + 18, cy + 8], 0, 180, fill=pupil_color, width=4)
        _draw_mouth(draw, cx, cy + 22, 20, "calm", "closed")
        draw.text((cx + 25, cy - 50), "✦", fill=c("#FFE4B5"), font=None)
    else:
        _draw_eye(draw, cx - 15, cy - 5, 14, c("#8B4513"), c("#FFFFFF"), expression)
        _draw_eye(draw, cx + 15, cy - 5, 14, c("#8B4513"), c("#FFFFFF"), expression)
        _draw_mouth(draw, cx, cy + 25, 24, expression, mouth)

    if pose == "wave":
        arm_x = cx + outer_r + 10
        draw.line([arm_x, cy - 20, arm_x + 30, cy - 50], fill=body_color, width=14)
        draw.ellipse([arm_x + 22, cy - 60, arm_x + 40, cy - 42], fill=body_color)
    if pose == "point":
        arm_x = cx + outer_r + 10
        draw.line([arm_x, cy - 10, arm_x + 25, cy - 25], fill=body_color, width=14)

    for _ in range(6):
        import random
        sx = cx + random.randint(-outer_r - 15, outer_r + 15)
        sy = cy + random.randint(-outer_r - 15, outer_r + 15)
        if abs(sx - cx) > outer_r * 0.6 or abs(sy - cy) > outer_r * 0.6:
            draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=c("#FFE4B5"))

    return img


def generate_ziggy(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2
    body_r = 130

    rainbow_colors = [c("#FF0000"), c("#FF8C00"), c("#FFD700"), c("#00FF00"), c("#4169E1"), c("#9932CC")]

    for i, color in enumerate(rainbow_colors):
        offset = i * 8
        draw.ellipse([cx - body_r + offset, cy - body_r + offset, cx + body_r - offset, cy + body_r - offset], fill=color)

    center_r = body_r - 35
    draw.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=c("#FFE4B5"))

    if pose == "sleep":
        draw.arc([cx - 20, cy - 8, cx - 4, cy + 8], 0, 180, fill=c("#000000"), width=4)
        draw.arc([cx + 4, cy - 8, cx + 20, cy + 8], 0, 180, fill=c("#000000"), width=4)
        _draw_mouth(draw, cx, cy + 25, 22, "calm", "closed")
    else:
        _draw_eye(draw, cx - 18, cy - 5, 16, c("#000000"), c("#FFFFFF"), expression)
        _draw_eye(draw, cx + 18, cy - 5, 16, c("#000000"), c("#FFFFFF"), expression)
        _draw_mouth(draw, cx, cy + 28, 28, expression, mouth)

    if pose == "dance":
        for i, color in enumerate(rainbow_colors):
            import math
            angle = math.radians(i * 60 + 30)
            sx = cx + int(body_r * 0.8 * math.cos(angle))
            sy = cy + int(body_r * 0.8 * math.sin(angle))
            draw.ellipse([sx - 12, sy - 12, sx + 12, sy + 12], fill=color)

    if pose == "wave":
        arm_x = cx + body_r + 5
        draw.line([arm_x, cy - 15, arm_x + 35, cy - 55], fill=c("#FFD700"), width=16)

    return img


def generate_boop(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#87CEEB")
    belly_color = c("#B0E0E6")
    pupil_color = c("#191970")
    cheek_color = c("#FFB6C1")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2 + 10

    body_rx = 140
    body_ry = 155
    draw.ellipse([cx - body_rx, cy - body_ry, cx + body_rx, cy + body_ry], fill=body_color)

    belly_rx = body_rx - 30
    belly_ry = body_ry - 25
    draw.ellipse([cx - belly_rx, cy - belly_ry + 15, cx + belly_rx, cy + belly_ry + 15], fill=belly_color)

    draw.ellipse([cx - 30, cy - 5, cx - 8, cy + 18], fill=cheek_color)
    draw.ellipse([cx + 8, cy - 5, cx + 30, cy + 18], fill=cheek_color)

    if pose == "sleep":
        eye_y = cy - 20
        draw.arc([cx - 22, eye_y - 8, cx - 6, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        draw.arc([cx + 6, eye_y - 8, cx + 22, eye_y + 8], 0, 180, fill=pupil_color, width=5)
        _draw_mouth(draw, cx, cy + 30, 20, "calm", "closed")
        draw.text((cx + 30, cy - 50), "z Z", fill=pupil_color, font=None)
    else:
        eye_y = cy - 20
        _draw_eye(draw, cx - 20, eye_y, 20, c("#191970"), c("#FFFFFF"), expression)
        _draw_eye(draw, cx + 20, eye_y, 20, c("#191970"), c("#FFFFFF"), expression)
        _draw_mouth(draw, cx, cy + 32, 30, expression, mouth)

    if pose == "wave":
        draw.line([cx + body_rx - 10, cy - 30, cx + body_rx + 40, cy - 75], fill=body_color, width=20)
        draw.ellipse([cx + body_rx + 30, cy - 85, cx + body_rx + 50, cy - 65], fill=body_color)
    if pose == "happy":
        draw.line([cx + body_rx - 15, cy - 40, cx + body_rx + 35, cy - 70], fill=body_color, width=18)
        draw.line([cx - body_rx + 15, cy - 40, cx - body_rx - 35, cy - 70], fill=body_color, width=18)
    if pose == "sad" or expression == "sad":
        draw.arc([cx - 20, cy + 20, cx + 20, cy + 40], 180, 360, fill="#333333", width=3)

    legs_y = cy + body_ry
    draw.ellipse([cx - 35, legs_y - 5, cx - 10, legs_y + 20], fill=body_color)
    draw.ellipse([cx + 10, legs_y - 5, cx + 35, legs_y + 20], fill=body_color)

    return img


def generate_sprout(pose: str, expression: str, mouth: str = "closed") -> Image.Image:
    img = Image.new("RGBA", (SPRITE_SIZE, SPRITE_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    c = _hex_to_rgb
    body_color = c("#90EE90")
    body_secondary = c("#228B22")
    flower_color = c("#FF69B4")
    flower_center = c("#FFD700")
    leaf_color = c("#32CD32")
    pupil_color = c("#006400")

    cx, cy = SPRITE_SIZE // 2, SPRITE_SIZE // 2 + 20

    if pose == "growing":
        body_r = 100
    else:
        body_r = 115

    draw.ellipse([cx - body_r, cy - body_r + 15, cx + body_r, cy + body_r + 15], fill=body_color)

    center_r = body_r - 20
    draw.ellipse([cx - center_r, cy - center_r + 20, cx + center_r, cy + center_r + 20], fill=c("#98FB98"))

    stem_top = cy - body_r - 10
    draw.arc([cx - 8, stem_top - 50, cx + 8, stem_top + 10], 0, 180, fill=body_secondary, width=8)

    leaf_positions = [(cx - 25, stem_top - 20), (cx + 25, stem_top - 35)]
    for lx, ly in leaf_positions:
        draw.ellipse([lx - 15, ly - 8, lx + 15, ly + 8], fill=leaf_color)
        draw.line([lx, ly, lx - 15 if lx < cx else lx + 15, ly], fill=c("#228B22"), width=2)

    flower_y = stem_top - 50
    petal_r = 18
    for angle in range(0, 360, 60):
        import math
        px = cx + int(petal_r * 1.5 * math.cos(math.radians(angle)))
        py = flower_y + int(petal_r * 1.5 * math.sin(math.radians(angle)))
        draw.ellipse([px - petal_r, py - petal_r, px + petal_r, py + petal_r], fill=flower_color)
    draw.ellipse([cx - 14, flower_y - 14, cx + 14, flower_y + 14], fill=flower_center)

    if pose == "sleep":
        eye_y = cy - 5
        draw.arc([cx - 18, eye_y - 8, cx - 4, eye_y + 8], 0, 180, fill=pupil_color, width=4)
        draw.arc([cx + 4, eye_y - 8, cx + 18, eye_y + 8], 0, 180, fill=pupil_color, width=4)
        _draw_mouth(draw, cx, cy + 20, 18, "calm", "closed")
    else:
        _draw_eye(draw, cx - 16, cy - 5, 14, c("#006400"), c("#FFFFFF"), expression)
        _draw_eye(draw, cx + 16, cy - 5, 14, c("#006400"), c("#FFFFFF"), expression)
        _draw_mouth(draw, cx, cy + 25, 24, expression, mouth)

    draw.ellipse([cx - 22, cy + 10, cx - 6, cy + 22], fill=c("#FFB6C1"))
    draw.ellipse([cx + 6, cy + 10, cx + 22, cy + 22], fill=c("#FFB6C1"))

    if pose == "wave":
        draw.line([cx + body_r - 10, cy - 10, cx + body_r + 35, cy - 45], fill=body_color, width=14)
        draw.ellipse([cx + body_r + 25, cy - 55, cx + body_r + 45, cy - 35], fill=body_color)
    if pose == "point":
        draw.line([cx + body_r - 10, cy - 5, cx + body_r + 30, cy - 20], fill=body_color, width=14)

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

        print(f"  {char_name}: generated sprites in {char_dir}")

    print(f"Total: {total} sprites generated")
    return total


if __name__ == "__main__":
    print("Generating character sprites...")
    generate_all_sprites()
    print("Done!")
