import os
import random
import logging
from PIL import Image, ImageDraw
from datetime import datetime

from utils.blender_renderer import render_blender_scene, render_blender_block
from utils.screen_capture import render_terminal, render_ide, render_browser, render_code_snippet
from utils.stock_video import search_videos_for_scenes as _search_stock
from models import get_video_model
from utils.scene_schema import DEEP_LESSON_CATS as _DEEP_LESSON_CATS

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "asset_router")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE = {}

MAX_STOCK_FOOTAGE_RATIO = 0.6


def _generate_static_image(description: str, keyword: str = "", width: int = 1920, height: int = 1080, video_id: str = "", scene_idx: int = 0) -> str:
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
    filename = f"static_{video_id}_{scene_idx:03d}.png"
    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path)
    return path


def _enforce_asset_diversity(scenes: list[dict]) -> list[dict]:
    stock_count = sum(1 for s in scenes if s.get("asset_type", "STOCK_FOOTAGE") == "STOCK_FOOTAGE")
    total = len(scenes)
    if total < 3 or stock_count / total <= MAX_STOCK_FOOTAGE_RATIO:
        return scenes
    overage = stock_count - int(total * MAX_STOCK_FOOTAGE_RATIO)
    alternatives = ["DIAGRAM_ANIMATION", "SCREEN_CAPTURE", "CODE_SNIPPET"]
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

    if render_type == "blender":
        path = render_blender_scene(scene, video_id, scene_idx, format_type)
        if path:
            logger.info(f"[AssetRouter] Scene {scene_idx}: blender OK ({os.path.basename(path)})")
            return {"path": path, "duration": duration, "asset_type": "DIAGRAM_ANIMATION", "source": "blender"}
        logger.warning(f"[AssetRouter] Blender not available for scene {scene_idx}, falling back")

    if render_type == "code" or asset_type in ("CODE_SNIPPET", "SCREEN_CAPTURE"):
        code = description.split("\n") if description else ["# code example", f"# {kw}"]
        path = render_code_snippet(code, width=1920, height=1080)
        if path:
            logger.info(f"[AssetRouter] Scene {scene_idx}: code snippet OK")
            return {"path": path, "duration": duration, "asset_type": "CODE_SNIPPET", "source": "code_snippet"}

    if os.getenv("ENABLE_STOCK_FOOTAGE", "true").lower() == "true":
        search_query = description or ", ".join(kw_list)
        path = _get_stock_clip(search_query, orientation, duration)
        if path and os.path.exists(path):
            logger.info(f"[AssetRouter] Scene {scene_idx}: stock OK (query={search_query[:60]})")
            return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
        for k in kw_list:
            path = _get_stock_clip(k, orientation, duration)
            if path and os.path.exists(path):
                logger.info(f"[AssetRouter] Scene {scene_idx}: stock OK (keyword={k})")
                return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}

    model = get_video_model()
    if model and model.is_available():
        prompt = scene.get("ltx_prompt", "") or description or ", ".join(kw_list)
        clip_path = model.generate_clip(prompt, int(duration), format_type=format_type)
        if clip_path:
            logger.info(f"[AssetRouter] Scene {scene_idx}: LTX OK ({os.path.basename(clip_path)})")
            return {"path": clip_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
    logger.warning(f"[AssetRouter] Scene {scene_idx}: ALL render methods exhausted "
                   f"(render_type={render_type}, asset_type={asset_type}, keywords={kw_list})")
    return None


def dispatch_scene(scene: dict, video_id: str, scene_idx: int = 0,
                   format_type: str = "long", category: str = "") -> dict | None:
    from utils.video_qa import check_corruption, check_visual_narration_match

    scene.setdefault("asset_keywords", [scene.get("keyword", "technology")])
    _try_blender_for_scene(scene, category)
    duration = scene.get("target_duration", scene.get("duration", 8.0))
    source = None

    for attempt in range(2):
        result = _render_scene_inner(scene, video_id, scene_idx, format_type, duration)
        if not result or not os.path.exists(result["path"]):
            continue
        if attempt == 1:
            return result
        qa = check_corruption(result["path"])
        if qa["is_corrupt"]:
            logger.warning(
                f"[AssetRouter] Scene {scene_idx} QA failed (attempt {attempt + 1}): "
                f"{qa['decode_errors']} decode errors — retrying"
            )
            if source is None:
                source = result["source"]
            scene["render_type"] = "stock"
            scene.pop("ltx_prompt", None)
            duration = max(duration * 1.1, duration + 1.0)
            continue
        visual_match, v_score, v_reason = check_visual_narration_match(
            scene.get("narration_text", ""),
            scene_keywords=scene.get("asset_keywords"),
            asset_type=result.get("asset_type", "STOCK_FOOTAGE"),
            ltx_prompt=scene.get("ltx_prompt", ""),
        )
        if visual_match:
            return result
        logger.warning(
            f"[AssetRouter] Scene {scene_idx} visual-narration mismatch "
            f"(score={v_score:.2f}, {v_reason}) — forcing stock retry with full description"
        )
        if source is None:
            source = result["source"]
        scene["render_type"] = "stock"
        scene.pop("ltx_prompt", None)
        duration = max(duration * 1.1, duration + 1.0)

    if result and os.path.exists(result["path"]):
        return result
    logger.warning(f"[AssetRouter] Scene {scene_idx}: 2-attempt loop exhausted, "
                   f"trying stock footage one more time with full description")
    kw = scene.get("keyword", "technology")
    desc = scene.get("description", kw)
    stock_path = _get_stock_clip(desc, orientation, duration)
    if stock_path and os.path.exists(stock_path):
        logger.info(f"[AssetRouter] Scene {scene_idx}: stock fallback OK (keyword={desc})")
        return {"path": stock_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    logger.warning(f"[AssetRouter] Scene {scene_idx}: all render+stock methods exhausted — "
                   f"generating branded title card as last resort")
    img_w, img_h = (1080, 1920) if format_type == "shorts" else (1920, 1080)
    static = _generate_static_image(scene.get("description", ""),
                                     scene.get("keyword", "technology"),
                                     width=img_w, height=img_h,
                                     video_id=video_id, scene_idx=scene_idx)
    if static:
        logger.info(f"[AssetRouter] Scene {scene_idx}: branded title card fallback OK")
        return {"path": static, "duration": duration, "asset_type": "STATIC_IMAGE", "source": "static_image"}
    logger.warning(f"[AssetRouter] Scene {scene_idx} DROPPED — all methods exhausted "
                   f"(render_type={scene.get('render_type', '?')}, "
                   f"asset_type={scene.get('asset_type', '?')})")
    return None


def _try_blender_for_scene(scene: dict, category: str = "") -> bool:
    """Check if a Blender template can handle this scene based on keyword matching.

    Any category can use Blender — the template keyword system decides.
    Returns True if scene was converted to render_type='blender'.
    """
    rt = scene.get("render_type", "stock")
    if rt == "blender":
        return True
    from blender_templates import TEMPLATE_KEYWORDS
    desc = (scene.get("description") or "") + " " + " ".join(scene.get("asset_keywords", []))
    desc_lower = desc.lower()
    for tmpl_name, keywords in TEMPLATE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            scene["render_type"] = "blender"
            scene["asset_type"] = "DIAGRAM_ANIMATION"
            logger.info(f"[AssetRouter] Routed scene to Blender template '{tmpl_name}'")
            return True
    return False


def dispatch_scenes(scenes: list[dict], video_id: str, format_type: str = "long", category: str = "") -> list[dict]:
    scenes = _enforce_asset_diversity(scenes)
    clips_map = {}
    blender_scenes = []
    ltx_batch = []

    model = get_video_model()
    use_ltx = model and model.is_available()

    for idx, scene in enumerate(scenes):
        rt = scene.get("render_type", "stock")
        if rt == "blender" or scene.get("asset_type") == "DIAGRAM_ANIMATION":
            if category not in _DEEP_LESSON_CATS:
                scene["render_type"] = "stock"
                scene.pop("asset_type", None)
                result = dispatch_scene(scene, video_id, idx, format_type, category)
                if result:
                    clips_map[idx] = result
            else:
                blender_scenes.append(scene)
        elif rt == "stock" and use_ltx:
            if _try_blender_for_scene(scene, category):
                blender_scenes.append(scene)
            else:
                ltx_batch.append((idx, scene))
        else:
            if _try_blender_for_scene(scene, category):
                blender_scenes.append(scene)
            else:
                result = dispatch_scene(scene, video_id, idx, format_type, category)
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
                result = dispatch_scene(scene, video_id, idx, format_type, category)
                if result:
                    clips_map[idx] = result

    clips = [clips_map[i] for i in range(len(scenes)) if i in clips_map]

    if blender_scenes:
        individual_success = 0
        for bs in blender_scenes:
            bs_idx = next(i for i, s in enumerate(scenes) if s is bs)
            result = dispatch_scene(bs, video_id, bs_idx, format_type, category)
            if result:
                clips_map[bs_idx] = result
                individual_success += 1

        if individual_success < len(blender_scenes) * 0.3:
            failed_scenes = [
                bs for bs in blender_scenes
                if next(i for i, s in enumerate(scenes) if s is bs) not in clips_map
            ]
            logger.warning(
                f"[AssetRouter] Only {individual_success}/{len(blender_scenes)} Blender scenes rendered individually, "
                f"trying render_blender_block for {len(failed_scenes)} remaining"
            )
            blender_path = render_blender_block(failed_scenes, video_id, format_type)
            if blender_path:
                total_dur = sum(s.get("duration", s.get("target_duration", 8.0)) for s in failed_scenes)
                insert_pos = min(
                    (next(i for i, s in enumerate(scenes) if s is bs) for bs in failed_scenes),
                    default=len(clips)
                )
                clips.insert(insert_pos, {"path": blender_path, "duration": total_dur,
                             "asset_type": "DIAGRAM_ANIMATION", "source": "blender_block"})
            else:
                img_w, img_h = (1080, 1920) if format_type == "shorts" else (1920, 1080)
                for bs in failed_scenes:
                    bs_idx = next(i for i, s in enumerate(scenes) if s is bs)
                    bs_desc = bs.get("description", bs.get("keyword", "technology"))
                    bs_orientation = "portrait" if format_type == "shorts" else "landscape"
                    bs_dur = bs.get("target_duration", bs.get("duration", 8.0))
                    stock_path = _get_stock_clip(bs_desc, bs_orientation, bs_dur)
                    if stock_path and os.path.exists(stock_path):
                        clips_map[bs_idx] = {"path": stock_path, "duration": bs_dur,
                            "asset_type": "STOCK_FOOTAGE", "source": "stock"}
                    else:
                        static = _generate_static_image(
                            bs.get("description", ""), bs.get("keyword", "technology"),
                            width=img_w, height=img_h,
                            video_id=video_id, scene_idx=bs_idx)
                        if static:
                            clips_map[bs_idx] = {"path": static, "duration": bs_dur,
                                "asset_type": "STATIC_IMAGE", "source": "static_image"}
        else:
            logger.info(
                f"[AssetRouter] Rendered {individual_success}/{len(blender_scenes)} Blender scenes individually"
            )

        clips = [clips_map[i] for i in range(len(scenes)) if i in clips_map]

    succeeded = len(clips)
    total = len(scenes)
    logger.info(f"[AssetRouter] Scene dispatch complete: {succeeded}/{total} scenes resolved")
    if succeeded < total:
        missing = [i for i in range(total) if i not in clips_map]
        logger.warning(f"[AssetRouter] {total - succeeded} scenes unresolved: indices {missing}")
    return clips
