import os
import re
import logging

logger = logging.getLogger(__name__)

ARCHITECT_MODE = os.getenv("SCENE_ARCHITECT_MODE", "advisory").lower()

from blender_templates import TEMPLATE_KEYWORDS as BLENDER_TEMPLATE_KEYWORDS


class SceneArchitectError(Exception):
    pass


def audit_scenes(scenes: list[dict]) -> list[dict]:
    warnings = []
    if not scenes:
        return warnings

    durations = [s.get("duration", s.get("target_duration", 8.0)) for s in scenes]
    avg_dur = sum(durations) / max(len(durations), 1)

    for i, scene in enumerate(scenes):
        issues = _check_scene(scene, i, durations, avg_dur)
        warnings.extend(issues)

    if warnings:
        for w in warnings:
            logger.warning("[SceneArchitect] %s", w["message"])
            if ARCHITECT_MODE == "enforce":
                raise SceneArchitectError(w["message"])

    return warnings


def _check_scene(scene: dict, idx: int, durations: list[float], avg_dur: float) -> list[dict]:
    issues = []

    ltx_issues = _check_ltx_prompt(scene, idx)
    issues.extend(ltx_issues)

    render_issues = _check_render_type(scene, idx)
    issues.extend(render_issues)

    dur_issue = _check_duration_balance(scene, idx, durations, avg_dur)
    if dur_issue:
        issues.append(dur_issue)

    return issues


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "and", "or", "but", "if", "while", "about", "up", "down", "like",
    "just", "because", "also", "very", "too", "not", "no", "only",
    "show", "see", "use", "used", "using", "make", "made", "get",
}


def _check_ltx_prompt(scene: dict, idx: int) -> list[dict]:
    narration = scene.get("narration_text", "")
    prompt = scene.get("ltx_prompt", "")
    if not narration or not prompt:
        return []
    narration_lower = narration.lower()
    prompt_lower = prompt.lower()
    nar_words = {w for w in re.findall(r'\b[a-z]{4,}\b', narration_lower) if w not in STOPWORDS}
    if not nar_words:
        return []
    matches = sum(1 for w in nar_words if w in prompt_lower)
    match_ratio = matches / max(len(nar_words), 1)
    if match_ratio < 0.1 and len(nar_words) >= 3:
        return [{
            "type": "generic_ltx_prompt",
            "scene": idx,
            "message": f"Scene {idx}: LTX prompt too generic — only {matches}/{len(nar_words)} narration keywords appear in prompt (need ≥3). Prompt may waste GPU time.",
            "severity": "warning",
        }]
    return []


def _check_render_type(scene: dict, idx: int) -> list[dict]:
    narration = scene.get("narration_text", "")
    render_type = scene.get("render_type", "stock")
    if render_type == "blender":
        return []
    if not narration:
        return []

    text_lower = narration.lower()
    matched_templates = []
    for tmpl_name, keywords in BLENDER_TEMPLATE_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                matched_templates.append(tmpl_name)
                break

    if matched_templates and render_type != "blender":
        return [{
            "type": "wrong_render_type",
            "scene": idx,
            "message": f"Scene {idx}: render_type='{render_type}' but narration matches Blender templates: {', '.join(matched_templates[:3])}. Set render_type='blender' for better visuals.",
            "severity": "warning",
            "suggested_render_type": "blender",
            "matched_templates": matched_templates,
        }]
    return []


def _check_duration_balance(scene: dict, idx: int, durations: list[float], avg_dur: float) -> dict | None:
    dur = scene.get("duration", scene.get("target_duration", 8.0))
    ratio = dur / max(avg_dur, 0.1)
    if ratio >= 3.0:
        return {
            "type": "duration_imbalance",
            "scene": idx,
            "message": f"Scene {idx}: duration={dur:.1f}s is {ratio:.1f}x the average ({avg_dur:.1f}s), may drag pacing.",
            "severity": "warning",
        }
    return None
