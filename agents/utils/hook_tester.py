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


def sync_hook_stats_from_youtube(max_videos: int = 50) -> int:
    """Pull real YouTube stats for each recorded hook test and update local data.

    Returns count of updated entries.
    """
    try:
        from utils.youtube_upload import fetch_video_stats
    except Exception:
        return 0

    data = _load_results()
    updated = 0

    for category in list(data.keys()):
        for formula in list(data.get(category, {}).keys()):
            entries = data[category][formula]
            for entry in entries:
                vid = entry.get("video_id", "")
                if not vid:
                    continue
                # Skip if already synced recently (< 1 hour ago)
                last_sync = entry.get("_last_sync", 0)
                if time.time() - last_sync < 3600:
                    continue
                try:
                    stats = fetch_video_stats(vid)
                    if stats:
                        entry["views"] = stats.get("views", entry.get("views", 0))
                        entry["retention"] = stats.get("average_view_duration_seconds", 0) / max(stats.get("duration_seconds", 1), 1)
                        entry["likes"] = stats.get("likes", entry.get("likes", 0))
                        entry["_last_sync"] = time.time()
                        updated += 1
                except Exception:
                    pass

            # Prune old unsynced entries (keep only synced ones)
            if updated > 0:
                data[category][formula] = entries

    if updated > 0:
        _save_results(data)

    return updated


def get_best_hook_for_topic(topic: str, category: str = "") -> dict:
    """Score which hook formula best matches a topic text.

    Combines keyword matching with historical performance data.
    Returns dict with formula, score, and reasoning.
    """
    topic_lower = topic.lower()
    formulas = {
        "question": ["what", "how", "why", "did", "do you", "can you", "would you", "is it", "are we", "should"],
        "bold_claim": ["secret", "truth", "nobody", "everyone", "actually", "the real", "stop", "never", "best"],
        "statistic": ["percent", "million", "billion", "times", "number", "x ", "ratio", "every"],
        "curiosity_gap": ["why", "the reason", "what if", "imagine", "discover", "revealed", "behind"],
        "pain_point": ["struggle", "hard", "difficult", "frustrating", "annoying", "problem", "waste"],
    }

    scores = {}
    for formula, keywords in formulas.items():
        score = sum(2 for kw in keywords if kw in topic_lower)
        scores[formula] = score

    # Weight by historical performance if available
    try:
        stats = get_hook_stats(category) if category else {}
        for formula in scores:
            s = stats.get(formula, {})
            if s.get("count", 0) > 0:
                scores[formula] += min(10, int(s["avg_views"] / 100))
    except Exception:
        pass

    best = max(scores, key=scores.get)
    return {"formula": best, "score": scores[best], "all_scores": scores}
