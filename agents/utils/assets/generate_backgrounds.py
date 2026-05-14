import os
from PIL import Image, ImageDraw, ImageFilter
import math

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
BG_SIZE = (1920, 1080)
BG_SIZE_PORTRAIT = (1080, 1920)


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def gradient_2d(draw, xy, color_top, color_bottom):
    x1, y1, x2, y2 = xy
    for y in range(y1, y2):
        ratio = (y - y1) / (y2 - y1)
        r = int(color_top[0] * (1 - ratio) + color_bottom[0] * ratio)
        g = int(color_top[1] * (1 - ratio) + color_bottom[1] * ratio)
        b = int(color_top[2] * (1 - ratio) + color_bottom[2] * ratio)
        draw.line([(x1, y), (x2, y)], fill=(r, g, b))


def generate_gradient_sky(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (135, 206, 235), (240, 248, 255))
    w, h = size
    for _ in range(8):
        cx = int(w * 0.1 + (w * 0.8) * (math.sin(_ * 1.7) * 0.5 + 0.5))
        cy = int(h * 0.1 + (h * 0.3) * (math.cos(_ * 1.3) * 0.5 + 0.5))
        r = 30 + _ * 10
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 180))
    return img


def generate_gradient_forest(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (173, 216, 230), (34, 139, 34))
    w, h = size
    for i in range(6):
        tree_x = int(w * 0.1 + i * w * 0.15)
        tree_h = int(h * 0.35)
        draw.polygon([(tree_x, h - tree_h), (tree_x - 40, h), (tree_x + 40, h)], fill=(0, 100, 0))
        draw.polygon([(tree_x, h - tree_h - 40), (tree_x - 30, h - tree_h + 10), (tree_x + 30, h - tree_h + 10)], fill=(0, 130, 0))
    return img


def generate_gradient_ocean(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (0, 119, 190), (0, 191, 255))
    w, h = size
    for y in range(h // 2, h, 15):
        amplitude = 10 + math.sin(y * 0.01) * 5
        for x in range(0, w, 4):
            offset = int(amplitude * math.sin(x * 0.02 + y * 0.01))
            draw.point((x, y + offset), fill=(100, 200, 255, 100))
    return img


def generate_gradient_space(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (10, 10, 40), (25, 25, 80))
    w, h = size
    import random
    rng = random.Random(42)
    for _ in range(80):
        sx = rng.randint(0, w)
        sy = rng.randint(0, h)
        brightness = rng.randint(150, 255)
        r = rng.randint(1, 3)
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(brightness, brightness, brightness))
    for _ in range(3):
        cx = rng.randint(50, w - 50)
        cy = rng.randint(50, h // 2)
        cr = rng.randint(15, 30)
        draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=(200, 200, 100))
        draw.ellipse([cx - cr - 5, cy - cr - 5, cx + cr + 5, cy + cr + 5], fill=(255, 255, 200, 50))
    return img


def generate_gradient_sunset(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (255, 94, 77), (255, 215, 0))
    w, h = size
    sun_cx, sun_cy = w // 2, h * 3 // 4
    sun_r = 60
    for r in range(sun_r * 3, sun_r, -5):
        alpha = max(0, 255 - int((sun_r * 3 - r) / (sun_r * 2) * 200))
        draw.ellipse([sun_cx - r, sun_cy - r, sun_cx + r, sun_cy + r], fill=(255, 200, 100, alpha))
    draw.ellipse([sun_cx - sun_r, sun_cy - sun_r, sun_cx + sun_r, sun_cy + sun_r], fill=(255, 255, 200))
    return img


def generate_gradient_night(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (10, 10, 50), (30, 30, 90))
    w, h = size
    import random
    rng = random.Random(123)
    for _ in range(100):
        sx = rng.randint(0, w)
        sy = rng.randint(0, h // 2)
        brightness = rng.randint(180, 255)
        r = rng.randint(1, 2)
        draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=(brightness, brightness, brightness))
    moon_cx, moon_cy = w * 3 // 4, h // 4
    moon_r = 40
    draw.ellipse([moon_cx - moon_r, moon_cy - moon_r, moon_cx + moon_r, moon_cy + moon_r], fill=(255, 255, 220))
    draw.ellipse([moon_cx + 10, moon_cy - 10, moon_cx + moon_r + 5, moon_cy + moon_r - 5], fill=(30, 30, 90))
    return img


def generate_gradient_garden(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (152, 251, 152), (34, 139, 34))
    w, h = size
    import random
    rng = random.Random(456)
    for _ in range(20):
        fx = rng.randint(20, w - 20)
        fy = rng.randint(h // 2, h - 20)
        color = rng.choice([(255, 182, 193), (255, 215, 0), (255, 105, 180), (147, 112, 219), (255, 69, 0)])
        for p in range(5):
            px = fx + int(10 * math.cos(p * 1.256))
            py = fy - 20 + int(10 * math.sin(p * 1.256))
            draw.ellipse([px - 6, py - 6, px + 6, py + 6], fill=color)
        draw.ellipse([fx - 4, fy - 4, fx + 4, fy + 4], fill=(255, 255, 0))
    return img


def generate_gradient_classroom(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (255, 248, 220), (245, 245, 220))
    w, h = size
    draw.rectangle([100, h - 200, w - 100, h - 20], fill=(210, 180, 140))
    board_y = 100
    board_h = 160
    draw.rectangle([w // 2 - 200, board_y, w // 2 + 200, board_y + board_h], fill=(50, 120, 50))
    draw.rectangle([w // 2 - 190, board_y + 10, w // 2 + 190, board_y + board_h - 10], fill=(70, 160, 70))
    for i, letter in enumerate("ABC"):
        lx = w // 2 - 100 + i * 80
        draw.text((lx, board_y + 50), letter, fill=(255, 255, 255))
    return img


def generate_gradient_bedroom(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (255, 228, 225), (255, 182, 193))
    w, h = size
    bed_w, bed_h = 400, 250
    bed_x, bed_y = (w - bed_w) // 2, h - bed_h - 50
    draw.rectangle([bed_x, bed_y, bed_x + bed_w, bed_y + bed_h], fill=(200, 180, 255))
    pillow_h = 40
    draw.rectangle([bed_x + 20, bed_y + 10, bed_x + 100, bed_y + pillow_h], fill=(255, 255, 255))
    draw.rectangle([bed_x + bed_w - 100, bed_y + 10, bed_x + bed_w - 20, bed_y + pillow_h], fill=(255, 255, 255))
    blanket_color = (180, 150, 255)
    draw.rectangle([bed_x + 50, bed_y + 80, bed_x + bed_w - 50, bed_y + bed_h - 10], fill=blanket_color)
    for _ in range(3):
        sx = w * 0.1 + _ * w * 0.35
        sy = h * 0.15
        draw.ellipse([sx - 15, sy - 15, sx + 15, sy + 15], fill=(255, 255, 100, 150))
    return img


def generate_gradient_underwater(size=BG_SIZE):
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    gradient_2d(draw, (0, 0, *size), (0, 105, 148), (0, 50, 100))
    w, h = size
    for y in range(h // 2, h, 20):
        for x in range(0, w, 4):
            amp = 5 + math.sin(y * 0.01) * 3
            offset = int(amp * math.sin(x * 0.03 + y * 0.02))
            draw.point((x, y + offset), fill=(50, 150, 200, 60))
    for _ in range(5):
        bx = 100 + _ * 350
        by = h - 60
        draw.ellipse([bx - 80, by - 15, bx + 80, by], fill=(0, 80, 60))
        draw.line([(bx - 60, by), (bx - 60, by - 40)], fill=(0, 100, 80), width=4)
        draw.line([(bx, by), (bx, by - 55)], fill=(0, 100, 80), width=6)
        draw.line([(bx + 40, by), (bx + 60, by - 35)], fill=(0, 100, 80), width=4)
    return img


def generate_color_solid(size=BG_SIZE, color="#FFF8DC"):
    rgb = _hex_to_rgb(color)
    return Image.new("RGB", size, rgb)


BACKGROUND_GENERATORS = {
    "gradient_sky": lambda s=BG_SIZE: generate_gradient_sky(s),
    "gradient_forest": lambda s=BG_SIZE: generate_gradient_forest(s),
    "gradient_ocean": lambda s=BG_SIZE: generate_gradient_ocean(s),
    "gradient_space": lambda s=BG_SIZE: generate_gradient_space(s),
    "gradient_sunset": lambda s=BG_SIZE: generate_gradient_sunset(s),
    "gradient_night": lambda s=BG_SIZE: generate_gradient_night(s),
    "gradient_garden": lambda s=BG_SIZE: generate_gradient_garden(s),
    "gradient_classroom": lambda s=BG_SIZE: generate_gradient_classroom(s),
    "gradient_bedroom": lambda s=BG_SIZE: generate_gradient_bedroom(s),
    "gradient_underwater": lambda s=BG_SIZE: generate_gradient_underwater(s),
    "color_solid": lambda s=BG_SIZE: generate_color_solid(s, "#FFF8DC"),
}


def generate_all_backgrounds(output_dir: str = None):
    if output_dir is None:
        output_dir = BACKGROUNDS_DIR
    os.makedirs(output_dir, exist_ok=True)

    for name, generator in BACKGROUND_GENERATORS.items():
        try:
            img_landscape = generator(BG_SIZE)
            landscape_path = os.path.join(output_dir, f"{name}_landscape.png")
            img_landscape.save(landscape_path, "PNG")

            img_portrait = generator(BG_SIZE_PORTRAIT)
            portrait_path = os.path.join(output_dir, f"{name}_portrait.png")
            img_portrait.save(portrait_path, "PNG")

            print(f"  {name}: landscape + portrait saved")
        except Exception as e:
            print(f"  {name}: FAILED - {e}")

    print(f"Backgrounds generated in {output_dir}")


if __name__ == "__main__":
    print("Generating backgrounds...")
    generate_all_backgrounds()
    print("Done!")
