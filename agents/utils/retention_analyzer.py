"""Retention Analyzer — track video retention curves and identify drop-off points.

Analyzes YouTube Analytics retention data to find:
- Where viewers drop off (hook failure, content gaps, outro too long)
- Which scenes retain best (reinforce those patterns)
- Optimal video length per category

Usage:
    from utils.retention_analyzer import analyze_retention, get_insights
    analysis = analyze_retention(video_id, retention_data)
    insights = get_insights("AI Explained")
"""
import os
import json
import time
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data" / "retention"
DATA_DIR.mkdir(parents=True, exist_ok=True)
RETENTION_FILE = DATA_DIR / "retention_data.json"


def _load_data() -> dict:
    if RETENTION_FILE.exists():
        try:
            return json.loads(RETENTION_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_data(data: dict):
    RETENTION_FILE.write_text(json.dumps(data, indent=2))


def analyze_retention(
    video_id: str,
    category: str,
    retention_curve: list[float],
    duration_seconds: float,
) -> dict:
    """Analyze a retention curve and return drop-off points and insights.

    retention_curve: list of % values (1.0 = 100% watching) at each second
    duration_seconds: total video duration

    Returns dict with:
    - hook_retention: % still watching at 5s (hook effectiveness)
    - avg_retention: average retention across video
    - drop_off_points: list of (timestamp, drop_magnitude) where biggest drops happen
    - scene_scores: estimated per-scene retention (if scene count provided)
    """
    if not retention_curve or duration_seconds <= 0:
        return {"hook_retention": 0, "avg_retention": 0, "drop_off_points": []}

    # Hook retention (first 5 seconds)
    hook_idx = min(5, len(retention_curve) - 1)
    hook_retention = retention_curve[hook_idx] if hook_idx < len(retention_curve) else 0

    # Average retention
    avg_retention = sum(retention_curve) / len(retention_curve) if retention_curve else 0

    # Find biggest drop-off points
    drop_offs = []
    for i in range(1, min(len(retention_curve), int(duration_seconds))):
        drop = retention_curve[i - 1] - retention_curve[i]
        if drop > 0.05:  # >5% drop
            drop_offs.append((i, round(drop, 3)))

    # Sort by magnitude
    drop_offs.sort(key=lambda x: x[1], reverse=True)

    # Save to data
    data = _load_data()
    if category not in data:
        data[category] = []
    data[category].append({
        "video_id": video_id,
        "hook_retention": round(hook_retention, 3),
        "avg_retention": round(avg_retention, 3),
        "drop_offs": drop_offs[:5],
        "duration": duration_seconds,
        "timestamp": time.time(),
    })
    # Keep last 100 entries per category
    data[category] = data[category][-100:]
    _save_data(data)

    return {
        "hook_retention": round(hook_retention, 3),
        "avg_retention": round(avg_retention, 3),
        "drop_off_points": drop_offs[:5],
    }


def get_insights(category: str) -> dict:
    """Get aggregated retention insights for a category."""
    data = _load_data()
    entries = data.get(category, [])
    if not entries:
        return {"avg_hook_retention": 0, "avg_overall_retention": 0, "common_drop_points": []}

    avg_hook = sum(e["hook_retention"] for e in entries) / len(entries)
    avg_overall = sum(e["avg_retention"] for e in entries) / len(entries)

    # Find common drop-off timestamps
    all_drops = []
    for e in entries:
        for ts, mag in e.get("drop_offs", []):
            all_drops.append((ts, mag))

    # Bucket drops into 5-second windows
    buckets = {}
    for ts, mag in all_drops:
        bucket = (ts // 5) * 5
        if bucket not in buckets:
            buckets[bucket] = []
        buckets[bucket].append(mag)

    common_drops = sorted(
        [(k, sum(v) / len(v)) for k, v in buckets.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    return {
        "avg_hook_retention": round(avg_hook, 3),
        "avg_overall_retention": round(avg_overall, 3),
        "common_drop_points": [(f"{t}s", round(m, 3)) for t, m in common_drops[:3]],
        "sample_size": len(entries),
    }
