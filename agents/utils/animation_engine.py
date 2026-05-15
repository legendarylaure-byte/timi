import os
import math
import json
import subprocess
import random
from pathlib import Path
from collections import OrderedDict
from PIL import Image, ImageDraw, ImageFont

from utils.animation_math import ANIMATION_FUNCTIONS, none_anim
from utils.assets import get_asset_path, ensure_dirs

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
CHARACTERS_DIR = os.path.join(ASSETS_DIR, "characters")
BACKGROUNDS_DIR = os.path.join(ASSETS_DIR, "backgrounds")
EFFECTS_DIR = os.path.join(ASSETS_DIR, "effects")

FPS = 30
TEMP_DIR = Path(__file__).parent.parent / "tmp" / "animation"
OUTPUT_DIR = Path(__file__).parent.parent / "output"

BG_CACHE = {}
EFFECT_CACHE = {}

_LRU_MAX = 10
CHAR_CACHE = OrderedDict()

FRAME_SIZE = {
    "shorts": (1080, 1920),
    "long": (1920, 1080),
}

_PERF_WARN_THRESHOLD_MS = 50


def _load_background(name: str, format_type: str) -> Image.Image:
    cache_key = f"{name}_{format_type}"
    if cache_key in BG_CACHE:
        return BG_CACHE[cache_key].copy()

    orientation = "portrait" if format_type == "shorts" else "landscape"
    filename = f"{name}_{orientation}.png"
    path = get_asset_path("background", filename)
    if not path:
        path = os.path.join(BACKGROUNDS_DIR, filename)
    if not os.path.exists(path):
        path = os.path.join(BACKGROUNDS_DIR, f"gradient_sky_{orientation}.png")

    if os.path.exists(path):
        img = Image.open(path).convert("RGB")
    else:
        w, h = FRAME_SIZE[format_type]
        img = Image.new("RGB", (w, h), (135, 206, 235))

    BG_CACHE[cache_key] = img.copy()
    return img


def _load_character_sprite(
    char_name: str, pose: str = "idle", expression: str = "neutral", mouth: str = "closed"
) -> Image.Image:
    cache_key = f"{char_name}_{pose}_{expression}_{mouth}"
    if cache_key in CHAR_CACHE:
        CHAR_CACHE.move_to_end(cache_key)
        return CHAR_CACHE[cache_key].copy()

    char_dir = os.path.join(CHARACTERS_DIR, char_name)
    filename = f"{pose}_{expression}_{mouth}.png"
    path = os.path.join(char_dir, filename)

    if not os.path.exists(path):
        filename = f"{pose}_{expression}.png"
        path = os.path.join(char_dir, filename)
    if not os.path.exists(path):
        path = os.path.join(char_dir, "idle_neutral.png")

    if os.path.exists(path):
        img = Image.open(path).convert("RGBA")
    else:
        size = 256
        img = Image.new("RGBA", (size, size), (200, 200, 200, 200))
        draw = ImageDraw.Draw(img)
        draw.ellipse([20, 20, size - 20, size - 20], fill=(255, 200, 200, 255))

    CHAR_CACHE[cache_key] = img.copy()
    if len(CHAR_CACHE) > _LRU_MAX:
        CHAR_CACHE.popitem(last=False)
    return img


def _load_effect(name: str) -> Image.Image:
    if name in EFFECT_CACHE:
        return EFFECT_CACHE[name].copy()
    path = os.path.join(EFFECTS_DIR, f"{name}.png")
    if os.path.exists(path):
        img = Image.open(path).convert("RGBA")
        EFFECT_CACHE[name] = img.copy()
        return img
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    EFFECT_CACHE[name] = img.copy()
    return img


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
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


def _compute_character_transform(char_config: dict, frame_idx: int, total_frames: int, anim_params: dict) -> dict:
    anim_name = char_config.get("animation", "float")
    anim_fn = ANIMATION_FUNCTIONS.get(anim_name, none_anim)

    t = frame_idx / FPS

    if anim_name == "slide_in":
        result = anim_fn(t, total_frames, direction=anim_params.get("direction", "left"), duration_ratio=0.5)
    elif anim_name == "bounce":
        result = anim_fn(t, amplitude=anim_params.get("amplitude", 15), frequency=anim_params.get("frequency", 2.0))
    elif anim_name == "float":
        result = anim_fn(t, amplitude=anim_params.get("amplitude", 8), period=anim_params.get("period", 3.0))
    elif anim_name == "wave":
        result = anim_fn(t, max_angle=anim_params.get("max_angle", 25), frequency=anim_params.get("frequency", 2.5))
    elif anim_name == "grow":
        result = anim_fn(t, scale_min=anim_params.get("scale_min", 0.8),
                         scale_max=anim_params.get("scale_max", 1.15),
                         frequency=anim_params.get("frequency", 1.5))
    elif anim_name == "wiggle":
        result = anim_fn(t, amplitude=anim_params.get("amplitude", 5), frequency=anim_params.get("frequency", 4.0))
    else:
        result = anim_fn(t)

    return result


def _render_text(draw: ImageDraw, text_cfg: dict, frame_w: int, frame_h: int, frame_idx: int, total_frames: int):
    text = text_cfg.get("text", "")
    if not text:
        return

    style = text_cfg.get("style", "narration")
    position = text_cfg.get("position", "center")

    font_sizes = {"title": 72, "emphasis": 56, "dialogue": 48, "narration": 40}
    font_size = font_sizes.get(style, 40)

    colors = {"title": (255, 215, 0), "emphasis": (255, 105, 180),
              "dialogue": (255, 255, 255), "narration": (255, 255, 255)}
    color = colors.get(style, (255, 255, 255))

    positions = {
        "center": (frame_w // 2, frame_h // 2),
        "top": (frame_w // 2, int(frame_h * 0.15)),
        "bottom": (frame_w // 2, int(frame_h * 0.85)),
        "left": (int(frame_w * 0.15), frame_h // 2),
        "right": (int(frame_w * 0.85), frame_h // 2),
    }
    pos = positions.get(position, positions["center"])

    try:
        font = _find_font(font_size)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = len(text) * font_size * 0.6, font_size
        font = ImageFont.load_default()

    fade_in_frames = int(FPS * 0.3)
    alpha_factor = min(1.0, frame_idx / max(fade_in_frames, 1)) if style == "title" else 1.0
    if alpha_factor < 1.0:
        alpha = int(255 * alpha_factor)
        color = tuple(min(255, c) for c in color[:3]) + (alpha,)

    x = pos[0] - tw // 2
    y = pos[1] - th // 2

    if style == "title":
        y_offset = -abs(math.sin(frame_idx * 0.02)) * 8
        y += y_offset

    bar_pad = 12
    draw.rectangle([x - bar_pad, y - bar_pad, x + tw + bar_pad, y + th + bar_pad], fill=(0, 0, 0, 160))

    outline_color = (0, 0, 0)
    for ox in (-2, 0, 2):
        for oy in (-2, 0, 2):
            if ox == 0 and oy == 0:
                continue
            draw.text((x + ox, y + oy), text, font=font, fill=outline_color)

    draw.text((x, y), text, font=font, fill=color)


def _render_effects(draw: ImageDraw, effects: list, frame_w: int, frame_h: int, frame_idx: int):
    for effect in effects:
        if effect == "sparkle":
            sparkle = _load_effect("sparkle")
            for i in range(3):
                phase = frame_idx + i * 20
                sx = (frame_w * 0.2 + i * frame_w * 0.3 + math.sin(phase * 0.05) * 50)
                sy = (frame_h * 0.2 + math.cos(phase * 0.07 + i) * 60)
                alpha = int(180 + 75 * math.sin(phase * 0.1))
                s = sparkle.copy()
                alpha_layer = s.split()[3].point(lambda x: min(x, alpha))
                s.putalpha(alpha_layer)
                draw.bitmap((int(sx), int(sy)), s)

        elif effect == "star_rain":
            star = _load_effect("star")
            for i in range(5):
                phase = frame_idx + i * 30
                sx = (frame_w * 0.1 + i * frame_w * 0.2 + math.sin(phase * 0.03) * 30)
                sy = ((phase * 3 + i * 200) % frame_h)
                alpha = max(0, 200 - int((sy / frame_h) * 150))
                s = star.copy()
                alpha_layer = s.split()[3].point(lambda x: min(x, alpha))
                s.putalpha(alpha_layer)
                draw.bitmap((int(sx), int(sy - 24)), s)

        elif effect == "rainbow_burst":
            burst = _load_effect("star_burst")
            for i in range(2):
                sx = frame_w * (0.3 + i * 0.4)
                sy = frame_h * 0.3
                alpha = int(100 + 80 * math.sin(frame_idx * 0.05 + i))
                b = burst.copy()
                alpha_layer = b.split()[3].point(lambda x: min(x, alpha))
                b.putalpha(alpha_layer)
                draw.bitmap((int(sx - 40), int(sy - 40)), b)

        elif effect == "fade_in":
            if frame_idx < FPS:
                alpha = int(255 * (1 - frame_idx / FPS))
                draw.rectangle([0, 0, frame_w, frame_h], fill=(0, 0, 0, alpha))

        elif effect == "fade_out":
            if frame_idx > 0:
                pass


def _is_speaking(frame_time_ms: float, phrase_timings: list) -> bool:
    if not phrase_timings:
        return False
    for pt in phrase_timings:
        if pt["start_ms"] <= frame_time_ms <= pt["end_ms"]:
            return True
    return False


def _lip_mouth_state(frame_time_ms: float, phrase_timings: list) -> str:
    if not _is_speaking(frame_time_ms, phrase_timings):
        return "closed"
    t_sec = frame_time_ms / 1000.0
    cycle_pos = math.sin(t_sec * 2 * math.pi * 6)
    if cycle_pos > 0.3:
        return "open"
    elif cycle_pos > -0.3:
        return "half"
    return "closed"


def _should_blink(char_blink_state: dict, frame_idx: int) -> bool:
    blink_frame = char_blink_state.get("blink_frame", -1)
    blink_frames = char_blink_state.get("blink_frames", 0)
    if blink_frame >= 0 and frame_idx < blink_frame + blink_frames:
        return True
    if frame_idx >= char_blink_state.get("next_blink", 0):
        char_blink_state["blink_frames"] = random.randint(2, 4)
        char_blink_state["blink_frame"] = frame_idx
        char_blink_state["next_blink"] = frame_idx + random.randint(90, 120)
        return True
    return False


def render_scenes(scene_configs: list[dict], voice_path: str = None, music_path: str = None,
                  video_id: str = "animation", format_type: str = "shorts",
                  phrase_timings: list = None) -> str | None:
    ensure_dirs()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    w, h = FRAME_SIZE.get(format_type, (1080, 1920))

    with open(os.path.join(ASSETS_DIR, "characters.json")) as f:
        characters_config = json.load(f)

    frames_dir = TEMP_DIR / f"frames_{video_id}"
    frames_dir.mkdir(parents=True, exist_ok=True)

    global_frame = 0
    scene_frame_offset = 0
    _blink_states = {}

    for si, scene in enumerate(scene_configs):
        duration = scene.get("duration", 5)
        scene_frames = int(duration * FPS)
        background_name = scene.get("background", "gradient_sky")
        characters = scene.get("characters", [])
        text_overlays = scene.get("text", [])
        effects = scene.get("effects", [])
        transition = scene.get("transition", "cut")
        camera = scene.get("camera", {})

        bg_img = _load_background(background_name, format_type)
        if bg_img.size != (w, h):
            bg_img = bg_img.resize((w, h), Image.LANCZOS)

        for fi in range(scene_frames):
            frame = bg_img.copy()
            draw = ImageDraw.Draw(frame, "RGBA")

            zoom = camera.get("zoom", 1.0)
            pan_x = camera.get("pan_x", 0)
            pan_y = camera.get("pan_y", 0)
            if zoom != 1.0:
                nw, nh = int(w / zoom), int(h / zoom)
                cx_src = int(w / 2 - nw / 2 + pan_x * fi)
                cy_src = int(h / 2 - nh / 2 + pan_y * fi)
                cx_src = max(0, min(cx_src, w - nw))
                cy_src = max(0, min(cy_src, h - nh))
                if nw > 0 and nh > 0:
                    cropped = frame.crop((cx_src, cy_src, cx_src + nw, cy_src + nh))
                    frame = cropped.resize((w, h), Image.LANCZOS)
                    draw = ImageDraw.Draw(frame, "RGBA")

            for char_cfg in characters:
                char_name = char_cfg.get("name", "pixel")
                pose = char_cfg.get("pose", "idle")
                expression = char_cfg.get("expression", "neutral")

                global_frame_time_ms = (scene_frame_offset + fi) / FPS * 1000.0
                mouth = _lip_mouth_state(global_frame_time_ms, phrase_timings) if phrase_timings else "closed"

                char_key = f"{char_name}_{char_cfg.get('x', 0.5)}_{char_cfg.get('y', 0.55)}"
                if char_key not in _blink_states:
                    _blink_states[char_key] = {"next_blink": random.randint(90, 120)}
                cbs = _blink_states[char_key]
                if _should_blink(cbs, global_frame):
                    expression = "sleep"
                    mouth = "closed"

                sprite = _load_character_sprite(char_name, pose, expression, mouth)

                char_def = characters_config.get(char_name, {})
                anim_params = char_def.get("animations", {}).get(char_cfg.get("animation", "float"), {})

                transform = _compute_character_transform(char_cfg, fi, scene_frames, anim_params)

                norm_x = char_cfg.get("x", 0.5)
                norm_y = char_cfg.get("y", 0.55)
                base_x = int(norm_x * w)
                base_y = int(norm_y * h)

                scale = char_def.get("size_default", 1.0)
                sprite_w = sprite.width
                sprite_h = sprite.height
                new_w = max(1, int(sprite_w * scale * transform["scale_x"]))
                new_h = max(1, int(sprite_h * scale * transform["scale_y"]))
                resized = sprite.resize((new_w, new_h), Image.LANCZOS)

                rot = transform.get("rotation", 0)
                if rot != 0:
                    resized = resized.rotate(rot, expand=True, resample=Image.BICUBIC)

                rx = base_x + int(transform.get("x", 0)) - resized.width // 2
                ry = base_y + int(transform.get("y", 0)) - resized.height // 2

                if 0 <= rx < w and 0 <= ry < h:
                    frame.paste(resized, (rx, ry), resized)

            for text_cfg in text_overlays:
                _render_text(draw, text_cfg, w, h, fi, scene_frames)

            for sl in scene.get("spotlights", []):
                from utils.text_animator import render_spotlight as _rs
                _rs(draw, sl, fi, w, h)

            for effect in effects:
                _render_effects(draw, effects, w, h, fi)

            if si > 0 and transition in ("fade", "dissolve") and fi < FPS:
                alpha = int(255 * (1 - (fi + 1) / FPS))
                draw.rectangle([0, 0, w, h], fill=(0, 0, 0, alpha))

            frame_path = frames_dir / f"frame_{global_frame:06d}.ppm"
            frame.save(frame_path, "PPM")
            global_frame += 1

        scene_frame_offset += scene_frames
        pct = (si + 1) / len(scene_configs) * 100
        print(f"[ANIMATION] Scene {si + 1}/{len(scene_configs)} rendered ({pct:.0f}%)")

    if global_frame == 0:
        print("[ANIMATION] No frames rendered")
        return None

    combined_video = str(TEMP_DIR / f"{video_id}_frames.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", str(frames_dir / "frame_%06d.ppm"),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2",
        combined_video,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"[ANIMATION] FFmpeg stitch error: {result.stderr[-300:]}")
            return None
    except Exception as e:
        print(f"[ANIMATION] FFmpeg stitch exception: {e}")
        return None

    if voice_path and os.path.exists(voice_path):
        mixed_audio = str(TEMP_DIR / f"{video_id}_audio.wav")
        try:
            from pydub import AudioSegment
            voice = AudioSegment.from_file(voice_path)
            if music_path and os.path.exists(music_path):
                music = AudioSegment.from_file(music_path)
                music = (music - 18) * (len(voice) // len(music) + 1)
                music = music[:len(voice)]
                mixed = voice.overlay(music)
            else:
                mixed = voice
            mixed.export(mixed_audio, format="wav")
        except Exception as e:
            print(f"[ANIMATION] Audio mix error: {e}")
            mixed_audio = voice_path

        final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
        cmd = [
            "ffmpeg", "-y",
            "-i", combined_video,
            "-i", mixed_audio,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            "-pix_fmt", "yuv420p",
            final_path,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and os.path.exists(final_path):
                print(f"[ANIMATION] Final video: {final_path}")
                import shutil
                shutil.rmtree(str(frames_dir), ignore_errors=True)
                return final_path
        except Exception as e:
            print(f"[ANIMATION] Final mux error: {e}")
            return None
    else:
        final_path = str(OUTPUT_DIR / f"{video_id}_{format_type}.mp4")
        import shutil
        shutil.move(combined_video, final_path)
        shutil.rmtree(str(frames_dir), ignore_errors=True)
        return final_path

    return None


def render_single_frame(scene_config: dict, format_type: str = "shorts") -> Image.Image:
    w, h = FRAME_SIZE.get(format_type, (1080, 1920))
    bg_name = scene_config.get("background", "gradient_sky")
    bg_img = _load_background(bg_name, format_type)
    if bg_img.size != (w, h):
        bg_img = bg_img.resize((w, h), Image.LANCZOS)

    frame = bg_img.copy()
    draw = ImageDraw.Draw(frame, "RGBA")

    for char_cfg in scene_config.get("characters", []):
        char_name = char_cfg.get("name", "pixel")
        pose = char_cfg.get("pose", "idle")
        expression = char_cfg.get("expression", "neutral")
        sprite = _load_character_sprite(char_name, pose, expression)

        norm_x = char_cfg.get("x", 0.5)
        norm_y = char_cfg.get("y", 0.55)
        base_x = int(norm_x * w)
        base_y = int(norm_y * h)

        rx = base_x - sprite.width // 2
        ry = base_y - sprite.height // 2
        frame.paste(sprite, (rx, ry), sprite)

    for text_cfg in scene_config.get("text", []):
        _render_text(draw, text_cfg, w, h, 0, 1)

    return frame
