import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def run_consistency_audit(title: str, script: str, format_type: str, category: str, video_id: str = "") -> dict:
    issues = []

    try:
        brand = _check_brand(script, format_type)
        issues.extend(brand)
    except Exception as e:
        logger.debug(f"[CONSISTENCY] Brand check failed: {e}")

    try:
        terms = _check_terminology(script)
        issues.extend(terms)
    except Exception as e:
        logger.debug(f"[CONSISTENCY] Terminology check failed: {e}")

    try:
        hook = _check_hook_rotation(video_id, format_type)
        issues.append(hook)
    except Exception as e:
        logger.debug(f"[CONSISTENCY] Hook rotation check failed: {e}")

    try:
        cross = _check_cross_references(title, script, category)
        issues.extend(cross)
    except Exception as e:
        logger.debug(f"[CONSISTENCY] Cross-reference check failed: {e}")

    error_count = len([i for i in issues if i.get("severity") == "error"])
    warning_count = len([i for i in issues if i.get("severity") == "warning"])
    info_count = len([i for i in issues if i.get("severity") == "info"])

    return {
        "title": title,
        "format": format_type,
        "category": category,
        "total_issues": len(issues),
        "errors": error_count,
        "warnings": warning_count,
        "info": info_count,
        "passed": error_count == 0,
        "issues": issues,
        "audited_at": datetime.utcnow().isoformat(),
    }


def _check_brand(script: str, format_type: str) -> list[dict]:
    issues = []

    try:
        from utils.brand_manager import pre_publish_brand_check
        brand_result = pre_publish_brand_check("", script, format_type, "")
        issues.extend(brand_result.get("issues", []))
    except Exception:
        pass

    sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    avg_words = sum(len(s.split()) for s in sentences) / max(len(sentences), 1)
    if avg_words > 15:
        issues.append({
            "type": "avg_sentence_length",
            "detail": f"Average sentence length {avg_words:.0f} words (target: <15)",
            "severity": "warning",
        })

    cta_phrases = ["subscribe", "like", "comment", "follow", "next video", "share", "bell icon"]
    cta_found = any(p in script.lower() for p in cta_phrases)
    if not cta_found:
        issues.append({
            "type": "missing_cta",
            "detail": "No call-to-action detected in script",
            "severity": "warning",
        })

    hook_phrases = [
        "imagine", "what if", "did you know", "here's the thing",
        "the truth is", "nobody tells you", "secretly",
        "why most", "stop", "actually",
    ]
    hook_found = any(p in script.lower()[:300] for p in hook_phrases)
    if not hook_found:
        issues.append({
            "type": "weak_hook",
            "detail": "No hook power phrase detected in first 300 chars",
            "severity": "info",
        })

    return issues


def _check_terminology(script: str) -> list[dict]:
    issues = []
    try:
        from utils.brand_manager import check_terminology
        issues.extend(check_terminology(script))
    except Exception:
        pass

    jargon_patterns = {
        "leverage": "use",
        "synergy": "combination",
        "utilize": "use",
        "paradigm": "model",
        "holistic": "complete",
        "optimize": "improve",
        "facilitate": "help",
        "implement": "build",
        "ecosystem": "system",
        "vertical": "industry",
    }
    for jargon, simpler in jargon_patterns.items():
        import re
        count = len(re.findall(r'\b' + jargon + r'\b', script, re.IGNORECASE))
        if count > 0:
            issues.append({
                "type": "jargon",
                "term": jargon,
                "suggestion": simpler,
                "count": count,
                "severity": "info",
            })

    return issues


def _check_hook_rotation(video_id: str, format_type: str) -> dict:
    try:
        from utils.brand_manager import _load_hook_history, suggest_next_hook_formula

        history = _load_hook_history()
        recent = history.get("hooks", [])[-3:]
        last_formula = history.get("last_formula")
        suggested = suggest_next_hook_formula()

        if last_formula:
            consecutive = 1
            for h in reversed(recent):
                if h.get("formula") == last_formula:
                    consecutive += 1
                else:
                    break
            if consecutive >= 2:
                return {
                    "type": "hook_rotation",
                    "detail": f"'{last_formula}' used {consecutive} times consecutively — consider '{suggested}'",
                    "severity": "warning",
                    "suggested": suggested,
                }

        return {
            "type": "hook_rotation",
            "detail": f"Hook rotation OK — suggested next: {suggested}",
            "severity": "info",
            "suggested": suggested,
        }

    except Exception as e:
        return {"type": "hook_rotation", "detail": f"Check failed: {e}", "severity": "info"}


def _check_cross_references(title: str, script: str, category: str) -> list[dict]:
    issues = []

    try:
        from utils.series_builder import pick_series_for_category, load_series
        series = pick_series_for_category(category)
        if series and series.get("videos"):
            part = series.get("current_part", 0) + 1
            if part > 1:
                prev_videos = sorted(
                    [v for v in series.get("videos", []) if v["part"] < part],
                    key=lambda v: v["part"],
                )
                if prev_videos:
                    last = prev_videos[-1]
                    ref_phrases = [
                        f"part {last['part']}",
                        f"last time",
                        f"previously",
                        f"as we covered",
                        f"building on",
                        f"in the last video",
                    ]
                    has_ref = any(p in script.lower() for p in ref_phrases)
                    if not has_ref:
                        issues.append({
                            "type": "missing_series_ref",
                            "detail": f"Part {part} of '{series['title']}' but no reference to Part {last['part']}",
                            "severity": "warning",
                        })
    except Exception as e:
        logger.debug(f"[CONSISTENCY] Cross-reference check: {e}")

    return issues


def get_audit_summary(audit_result: dict) -> str:
    if audit_result.get("passed"):
        return f"✅ Audit passed ({audit_result.get('info', 0)} info items)"
    parts = []
    if audit_result.get("errors", 0) > 0:
        parts.append(f"❌ {audit_result['errors']} errors")
    if audit_result.get("warnings", 0) > 0:
        parts.append(f"⚠️ {audit_result['warnings']} warnings")
    if audit_result.get("info", 0) > 0:
        parts.append(f"ℹ️ {audit_result['info']} info")
    return " | ".join(parts) if parts else "✅ Audit passed"
