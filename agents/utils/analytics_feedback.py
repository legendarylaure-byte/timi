import json
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)

FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "analytics")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback_loop.json")
os.makedirs(FEEDBACK_DIR, exist_ok=True)


def _load_feedback() -> dict:
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"iterations": [], "active_insights": {}, "category_performance": {}, "format_performance": {}}


def _save_feedback(data: dict):
    with open(FEEDBACK_FILE, "w") as f:
        json.dump(data, f, indent=2)


def analyze_recent_performance(video_analytics: list[dict], days: int = 30) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)
    recent = [v for v in video_analytics if v.get("created_at", "") >= cutoff.isoformat()]

    cat_stats = defaultdict(lambda: {"count": 0, "total_views": 0, "total_likes": 0, "total_comments": 0, "total_ctr": 0})
    fmt_stats = defaultdict(lambda: {"count": 0, "total_views": 0, "total_engagement": 0})

    for v in recent:
        cat = v.get("category", "Unknown")
        fmt = v.get("format", "shorts")
        views = v.get("views", 0)
        likes = v.get("likes", 0)
        comments = v.get("comments", 0)
        ctr = v.get("ctr", 0)

        cat_stats[cat]["count"] += 1
        cat_stats[cat]["total_views"] += views
        cat_stats[cat]["total_likes"] += likes
        cat_stats[cat]["total_comments"] += comments
        cat_stats[cat]["total_ctr"] += ctr

        fmt_stats[fmt]["count"] += 1
        fmt_stats[fmt]["total_views"] += views
        fmt_stats[fmt]["total_engagement"] += likes + comments

    cat_performance = {}
    for cat, s in cat_stats.items():
        avg_views = s["total_views"] / s["count"] if s["count"] > 0 else 0
        avg_ctr = s["total_ctr"] / s["count"] if s["count"] > 0 else 0
        cat_performance[cat] = {"videos": s["count"], "avg_views": round(avg_views, 1), "avg_ctr": round(avg_ctr, 2)}

    fmt_performance = {}
    for fmt, s in fmt_stats.items():
        avg_views = s["total_views"] / s["count"] if s["count"] > 0 else 0
        fmt_performance[fmt] = {"videos": s["count"], "avg_views": round(avg_views, 1)}

    best_category = max(cat_performance, key=lambda c: cat_performance[c]["avg_views"]) if cat_performance else None
    best_format = max(fmt_performance, key=lambda f: fmt_performance[f]["avg_views"]) if fmt_performance else None

    insights = {
        "analyzed_at": datetime.utcnow().isoformat(),
        "period_days": days,
        "total_videos": len(recent),
        "best_category": best_category,
        "best_format": best_format,
        "category_performance": cat_performance,
        "format_performance": fmt_performance,
        "recommendations": _generate_recommendations(cat_performance, fmt_performance, best_category, best_format),
    }

    fb = _load_feedback()
    fb["iterations"].append(insights)
    fb["active_insights"] = insights
    fb["category_performance"] = cat_performance
    fb["format_performance"] = fmt_performance
    _save_feedback(fb)

    _sync_insights_to_firestore(insights)

    return insights


def _sync_insights_to_firestore(insights: dict):
    try:
        from utils.firebase_status import get_firestore_client
        from firebase_admin import firestore

        db = get_firestore_client()
        if db is None:
            return
        db.collection("analytics").document("insights").set(
            {
                "best_category": insights.get("best_category", ""),
                "best_format": insights.get("best_format", ""),
                "recommendations": insights.get("recommendations", []),
                "category_performance": insights.get("category_performance", {}),
                "format_performance": insights.get("format_performance", {}),
                "total_videos_analyzed": insights.get("total_videos", 0),
                "period_days": insights.get("period_days", 30),
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.info("[ANALYTICS] Synced insights to Firestore")
    except Exception as e:
        logger.warning(f"[ANALYTICS] Firestore sync failed: {e}")


def _generate_recommendations(cat_perf: dict, fmt_perf: dict, best_cat: str | None, best_fmt: str | None) -> list:
    recs = []
    if best_cat:
        recs.append(f"Prioritize '{best_cat}' content — highest avg views in last 30 days")
        low_cats = [(c, d) for c, d in cat_perf.items() if d["avg_views"] < 50 and d["videos"] > 1]
        for cat, data in low_cats:
            recs.append(f"Reduce or rework '{cat}' content — only {data['avg_views']} avg views across {data['videos']} videos")
    if best_fmt:
        recs.append(f"Favor '{best_fmt}' format — outperforms other formats")
    if not recs:
        recs.append("Not enough data yet — continue producing consistent content")
    return recs


def get_active_insights() -> dict:
    fb = _load_feedback()
    return fb.get("active_insights", {})


def get_pipeline_tuning() -> dict:
    insights = get_active_insights()
    tuning = {
        "preferred_category": None,
        "preferred_format": None,
        "virality_boost": 0,
        "scene_count_adjust": 0,
        "voice_rate_adjust": "0%",
    }
    if not insights:
        return tuning
    best_cat = insights.get("best_category")
    best_fmt = insights.get("best_format")
    if best_cat:
        tuning["preferred_category"] = best_cat
    if best_fmt:
        tuning["preferred_format"] = best_fmt
        if best_fmt == "shorts":
            tuning["virality_boost"] = 10
            tuning["scene_count_adjust"] = -2
        else:
            tuning["virality_boost"] = 5
            tuning["scene_count_adjust"] = 2
    cat_perf = insights.get("category_performance", {})
    if cat_perf and best_cat and cat_perf.get(best_cat, {}).get("avg_views", 0) > 1000:
        tuning["voice_rate_adjust"] = "+5%"
    return tuning


def get_optimization_prompt_injection() -> str:
    insights = get_active_insights()
    if not insights:
        return ""
    recs = insights.get("recommendations", [])
    best_cat = insights.get("best_category", "")
    best_fmt = insights.get("best_format", "")
    parts = []
    if best_cat:
        parts.append(f"Your best-performing category is '{best_cat}'.")
    if best_fmt:
        parts.append(f"Your best-performing format is '{best_fmt}'.")
    if recs:
        parts.append("Recent insights: " + " ".join(recs[:2]))
    return " ".join(parts)
