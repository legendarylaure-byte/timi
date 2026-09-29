import os
import random
import uuid
import tempfile
import logging
from PIL import Image, ImageDraw
from datetime import datetime

from utils.screen_capture import render_terminal, render_ide, render_browser, render_code_snippet
from utils.stock_video import search_videos_for_scenes as _search_stock
from utils.concurrent_pipeline import run_with_gpu_lock
from models import get_video_model
from utils.brand_palette import LICORICE, PURPLE, hex_to_rgb

logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "asset_router")
os.makedirs(OUTPUT_DIR, exist_ok=True)

CACHE = {}

MAX_STOCK_FOOTAGE_RATIO = 0.6


def _build_ltx_prompt(scene: dict, visual: str) -> str:
    """The one place an LTX prompt is assembled.

    Both the render path and the narration-match gate MUST call this. The gate
    exists to avoid wasting a ~20 minute LTX render, so if it validates a
    different prompt than the one actually rendered it is checking the wrong
    thing. These two sites used to duplicate the logic inline, which is the same
    class of bug as the D34 hook salt: add a brand phrase to one and the gate
    silently stops matching the render.

    The brand accent phrase goes here because this is the only point where the
    model is told what colour to light the scene with. Brand colour applied as
    an overlay later reads as an overlay; asked for here it reads as produced by.
    """
    from utils.visual_profiles import brand_lighting_phrase

    base = visual[:500].strip()
    lighting = brand_lighting_phrase(scene.get("category", "") or "")
    if lighting and lighting.lower() not in base.lower():
        base = f"{base}, {lighting}"
    narration = scene.get("narration_text", "") or ""
    if narration:
        return f"{base} -- narration context: {narration[:150].strip()}"
    return base


def _generate_static_image(description: str, keyword: str = "", width: int = 1920, height: int = 1080, video_id: str = "", scene_idx: int = 0) -> str:
    from PIL import ImageFont
    bg = LICORICE
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    accent = hex_to_rgb(PURPLE)
    title_text = (keyword or description or "AI Explained").strip()
    if len(title_text) > 60:
        title_text = title_text[:57] + "..."
    font_size = 64
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except (OSError, IOError):
        # This used to be a second try of the *same* path, so the fallback could
        # never differ from the primary. ponytail: DejaVu is a container path --
        # off-container this lands on the bitmap default and the card renders
        # near-empty (measured: 99.88% background). The container is the render
        # target, so that is a host-preview limit, not a pipeline fault.
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
        sub_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", sub_font_size)
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
    alternatives = ["STATIC_IMAGE", "SCREEN_CAPTURE", "CODE_SNIPPET"]
    changed = 0
    for s in scenes:
        if s.get("asset_type", "STOCK_FOOTAGE") == "STOCK_FOOTAGE" and changed < overage:
            alt = random.choice(alternatives)
            s["asset_type"] = alt
            changed += 1
    return scenes


def _get_stock_clip(keyword: str, orientation: str = "landscape", duration: float = 8.0, video_id: str = "") -> str | None:
    # Cache key includes video_id: keying on the keyword alone made every video with
    # the same keyword reuse the exact same clip within one process.
    cache_key = f"stock_{video_id}_{keyword}_{orientation}"
    if cache_key in CACHE:
        cached = CACHE[cache_key]
        if cached and os.path.exists(cached) and os.path.getsize(cached) > 1000:
            return cached
    try:
        scenes_input = [{"keyword": keyword, "target_duration": duration, "description": keyword}]
        clips = _search_stock(scenes_input, orientation=orientation, video_id=video_id)
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
    # Plumbing keywords ("intro", "channel_brand") are not searchable content.
    # Dropped here because this list feeds both the stock search and, further
    # down, the LTX prompt fallback in dispatch_scene -- one filter, both paths.
    from utils.scene_parser import clean_scene_keywords
    kw_list = clean_scene_keywords(scene.get("asset_keywords", [kw])) or clean_scene_keywords([kw]) or ["technology"]
    if isinstance(kw_list, str):
        kw_list = [kw_list]

    if render_type == "code" or asset_type in ("CODE_SNIPPET", "SCREEN_CAPTURE"):
        code = description.split("\n") if description else ["# code example", f"# {kw}"]
        path = render_code_snippet(code, width=1920, height=1080)
        if path:
            logger.info(f"[AssetRouter] Scene {scene_idx}: code snippet OK")
            return {"path": path, "duration": duration, "asset_type": "CODE_SNIPPET", "source": "code_snippet"}

    model = get_video_model()
    if model and model.is_available():
        visual = scene.get("ltx_prompt", "") or description or ", ".join(kw_list)
        prompt = _build_ltx_prompt(scene, visual)
        clip_path = run_with_gpu_lock(model.generate_clip, prompt, int(duration),
                                      format_type=format_type, timeout=3600,
                                      seed=abs(hash(f"{video_id}_{scene_idx}")) % (2**31 - 1))
        if clip_path:
            logger.info(f"[AssetRouter] Scene {scene_idx}: LTX OK ({os.path.basename(clip_path)})")
            return {"path": clip_path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}

    if os.getenv("ENABLE_STOCK_FOOTAGE", "true").lower() == "true":
        search_query = ", ".join(kw_list) or description
        path = _get_stock_clip(search_query, orientation, duration, video_id=video_id)
        if path and os.path.exists(path):
            logger.info(f"[AssetRouter] Scene {scene_idx}: stock OK (query={search_query[:60]})")
            return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
        for k in kw_list:
            path = _get_stock_clip(k, orientation, duration, video_id=video_id)
            if path and os.path.exists(path):
                logger.info(f"[AssetRouter] Scene {scene_idx}: stock OK (keyword={k})")
                return {"path": path, "duration": duration, "asset_type": "STOCK_FOOTAGE", "source": "stock"}
    logger.warning(f"[AssetRouter] Scene {scene_idx}: ALL render methods exhausted "
                   f"(render_type={render_type}, asset_type={asset_type}, keywords={kw_list})")
    return None


def dispatch_scene(scene: dict, video_id: str, scene_idx: int = 0,
                   format_type: str = "long", category: str = "") -> dict | None:
    from utils.video_qa import check_corruption, check_visual_narration_match

    scene.setdefault("asset_keywords", [scene.get("keyword", "technology")])
    # Keep the plumbing out of the stored scene too, not just the local copy:
    # this list is read again by the narration-match gate below, and by the
    # LTX prompt fallback, so filtering only at the search site would leave the
    # words live everywhere else.
    from utils.scene_parser import clean_scene_keywords
    scene["asset_keywords"] = (
        clean_scene_keywords(scene["asset_keywords"])
        or clean_scene_keywords([scene.get("keyword", "technology")])
        or ["technology"]
    )
    duration = scene.get("target_duration", scene.get("duration", 8.0))
    orientation = "portrait" if format_type == "shorts" else "landscape"
    source = None

    # Build the exact prompt _render_scene_inner will use so the narration-match
    # gate checks the real prompt (visual-first, brand accent, narration as tail)
    # — otherwise a visual-first prompt fails the gate and wastes one full LTX
    # render on retry. Shared builder, not a copy: see _build_ltx_prompt.
    _visual = scene.get("ltx_prompt", "") or scene.get("description", "") or ", ".join(scene.get("asset_keywords", []))
    _built_prompt = _build_ltx_prompt(scene, _visual)

    for attempt in range(2):
        # Intro/outro go straight to the branded title card. They used to be
        # render_type="stock" with keywords like "subscribe"/"outro"/"channel_brand",
        # which meant the identical generic clip appeared in every single video.
        if scene.get("render_type") == "branded_card":
            img_w, img_h = (1080, 1920) if format_type == "shorts" else (1920, 1080)
            static = _generate_static_image(
                scene.get("description", ""), scene.get("keyword", "Vyom Ai Cloud"),
                width=img_w, height=img_h, video_id=video_id, scene_idx=scene_idx)
            if static and os.path.exists(static):
                return {"path": static, "duration": duration,
                        "asset_type": "STATIC_IMAGE", "source": "branded_card"}
            logger.warning(f"[AssetRouter] Scene {scene_idx}: branded card failed, falling through")

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
            ltx_prompt=_built_prompt,
        )
        if visual_match:
            return result
        logger.warning(
            f"[AssetRouter] Scene {scene_idx} visual-narration mismatch "
            f"(score={v_score:.2f}, {v_reason})"
        )
        if source is None:
            source = result["source"]
        if source == "ltx":
            narration = scene.get("narration_text", "")
            if narration:
                scene["narration_text"] = narration  # narration tail is already in _built_prompt
        else:
            scene["render_type"] = "stock"
            scene.pop("ltx_prompt", None)
        duration = max(duration * 1.1, duration + 1.0)

    if result and os.path.exists(result["path"]):
        return result
    logger.warning(f"[AssetRouter] Scene {scene_idx}: 2-attempt loop exhausted, "
                   f"trying stock footage one more time with full description")
    kw = scene.get("keyword", "technology")
    desc = scene.get("description", kw)
    stock_path = _get_stock_clip(desc, orientation, duration, video_id=video_id)
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


def describe_render_chain() -> list[tuple[str, str, str]]:
    """Describe which render backends are actually live, for the startup log.

    Returns [(component, status, remediation_if_degraded)]. The point is to make a
    silent degradation visible at boot rather than discovering it as "why does every
    video look like a slideshow" weeks later. A deliberately-off component (the paid
    cloud model) is reported as informational, not as a fault.
    """
    out = []

    try:
        model = get_video_model()
    except Exception:
        model = None
    if model is not None and getattr(model, "is_available", lambda: False)():
        out.append((f"ai_video[{model.name()}]", "on (PAID)", ""))
    else:
        out.append(("ai_video", "none (zero-cost)",
                    "intentional: LTX needs MLX (Apple-only) and the cloud model is "
                    "disabled; all visuals come from stock/code/branded-card"))

    out.append(("stock", "on", ""))
    out.append(("code_snippets", "on (PIL terminal/ide/browser panels)", ""))
    out.append(("branded_card", "on (last-resort floor)", ""))
    return out


def dispatch_scenes(scenes: list[dict], video_id: str, format_type: str = "long", category: str = "") -> list[dict]:
    clips_map = {}
    ltx_batch = []

    _enforce_asset_diversity(scenes)
    model = get_video_model()
    use_ltx = model and model.is_available()

    for idx, scene in enumerate(scenes):
        rt = scene.get("render_type", "stock")
        if rt == "stock" and use_ltx:
            ltx_batch.append((idx, scene))
        else:
            result = dispatch_scene(scene, video_id, idx, format_type, category)
            if result:
                clips_map[idx] = result

    # --- LTX batch ---
    if ltx_batch and use_ltx:
        ltx_scenes = [s for _, s in ltx_batch]
        paths = run_with_gpu_lock(model.generate_clips, ltx_scenes, video_id, format_type, timeout=3600)
        for (idx, scene), path in zip(ltx_batch, paths):
            if path and os.path.exists(path):
                dur = scene.get("target_duration", scene.get("duration", 8.0))
                clips_map[idx] = {"path": path, "duration": dur, "asset_type": "STOCK_FOOTAGE", "source": "ltx"}
            else:
                result = dispatch_scene(scene, video_id, idx, format_type, category)
                if result:
                    clips_map[idx] = result

    clips = [clips_map[i] for i in range(len(scenes)) if i in clips_map]

    succeeded = len(clips)
    total = len(scenes)
    logger.info(f"[AssetRouter] Scene dispatch complete: {succeeded}/{total} scenes resolved")
    if succeeded < total:
        missing = [i for i in range(total) if i not in clips_map]
        logger.warning(f"[AssetRouter] {total - succeeded} scenes unresolved: indices {missing}")
    return clips
