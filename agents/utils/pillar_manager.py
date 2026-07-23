"""Content pillar strategy — enforce ratios, track balance, suggest topics."""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from utils.scene_schema import DEEP_LESSON_CATS, normalize_category

logger = logging.getLogger(__name__)

# CPM rates for revenue-optimized scheduling (USD per 1000 views)
CPM_RATES = {
    "Business & Finance": 25,
    "Health & Medicine": 18,
    "Programming & Software": 13,
    "Science & Technology": 12,
    "AI News": 8,
}


def _pillar_type(name: str) -> str:
    return "deep_lesson" if name in DEEP_LESSON_CATS else "quick_short"


CONTENT_PILLARS = {
    "AI News": {"ratio": 0.25, "priority": 5, "cpm": 8, "description": "Latest AI developments, model releases, industry moves, breaking news"},
    "Science & Technology": {"ratio": 0.25, "priority": 5, "cpm": 12, "description": "Science discoveries, tech innovations, research breakthroughs, engineering marvels"},
    "Business & Finance": {"ratio": 0.20, "priority": 4, "cpm": 25, "description": "Business strategy, economics, markets, entrepreneurship, AI in business"},
    "Health & Medicine": {"ratio": 0.15, "priority": 3, "cpm": 18, "description": "Health science, medical breakthroughs, nutrition, AI in healthcare"},
    "Programming & Software": {"ratio": 0.15, "priority": 3, "cpm": 13, "description": "Code tutorials, software engineering, development tools, AI tooling"},
}

# populate category_type from the single source of truth
for _name in CONTENT_PILLARS:
    CONTENT_PILLARS[_name]["category_type"] = _pillar_type(_name)

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
                data = json.load(f)
            # Migrate old categories into new 5
            _migrate_tracker(data)
            return data
        except Exception as e:
            logger.warning("[pillar] Failed to load tracker: %s", e)
    return {"pillars": {p: {"video_count": 0, "last_post": None, "total_views": 0} for p in CONTENT_PILLARS}}


def _migrate_tracker(data: dict):
    """Consolidate old category entries into the new 5 canonical categories."""
    pillars = data.get("pillars", {})
    migrated = False
    for old_cat in list(pillars.keys()):
        if old_cat not in CONTENT_PILLARS:
            new_cat = normalize_category(old_cat)
            if new_cat != old_cat and new_cat in CONTENT_PILLARS:
                old_data = pillars.pop(old_cat)
                if new_cat in pillars:
                    pillars[new_cat]["video_count"] += old_data.get("video_count", 0)
                    if old_data.get("last_post") and (not pillars[new_cat].get("last_post") or old_data["last_post"] > pillars[new_cat]["last_post"]):
                        pillars[new_cat]["last_post"] = old_data["last_post"]
                    pillars[new_cat]["total_views"] += old_data.get("total_views", 0)
                else:
                    pillars[new_cat] = old_data
                migrated = True
            else:
                # Unknown category, remove
                pillars.pop(old_cat)
                migrated = True
    # Ensure all 5 pillars exist
    for p in CONTENT_PILLARS:
        if p not in pillars:
            pillars[p] = {"video_count": 0, "last_post": None, "total_views": 0}
    if migrated:
        _save_tracker(data)


def _save_tracker(data: dict):
    try:
        with open(_pillar_path(), "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning("[pillar] Failed to save tracker: %s", e)


def track_pillar_video(category: str, views: int = 0):
    """Record a video published in a pillar category."""
    category = normalize_category(category)
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


def get_revenue_optimized_category() -> str:
    """Pick the best category weighted by CPM × freshness × balance.

    High-CPM categories get produced more often, but balance is still respected.
    Returns the single best category to produce next.
    """
    balance = get_pillar_balance()
    best_cat = "AI News"
    best_score = -1

    for name in CONTENT_PILLARS:
        cpm = CONTENT_PILLARS[name].get("cpm", CPM_RATES.get(name, 8))
        b = balance.get(name, {})
        gap = b.get("gap", 0)

        # Revenue weight: CPM normalized 0-25
        revenue_w = min(25, cpm)

        # Freshness: days since last post (more days = higher score)
        last_post = b.get("last_post")
        if last_post:
            try:
                days_since = (datetime.utcnow() - datetime.fromisoformat(last_post)).days
            except Exception:
                days_since = 14
        else:
            days_since = 30
        freshness_w = min(25, days_since * 2)

        # Balance: underrepresented categories get boost (gap < 0 = needs more)
        balance_w = min(25, max(0, int(-gap * 100 + 12)))

        total = revenue_w + freshness_w + balance_w

        if total > best_score:
            best_score = total
            best_cat = name

    return best_cat
