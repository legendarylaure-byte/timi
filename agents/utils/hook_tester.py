"""Hook A/B Tester — track hook formula performance and suggest optimal rotation.

Records which hook formulas (question, bold_claim, statistic, curiosity_gap,
pain_point) perform best per category, and suggests the next formula to use.

Usage:
    from utils.hook_tester import suggest_hook_formula, record_hook_result
    formula = suggest_hook_formula("AI Explained")
    # ... generate video ...
    record_hook_result(video_id, "AI Explained", "question", views=1500, retention=0.45)
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data" / "hook_testing"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_FILE = DATA_DIR / "hook_results.json"

FORMULAS = ["question", "bold_claim", "statistic", "curiosity_gap", "pain_point"]


def _load_results() -> dict:
    if RESULTS_FILE.exists():
        try:
            return json.loads(RESULTS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_results(data: dict):
    RESULTS_FILE.write_text(json.dumps(data, indent=2))


def suggest_hook_formula(category: str) -> str:
    """Suggest the best hook formula for a category based on past performance.

    Returns the formula with highest average views. Falls back to rotation
    if no data exists.
    """
    data = _load_results()
    cat_data = data.get(category, {})

    if not cat_data:
        # No data — use simple rotation based on category hash
        idx = hash(category) % len(FORMULAS)
        return FORMULAS[idx]

    # Score each formula by average views
    best_formula = FORMULAS[0]
    best_avg = 0
    for formula in FORMULAS:
        entries = cat_data.get(formula, [])
        if entries:
            avg_views = sum(e.get("views", 0) for e in entries) / len(entries)
            if avg_views > best_avg:
                best_avg = avg_views
                best_formula = formula

    return best_formula


def record_hook_result(
    video_id: str,
    category: str,
    formula: str,
    views: int = 0,
    retention: float = 0.0,
    likes: int = 0,
):
    """Record a hook formula's performance for a video."""
    data = _load_results()
    if category not in data:
        data[category] = {}
    if formula not in data[category]:
        data[category][formula] = []

    data[category][formula].append({
        "video_id": video_id,
        "views": views,
        "retention": retention,
        "likes": likes,
        "timestamp": time.time(),
    })

    # Keep last 50 entries per formula per category
    data[category][formula] = data[category][formula][-50:]
    _save_results(data)


def get_hook_stats(category: str) -> dict:
    """Get performance stats for each hook formula in a category."""
    data = _load_results()
    cat_data = data.get(category, {})
    stats = {}

    for formula in FORMULAS:
        entries = cat_data.get(formula, [])
        if entries:
            avg_views = sum(e.get("views", 0) for e in entries) / len(entries)
            avg_retention = sum(e.get("retention", 0) for e in entries) / len(entries)
            stats[formula] = {
                "count": len(entries),
                "avg_views": round(avg_views),
                "avg_retention": round(avg_retention, 3),
            }
        else:
            stats[formula] = {"count": 0, "avg_views": 0, "avg_retention": 0}

    return stats
