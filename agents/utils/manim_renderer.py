import os
import hashlib
import json
import subprocess
import logging
from datetime import datetime

from utils.manim_templates import (
    neural_network_template,
    attention_template,
    transformer_block_template,
    algorithm_flow_template,
    bar_chart_template,
    text_reveal_template,
)

logger = logging.getLogger(__name__)

MANIM_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "manim_cache")
MANIM_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "manim_render")
os.makedirs(MANIM_CACHE_DIR, exist_ok=True)
os.makedirs(MANIM_OUTPUT_DIR, exist_ok=True)

MANIM_BIN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".venv", "bin", "manim")
if not os.path.exists(MANIM_BIN):
    MANIM_BIN = "manim"

TEMPLATE_MAP = {
    "neural_network": neural_network_template,
    "attention": attention_template,
    "transformer": transformer_block_template,
    "algorithm_flow": algorithm_flow_template,
    "bar_chart": bar_chart_template,
    "text_reveal": text_reveal_template,
}


def _scene_hash(scene: dict) -> str:
    key = json.dumps(scene, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cached_path(scene_hash: str) -> str | None:
    path = os.path.join(MANIM_CACHE_DIR, f"{scene_hash}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    return None


def _select_template(scene: dict) -> tuple[str, dict] | None:
    keywords = scene.get("asset_keywords", [])
    description = scene.get("description", "")
    text = (str(keywords) + " " + description).lower()

    theme_score = {}
    for tmpl_name in TEMPLATE_MAP:
        score = 0
        if tmpl_name == "neural_network":
            for kw in ["neural", "network", "layer", "deep learning", "mlp", "perceptron", "neuron"]:
                if kw in text:
                    score += 2
        elif tmpl_name == "attention":
            for kw in ["attention", "transformer", "qkv", "query", "key", "value", "self-attention"]:
                if kw in text:
                    score += 2
        elif tmpl_name == "transformer":
            for kw in ["transformer", "encoder", "decoder", "architecture", "block"]:
                if kw in text:
                    score += 2
        elif tmpl_name == "algorithm_flow":
            for kw in ["flow", "pipeline", "process", "step", "stage", "algorithm", "sequential"]:
                if kw in text:
                    score += 1
        elif tmpl_name == "bar_chart":
            for kw in ["chart", "graph", "comparison", "performance", "benchmark", "metric", "stat"]:
                if kw in text:
                    score += 1
        elif tmpl_name == "text_reveal":
            for kw in ["reveal", "insight", "key", "takeaway", "conclusion", "summary", "important"]:
                if kw in text:
                    score += 1
        if score > 0:
            theme_score[tmpl_name] = score

    if not theme_score:
        return None

    best = max(theme_score, key=theme_score.get)
    return best, {"title": scene.get("text", [{}])[0].get("text", "") if scene.get("text") else "Concept"}


def render_manim_scene(scene: dict, video_id: str, scene_idx: int = 0, quality: str = "h") -> str | None:
    s_hash = _scene_hash(scene)
    cached = _cached_path(s_hash)
    if cached:
        logger.info(f"[Manim] Using cached render: {cached}")
        return cached

    selection = _select_template(scene)
    if not selection:
        logger.info(f"[Manim] No matching template, fallback for scene {scene_idx}")
        return None

    tmpl_name, params = selection
    tmpl_fn = TEMPLATE_MAP[tmpl_name]

    title = params.get("title", "Concept")
    dur = scene.get("target_duration", scene.get("duration", 6.0))
    code = tmpl_fn(title=title, duration=dur)

    scene_class_name = {
        "neural_network": "NeuralNetworkScene",
        "attention": "AttentionScene",
        "transformer": "TransformerScene",
        "algorithm_flow": "AlgorithmFlowScene",
        "bar_chart": "BarChartScene",
        "text_reveal": "TextRevealScene",
    }.get(tmpl_name, "Scene")

    py_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.py")
    output_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.mp4")
    with open(py_path, "w") as f:
        f.write(code)

    quality_flag = f"-q{quality}"

    try:
        result = subprocess.run(
            [MANIM_BIN, quality_flag, "--format=mp4", "-o", output_path, py_path, scene_class_name],
            capture_output=True, text=True, timeout=120,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            shutil_path = os.path.join(MANIM_CACHE_DIR, f"{s_hash}.mp4")
            import shutil
            shutil.copy2(output_path, shutil_path)
            logger.info(f"[Manim] Rendered {tmpl_name} -> {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
        else:
            logger.warning(f"[Manim] Render failed for {tmpl_name}: {result.stderr[-300:]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning(f"[Manim] Timeout rendering {tmpl_name}")
        return None
    except Exception as e:
        logger.warning(f"[Manim] Error rendering {tmpl_name}: {e}")
        return None


def compose_manim_block(scenes: list[dict], video_id: str, quality: str = "h") -> str | None:
    """Render multiple consecutive Manim scenes as a single video block."""
    import re
    combined_code = ""
    class_count = 0
    class_names = []
    for idx, scene in enumerate(scenes):
        selection = _select_template(scene)
        if not selection:
            continue
        tmpl_name, params = selection
        tmpl_fn = TEMPLATE_MAP[tmpl_name]
        title = params.get("title", f"Part {idx + 1}")
        dur = scene.get("target_duration", scene.get("duration", 6.0))
        code = tmpl_fn(title=title, duration=dur)
        unique_class = f"ManimBlock_{video_id}_{idx}"
        code = code.replace("class NeuralNetworkScene", f"class {unique_class}")
        code = code.replace("class AttentionScene", f"class {unique_class}")
        code = code.replace("class TransformerScene", f"class {unique_class}")
        code = code.replace("class AlgorithmFlowScene", f"class {unique_class}")
        code = code.replace("class BarChartScene", f"class {unique_class}")
        code = code.replace("class TextRevealScene", f"class {unique_class}")
        combined_code += f"\n\n{code}"
        class_names.append(unique_class)
        class_count += 1

    if not combined_code:
        return None

    py_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_block_{video_id}.py")
    output_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_block_{video_id}.mp4")
    with open(py_path, "w") as f:
        f.write(combined_code)

    quality_flag = f"-q{quality}"
    cmd = [MANIM_BIN, quality_flag, "--format=mp4", "-o", output_path, py_path] + class_names
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"[Manim] Composed block: {class_count} scenes -> {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
        else:
            logger.warning(f"[Manim] Block render failed: {result.stderr[-400:]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning(f"[Manim] Block render timeout")
        return None
    except Exception as e:
        logger.warning(f"[Manim] Block render error: {e}")
        return None
