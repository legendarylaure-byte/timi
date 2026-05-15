import json
import math
import os
import re

from PIL import ImageDraw, ImageFont

FPS = 30

SPOTLIGHT_WORDS = {
    "big": {"animation": "scale_up", "color": (255, 100, 100)},
    "small": {"animation": "scale_down", "color": (100, 200, 255)},
    "huge": {"animation": "scale_up", "color": (255, 50, 50)},
    "tiny": {"animation": "scale_down", "color": (150, 220, 255)},
    "tall": {"animation": "scale_up", "color": (100, 255, 100)},
    "short": {"animation": "scale_down", "color": (255, 200, 100)},
    "fast": {"animation": "shake", "color": (255, 100, 0)},
    "slow": {"animation": "float", "color": (100, 150, 255)},
    "jump": {"animation": "bounce_up", "color": (255, 200, 0)},
    "run": {"animation": "shake", "color": (255, 100, 50)},
    "spin": {"animation": "spin_text", "color": (200, 100, 255)},
    "fly": {"animation": "float_up", "color": (100, 200, 255)},
    "swim": {"animation": "wave_text", "color": (50, 150, 255)},
    "dance": {"animation": "bounce_up", "color": (255, 150, 200)},
    "sing": {"animation": "pulse", "color": (255, 100, 200)},
    "happy": {"animation": "bounce_up", "color": (255, 215, 0)},
    "sad": {"animation": "fade_tint", "color": (100, 100, 200)},
    "angry": {"animation": "shake", "color": (255, 50, 0)},
    "surprised": {"animation": "scale_up", "color": (255, 255, 0)},
    "brave": {"animation": "scale_up", "color": (255, 200, 50)},
    "clever": {"animation": "twinkle_text", "color": (200, 200, 255)},
    "kind": {"animation": "pulse", "color": (255, 150, 200)},
    "strong": {"animation": "scale_up", "color": (255, 50, 50)},
    "gentle": {"animation": "float", "color": (200, 255, 200)},
    "hot": {"animation": "shake", "color": (255, 50, 0)},
    "cold": {"animation": "fade_tint", "color": (100, 200, 255)},
    "wet": {"animation": "wave_text", "color": (50, 100, 255)},
    "dry": {"animation": "pulse", "color": (200, 200, 100)},
    "light": {"animation": "float_up", "color": (255, 255, 200)},
    "heavy": {"animation": "scale_down", "color": (150, 100, 50)},
    "soft": {"animation": "float", "color": (255, 200, 200)},
    "hard": {"animation": "shake", "color": (150, 150, 150)},
    "up": {"animation": "float_up", "color": (100, 255, 100)},
    "down": {"animation": "scale_down", "color": (200, 100, 100)},
    "red": {"animation": "color_flash", "color": (255, 0, 0)},
    "blue": {"animation": "color_flash", "color": (0, 0, 255)},
    "green": {"animation": "color_flash", "color": (0, 180, 0)},
    "yellow": {"animation": "color_flash", "color": (255, 215, 0)},
    "orange": {"animation": "color_flash", "color": (255, 140, 0)},
    "purple": {"animation": "color_flash", "color": (160, 32, 240)},
    "pink": {"animation": "color_flash", "color": (255, 105, 180)},
    "white": {"animation": "pulse", "color": (255, 255, 255)},
    "black": {"animation": "pulse", "color": (50, 50, 50)},
    "circle": {"animation": "spin_text", "color": (255, 200, 50)},
    "square": {"animation": "pulse", "color": (100, 200, 255)},
    "star": {"animation": "twinkle_text", "color": (255, 215, 0)},
    "heart": {"animation": "pulse", "color": (255, 50, 100)},
    "moon": {"animation": "float", "color": (200, 200, 220)},
    "sun": {"animation": "pulse", "color": (255, 215, 0)},
    "planet": {"animation": "spin_text", "color": (100, 200, 255)},
    "water": {"animation": "wave_text", "color": (50, 100, 255)},
    "seed": {"animation": "grow_text", "color": (100, 200, 100)},
    "grow": {"animation": "grow_text", "color": (50, 200, 50)},
    "flower": {"animation": "grow_text", "color": (255, 100, 200)},
    "rainbow": {"animation": "color_flash", "color": (255, 200, 50)},
    "magic": {"animation": "twinkle_text", "color": (200, 100, 255)},
    "dream": {"animation": "float", "color": (200, 200, 255)},
    "wish": {"animation": "float_up", "color": (255, 215, 200)},
    "one": {"animation": "count_up", "color": (255, 200, 50)},
    "two": {"animation": "count_up", "color": (100, 200, 255)},
    "three": {"animation": "count_up", "color": (100, 255, 100)},
    "four": {"animation": "count_up", "color": (255, 150, 100)},
    "five": {"animation": "count_up", "color": (200, 100, 255)},
}


def load_phrase_timing(timing_file: str) -> list[dict]:
    if not timing_file or not os.path.exists(timing_file):
        return []
    with open(timing_file) as f:
        data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("phrases", [])


def extract_spotlight_events(timing_file: str, narration_text: str, fps: int = FPS) -> list[dict]:
    phrases = load_phrase_timing(timing_file)
    events = []

    for phrase in phrases:
        text = phrase.get("text", "")
        start_ms = phrase.get("start_ms", 0)
        end_ms = phrase.get("end_ms", 0)
        if not text or start_ms >= end_ms:
            continue

        words = re.findall(r"[A-Za-z]+", text)
        for word in words:
            word_lower = word.lower()
            if word_lower in SPOTLIGHT_WORDS:
                config = SPOTLIGHT_WORDS[word_lower]
                events.append({
                    "word": word,
                    "frame_start": int(start_ms * fps / 1000),
                    "frame_end": int(end_ms * fps / 1000),
                    "animation": config["animation"],
                    "color": config["color"],
                })

    events.sort(key=lambda e: e["frame_start"])
    merged = []
    for event in events:
        if merged and merged[-1]["word"] == event["word"] and event["frame_start"] - merged[-1]["frame_end"] < fps:
            merged[-1]["frame_end"] = max(merged[-1]["frame_end"], event["frame_end"])
        else:
            merged.append(event)

    return merged


def assign_spotlights_to_scenes(
    spotlights: list[dict], scene_durations: list[float], fps: int = FPS
) -> list[list[dict]]:
    scene_frames = [int(d * fps) for d in scene_durations]
    cumulative = [sum(scene_frames[:i]) for i in range(len(scene_frames) + 1)]

    result = [[] for _ in scene_frames]
    for event in spotlights:
        gs, ge = event["frame_start"], event["frame_end"]
        for si in range(len(scene_frames)):
            cs, ce = cumulative[si], cumulative[si + 1]
            local_start = max(gs, cs) - cs
            local_end = min(ge, ce) - cs
            if local_end > local_start:
                result[si].append({
                    "word": event["word"],
                    "local_start": local_start,
                    "local_end": local_end,
                    "duration_frames": local_end - local_start,
                    "animation": event["animation"],
                    "color": event["color"],
                })
    return result


def process_spotlights(scene_configs: list[dict], timing_file: str, narration_text: str, fps: int = FPS) -> list[dict]:
    spotlights = extract_spotlight_events(timing_file, narration_text, fps)
    if not spotlights:
        return scene_configs

    durations = [s.get("duration", 5) for s in scene_configs]
    per_scene = assign_spotlights_to_scenes(spotlights, durations, fps)

    result = []
    for i, scene in enumerate(scene_configs):
        scene = dict(scene)
        if per_scene[i]:
            existing = scene.get("spotlights", [])
            scene["spotlights"] = existing + per_scene[i]
        result.append(scene)

    total = sum(len(s) for s in per_scene)
    print(f"[TEXT_ANIMATOR] Injected {total} spotlight events across {sum(1 for s in per_scene if s)} scenes")
    return result


def _find_spotlight_font(word: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/ArialBold.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.truetype("Arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def render_spotlight(draw: ImageDraw.ImageDraw, spotlight: dict, frame_idx: int, frame_w: int, frame_h: int):
    local = frame_idx - spotlight["local_start"]
    total = spotlight["duration_frames"]
    if local < 0 or local >= total:
        return

    word = spotlight["word"]
    anim = spotlight["animation"]
    color = spotlight["color"]
    font_size = 64
    font = _find_spotlight_font(word, font_size)

    bbox = draw.textbbox((0, 0), word, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = frame_w // 2, int(frame_h * 0.35)

    progress = local / max(total - 1, 1)

    if anim == "scale_up":
        scale = 1.0 + 0.5 * (1 - abs(progress - 0.5) * 2)
        current_size = int(font_size * scale)
        font = _find_spotlight_font(word, current_size)
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = cx - tw // 2, cy - th // 2 + int(math.sin(progress * math.pi * 2) * 5)

    elif anim == "scale_down":
        scale = 1.0 - 0.3 * (1 - abs(progress - 0.5) * 2)
        scale = max(0.5, scale)
        current_size = int(font_size * scale)
        font = _find_spotlight_font(word, current_size)
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = cx - tw // 2, cy - th // 2

    elif anim == "bounce_up":
        bounce_y = cy - abs(math.sin(progress * math.pi * 3)) * 30
        x, y = cx - tw // 2, bounce_y - th // 2

    elif anim == "shake":
        shake_x = math.sin(progress * math.pi * 8) * 10
        x, y = cx - tw // 2 + int(shake_x), cy - th // 2

    elif anim == "float":
        float_y = math.sin(progress * math.pi * 2) * 15
        x, y = cx - tw // 2, cy - th // 2 + int(float_y)

    elif anim == "float_up":
        up_y = -progress * 40
        alpha = int(255 * (1 - progress * 0.5))
        x, y = cx - tw // 2, cy - th // 2 + int(up_y)
        color = tuple(min(255, c) for c in color[:3]) + (alpha,)

    elif anim == "wave_text":
        wave_y = math.sin(progress * math.pi * 4 + cx * 0.05) * 12
        x, y = cx - tw // 2, cy - th // 2 + int(wave_y)

    elif anim == "spin_text":
        x, y = cx - tw // 2, cy - th // 2

    elif anim == "pulse":
        pulse = 1.0 + 0.15 * math.sin(progress * math.pi * 4)
        current_size = int(font_size * pulse)
        font = _find_spotlight_font(word, current_size)
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = cx - tw // 2, cy - th // 2

    elif anim == "fade_tint":
        tint_alpha = int(100 * (1 - abs(progress - 0.5) * 2))
        x, y = cx - tw // 2, cy - th // 2
        draw.rectangle([x - 10, y - 10, x + tw + 10, y + th + 10],
                       fill=(color[0], color[1], color[2], tint_alpha))

    elif anim == "twinkle_text":
        alpha = int(180 + 75 * math.sin(progress * math.pi * 6))
        color = tuple(min(255, c) for c in color[:3]) + (alpha,)
        x, y = cx - tw // 2, cy - th // 2

    elif anim == "grow_text":
        grow_progress = min(1.0, progress * 3)
        current_size = int(font_size * (0.3 + 0.7 * grow_progress))
        font = _find_spotlight_font(word, current_size)
        bbox = draw.textbbox((0, 0), word, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = cx - tw // 2, cy - th // 2

    elif anim == "color_flash":
        hue_shift = int(255 * (0.5 + 0.5 * math.sin(progress * math.pi * 4)))
        flash_color = (min(255, color[0] + hue_shift // 4),
                       min(255, color[1] + (255 - hue_shift) // 4),
                       min(255, color[2] + hue_shift // 3))
        color = flash_color
        x, y = cx - tw // 2, cy - th // 2

    else:
        x, y = cx - tw // 2, cy - th // 2

    outline_color = (0, 0, 0)
    for ox in (-3, 0, 3):
        for oy in (-3, 0, 3):
            if ox == 0 and oy == 0:
                continue
            draw.text((x + ox, y + oy), word, font=font, fill=outline_color)
    draw.text((x, y), word, font=font, fill=color)
