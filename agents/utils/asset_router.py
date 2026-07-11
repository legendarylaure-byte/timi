import os
import random
import logging
from PIL import Image, ImageDraw
from datetime import datetime

from utils.manim_renderer import render_manim_scene, compose_manim_block
from utils.screen_capture import render_terminal, render_ide, render_browser, render_code_snippet
from utils.stock_video import search_videos_for_scenes as _search_stock
from models import get_video_model

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "asset_router")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE = {}

MAX_STOCK_FOOTAGE_RATIO = 0.6


def _generate_static_image(description: str, keyword: str = "", width: int = 1920, height: int = 1080) -> str:
    from PIL import ImageFont
    bg = "#1e1e1e"
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    accent = (0, 204, 204)
    title_text = (keyword or description or "AI Explained").strip()
    if len(title_text) > 60:
        title_text = title_text[:57] + "..."
    font_size = 64
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), title_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (width - tw) // 2
    y = (height - th) // 2
    for dx, dy in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
        draw.text((x + dx, y + dy), title_text, fill=(0, 0, 0), font=font)
    draw.text((x, y), title_text, fill=(255, 255, 255), font=font)
    stripe_y = y + th + 24
    stripe_w = min(tw + 120, width - 80)
    stripe_x = (width - stripe_w) // 2
    draw.rectangle([stripe_x, stripe_y, stripe_x + stripe_w, stripe_y + 4], fill=accent)
    subtitle_text = "Vyom Ai Cloud"
    sub_font_size = 28
    try:
        sub_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sub_font_size)
    except (OSError, IOError):
        sub_font = ImageFont.load_default()
    sub_bbox = draw.textbbox((0, 0), subtitle_text, font=sub_font)
    sub_tw = sub_bbox[2] - sub_bbox[0]
    sub_x = (width - sub_tw) // 2
    sub_y = stripe_y + 16
    draw.text((sub_x, sub_y), subtitle_text, fill=(180, 180, 180), font=sub_font)
    corner_size = 6
    draw.ellipse([60, 60, 60 + corner_size * 2, 60 + corner_size * 2], fill=accent)
    draw.ellipse([width - 60 - corner_size * 2, 60, width - 60, 60 + corner_size * 2], fill=accent)
    draw.ellipse([60, height - 60 - corner_size * 2, 60 + corner_size * 2, height - 60], fill=accent)
    draw.ellipse([width - 60 - corner_size * 2, height - 60 - corner_size * 2, width - 60, height - 60], fill=accent)
    filename = f"static_{keyword or description}_{hash(description) % 10000:04d}.png"
    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path)
    return path


def _enforce_asset_diversity(scenes: list[dict]) -> list[dict]:
    stock_count = sum(1 for s in scenes if s.get("asset_type", "STOCK_FOOTAGE") == "STOCK_FOOTAGE")
    total = len(scenes)
    if total < 3 or stock_count / total <= MAX_STOCK_FOOTAGE_RATIO:
        return scenes
    overage = stock_count - int(total * MAX_STOCK_FOOTAGE_RATIO)
    alternatives = ["DIAGRAM_ANIMATION", "SCREEN_CAPTURE", "CODE_SNIPPET", "STATIC_IMAGE"]
    changed = 0
    for s in scenes:
        if s.get("asset_type", "STOCK_FOOTAGE") == "STOCK_FOOTAGE" and changed < overage:
            alt = random.choice(alternatives)
            s["asset_type"] = alt
            changed += 1
    return scenes


def _get_stock_clip(keyword: str, orientation: str = "landscape", duration: float = 8.0) -> str | None:
    cache_key = f"stock_{keyword}_{orientation}"
    if cache_key in CACHE:
        cached = CACHE[cache_key]
        if cached and os.path.exists(cached) and os.path.getsize(cached) > 1000:
            return cached
    try:
        scenes_input = [{"keyword": keyword, "target_duration": duration, "description": keyword}]
        clips = _search_stock(scenes_input, orientation=orientation)
        if clips and len(clips) > 0:
            result = clips[0].get("path")
            if result and os.path.getsize(result) > 1000:
                CACHE[cache_key] = result
                return result
            if result and os.path.exists(result):
                logger.warning(f"[AssetRouter] Stock clip too small or corrupt after download: {result}")
    except Exception as e:
        logger.warning(f"[AssetRouter] Stock search failed for '{keyword}': {e}")
    return None


def _render_scene_inner(scene: dict, video_id: str, scene_idx: int,
                        format_type: str, duration: float) -> dict | None:
    render_type = scene.get("render_type", "stock")
    asset_type = scene.get("asset_type", "STOCK_FOOTAGE")
    orientation = "portrait" if format_type == "shorts" else "landscape"
    kw = scene.get("keyword", "technology")
    description = scene.get("description", "")
    kw_list = scene.get("asset_keywords", [kw])
    if isinstance(kw_list, list):
        kw_list = kw_list
    else:
        kw_list = [kw_list]

    if render_type == "manim":
        path = render_manim_scene(scene, video_id, scene_idx)
        if path:
            return {"path": path, "duration": duration, "asset_type": "DIAGRAM_ANIMATION", "source": "manim"}
        logger.warning(f"[AssetRouter] Manim not available for scene {scene_idx}, falling back to stock")

    if render_type == "code" or asset_type in ("CODE_SNIPPET", "SCREEN_CAPTURE"):
        code = description.split("\n") if description else ["# code example", f"# {kw}"]
        path = render_code_snippet(code, width=1920, height=1080)
        if path:
            return {"path": path, "duration": duration, "asset_type": "CODE_SNIPPET", "source": "code_snippet"}

    if asset_type == "STATIC_IMAGE":
        path = _generate_static_image(description, kw)
        if path:
            return {"path": path, "duration": duration, "asset_type": "STATIC_IMAGE", "source": "static_image"}

    model = get_video_model()
    if model and model.is_available():
        prompt = scene.get("ltx_prompt", "") or description or ", ".join(kw_list)
        clip_path = model.generate_clip(prompt, int(duration))
        if clip_path:
            return {"path": clip_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
    for k in kw_list:
        path = _get_stock_clip(k, orientation, duration)
        if path and os.path.exists(path):
            return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    fallback = _get_stock_clip("technology", orientation, duration)
    if fallback and os.path.exists(fallback):
        return {"path": fallback, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    return None


def dispatch_scene(scene: dict, video_id: str, scene_idx: int = 0,
                   format_type: str = "long") -> dict | None:
    from utils.video_qa import check_corruption

    scene.setdefault("asset_keywords", [scene.get("keyword", "technology")])
    duration = scene.get("target_duration", scene.get("duration", 8.0))
    source = None

    for attempt in range(2):
        result = _render_scene_inner(scene, video_id, scene_idx, format_type, duration)
        if not result or not os.path.exists(result["path"]):
            continue
        if attempt == 1:
            return result
        qa = check_corruption(result["path"])
        if not qa["is_corrupt"]:
            return result
        logger.warning(
            f"[AssetRouter] Scene {scene_idx} QA failed (attempt {attempt + 1}): "
            f"{qa['decode_errors']} decode errors — retrying"
        )
        if source is None:
            source = result["source"]
        scene["render_type"] = "stock"
        scene.pop("ltx_prompt", None)
        duration = max(duration * 1.1, duration + 1.0)

    if result and os.path.exists(result["path"]):
        return result
    static = _generate_static_image(scene.get("description", ""),
                                     scene.get("keyword", "technology"))
    if static:
        return {"path": static, "duration": duration, "asset_type": "STATIC_IMAGE", "source": "static_image"}
    return None


def dispatch_scenes(scenes: list[dict], video_id: str, format_type: str = "long") -> list[dict]:
    scenes = _enforce_asset_diversity(scenes)
    clips_map = {}
    manim_scenes = []
    ltx_batch = []

    model = get_video_model()
    use_ltx = model and model.is_available()

    for idx, scene in enumerate(scenes):
        rt = scene.get("render_type", "stock")
        if rt == "manim" or scene.get("asset_type") == "DIAGRAM_ANIMATION":
            manim_scenes.append(scene)
        elif rt == "stock" and use_ltx:
            ltx_batch.append((idx, scene))
        else:
            result = dispatch_scene(scene, video_id, idx, format_type)
            if result:
                clips_map[idx] = result

    if ltx_batch and use_ltx:
        ltx_scenes = [s for _, s in ltx_batch]
        paths = model.generate_clips(ltx_scenes, video_id, format_type)
        for (idx, scene), path in zip(ltx_batch, paths):
            if path and os.path.exists(path):
                dur = scene.get("target_duration", scene.get("duration", 8.0))
                clips_map[idx] = {"path": path, "duration": dur, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
            else:
                result = dispatch_scene(scene, video_id, idx, format_type)
                if result:
                    clips_map[idx] = result

    clips = [clips_map[i] for i in range(len(scenes)) if i in clips_map]

    if manim_scenes:
        manim_path = compose_manim_block(manim_scenes, video_id, quality="h")
        if manim_path:
            total_dur = sum(s.get("duration", s.get("target_duration", 8.0)) for s in manim_scenes)
            manim_idx = next(
                (i for i, s in enumerate(scenes) if s.get("render_type") == "manim" or s.get("asset_type") == "DIAGRAM_ANIMATION"),
                len(clips)
            )
            insert_pos = min(manim_idx, len(clips))
            clips.insert(insert_pos, {"path": manim_path, "duration": total_dur, "asset_type": "DIAGRAM_ANIMATION", "source": "manim_block"})
        else:
            logger.warning(f"[AssetRouter] compose_manim_block failed, rendering {len(manim_scenes)} scenes individually")
            for ms in manim_scenes:
                ms_idx = next(i for i, s in enumerate(scenes) if s is ms)
                result = dispatch_scene(ms, video_id, ms_idx, format_type)
                if result:
                    clips_map[ms_idx] = result
            clips = [clips_map[i] for i in range(len(scenes)) if i in clips_map]

    return clips
