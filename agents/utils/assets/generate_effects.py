import os
from PIL import Image, ImageDraw, ImageFilter
import math

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
EFFECTS_DIR = os.path.join(ASSETS_DIR, "effects")


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def generate_sparkle(size=64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    r = size // 3
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        ex = cx + int(r * 0.7 * math.cos(rad))
        ey = cy + int(r * 0.7 * math.sin(rad))
        draw.ellipse([ex - 3, ey - 3, ex + 3, ey + 3], fill=(255, 255, 200, 220))
    draw.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 255, 255, 255))
    draw.line([(cx - r, cy), (cx + r, cy)], fill=(255, 255, 200, 180), width=2)
    draw.line([(cx, cy - r), (cx, cy + r)], fill=(255, 255, 200, 180), width=2)
    return img


def generate_star(size=48):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    outer_r = size // 2 - 2
    inner_r = outer_r // 2
    points = []
    for i in range(10):
        angle = i * 36 - 90
        r = outer_r if i % 2 == 0 else inner_r
        x = cx + r * math.cos(math.radians(angle))
        y = cy + r * math.sin(math.radians(angle))
        points.append((x, y))
    draw.polygon(points, fill=(255, 215, 0, 220))
    draw.polygon(points, fill=None, outline=(255, 255, 200, 150), width=1)
    return img


def generate_heart(size=48):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2 + 2
    r = size // 5
    draw.ellipse([cx - r, cy - r - 4, cx, cy + 3], fill=(255, 105, 180, 200))
    draw.ellipse([cx, cy - r - 4, cx + r, cy + 3], fill=(255, 105, 180, 200))
    draw.polygon([(cx - r - 2, cy + 2), (cx + r + 2, cy + 2), (cx, cy + r + 8)], fill=(255, 105, 180, 200))
    return img


def generate_cloud(size=96):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    white = (255, 255, 255, 200)
    draw.ellipse([cx - 25, cy - 10, cx + 10, cy + 20], fill=white)
    draw.ellipse([cx - 15, cy - 20, cx + 20, cy + 10], fill=white)
    draw.ellipse([cx - 5, cy - 25, cx + 30, cy + 5], fill=white)
    return img


def generate_rainbow_arc(size=128):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [(255, 0, 0, 150), (255, 165, 0, 150), (255, 255, 0, 150),
              (0, 255, 0, 150), (0, 0, 255, 150), (128, 0, 128, 150)]
    cx, cy = size // 2, size - 10
    for i, color in enumerate(colors):
        r = size // 2 - i * 5
        draw.arc([cx - r, cy - r, cx + r, cy + r], 0, 180, fill=color, width=4)
    return img


def generate_star_burst(size=80):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size // 2, size // 2
    for i in range(12):
        angle = i * 30
        rad = math.radians(angle)
        length = size // 3
        ex = cx + int(length * math.cos(rad))
        ey = cy + int(length * math.sin(rad))
        draw.line([(cx, cy), (ex, ey)], fill=(255, 255, 200, 150), width=2)
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(255, 255, 255, 220))
    return img


EFFECT_GENERATORS = {
    "sparkle": (64, generate_sparkle),
    "star": (48, generate_star),
    "heart": (48, generate_heart),
    "cloud": (96, generate_cloud),
    "rainbow_arc": (128, generate_rainbow_arc),
    "star_burst": (80, generate_star_burst),
}


def generate_all_effects(output_dir: str = None):
    if output_dir is None:
        output_dir = EFFECTS_DIR
    os.makedirs(output_dir, exist_ok=True)

    for name, (size, generator) in EFFECT_GENERATORS.items():
        try:
            img = generator()
            filepath = os.path.join(output_dir, f"{name}.png")
            img.save(filepath, "PNG")
            print(f"  {name}: saved ({size}x{size})")
        except Exception as e:
            print(f"  {name}: FAILED - {e}")

    print(f"Effects generated in {output_dir}")


if __name__ == "__main__":
    print("Generating effects...")
    generate_all_effects()
    print("Done!")
