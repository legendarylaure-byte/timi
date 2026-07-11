import os
import re
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from utils.subprocess_helper import safe_run, safe_run_bool

THUMBNAIL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "thumbnails")


def _ensure_thumbnail_dir():
    os.makedirs(THUMBNAIL_DIR, exist_ok=True)


_ensure_thumbnail_dir()

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

DARK_COLORS = {
    "bg_dark": (10, 10, 15),
    "indigo": (99, 102, 241),
    "cyan": (34, 211, 238),
    "violet": (167, 139, 250),
    "white": (255, 255, 255),
    "gray": (156, 163, 175),
    "accent_gradient_start": (99, 102, 241),
    "accent_gradient_end": (34, 211, 238),
}


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
        for seed_val in range(hash(topic + "sparkles") % 100, hash(topic + "sparkles") % 100 + 10):
            x = (seed_val * 31) % width
            y = (seed_val * 37) % height
            size = 3 + (seed_val * 3) % 8
            draw.ellipse([(x, y), (x + size, y + size)], fill=scheme["accent"] + (150,))

    if output_filename is None:
        output_filename = f"thumb_{format_type}_{hash(topic) % 100000}.png"
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


def _score_thumbnail(variant: dict) -> float:
    text_len = variant.get("text_length", 0)
    contrast = variant.get("contrast", 0.5)
    scheme_idx = variant.get("scheme_idx", 0)
    score = 50
    score += min(text_len * 2, 20)
    if contrast > 0.3 and contrast < 0.9:
        score += 15
    if scheme_idx in (1, 4, 6):
        score += 10
    score += variant.get("blob_density", 5)
    return score


def generate_thumbnail_variants(topic: str, thumbnail_text: str, format_type: str = "shorts") -> dict:
    variants = []
    text_overlay = extract_text_overlay(thumbnail_text)
    overlay = text_overlay or " ".join(topic.split()[:4])
    styles = ["abstract", "dark"]

    for i in range(3):
        style = styles[i % len(styles)]
        scheme_idx = (hash(topic + str(i)) % len(COLOR_SCHEMES))
        out = f"thumb_{format_type}_{hash(topic + str(i)) % 100000}.png"
        result = generate_thumbnail_image(topic, thumbnail_text, format_type, out, style=style)
        if result["success"]:
            blob_density = 5 + (hash(str(i)) % 10)
            variants.append({
                "path": result["path"],
                "scheme_idx": scheme_idx,
                "text_length": len(overlay),
                "contrast": 0.4 + (hash(str(i)) % 30) / 100,
                "blob_density": blob_density,
                "style": style,
                "score": 0,
            })

    for v in variants:
        v["score"] = _score_thumbnail(v)

    variants.sort(key=lambda x: x["score"], reverse=True)
    best = variants[0] if variants else None

    return {
        "best": best["path"] if best else None,
        "variants": [v["path"] for v in variants],
        "count": len(variants),
    }


def _find_font(size: int):
    candidates = [
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
    frame_path = os.path.join(THUMBNAIL_DIR, f"frame_{hash(video_path) % 100000}.jpg")
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
        output_filename = f"thumb_video_{hash(video_path) % 100000}.png"
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
        scheme = COLOR_SCHEMES[hash(title) % len(COLOR_SCHEMES)]
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
    """Preferred: video frame thumbnail. Fallback: abstract art thumbnail."""
    result = generate_thumbnail_from_video(video_path, title, format_type)
    if result["success"]:
        print(f"[THUMBNAIL] Generated video-frame thumbnail: {result['path']}")
        return result["path"]
    print(f"[THUMBNAIL] Video frame failed, using abstract art")
    return answer_path
