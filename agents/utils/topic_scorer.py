"""Topic Scorer — rank candidate topics with composite scoring.

Scores every candidate topic on viral potential, search demand,
competition level, and revenue potential before it enters the pipeline.

Usage:
    from utils.topic_scorer import score_topic, rank_topics, get_smart_category_slot
    score = score_topic("How AI Will Replace Doctors", "Health & Medicine")
    ranked = rank_topics([{"title": "...", "category": "..."}, ...])
    best_cat = get_smart_category_slot()
"""
import json
import math
import os
import time
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "topic_scorer"
DATA_DIR.mkdir(parents=True, exist_ok=True)
SCORES_FILE = DATA_DIR / "topic_scores.json"

VALID_CATEGORIES = ["AI News", "Science & Technology", "Business & Finance", "Health & Medicine", "Programming & Software"]

CPM_RATES = {
    "Business & Finance": 25,
    "Health & Medicine": 18,
    "Programming & Software": 13,
    "Science & Technology": 12,
    "AI News": 8,
}


@dataclass
class TopicScore:
    total: int  # 0-100 composite
    viral_potential: int  # 0-25: title hooks, controversy, surprise
    search_demand: int  # 0-25: trending velocity, search volume
    competition: int  # 0-25: fewer existing videos = higher
    revenue_potential: int  # 0-25: CPM × view potential
    hook_formula: str  # suggested hook type
    category: str
    reasoning: str


def _load_scores() -> dict:
    if SCORES_FILE.exists():
        try:
            return json.loads(SCORES_FILE.read_text())
        except Exception:
            pass
    return {"scored_topics": [], "category_stats": {}}


def _save_scores(data: dict):
    SCORES_FILE.write_text(json.dumps(data, indent=2))


def _score_viral_potential(title: str) -> int:
    """Score title for viral hooks (0-25)."""
    score = 10  # base
    t = title.lower()

    # Question marks create curiosity
    if "?" in title:
        score += 5

    # Power words trigger emotion
    power_words = ["secret", "truth", "nobody", "actually", "really", "shocking",
                   "amazing", "insane", "unbelievable", "mind-blowing", "crazy",
                   "never", "always", "why", "how", "what if"]
    score += min(5, sum(2 for w in power_words if w in t))

    # Numbers in title
    if any(c.isdigit() for c in title):
        score += 3

    # Comparison/vs format
    if any(w in t for w in ["vs", "compared", "better", "best", "top", "worst"]):
        score += 3

    # Controversy indicators
    if any(w in t for w in ["wrong", "myth", "lie", "fake", "scam", "overrated"]):
        score += 4

    # Concise titles perform better on Shorts
    word_count = len(title.split())
    if word_count <= 6:
        score += 2
    elif word_count > 12:
        score -= 2

    return min(25, max(0, score))


def _score_search_demand(title: str, category: str) -> int:
    """Score based on trending data and search demand (0-25)."""
    # Check trend history for this topic
    try:
        from utils.trend_engine import get_trend_history, CATEGORY_KEYWORDS
        recent = get_trend_history(hours=168)  # last 7 days

        # Direct title match
        for t in recent:
            if _titles_similar(title, t.get("title", "")):
                return min(25, 15 + t.get("scores", {}).get("engagement", 0) // 40)

        # Keyword match
        keywords = CATEGORY_KEYWORDS.get(category, [])
        title_words = set(title.lower().split())
        matching = sum(1 for kw in keywords if kw in title_words or any(tw in kw for tw in title_words))
        if matching > 0:
            return min(25, 10 + matching * 3)

    except Exception:
        pass

    # Default: estimate based on category popularity
    base = {"AI News": 15, "Science & Technology": 13, "Health & Medicine": 14,
            "Business & Finance": 12, "Programming & Software": 13}
    return base.get(category, 10)


def _score_competition(title: str, category: str) -> int:
    """Score based on how many similar videos exist (0-25, fewer = higher)."""
    try:
        from utils.trend_engine import get_trend_history
        recent = get_trend_history(hours=168)
        similar = sum(1 for t in recent if _titles_similar(title, t.get("title", "")))
        # Fewer similar = less competition = higher score
        return max(0, min(25, 25 - similar * 5))
    except Exception:
        return 15


def _score_revenue_potential(category: str) -> int:
    """Score based on CPM rate (0-25)."""
    cpm = CPM_RATES.get(category, 8)
    return min(25, int(cpm * 1.0))


def _suggest_hook(title: str) -> str:
    """Suggest the best hook formula for a title."""
    t = title.lower()
    if "?" in title:
        return "question"
    if any(w in t for w in ["secret", "truth", "nobody", "actually", "shocking", "wrong", "myth"]):
        return "pain_point"
    if any(c.isdigit() for c in title):
        return "statistic"
    if any(w in t for w in ["vs", "compared", "better", "best", "top"]):
        return "bold_claim"
    return "curiosity_gap"


def _titles_similar(a: str, b: str) -> bool:
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap > 0.5


def score_topic(title: str, category: str, description: str = "") -> TopicScore:
    """Score a topic with a 4-dimension composite (0-100)."""
    viral = _score_viral_potential(title)
    demand = _score_search_demand(title, category)
    comp = _score_competition(title, category)
    revenue = _score_revenue_potential(category)
    total = viral + demand + comp + revenue  # each 0-25, total 0-100

    hook = _suggest_hook(title)

    reasoning_parts = []
    if viral >= 20:
        reasoning_parts.append("strong viral hooks")
    elif viral <= 10:
        reasoning_parts.append("weak title hooks")
    if demand >= 18:
        reasoning_parts.append("high search demand")
    if comp >= 20:
        reasoning_parts.append("low competition")
    elif comp <= 8:
        reasoning_parts.append("high competition")
    if revenue >= 20:
        reasoning_parts.append(f"high CPM (${CPM_RATES.get(category, 8)}/1k)")

    return TopicScore(
        total=min(100, total),
        viral_potential=viral,
        search_demand=demand,
        competition=comp,
        revenue_potential=revenue,
        hook_formula=hook,
        category=category,
        reasoning="; ".join(reasoning_parts) if reasoning_parts else "average potential",
    )


def rank_topics(candidates: list[dict]) -> list[dict]:
    """Score and rank candidate topics. Returns sorted by total score.

    Filters out topics below 30/100 (not worth producing).
    Each candidate needs: {"title": str, "category": str}
    """
    scored = []
    for c in candidates:
        title = c.get("title", "")
        category = c.get("category", "AI News")
        if not title:
            continue
        ts = score_topic(title, category, c.get("description", ""))
        scored.append({**c, "topic_score": asdict(ts)})

    scored.sort(key=lambda x: x["topic_score"]["total"], reverse=True)

    # Filter below threshold
    above_threshold = [s for s in scored if s["topic_score"]["total"] >= 30]
    below = [s for s in scored if s["topic_score"]["total"] < 30]

    if below:
        logger.info(f"[SCORER] Filtered {len(below)} low-scoring topics: {[b['title'][:40] for b in below]}")

    return above_threshold


def get_smart_category_slot() -> str:
    """Pick the best category to produce NEXT based on CPM, freshness, and balance.

    Returns the category name.
    """
    try:
        from utils.pillar_manager import get_pillar_balance, CPM_RATES as pillar_cpm
        balance = get_pillar_balance()
    except Exception:
        balance = {}

    best_cat = "AI News"
    best_score = -1

    for cat in VALID_CATEGORIES:
        cpm = CPM_RATES.get(cat, 8)
        b = balance.get(cat, {})

        # Revenue weight: CPM normalized to 0-25
        revenue_w = min(25, cpm)

        # Freshness: days since last post (more days = higher score)
        last_post = b.get("last_post")
        if last_post:
            try:
                days_since = (datetime.utcnow() - datetime.fromisoformat(last_post)).days
            except Exception:
                days_since = 14
        else:
            days_since = 30  # never posted = highest freshness
        freshness_w = min(25, days_since * 2)

        # Balance: how underrepresented (gap < 0 = needs more)
        gap = b.get("gap", 0)
        balance_w = min(25, max(0, int(-gap * 100 + 12)))

        total = revenue_w + freshness_w + balance_w

        if total > best_score:
            best_score = total
            best_cat = cat

    logger.info(f"[SCORER] Smart category slot: {best_cat} (score: {best_score})")
    return best_cat


def record_topic_score(video_id: str, title: str, category: str, score: int, views: int = 0):
    """Record a topic's score for future analysis."""
    data = _load_scores()
    data["scored_topics"].append({
        "video_id": video_id,
        "title": title,
        "category": category,
        "score": score,
        "views": views,
        "timestamp": datetime.utcnow().isoformat(),
    })
    data["scored_topics"] = data["scored_topics"][-500:]

    # Update category stats
    if category not in data["category_stats"]:
        data["category_stats"][category] = {"avg_score": 0, "count": 0, "total_score": 0}
    cs = data["category_stats"][category]
    cs["count"] += 1
    cs["total_score"] += score
    cs["avg_score"] = round(cs["total_score"] / cs["count"])

    _save_scores(data)
