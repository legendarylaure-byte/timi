import os
import logging
from datetime import datetime

from utils.manim_renderer import render_manim_scene, compose_manim_block
from utils.screen_capture import render_terminal, render_ide, render_browser, render_code_snippet
from utils.stock_video import search_videos_for_scenes as _search_stock
from utils import ltx_engine

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "asset_router")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE = {}


def _get_stock_clip(keyword: str, orientation: str = "landscape", duration: float = 8.0) -> str | None:
    cache_key = f"stock_{keyword}_{orientation}"
    if cache_key in CACHE:
        return CACHE[cache_key]
    try:
        scenes_input = [{"keyword": keyword, "target_duration": duration, "description": keyword}]
        clips = _search_stock(scenes_input, orientation=orientation)
        if clips and len(clips) > 0:
            result = clips[0].get("path")
            CACHE[cache_key] = result
            return result
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

    if asset_type == "DIAGRAM_ANIMATION":
        path = render_manim_scene(scene, video_id, scene_idx, quality="h")
        if path:
            return {"path": path, "duration": duration, "asset_type": "DIAGRAM_ANIMATION", "source": "manim"}

    if asset_type == "CODE_SNIPPET":
        code_lines = scene.get("code_lines", [
            "# Example code",
            "import torch",
            "import torch.nn as nn",
            "",
            "class Transformer(nn.Module):",
            "    def __init__(self):",
            "        super().__init__()",
            f"    # {description[:50] if description else 'TODO'}",
        ])
        path = render_code_snippet(code_lines)
        if path:
            return {"path": path, "duration": min(duration, 10.0), "asset_type": "CODE_SNIPPET", "source": "screencap"}

    if asset_type == "SCREEN_CAPTURE":
        cap_type = scene.get("capture_type", "terminal")
        code_lines = scene.get("code_lines", [
            "$ python3 train.py --model transformer --epochs 100",
            "Epoch 1/100: loss=2.345, acc=0.723",
            "Epoch 2/100: loss=1.876, acc=0.812",
            "Epoch 3/100: loss=1.543, acc=0.867",
            f"# {description[:50] if description else 'Training in progress'}",
        ])
        title = scene.get("title", scene.get("keyword", "capture"))
        if cap_type == "browser":
            path = render_browser(url=scene.get("url", "https://example.com"))
        elif cap_type == "ide":
            path = render_ide(code_lines, title=title)
        else:
            path = render_terminal(code_lines, title=title)
        if path:
            return {"path": path, "duration": min(duration, 10.0), "asset_type": "SCREEN_CAPTURE", "source": "screencap"}

    stock_kw = keywords[0] if isinstance(keywords, list) else keywords
    if ltx_engine.is_available():
        prompt = description or stock_kw
        ltx_path = ltx_engine.generate_clip(prompt, int(duration))
        if ltx_path:
            return {"path": ltx_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
    path = _get_stock_clip(stock_kw, orientation, duration)
    if path:
        return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    fallback = _get_stock_clip("technology", orientation, duration)
    if fallback:
        return {"path": fallback, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    return None


def dispatch_scenes(scenes: list[dict], video_id: str, format_type: str = "long") -> list[dict]:
    clips = []
    manim_scenes = []
    for idx, scene in enumerate(scenes):
        if scene.get("asset_type") == "DIAGRAM_ANIMATION":
            manim_scenes.append(scene)
            continue
        result = dispatch_scene(scene, video_id, idx, format_type)
        if result:
            clips.append(result)

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
