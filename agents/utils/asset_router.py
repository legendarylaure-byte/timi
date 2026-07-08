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
    colors = ["#1a1a2e", "#16213e", "#0f3460", "#533483", "#2d3436", "#0c0c1d", "#1e272e", "#130f40"]
    bg = random.choice(colors)
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    accent = tuple(int(bg[i:i+2], 16) for i in (1, 3, 5))
    accent = tuple(min(c + 40, 255) for c in accent)
    for _ in range(random.randint(3, 6)):
        x1, y1 = random.randint(0, width), random.randint(0, height)
        x2, y2 = random.randint(0, width), random.randint(0, height)
        draw.ellipse([(x1, y1), (x2, y2)], outline=accent, width=random.randint(1, 3))
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


def dispatch_scene(scene: dict, video_id: str, scene_idx: int = 0, format_type: str = "long") -> dict | None:
    asset_type = scene.get("asset_type", "STOCK_FOOTAGE")
    orientation = "portrait" if format_type == "shorts" else "landscape"
    kw = scene.get("keyword", "technology")
    scene.setdefault("asset_keywords", [kw])
    keywords = scene["asset_keywords"]
    description = scene.get("description", "")
    duration = scene.get("target_duration", scene.get("duration", 8.0))

    kw_list = keywords if isinstance(keywords, list) else [keywords]

    if asset_type == "SCREEN_CAPTURE":
        code = description.split("\n") if description else [f"# {kw}"]
        path = render_terminal(code, title=f"scene_{scene_idx}.py", width=1920, height=1080)
        if path:
            return {"path": path, "duration": duration, "asset_type": "SCREEN_CAPTURE", "source": "screen_capture"}

    if asset_type == "CODE_SNIPPET":
        code = description.split("\n") if description else ["import ai", "ai.explain(kw)"]
        path = render_code_snippet(code, width=1920, height=1080)
        if path:
            return {"path": path, "duration": duration, "asset_type": "CODE_SNIPPET", "source": "code_snippet"}

    if asset_type == "STATIC_IMAGE":
        path = _generate_static_image(description, kw)
        if path:
            return {"path": path, "duration": duration, "asset_type": "STATIC_IMAGE", "source": "static_image"}

    if asset_type == "DIAGRAM_ANIMATION":
        path = render_manim_scene(scene, video_id)
        if path:
            return {"path": path, "duration": duration, "asset_type": "DIAGRAM_ANIMATION", "source": "manim"}

    model = get_video_model()
    if model and model.is_available():
        prompt = scene.get("ltx_prompt", "") or description or ", ".join(kw_list)
        clip_path = model.generate_clip(prompt, int(duration))
        if clip_path:
            return {"path": clip_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
    for kw in kw_list:
        path = _get_stock_clip(kw, orientation, duration)
        if path and os.path.exists(path):
            return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    fallback = _get_stock_clip("technology", orientation, duration)
    if fallback and os.path.exists(fallback):
        return {"path": fallback, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    return None


def dispatch_scenes(scenes: list[dict], video_id: str, format_type: str = "long") -> list[dict]:
    scenes = _enforce_asset_diversity(scenes)
    clips_map = {}
    manim_scenes = []
    ltx_batch = []

    model = get_video_model()
    use_ltx = model and model.is_available()

    for idx, scene in enumerate(scenes):
        if scene.get("asset_type") == "DIAGRAM_ANIMATION":
            manim_scenes.append(scene)
        elif use_ltx:
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
                (i for i, s in enumerate(scenes) if s.get("asset_type") == "DIAGRAM_ANIMATION"),
                len(clips)
            )
            insert_pos = min(manim_idx, len(clips))
            clips.insert(insert_pos, {"path": manim_path, "duration": total_dur, "asset_type": "DIAGRAM_ANIMATION", "source": "manim_block"})

    return clips
