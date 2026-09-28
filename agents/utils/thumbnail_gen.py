import os
import re
import zlib
import random
import time
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils.subprocess_helper import safe_run, safe_run_bool
from utils.brand_palette import (
    LICORICE, PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE, WHITE, ACCENT_RAMP,
    hex_to_rgb, lerp,
)

THUMBNAIL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "thumbnails")


def _ensure_thumbnail_dir():
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)


_ensure_thumbnail_dir()

# Thumbnail palettes, derived from the channel brand rather than hand-picked.
#
# These were eight unrelated schemes (teal, green, red, orange) chosen by
# `hash(topic) % 8`. Two problems: the thumbnail is the most-seen surface the
# channel has -- it is what people see in browse and search -- and it was the
# one place carrying no brand at all; and `hash()` on a str is salted per
# process, so the same topic rendered a different palette after every restart
# and nothing was reproducible.
#
# Every scheme is a dark gradient over Licorice. Dark bases are not just
# on-brand, they are also what makes the white text reliably legible: the old
# light schemes (a near-white #DFE6E9) forced a per-scheme dark text colour, and
# that is the kind of thing that silently ships unreadable when the wrap count
# changes.
#
# The gradient's light end is the accent blended 50% toward Licorice, NOT the
# accent itself. Measured against WCAG, white on the full-brightness accents is
# 5.63:1 (violet) but only 3.06:1 (pink) and 2.49:1 (orange) -- below AA, i.e.
# unreadable at thumbnail size. Blending to 50% puts the worst case at ~5.4:1
# while keeping the hue. The decorative accents stay at full brightness, so the
# thumbnail still pops; only the surface the text sits on is deepened.
_GRADIENT_BLEND = 0.5
BRAND_SCHEMES = [
    {"bg1": hex_to_rgb(LICORICE), "bg2": lerp(acc, LICORICE, _GRADIENT_BLEND),
     "accent": hex_to_rgb(acc), "text": hex_to_rgb(WHITE)}
    for acc in (VIOLET, PURPLE, PINK, ORANGE, VIOLET, PURPLE)
]
# Kept as the module's public name -- pick_best_thumbnail and the selfcheck read it.
COLOR_SCHEMES = BRAND_SCHEMES

DARK_COLORS = {
    "bg_dark": hex_to_rgb(LICORICE),
    "indigo": hex_to_rgb(PURPLE),
    "cyan": hex_to_rgb(LIGHT_ORANGE),
    "violet": hex_to_rgb(VIOLET),
    "white": hex_to_rgb(WHITE),
    "gray": (156, 163, 175),
    "accent_gradient_start": hex_to_rgb(VIOLET),
    "accent_gradient_end": hex_to_rgb(PINK),
}


def _stable_hash(text: str) -> int:
    """crc32, not hash().

    Python salts str hashes per process (PYTHONHASHSEED), so every one of these
    call sites produced a different value after a container restart: the palette
    changed, and worse the *output filenames* changed, so a thumbnail could not
    be re-found by name and any name-keyed cache missed every time.
    """
    return zlib.crc32(text.encode("utf-8"))


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


def _draw_grid(draw: ImageDraw, width: int, height: int, spacing: int = 60, opacity: int = 15):
    grid_color = (255, 255, 255, opacity)
    for x in range(0, width, spacing):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, spacing):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)


def _draw_gradient_bar(draw: ImageDraw, width: int, height: int, bar_height: int = 6):
    c = DARK_COLORS
    for x in range(width):
        ratio = x / width
        r = int(c["accent_gradient_start"][0] * (1 - ratio) + c["accent_gradient_end"][0] * ratio)
        g = int(c["accent_gradient_start"][1] * (1 - ratio) + c["accent_gradient_end"][1] * ratio)
        b = int(c["accent_gradient_start"][2] * (1 - ratio) + c["accent_gradient_end"][2] * ratio)
        draw.line([(x, height - bar_height), (x, height)], fill=(r, g, b))


def _draw_circle_decoration(draw: ImageDraw, width: int, height: int, count: int = 3):
    for _ in range(count):
        cx = random.randint(50, width - 50)
        cy = random.randint(50, height - 50)
        r = random.randint(40, 120)
        color = random.choice([DARK_COLORS["indigo"], DARK_COLORS["cyan"], DARK_COLORS["violet"]])
        color = (*color[:3], 30)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=None)


def generate_thumbnail_image(topic: str, thumbnail_text: str, format_type: str = "shorts",
                              output_filename: str = None, style: str = "abstract") -> dict:
    if format_type == "shorts":
        width, height = 1080, 1920
    else:
        width, height = 1280, 720

    if style == "dark":
        c = DARK_COLORS
        img = Image.new("RGBA", (width, height), c["bg_dark"])
        draw = ImageDraw.Draw(img)
        _draw_grid(draw, width, height, spacing=80, opacity=10)
        _draw_circle_decoration(draw, width, height, count=4)
        _draw_gradient_bar(draw, width, height)
        title_color = c["indigo"]
        sub_color = c["cyan"]
    else:
        # Stable across restarts: zlib.crc32, not hash() (PYTHONHASHSEED salts str hashes).
        scheme = COLOR_SCHEMES[zlib.crc32(topic.encode("utf-8")) % len(COLOR_SCHEMES)]
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

        _seed0 = zlib.crc32(topic.encode("utf-8")) % 100
        for seed_val in range(_seed0, _seed0 + 5):
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
        title_color = scheme["text"]
        sub_color = scheme["accent"]

    sdxl_prompt = extract_sdxl_prompt(thumbnail_text)
    text_overlay = extract_text_overlay(thumbnail_text)
    if not text_overlay or len(text_overlay) < 3:
        text_overlay = sdxl_prompt[:60] if sdxl_prompt else " ".join(topic.split()[:4])

    title_font = _find_font(80 if format_type == "long" else 100)
    subtitle_font = _find_font(40 if format_type == "long" else 50)

    if format_type == "long":
        text_y = height // 3
        title_max_width = width - 100
        title_lines = _wrap_text(text_overlay, title_font, title_max_width)
        for line in title_lines:
            _draw_text_shadow(draw, line, (width // 2, text_y), title_font, title_color)
            text_y += title_font.size + 20

        topic_lines = _wrap_text(topic, subtitle_font, title_max_width - 50)
        topic_y = text_y + 20
        for line in topic_lines:
            _draw_text_shadow(draw, line, (width // 2, topic_y), subtitle_font, sub_color)
            topic_y += subtitle_font.size + 10
    else:
        text_y = height // 3
        title_max_width = width - 100
        title_lines = _wrap_text(text_overlay, title_font, title_max_width)
        for line in title_lines:
            _draw_text_shadow(draw, line, (width // 2, text_y), title_font, title_color)
            text_y += title_font.size + 15

        topic_lines = _wrap_text(topic, subtitle_font, title_max_width - 50)
        topic_y = text_y + 30
        for line in topic_lines:
            _draw_text_shadow(draw, line, (width // 2, topic_y), subtitle_font, sub_color)
            topic_y += subtitle_font.size + 8

    if style != "dark":
        for seed_val in range(_stable_hash(topic + "sparkles") % 100, _stable_hash(topic + "sparkles") % 100 + 10):
            x = (seed_val * 31) % width
            y = (seed_val * 37) % height
            size = 3 + (seed_val * 3) % 8
            draw.ellipse([(x, y), (x + size, y + size)], fill=scheme["accent"] + (150,))

    if output_filename is None:
        output_filename = f"thumb_{format_type}_{_stable_hash(topic) % 100000}.png"
    output_path = os.path.join(THUMBNAIL_DIR, output_filename)

    _ensure_thumbnail_dir()
    try:
        img.save(output_path, "PNG", quality=95)
    except Exception as e:
        print(f"[THUMBNAIL] Failed to save thumbnail: {e}")
        return {
            "success": False,
            "path": output_path,
            "error": str(e),
        }

    return {
        "success": True,
        "path": output_path,
        "dimensions": f"{width}x{height}",
        "format": format_type,
        "style": style,
    }


def _measure_image(path: str) -> dict:
    """Measure REAL visual properties from pixels.

    The old scorer derived every metric from `hash(loop_index)` — identical on every
    run, unrelated to the image. A thumbnail has to be judged on what a viewer
    actually sees, so measure the pixels: colourfulness, edge/detail density, and
    luminance spread (flat art scores badly, which is the point).
    """
    out = {"colorfulness": 0.0, "edge_density": 0.0, "contrast": 0.0}
    try:
        from PIL import ImageFilter as _IF
        import numpy as np
        with Image.open(path) as im:
            im = im.convert("RGB")
            small = im.resize((160, 90), Image.BILINEAR)
            arr = np.asarray(small).astype("float32")
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            rg = np.abs(r - g)
            yb = np.abs(0.5 * (r + g) - b)
            out["colorfulness"] = float((np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2)))
            gray = np.asarray(small.convert("L")).astype("float32")
            out["contrast"] = float(gray.std() / 128.0)
            edges = np.asarray(small.convert("L").filter(_IF.FIND_EDGES)).astype("float32")
            out["edge_density"] = float((edges > 24).mean())
    except Exception:
        pass
    return out


def _score_thumbnail(variant: dict) -> float:
    """Score a thumbnail on measured properties. Higher is better."""
    m = variant.get("measured") or {}
    colorfulness = m.get("colorfulness", 0.0)
    edge_density = m.get("edge_density", 0.0)
    contrast = m.get("contrast", 0.0)

    score = 20.0
    # Colourful photos beat flat gradients.
    score += min(colorfulness, 80.0) * 0.6
    # Some detail is good (readable subject); a mush of noise is not.
    if 0.04 <= edge_density <= 0.30:
        score += 25.0
    elif edge_density > 0.30:
        score += max(0.0, 25.0 - (edge_density - 0.30) * 60.0)
    # Luminance spread: the text has to read against it.
    if 0.18 <= contrast <= 0.55:
        score += 20.0
    # Text length: YouTube thumbnails should be near-wordless. The old scorer
    # REWARDED longer text, which is backwards.
    text_len = variant.get("text_length", 0)
    if 0 < text_len <= 40:
        score += 15.0
    elif text_len > 70:
        score -= 10.0
    return round(score, 2)


# --- Concept F: "Lavender Editorial" -- LOCKED by the owner 2026-09-28. ---------
# Pale lavender ground, violet serif headline, brand ramp rule, orange tick,
# licorice footer. Replaces the dark scrimmed-photo Concept B.
#
# Colour here is arithmetic, not taste. On this ground only LICORICE (18.4:1) and
# VIOLET (5.6:1) clear AA as text; PURPLE clears only the 3:1 large-text bar, and
# PINK / ORANGE / LIGHT_ORANGE / AMBER run 1.7-3.1:1 and are decorative. So PURPLE
# is confined to display type and ORANGE to a mark. The assertion in _draw_light
# is the guard: a later edit that reaches for a decorative colour as type fails
# here instead of quietly shipping unreadable text.
_BODY_SAFE = {LICORICE, VIOLET}
_DISPLAY_SAFE = _BODY_SAFE | {PURPLE}
GROUND = lerp(WHITE, PURPLE, 0.07)  # #F8F3FF, a lerp of two brand colours
KICKER = "AI EXPLAINED"
FOOTER = "Vyom Ai Cloud"


def _soft_blob(img, cx, cy, r, col, t):
    """A brand-coloured wash. Decorative only -- never behind body text."""
    base = img.copy()
    wash = Image.new("RGB", img.size, lerp(WHITE, col, t))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
    return Image.composite(wash, base, mask.filter(ImageFilter.GaussianBlur(max(2, r // 3))))


def _accent_rule(d, x, y, w, h):
    seg = max(1, w // len(ACCENT_RAMP))
    for i, hexcol in enumerate(ACCENT_RAMP):
        x0 = x + i * seg
        x1 = x + (i + 1) * seg if i < len(ACCENT_RAMP) - 1 else x + w
        d.rectangle([(x0, y), (x1, y + h)], fill=hex_to_rgb(hexcol))


def _draw_light(d, xy, s, font, fill, width=0, display=False):
    """Text on the light ground, refusing any colour that cannot carry it."""
    if not s:
        return
    allowed = _DISPLAY_SAFE if display else _BODY_SAFE
    assert fill in allowed, (
        f"{fill} is not text-safe on the light thumbnail ground "
        f"(decorative brand colours run 1.7-3.1:1 there) -- use it on a rule or mark"
    )
    rgb = hex_to_rgb(fill)
    for i, line in enumerate(_wrap_text(s, font, width) if width else [s]):
        d.text((xy[0], xy[1] + i * int(font.size * 1.16)), line, font=font, fill=rgb)


def _compose_thumbnail(background: str, title: str, out_path: str,
                       format_type: str = "long", style: str = "abstract") -> str:
    """Compose the locked Concept F card. Returns "" if it fails.

    `background` and `style` are kept so callers are unchanged, but Concept F is a
    flat palette ground and deliberately does not composite a photo. Putting one
    back is a different design, not a flag: it needs the scrim, the crop and the
    contrast re-check that the light ground replaced.
    """
    try:
        target = (1080, 1920) if format_type == "shorts" else (1280, 720)
        tw, th = target

        img = _soft_blob(Image.new("RGB", (tw, th), GROUND),
                         int(tw * 0.86), int(th * 0.80),
                         int(min(tw, th) * 0.46), VIOLET, 0.30)
        d = ImageDraw.Draw(img)
        pad = int(tw * 0.075)

        _accent_rule(d, pad, int(th * 0.20), int(tw * 0.26), max(5, th // 150))
        _draw_light(d, (pad, int(th * 0.25)), KICKER, _find_font(int(th * 0.030)), VIOLET)
        _draw_light(d, (pad, int(th * 0.33)), title,
                    _find_font(int(th * 0.082), serif=True), VIOLET,
                    width=int(tw * 0.78))
        d.rectangle(
            [(pad, int(th * 0.86)),
             (pad + int(tw * 0.10), int(th * 0.86) + max(4, th // 200))],
            fill=hex_to_rgb(ORANGE),
        )
        _draw_light(d, (pad, int(th * 0.89)), FOOTER, _find_font(int(th * 0.028)), LICORICE)

        _ensure_thumbnail_dir()
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        # JPEG: YouTube rejects thumbnails over 2MB and PNG art hits that fast.
        img.save(out_path, "JPEG", quality=92, optimize=True)
        return out_path if os.path.exists(out_path) and os.path.getsize(out_path) > 2000 else ""
    except Exception as e:
        print(f"[THUMBNAIL] compose failed: {e}")
        return ""


def fit_under_2mb(path: str, limit: int = 2 * 1024 * 1024 - 4096) -> str:
    """Shrink a thumbnail until YouTube's ~2MB limit accepts it. Returns the path."""
    if not path or not os.path.exists(path):
        return path
    if os.path.getsize(path) <= limit:
        return path
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            quality, width = 92, im.width
            while quality >= 40 and os.path.getsize(path) > limit:
                tmp = path + ".tmp.jpg"
                im.save(tmp, "JPEG", quality=quality, optimize=True)
                os.replace(tmp, path)
                if os.path.getsize(path) <= limit:
                    break
                quality -= 12
                if quality < 40 and width > 640:
                    # Still too big: downscale a notch and retry.
                    width = max(640, int(width * 0.85))
                    im = im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)
        print(f"[THUMBNAIL] Compressed to {os.path.getsize(path)}B (limit {limit}B)")
    except Exception as e:
        print(f"[THUMBNAIL] 2MB fit failed: {e}")
    return path


def generate_thumbnail_variants(topic: str, thumbnail_text: str, format_type: str = "shorts") -> dict:
    """Compose the locked Concept F card.

    Concept F is a flat palette ground, so an image model has nothing to add: the
    old 3-photo Pollinations round and the measured/scored candidate list are gone
    rather than left generating images that _compose_thumbnail then discards. One
    deterministic card per video. The `variants` key stays non-empty because
    main.py falls back to variants[0].
    """
    text_overlay = extract_text_overlay(thumbnail_text)
    overlay = (text_overlay or " ".join(topic.split()[:4])).strip()

    _ensure_thumbnail_dir()
    out = os.path.join(THUMBNAIL_DIR, f"thumb_{format_type}_f.jpg")
    if not _compose_thumbnail("", overlay, out, format_type=format_type, style="photo"):
        return {"best": None, "variants": [], "count": 0, "source": "failed"}
    return {
        "best": out,
        "variants": [out],
        "count": 1,
        "source": "concept_f",
        "measured": _measure_image(out),
    }


def _find_font(size: int, serif: bool = False):
    # serif=True gives the Concept B display voice used on thumbnails/cards.
    # DejaVuSerif is the reliable in-image face (the card renderer already uses
    # it); the macOS faces are host-only and absent from the container.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/Library/Fonts/Georgia Bold.ttf",
    ] if serif else [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


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


def _detect_stable_scene_time(video_path: str, video_duration: float) -> float:
    """Find a stable frame timestamp (not during a scene change or transition)."""
    try:
        cmd = [
            "ffmpeg", "-i", video_path, "-vf",
            f"select='gt(scene,0.1)',showinfo",
            "-vsync", "vfr", "-frames:v", "20", "-f", "null", "-"
        ]
        result = safe_run(cmd, timeout=60, capture_output=True)
        stderr = result.stderr or ""
        pts_times = re.findall(r'pts_time:([\d.]+)', stderr)
        if pts_times:
            scene_changes = [float(t) for t in pts_times if float(t) > 0]
            if len(scene_changes) >= 2:
                gaps = []
                for i in range(1, len(scene_changes)):
                    gap = scene_changes[i] - scene_changes[i - 1]
                    if gap > 1.0:
                        gaps.append((scene_changes[i - 1] + gap / 2, gap))
                if gaps:
                    longest = max(gaps, key=lambda x: x[1])
                    return longest[0]
            if scene_changes:
                midpoint = len(scene_changes) // 3
                return scene_changes[midpoint] + 0.5
        return video_duration * 0.25
    except Exception:
        return video_duration * 0.25


def extract_video_frame(video_path: str, time_sec: float = None, smart: bool = True) -> str:
    """Extract a frame from the video at the given timestamp for a thumbnail.
    
    If smart=True and no time_sec given, automatically picks the midpoint of the
    longest stable segment (no scene changes).
    """
    frame_path = os.path.join(THUMBNAIL_DIR, f"frame_{_stable_hash(video_path) % 100000}.jpg")
    os.makedirs(os.path.dirname(frame_path), exist_ok=True)
    if time_sec is None:
        if smart:
            try:
                probe = safe_run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                    timeout=10)
                dur = float(probe.stdout.strip())
                time_sec = _detect_stable_scene_time(video_path, dur)
            except Exception:
                time_sec = 4.0
        else:
            time_sec = 4.0
    try:
        safe_run_bool(
            ["ffmpeg", "-ss", str(time_sec), "-i", video_path,
             "-frames:v", "1", "-q:v", "3", "-y", frame_path],
            timeout=30)
        if os.path.exists(frame_path) and os.path.getsize(frame_path) > 1000:
            return frame_path
    except Exception:
        pass
    return ""


def generate_thumbnail_from_video(video_path: str, title: str, format_type: str = "shorts",
                                   output_filename: str = None) -> dict:
    """Generate a thumbnail using a frame from the actual video content."""
    from PIL import ImageDraw
    if output_filename is None:
        output_filename = f"thumb_video_{_stable_hash(video_path) % 100000}.png"
    output_path = os.path.join(THUMBNAIL_DIR, output_filename)
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)

    frame_path = extract_video_frame(video_path, smart=True)

    if format_type == "shorts":
        thumb_w, thumb_h = 1080, 1920
    else:
        thumb_w, thumb_h = 1280, 720

    if frame_path:
        try:
            frame = Image.open(frame_path).convert("RGB")
            frame = frame.filter(ImageFilter.GaussianBlur(radius=8))
            bg = frame.resize((thumb_w, thumb_h), Image.LANCZOS)
        except Exception:
            scheme = COLOR_SCHEMES[0]
            bg = Image.new("RGB", (thumb_w, thumb_h), scheme["bg1"])
    else:
        scheme = COLOR_SCHEMES[_stable_hash(title) % len(COLOR_SCHEMES)]
        bg = Image.new("RGB", (thumb_w, thumb_h), scheme["bg1"])
        for seed_val in range(100, 105):
            rng = seed_val
            cx = (rng * 17) % thumb_w
            cy = (rng * 23) % thumb_h
            radius = 80 + (rng * 7) % 120
            color = COLOR_SCHEMES[(seed_val + 1) % len(COLOR_SCHEMES)]["accent"]
            blob = Image.new("RGBA", (radius * 2, radius * 2), (0, 0, 0, 0))
            bd = ImageDraw.Draw(blob)
            bd.ellipse([(0, 0), (radius * 2, radius * 2)], fill=color + (80,))
            blob = blob.filter(ImageFilter.GaussianBlur(radius=25))
            bg.paste(blob, (cx - radius, cy - radius), blob)

    draw = ImageDraw.Draw(bg)
    title_font = _find_font(120 if format_type == "shorts" else 100)
    max_width = thumb_w - 120
    title_lines = _wrap_text(title, title_font, max_width)
    text_y = thumb_h // 3
    for line in title_lines:
        _draw_text_shadow(draw, line, (thumb_w // 2, text_y), title_font, (255, 255, 255), offset=5)
        text_y += title_font.size + 15

    # Add channel branding
    brand_font = _find_font(40)
    _draw_text_shadow(draw, "Vyom Ai Cloud", (thumb_w // 2, thumb_h - 120), brand_font, (200, 200, 200), offset=3)

    try:
        bg.save(output_path, "PNG", quality=95)
        return {"success": True, "path": output_path, "dimensions": f"{thumb_w}x{thumb_h}", "format": format_type}
    except Exception as e:
        return {"success": False, "path": output_path, "error": str(e)}


def pick_best_thumbnail(answer_path: str, video_path: str, title: str, format_type: str) -> str:
    """Pick the best available thumbnail.

    The old version ignored the generated variants entirely and always returned a
    blurred video frame, throwing away the work of generate_thumbnail_variants().
    Now: use the best generated variant when we have one, and only fall back to the
    video frame / procedural art when there isn't.
    """
    chosen = answer_path
    if answer_path and os.path.exists(answer_path):
        try:
            measured = _measure_image(answer_path)
            if _score_thumbnail({"measured": measured, "text_length": len(title or "")}) > 0:
                chosen = answer_path
        except Exception:
            chosen = answer_path

    if video_path and os.path.exists(video_path):
        result = generate_thumbnail_from_video(video_path, title, format_type)
        if result["success"] and os.path.exists(result["path"]):
            # A video frame is a real photo but carries no title text, so only take
            # it when we have nothing better.
            if not chosen or not os.path.exists(chosen):
                chosen = result["path"]
                print(f"[THUMBNAIL] Using video-frame thumbnail: {chosen}")
            else:
                print("[THUMBNAIL] Keeping generated variant over video frame")

    if not chosen:
        print("[THUMBNAIL] No usable thumbnail")

    return fit_under_2mb(chosen) if chosen else ""


def _get_thumbnail_style_from_path(path: str) -> str:
    """Extract thumbnail style from file path for analytics tracking."""
    if not path:
        return "unknown"
    if "video_frame" in path:
        return "video_frame"
    if "abstract" in path:
        return "abstract"
    if "dark" in path:
        return "dark"
    if "thumb_" in path:
        parts = os.path.basename(path).split("_")
        return parts[1] if len(parts) > 1 else "generated"
    return "unknown"


def record_thumbnail_for_ctr(video_id: str, thumbnail_path: str) -> None:
    """Record which thumbnail style was used for analytics correlation."""
    style = _get_thumbnail_style_from_path(thumbnail_path)
    thumb_dir = Path(__file__).parent.parent / "data" / "thumbnail_ctr"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    record_path = thumb_dir / "thumbnail_ctr.json"
    data = {}
    rp = str(record_path)
    if os.path.exists(rp):
        try:
            with open(rp) as f:
                data = json.load(f)
        except Exception:
            pass
    data[video_id] = {"style": style, "path": thumbnail_path, "timestamp": time.time()}
    os.makedirs(os.path.dirname(rp), exist_ok=True)
    with open(rp, "w") as f:
        json.dump(data, f, indent=2)
