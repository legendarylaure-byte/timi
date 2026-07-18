import os
import json
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "brand")
os.makedirs(DATA_DIR, exist_ok=True)
STYLE_FILE = os.path.join(DATA_DIR, "style_guide.json")
HOOK_FILE = os.path.join(DATA_DIR, "hook_history.json")
TERM_FILE = os.path.join(DATA_DIR, "vocabulary.json")

DEFAULT_STYLE_GUIDE = {
    "channel_name": "Vyom Ai Cloud",
    "tagline": "AI Made Simple",
    "colors": {"primary": "#8a50e8", "secondary": "#c060d0", "accent": "#e07040", "text": "#FFFFFF"},
    "fonts": {"title": "Inter Bold", "body": "Inter Regular", "caption": "Inter Medium"},
    "voice": {
        "tone": "educational, friendly, authoritative",
        "audience": "non-technical beginners",
        "rules": [
            "Explain every technical term from first principles",
            "Use analogies for complex concepts",
            "Never assume prior knowledge",
            "Keep sentences under 20 words",
            "End with a clear takeaway",
        ],
    },
    "visual": {
        "intro_duration": 3.0,
        "outro_duration": 5.0,
        "transition": "fade",
        "subtitle_color": "&H00FFFFFF&",
        "subtitle_font_size": 24,
        "thumbnail_style": "bold text on dark background with accent color",
    },
    "structure": {
        "shorts": ["hook (0-3s)", "explanation", "takeaway", "cta"],
        "long": ["hook (0-15s)", "context", "main explanation (10-14 sections)", "summary", "outro with cta"],
    },
    "values": [
        "Factual accuracy above all — never fabricate statistics",
        "Accessibility — make complex topics understandable",
        "Honesty — acknowledge uncertainty when unsure",
        "Consistency — maintain cross-video terminology",
    ],
}

HOOK_FORMULAS = ["question", "bold_claim", "statistic", "curiosity_gap", "pain_point"]


def _load_style() -> dict:
    if os.path.exists(STYLE_FILE):
        try:
            with open(STYLE_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load style guide: {e}")
    _save_style(DEFAULT_STYLE_GUIDE)
    return DEFAULT_STYLE_GUIDE


def _save_style(data: dict):
    with open(STYLE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load_hook_history() -> dict:
    if os.path.exists(HOOK_FILE):
        try:
            with open(HOOK_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load hook history: {e}")
    return {"hooks": [], "last_formula": None}


def _save_hook_history(data: dict):
    with open(HOOK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load_vocabulary() -> dict:
    if os.path.exists(TERM_FILE):
        try:
            with open(TERM_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load vocabulary: {e}")
    return {"preferred": {}, "avoided": {}}


def _save_vocabulary(data: dict):
    with open(TERM_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_style_guide() -> dict:
    return _load_style()


def update_style_rule(category: str, key: str, value):
    guide = _load_style()
    if category in guide:
        guide[category][key] = value
        _save_style(guide)
        logger.info(f"[BRAND] Updated style: {category}.{key} = {value}")
    else:
        logger.warning(f"[BRAND] Unknown style category: {category}")


def record_hook_usage(video_id: str, title: str, formula: str, format_type: str):
    history = _load_hook_history()
    history["hooks"].append({
        "video_id": video_id,
        "title": title,
        "formula": formula,
        "format": format_type,
        "timestamp": datetime.utcnow().isoformat(),
    })
    history["last_formula"] = formula
    _save_hook_history(history)
    logger.info(f"[BRAND] Recorded hook: {formula} for {title}")


def suggest_next_hook_formula() -> str:
    history = _load_hook_history()
    last = history.get("last_formula")

    recent = history.get("hooks", [])[-5:]
    recent_formulas = [h["formula"] for h in recent]

    counts = {}
    for f in HOOK_FORMULAS:
        counts[f] = recent_formulas.count(f)

    sorted_formulas = sorted(HOOK_FORMULAS, key=lambda f: (counts[f], f == last))
    return sorted_formulas[0]


def add_preferred_term(term: str, replacement: str, category: str = "general"):
    vocab = _load_vocabulary()
    vocab["preferred"][term.lower()] = {"replacement": replacement, "category": category}
    _save_vocabulary(vocab)
    logger.info(f"[BRAND] Added preferred term: {term} -> {replacement}")


def add_avoided_term(term: str, reason: str = "", severity: str = "warning"):
    vocab = _load_vocabulary()
    vocab["avoided"][term.lower()] = {"reason": reason, "severity": severity}
    _save_vocabulary(vocab)
    logger.info(f"[BRAND] Added avoided term: {term} ({reason})")


def check_terminology(text: str) -> list[dict]:
    vocab = _load_vocabulary()
    issues = []
    text_lower = text.lower()

    for term, info in vocab.get("avoided", {}).items():
        if term in text_lower:
            issues.append({
                "type": "avoided_term",
                "term": term,
                "reason": info.get("reason", ""),
                "severity": info.get("severity", "warning"),
            })

    for term, info in vocab.get("preferred", {}).items():
        replacement = info.get("replacement", "")
        if term in text_lower and replacement and replacement.lower() not in text_lower:
            issues.append({
                "type": "preferred_term",
                "term": term,
                "suggested": replacement,
                "severity": "info",
            })

    return issues


def get_brand_context() -> str:
    guide = _load_style()
    parts = [
        f"Channel: {guide.get('channel_name', '')} — {guide.get('tagline', '')}",
        f"Tone: {guide.get('voice', {}).get('tone', 'educational')}",
        f"Audience: {guide.get('voice', {}).get('audience', 'beginners')}",
        "Voice rules:",
    ]
    for rule in guide.get("voice", {}).get("rules", []):
        parts.append(f"  - {rule}")
    return "\n".join(parts)


def pre_publish_brand_check(title: str, script: str, format_type: str, category: str) -> dict:
    issues = []

    guide = _load_style()
    voice_rules = guide.get("voice", {}).get("rules", [])
    sentences = [s.strip() for s in script.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    long_sentences = [s for s in sentences if len(s.split()) > 20]
    if long_sentences:
        issues.append({
            "type": "sentence_length",
            "count": len(long_sentences),
            "detail": f"{len(long_sentences)} sentences exceed 20 words",
            "severity": "warning",
        })

    term_issues = check_terminology(script)
    issues.extend(term_issues)

    if format_type == "shorts":
        expected_structure = guide.get("structure", {}).get("shorts", [])
        has_cta = any(w in script.lower() for w in ["subscribe", "follow", "next video", "comment", "like"])
        if not has_cta:
            issues.append({
                "type": "missing_cta",
                "detail": "No call-to-action found in script",
                "severity": "warning",
            })

    return {
        "title": title,
        "format": format_type,
        "category": category,
        "issue_count": len(issues),
        "issues": issues,
        "passed": len([i for i in issues if i.get("severity") == "error"]) == 0,
    }
