"""Content pillar strategy — enforce ratios, track balance, suggest topics."""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

CONTENT_PILLARS = {
    # Deep lesson pillars (Manim-heavy, curriculum-based, 3/week)
    "AI Foundations": {"ratio": 0.15, "priority": 5, "category_type": "deep_lesson", "description": "Foundational AI/ML concepts — neural networks, backpropagation, gradient descent"},
    "LLM Internals": {"ratio": 0.15, "priority": 5, "category_type": "deep_lesson", "description": "How LLMs work — tokenization, embeddings, attention, transformers, generation"},
    "Training & Data": {"ratio": 0.10, "priority": 4, "category_type": "deep_lesson", "description": "Training pipelines — RLHF, fine-tuning, LoRA, datasets, evaluation"},
    "AI Systems": {"ratio": 0.08, "priority": 4, "category_type": "deep_lesson", "description": "Systems — RAG, agents, multi-modal, deployment, best practices"},
    # Quick short pillars (LTX/stock, fast-paced, 3/day)
    "AI Explained": {"ratio": 0.18, "priority": 3, "category_type": "quick_short", "description": "Quick AI/ML concept explainers"},
    "AI News": {"ratio": 0.12, "priority": 3, "category_type": "quick_short", "description": "Latest AI developments and updates"},
    "Tool Tutorials": {"ratio": 0.08, "priority": 2, "category_type": "quick_short", "description": "AI tool guides and how-tos"},
    "Code & Build": {"ratio": 0.06, "priority": 2, "category_type": "quick_short", "description": "Code walkthroughs, build projects"},
    "Paper Breakdowns": {"ratio": 0.04, "priority": 1, "category_type": "quick_short", "description": "Academic paper summaries"},
    "Career & Learning": {"ratio": 0.04, "priority": 1, "category_type": "quick_short", "description": "Career advice, learning paths"},
}

PILLAR_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "pillars"
)
os.makedirs(PILLAR_DATA_DIR, exist_ok=True)


def _pillar_path() -> str:
    return os.path.join(PILLAR_DATA_DIR, "pillar_tracker.json")


def _load_tracker() -> dict:
    path = _pillar_path()
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning("[pillar] Failed to load tracker: %s", e)
    return {"pillars": {p: {"video_count": 0, "last_post": None, "total_views": 0} for p in CONTENT_PILLARS}}


def _save_tracker(data: dict):
    try:
        with open(_pillar_path(), "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("[pillar] Failed to save tracker: %s", e)


def track_pillar_video(category: str, views: int = 0):
    """Record a video published in a pillar category."""
    tracker = _load_tracker()
    if category in tracker["pillars"]:
        tracker["pillars"][category]["video_count"] += 1
        tracker["pillars"][category]["last_post"] = datetime.utcnow().isoformat()
        tracker["pillars"][category]["total_views"] += views
    else:
        tracker["pillars"][category] = {"video_count": 1, "last_post": datetime.utcnow().isoformat(), "total_views": views}
    _save_tracker(tracker)


def get_pillar_balance() -> dict:
    """Get current pillar balance vs target ratios over rolling 7/14/30 days.

    Returns dict of pillar_name -> {actual_ratio, target_ratio, gap, videos, priority}
    """
    tracker = _load_tracker()
    total_videos = sum(p["video_count"] for p in tracker["pillars"].values())

    balance = {}
    for name, config in CONTENT_PILLARS.items():
        pillar_data = tracker["pillars"].get(name, {"video_count": 0, "last_post": None, "total_views": 0})
        actual_ratio = pillar_data["video_count"] / max(total_videos, 1)
        gap = actual_ratio - config["ratio"]

        balance[name] = {
            "actual_ratio": round(actual_ratio, 3),
            "target_ratio": config["ratio"],
            "gap": round(gap, 3),
            "videos": pillar_data["video_count"],
            "last_post": pillar_data["last_post"],
            "total_views": pillar_data["total_views"],
            "priority": config["priority"],
            "description": config["description"],
        }

    return balance


def get_underrepresented_pillars(min_gap: float = -0.05) -> list[dict]:
    """Get pillars that are below their target ratio by at least min_gap."""
    balance = get_pillar_balance()
    underrepresented = []
    for name, data in balance.items():
        if data["gap"] < min_gap:
            underrepresented.append({"name": name, **data})
    underrepresented.sort(key=lambda x: x["gap"])
    return underrepresented


def get_overrepresented_pillars(max_gap: float = 0.05) -> list[dict]:
    """Get pillars above their target ratio."""
    balance = get_pillar_balance()
    overrepresented = []
    for name, data in balance.items():
        if data["gap"] > max_gap:
            overrepresented.append({"name": name, **data})
    overrepresented.sort(key=lambda x: -x["gap"])
    return overrepresented


def suggest_next_pillar() -> Optional[dict]:
    """Suggest the next pillar to produce content for, based on balance + priority."""
    underrepresented = get_underrepresented_pillars()
    if underrepresented:
        return underrepresented[0]

    balance = get_pillar_balance()
    sorted_by_staleness = sorted(
        [{"name": n, **d} for n, d in balance.items()],
        key=lambda x: (
            x["last_post"] or "2000-01-01",
            -x["priority"]
        )
    )
    return sorted_by_staleness[0] if sorted_by_staleness else None


def validate_plan_balance(plan: list) -> list:
    """Validate a content plan against pillar balance — swap overrepresented for underrepresented.

    Mutates plan items' 'category' and 'reasoning' fields in-place.
    """
    underrepresented = get_underrepresented_pillars(min_gap=-0.02)
    if not underrepresented:
        return plan

    balance = get_pillar_balance()
    overrepresented = sorted(
        [{"name": n, **d} for n, d in balance.items() if d["gap"] > 0.03],
        key=lambda x: -x["gap"]
    )

    swap_count = 0
    for item in plan:
        if not overrepresented or not underrepresented:
            break
        cat = item.get("category", "")
        b = balance.get(cat)
        if b and b["gap"] > 0.03:
            swap_target = underrepresented[0]
            old_cat = cat
            item["category"] = swap_target["name"]
            item["reasoning"] = f"Pillar-balanced: swapped from {old_cat} to {swap_target['name']} (underrepresented)"
            overrepresented.pop(0)
            underrepresented.pop(0)
            swap_count += 1

    if swap_count:
        logger.info("[pillar] Plan balance validation: %d categories swapped", swap_count)
    return plan


def generate_pillar_context() -> str:
    """Generate context text for the scheduler planner about pillar balance."""
    balance = get_pillar_balance()
    underrepresented = [n for n, d in balance.items() if d["gap"] < -0.02]

    if not underrepresented:
        return ""

    lines = ["Content pillar balance targets (ratio = target share of all content):"]
    for name in underrepresented:
        d = balance[name]
        lines.append(f"  - {name}: {d['actual_ratio']:.0%} actual vs {d['target_ratio']:.0%} target (under by {abs(d['gap']):.0%})")

    lines.append(f"Suggest focusing on: {underrepresented[0]}")
    return "\n".join(lines)
