import os
import hashlib
import json
import logging
import textwrap
from utils.subprocess_helper import safe_run, register_temp_dir
from datetime import datetime

from utils.manim_templates import (
    neural_network_template,
    attention_template,
    transformer_block_template,
    algorithm_flow_template,
    bar_chart_template,
    text_reveal_template,
    gradient_descent_template,
    convolution_template,
    recurrent_template,
    architecture_diagram_template,
    data_flow_diagram_template,
    timeline_template,
    comparison_chart_template,
    process_flow_template,
    concept_map_template,
    loss_landscape_template,
    embedding_space_template,
    decision_boundary_template,
    matrix_multiplication_template,
    backpropagation_template,
    probability_distribution_template,
    intro_template,
    outro_template,
)
from crew.manim_agent import enhance_manim_params, ManimScenePlan, select_template_llm
from utils.manim_validator import validate_manim_code
from crew.manim_code_gen import generate_manim_code

logger = logging.getLogger(__name__)

MANIM_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "manim_cache")
MANIM_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tmp", "manim_render")
os.makedirs(MANIM_CACHE_DIR, exist_ok=True)
os.makedirs(MANIM_OUTPUT_DIR, exist_ok=True)
register_temp_dir(str(MANIM_OUTPUT_DIR))

CODE_CACHE_DIR = os.path.join(MANIM_CACHE_DIR, "gen_codes")
os.makedirs(CODE_CACHE_DIR, exist_ok=True)

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
    "gradient_descent": gradient_descent_template,
    "convolution": convolution_template,
    "recurrent": recurrent_template,
    "architecture": architecture_diagram_template,
    "data_flow": data_flow_diagram_template,
    "timeline": timeline_template,
    "comparison": comparison_chart_template,
    "process_flow": process_flow_template,
    "concept_map": concept_map_template,
    "loss_landscape": loss_landscape_template,
    "embedding_space": embedding_space_template,
    "decision_boundary": decision_boundary_template,
    "matrix_multiplication": matrix_multiplication_template,
    "backpropagation": backpropagation_template,
    "probability_distribution": probability_distribution_template,
    "intro": intro_template,
    "outro": outro_template,
}


def _scene_hash(scene: dict) -> str:
    key = json.dumps(scene, sort_keys=True)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cached_path(scene_hash: str) -> str | None:
    path = os.path.join(MANIM_CACHE_DIR, f"{scene_hash}.mp4")
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return path
    return None


TEMPLATE_CLASS_NAMES: dict[str, str] = {
    "neural_network": "NeuralNetworkScene",
    "attention": "AttentionScene",
    "transformer": "TransformerScene",
    "algorithm_flow": "AlgorithmFlowScene",
    "bar_chart": "BarChartScene",
    "text_reveal": "TextRevealScene",
    "gradient_descent": "GradientDescentScene",
    "convolution": "ConvolutionScene",
    "recurrent": "RecurrentScene",
    "architecture": "ArchitectureDiagramScene",
    "data_flow": "DataFlowScene",
    "timeline": "TimelineScene",
    "comparison": "ComparisonScene",
    "process_flow": "ProcessFlowScene",
    "concept_map": "ConceptMapScene",
    "loss_landscape": "LossLandscapeScene",
    "embedding_space": "EmbeddingSpaceScene",
    "decision_boundary": "DecisionBoundaryScene",
    "matrix_multiplication": "MatrixMultiplyScene",
    "backpropagation": "BackpropagationScene",
    "probability_distribution": "ProbabilityDistributionScene",
    "intro": "IntroScene",
    "outro": "OutroScene",
}

TEMPLATE_CLASS_KEYS = list(TEMPLATE_CLASS_NAMES.values())
TEMPLATE_CLASS_PATTERNS = [f"class {name}" for name in TEMPLATE_CLASS_NAMES.values()]


def _select_template(scene: dict) -> tuple[str, dict, ManimScenePlan | None] | None:
    plan = enhance_manim_params(scene)

    similar = query_similar_scenes(
        (scene.get("description") or "") + " " + " ".join(scene.get("asset_keywords", [])),
        top_k=1
    )
    if similar and similar[0].get("score", 1.0) < 0.5:
        suggested = similar[0].get("metadata", {}).get("template_name", "")
        if suggested in TEMPLATE_MAP and suggested != plan.template_name:
            logger.info(f"[Manim] RAG suggests '{suggested}' (score={similar[0]['score']:.3f}) over heuristic '{plan.template_name}'")
            plan.template_name = suggested

    if plan.template_name not in TEMPLATE_MAP:
        desc = scene.get("description", "") or " ".join(scene.get("asset_keywords", []))
        fallback_lines = textwrap.wrap(desc[:80], width=40)[:3] if desc else (scene.get("asset_keywords", [])[:3] or ["Animation"])
        title = (scene.get("text") or [{}])[0].get("text", "") or "Concept"
        return "text_reveal", {"title": title, "lines": fallback_lines, "entry_time": plan.timing.entry, "exit_time": plan.timing.exit}, plan

    tmpl_name = plan.template_name
    params = plan.params.copy()
    params.update({"entry_time": plan.timing.entry, "exit_time": plan.timing.exit})
    return tmpl_name, params, plan


def render_manim_scene(scene: dict, video_id: str, scene_idx: int = 0, quality: str = "h") -> str | None:
    s_hash = _scene_hash(scene)
    cached = _cached_path(s_hash)
    if cached:
        logger.info(f"[Manim] Using cached render: {cached}")
        return cached

    # Heuristic template selection
    plan = enhance_manim_params(scene)

    # LLM-powered template resolution for novel/uncertain scenes
    if plan.template_name == "custom":
        llm_plan = select_template_llm(scene)
        if llm_plan:
            if llm_plan.template_name in TEMPLATE_MAP:
                logger.info(f"[Manim] LLM resolved '{llm_plan.template_name}' instead of custom")
                plan = llm_plan
            elif llm_plan.template_name == "custom":
                plan = llm_plan  # LLM confirms custom, use its plan

    # Custom LLM code generation path
    if plan.template_name == "custom":
        output_path = _generate_custom_scene(scene, plan, s_hash, video_id, scene_idx, quality)
        if output_path:
            return output_path
        logger.info(f"[Manim] Custom gen failed, falling back to template for scene {scene_idx}")
        selection = _select_template(scene)
        if not selection:
            return None
        tmpl_name, params, plan = selection
    else:
        # Template-based rendering (heuristic or LLM-resolved match)
        if plan.template_name not in TEMPLATE_MAP:
            plan.template_name = "text_reveal"
        tmpl_name = plan.template_name
        params = plan.params.copy()
        params.update({"entry_time": plan.timing.entry, "exit_time": plan.timing.exit})

    tmpl_fn = TEMPLATE_MAP[tmpl_name]
    title = params.get("title", "Concept")
    dur = scene.get("target_duration", scene.get("duration", 6.0))
    tmpl_kwargs = {k: v for k, v in params.items() if k not in ("title", "entry_time", "exit_time")}
    code = tmpl_fn(title=title, duration=dur, **tmpl_kwargs)

    scene_class_name = TEMPLATE_CLASS_NAMES.get(tmpl_name, "Scene")

    py_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.py")
    output_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.mp4")
    with open(py_path, "w") as f:
        f.write(code)

    quality_flag = f"-q{quality}"

    try:
        result = safe_run(
            [MANIM_BIN, quality_flag, "--format=mp4", "-o", output_path, py_path, scene_class_name],
            timeout=120,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            shutil_path = os.path.join(MANIM_CACHE_DIR, f"{s_hash}.mp4")
            import shutil
            shutil.copy2(output_path, shutil_path)
            logger.info(f"[Manim] Rendered {tmpl_name} -> {output_path} ({os.path.getsize(output_path)} bytes)")
            _index_template_usage(scene, plan)
            return output_path
        else:
            logger.warning(f"[Manim] Render failed for {tmpl_name}: {result.stderr[-300:]}")
            return None
    except Exception as e:
        logger.warning(f"[Manim] Error rendering {tmpl_name}: {e}")
        return None


def _generate_custom_code(scene: dict, plan: ManimScenePlan) -> tuple[str | None, str | None, dict | None]:
    """Generate Manim code via LLM for a custom scene. Returns (code, scene_class, error_info)."""
    description = scene.get("description", "") or " ".join(scene.get("asset_keywords", []))
    if not description:
        return None, None, {"error": "empty description"}

    title = plan.params.get("title", "Concept")
    dur = scene.get("target_duration", scene.get("duration", 6.0))
    similar = query_similar_scenes(description, top_k=3, success_only=True)

    code = generate_manim_code(
        description=description,
        title=title,
        duration=dur,
        scene_type=plan.scene_type,
        similar_examples=similar,
    )
    if not code:
        return None, None, {"error": "LLM returned no code"}

    validation = validate_manim_code(code)
    if not validation["valid"]:
        for attempt in range(2):
            logger.info(f"[Manim] Code invalid, self-heal attempt {attempt + 1}/2: {validation['errors'][:2]}")
            code = generate_manim_code(
                description=description,
                title=title,
                duration=dur,
                scene_type=plan.scene_type,
                similar_examples=similar,
                errors=validation["errors"],
            )
            if not code:
                break
            validation = validate_manim_code(code)
            if validation["valid"]:
                break

        if not validation["valid"]:
            return None, None, {"errors": validation["errors"]}

    return code, validation.get("scene_class") or "GeneratedScene", None


def _generate_custom_scene(scene: dict, plan: ManimScenePlan, s_hash: str, video_id: str, scene_idx: int, quality: str) -> str | None:
    code, scene_class_name, err = _generate_custom_code(scene, plan)
    if not code:
        error_msg = (err.get("error") or "") if err else ""
        if not error_msg and err and err.get("errors"):
            error_msg = "; ".join(err["errors"][:3])
        _index_template_usage(scene, plan, success=False, error=error_msg or "code generation failed")
        return None

    py_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.py")
    output_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_{video_id}_{scene_idx}.mp4")
    with open(py_path, "w") as f:
        f.write(code)

    quality_flag = f"-q{quality}"

    try:
        result = safe_run(
            [MANIM_BIN, quality_flag, "--format=mp4", "-o", output_path, py_path, scene_class_name],
            timeout=120,
        )
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            shutil_path = os.path.join(MANIM_CACHE_DIR, f"{s_hash}.mp4")
            import shutil
            shutil.copy2(output_path, shutil_path)
            logger.info(f"[Manim] Custom render succeeded -> {output_path} ({os.path.getsize(output_path)} bytes)")
            _index_template_usage(scene, plan, code=code, success=True)
            return output_path
        else:
            error_msg = result.stderr[-500:] if hasattr(result, "stderr") and result.stderr else "ffmpeg render produced no output"
            logger.warning(f"[Manim] Custom render failed: {error_msg}")
            _index_template_usage(scene, plan, code=code, success=False, error=error_msg)
            return None
    except Exception as e:
        logger.warning(f"[Manim] Custom render error: {e}")
        _index_template_usage(scene, plan, code=code, success=False, error=str(e))
        return None


def compose_manim_block(scenes: list[dict], video_id: str, quality: str = "h") -> str | None:
    import re
    sanitized_id = re.sub(r'[^a-zA-Z0-9_]', '_', video_id)
    combined_code = ""
    class_names = []
    for idx, scene in enumerate(scenes):
        # Try LLM custom generation for novel scenes
        plan = enhance_manim_params(scene)
        if plan.template_name == "custom":
            code, scene_class_name, _ = _generate_custom_code(scene, plan)
            if code:
                unique_class = f"ManimBlock_{sanitized_id}_{idx}"
                code = code.replace(f"class {scene_class_name}", f"class {unique_class}")
                combined_code += f"\n\n{code}"
                class_names.append(unique_class)
                continue

        # Template-based fallback
        selection = _select_template(scene)
        if not selection:
            continue
        tmpl_name, params, plan = selection
        tmpl_fn = TEMPLATE_MAP[tmpl_name]
        title = params.get("title", f"Part {idx + 1}")
        dur = scene.get("target_duration", scene.get("duration", 6.0))
        tmpl_kwargs = {k: v for k, v in params.items() if k not in ("title", "entry_time", "exit_time")}
        code = tmpl_fn(title=title, duration=dur, **tmpl_kwargs)
        unique_class = f"ManimBlock_{sanitized_id}_{idx}"
        for pattern in TEMPLATE_CLASS_PATTERNS:
            code = code.replace(pattern, f"class {unique_class}")
        combined_code += f"\n\n{code}"
        class_names.append(unique_class)
        _index_template_usage(scene, plan)

    if not combined_code:
        return None

    py_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_block_{video_id}.py")
    output_path = os.path.join(MANIM_OUTPUT_DIR, f"manim_block_{video_id}.mp4")
    with open(py_path, "w") as f:
        f.write(combined_code)

    quality_flag = f"-q{quality}"
    cmd = [MANIM_BIN, quality_flag, "--format=mp4", "-o", output_path, py_path] + class_names
    try:
        result = safe_run(cmd, timeout=300)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info(f"[Manim] Composed block: {len(class_names)} scenes -> {output_path} ({os.path.getsize(output_path)} bytes)")
            return output_path
        else:
            logger.warning(f"[Manim] Block render failed: {result.stderr[-400:]}")
            return None
    except Exception as e:
        logger.warning(f"[Manim] Block render error: {e}")
        return None


def _index_template_usage(scene: dict, plan: ManimScenePlan, code: str | None = None, success: bool = True, error: str | None = None) -> None:
    """Index scene-to-template mapping in chromadb for future RAG retrieval."""
    try:
        import chromadb
        client = chromadb.PersistentClient(
            path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")
        )
        collection = client.get_or_create_collection(
            name="manim_templates",
            metadata={"hnsw:space": "cosine"}
        )
        desc = (scene.get("description") or "") + " " + " ".join(scene.get("asset_keywords", []))
        doc_id = _scene_hash(scene)

        code_path = None
        if code:
            code_path = os.path.join(CODE_CACHE_DIR, f"{doc_id}.py")
            with open(code_path, "w") as f:
                f.write(code)

        metadata = {
            "template_name": plan.template_name,
            "scene_type": plan.scene_type,
            "reason": plan.reason,
            "timestamp": datetime.utcnow().isoformat(),
            "success": success,
        }
        if code_path:
            metadata["code_path"] = code_path
        if error:
            metadata["error"] = error[:500]

        collection.upsert(
            ids=[doc_id],
            documents=[desc],
            metadatas=[metadata],
        )
    except Exception as e:
        logger.debug(f"[Manim RAG] Index skipped: {e}")


def query_similar_scenes(description: str, top_k: int = 3, success_only: bool = True) -> list[dict]:
    """Query chromadb for scenes similar to the given description."""
    try:
        import chromadb
        client = chromadb.PersistentClient(
            path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")
        )
        collection = client.get_collection(name="manim_templates")

        query_kwargs = {"query_texts": [description], "n_results": top_k}
        if success_only:
            query_kwargs["where"] = {"success": True}

        try:
            results = collection.query(**query_kwargs)
        except Exception:
            query_kwargs.pop("where", None)
            results = collection.query(**query_kwargs)

        matches = []
        for i in range(len(results["ids"][0])):
            metadata = results["metadatas"][0][i]
            if success_only and metadata.get("success") is False:
                continue

            code = None
            if metadata.get("code_path"):
                try:
                    with open(metadata["code_path"]) as f:
                        code = f.read()
                except Exception:
                    pass

            matches.append({
                "id": results["ids"][0][i],
                "score": results["distances"][0][i] if results.get("distances") else 0,
                "metadata": metadata,
                "code": code,
                "document": results["documents"][0][i][:200] if results.get("documents") else "",
            })
        return matches
    except Exception:
        return []
