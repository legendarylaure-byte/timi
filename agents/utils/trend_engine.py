"""Trend Engine — multi-source trending topic discovery with scoring.

Pulls from YouTube Trending, Hacker News, Reddit, and Google Trends.
Deduplicates, scores freshness + engagement + relevance + virality,
and returns ranked topics for the channel's 5 categories.

Usage:
    from utils.trend_engine import discover_trending_topics, get_daily_digest
    trends = discover_trending_topics(hours_back=48)
    digest = get_daily_digest()
"""
import json
import os
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "trends"
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_FILE = DATA_DIR / "trend_history.json"

VALID_CATEGORIES = ["AI News", "Science & Technology", "Business & Finance", "Health & Medicine", "Programming & Software"]

# Category keywords for relevance matching
CATEGORY_KEYWORDS = {
    "AI News": ["ai", "artificial intelligence", "gpt", "llm", "openai", "google ai", "anthropic", "deepmind", "machine learning", "neural", "transformer", "chatbot", "copilot", "gemini", "claude", "meta ai"],
    "Science & Technology": ["science", "research", "discovery", "physics", "chemistry", "biology", "space", "nasa", "spacex", "quantum", "energy", "climate", "tech", "innovation", "breakthrough", "engineer", "robot"],
    "Business & Finance": ["business", "finance", "market", "stock", "economy", "startup", "funding", "ipo", "revenue", "profit", "crypto", "bitcoin", "investment", "vc", "acquisition", "merger"],
    "Health & Medicine": ["health", "medical", "drug", "fda", "clinical", "disease", "treatment", "diagnosis", "hospital", "nutrition", "mental health", "cancer", "vaccine", "genome", "biotech"],
    "Programming & Software": ["programming", "coding", "developer", "software", "github", "open source", "python", "javascript", "rust", "api", "database", "cloud", "docker", "linux", "devops", "framework"],
}


def _load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []


def _save_history(trends: list):
    history = _load_history()
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    history = [h for h in history if h.get("timestamp", "") >= cutoff]
    history.extend(trends)
    HISTORY_FILE.write_text(json.dumps(history[-500:], indent=2))


def _classify_category(title: str, description: str = "") -> str:
    """Classify a title into one of the 5 categories based on keyword matching."""
    text = (title + " " + description).lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "AI News"


def _dedupe(trends: list) -> list:
    """Deduplicate by title similarity (hash of normalized title)."""
    seen = set()
    deduped = []
    for t in trends:
        key = hashlib.md5(t.get("title", "").lower().strip().encode()).hexdigest()[:12]
        if key not in seen:
            seen.add(key)
            deduped.append(t)
    return deduped


# ── Source 1: YouTube Trending ──────────────────────────────────────────────

def _fetch_youtube_trending(max_results: int = 20) -> list:
    """YouTube Most Popular chart via Data API v3."""
    try:
        from utils.youtube_upload import get_youtube_credentials
        from googleapiclient.discovery import build

        creds = get_youtube_credentials()
        if not creds:
            return []

        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="US",
            maxResults=max_results,
        ).execute()

        trends = []
        for item in response.get("items", []):
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            desc = snippet.get("description", "")
            view_count = int(item.get("statistics", {}).get("viewCount", 0))
            category = _classify_category(title, desc)

            trends.append({
                "title": title,
                "description": desc[:200],
                "category": category,
                "source": "youtube",
                "engagement": view_count,
                "freshness_hours": max(1, int((datetime.utcnow() - datetime.fromisoformat(snippet.get("publishedAt", datetime.utcnow().isoformat()).replace("Z", "+00:00")).replace(tzinfo=None)).total_seconds() / 3600)),
                "source_url": f"https://youtube.com/watch?v={item.get('id', '')}",
            })
        logger.info(f"[TREND] YouTube: {len(trends)} trending videos")
        return trends
    except Exception as e:
        logger.warning(f"[TREND] YouTube fetch failed: {e}")
        return []


# ── Source 2: Hacker News ───────────────────────────────────────────────────

def _fetch_hacker_news(max_results: int = 30) -> list:
    """Hacker News top stories via Firebase API (free, no key)."""
    try:
        import urllib.request
        url = "https://hacker-news.firebaseio.com/v0/topstories.json"
        with urllib.request.urlopen(url, timeout=10) as resp:
            story_ids = json.loads(resp.read())[:max_results]

        trends = []
        for sid in story_ids:
            try:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{sid}.json"
                with urllib.request.urlopen(item_url, timeout=5) as resp:
                    item = json.loads(resp.read())
                title = item.get("title", "")
                score = item.get("score", 0)
                posted = datetime.fromtimestamp(item.get("time", 0))
                hours_ago = max(1, int((datetime.utcnow() - posted).total_seconds() / 3600))
                category = _classify_category(title)

                trends.append({
                    "title": title,
                    "description": "",
                    "category": category,
                    "source": "hackernews",
                    "engagement": score * 10,  # normalize HN score to ~view scale
                    "freshness_hours": hours_ago,
                    "source_url": item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                })
            except Exception:
                continue
        logger.info(f"[TREND] Hacker News: {len(trends)} stories")
        return trends
    except Exception as e:
        logger.warning(f"[TREND] HN fetch failed: {e}")
        return []


# ── Source 3: Reddit ────────────────────────────────────────────────────────

def _fetch_reddit(subreddits: list[str] = None, max_per_sub: int = 15) -> list:
    """Reddit hot posts from tech/AI subreddits (public JSON, no API key)."""
    if subreddits is None:
        subreddits = ["technology", "artificial", "programming", "MachineLearning", "science", "Futurology"]

    trends = []
    for sub in subreddits:
        try:
            import urllib.request
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={max_per_sub}"
            req = urllib.request.Request(url, headers={"User-Agent": "TimiBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            for child in data.get("data", {}).get("children", []):
                post = child.get("data", {})
                title = post.get("title", "")
                upvotes = post.get("ups", 0)
                created = datetime.fromtimestamp(post.get("created_utc", 0))
                hours_ago = max(1, int((datetime.utcnow() - created).total_seconds() / 3600))
                category = _classify_category(title, post.get("selftext", "")[:200])

                trends.append({
                    "title": title,
                    "description": post.get("selftext", "")[:200],
                    "category": category,
                    "source": f"reddit:{sub}",
                    "engagement": upvotes,
                    "freshness_hours": hours_ago,
                    "source_url": f"https://reddit.com{post.get('permalink', '')}",
                })
        except Exception as e:
            logger.warning(f"[TREND] Reddit r/{sub} failed: {e}")
            continue
    logger.info(f"[TREND] Reddit: {len(trends)} posts from {len(subreddits)} subs")
    return trends


# ── Source 4: Google Trends ─────────────────────────────────────────────────

def _fetch_google_trends() -> list:
    """Google Trends rising queries via pytrends (scraping, no API key)."""
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(
            kw_list=["artificial intelligence", "machine learning", "AI tools", "large language model", "tech news"],
            cat=0, timeframe="now 7-d", geo="", gprop="",
        )
        rising = pytrends.related_queries()
        results = []
        seen = set()
        for kw, data in rising.items():
            if data is None or "rising" not in data or data["rising"] is None:
                continue
            for _, row in data["rising"].iterrows():
                query = row.get("query", "")
                if not query or query in seen:
                    continue
                seen.add(query)
                value = row.get("value", 0)
                category = _classify_category(query)
                results.append({
                    "title": query,
                    "description": "",
                    "category": category,
                    "source": "google_trends",
                    "engagement": max(10000, int(value * 10000)) if isinstance(value, (int, float)) else 50000,
                    "freshness_hours": 168,  # 7 days
                    "source_url": f"https://trends.google.com/trends/explore?q={query.replace(' ', '+')}",
                })
        logger.info(f"[TREND] Google Trends: {len(results)} rising queries")
        return results[:15]
    except Exception as e:
        logger.warning(f"[TREND] Google Trends failed: {e}")
        return []


# ── Scoring ─────────────────────────────────────────────────────────────────

def _score_trend(trend: dict) -> dict:
    """Score a trend on 4 dimensions (0-100 each, weighted total 0-100)."""
    # Freshness: newer = higher (exponential decay, 48h half-life)
    hours = trend.get("freshness_hours", 24)
    freshness = max(0, 100 * (0.5 ** (hours / 48)))

    # Engagement: log-scaled, normalized to 0-100
    import math
    eng = trend.get("engagement", 0)
    engagement = min(100, math.log10(max(eng, 1)) / 7 * 100)  # 10M = 100

    # Relevance: is this in our categories? (binary bonus)
    relevance = 60 if trend.get("category") in VALID_CATEGORIES else 20

    # Virality: combination of freshness and engagement velocity
    virality = (freshness * 0.6 + engagement * 0.4) if hours < 24 else freshness * 0.3

    total = int(freshness * 0.25 + engagement * 0.30 + relevance * 0.20 + virality * 0.25)
    trend["scores"] = {
        "freshness": round(freshness),
        "engagement": round(engagement),
        "relevance": round(relevance),
        "virality": round(virality),
        "total": min(100, total),
    }
    return trend


# ── Main Entry Points ───────────────────────────────────────────────────────

def discover_trending_topics(hours_back: int = 48) -> list:
    """Discover and score trending topics from all 4 sources.

    Returns top 20 trends sorted by score.
    """
    logger.info(f"[TREND] Discovering trends (last {hours_back}h)...")

    all_trends = []
    all_trends.extend(_fetch_youtube_trending())
    all_trends.extend(_fetch_hacker_news())
    all_trends.extend(_fetch_reddit())
    all_trends.extend(_fetch_google_trends())

    # Filter by hours_back
    cutoff_hours = hours_back
    all_trends = [t for t in all_trends if t.get("freshness_hours", 0) <= cutoff_hours]

    # Dedupe
    deduped = _dedupe(all_trends)

    # Score
    scored = [_score_trend(t) for t in deduped]

    # Sort by total score
    scored.sort(key=lambda t: t.get("scores", {}).get("total", 0), reverse=True)

    top = scored[:20]

    # Save to history
    for t in top:
        t["timestamp"] = datetime.utcnow().isoformat()
    _save_history(top)

    source_counts = {}
    for t in top:
        src = t.get("source", "unknown")
        source_counts[src] = source_counts.get(src, 0) + 1
    logger.info(f"[TREND] {len(top)} trends scored: {source_counts}")

    return top


def score_topic_for_channel(title: str, category: str, description: str = "") -> dict:
    """Score how well a specific topic fits this channel.

    Returns dict with total score (0-100) and breakdown.
    """
    # Relevance: does it fit our categories?
    relevance = 80 if category in VALID_CATEGORIES else 20

    # CPM potential
    CPM_MAP = {"Business & Finance": 25, "Health & Medicine": 18, "Programming & Software": 13, "Science & Technology": 12, "AI News": 8}
    cpm = CPM_MAP.get(category, 8)
    revenue_potential = min(100, cpm * 4)  # normalize to 0-100

    # Hook potential: title analysis
    hook = 50  # base
    title_lower = title.lower()
    if "?" in title: hook += 15  # question
    if any(w in title_lower for w in ["secret", "truth", "nobody", "actually", "really"]): hook += 10  # power words
    if any(c.isdigit() for c in title): hook += 10  # numbers
    if any(w in title_lower for w in ["vs", "compared", "better"]): hook += 10  # comparison
    if len(title.split()) <= 8: hook += 5  # concise

    # Competition: check trend history for similar topics
    history = _load_history()
    similar_count = sum(1 for h in history if _titles_similar(title, h.get("title", "")))
    competition = max(0, 100 - similar_count * 10)  # fewer similar = less competition = higher score

    total = int(relevance * 0.3 + revenue_potential * 0.25 + hook * 0.25 + competition * 0.2)

    return {
        "total": min(100, total),
        "relevance": relevance,
        "revenue_potential": revenue_potential,
        "hook_potential": min(100, hook),
        "competition": competition,
        "category": category,
        "cpm": cpm,
    }


def get_daily_digest() -> list:
    """Generate 5 ready-to-produce topic ideas from today's trends.

    Each idea includes title, category, suggested hook, and why it'll work.
    """
    trends = discover_trending_topics(hours_back=24)
    if not trends:
        return []

    # Pick top 5, diversified by category
    used_cats = set()
    digest = []
    for t in trends:
        cat = t.get("category", "AI News")
        if cat in used_cats and len(digest) < 5:
            continue
        used_cats.add(cat)
        digest.append({
            "title": t.get("title", ""),
            "category": cat,
            "source": t.get("source", ""),
            "source_url": t.get("source_url", ""),
            "score": t.get("scores", {}).get("total", 0),
            "hook_formula": _suggest_hook_for_title(t.get("title", "")),
            "why_it_works": f"Trending on {t.get('source', 'unknown')} with {t.get('scores', {}).get('engagement', 0)} engagement score, {t.get('scores', {}).get('freshness', 0)} freshness",
        })
        if len(digest) >= 5:
            break

    return digest


def _suggest_hook_for_title(title: str) -> str:
    """Suggest a hook formula based on the title pattern."""
    t = title.lower()
    if "?" in t:
        return "question"
    if any(w in t for w in ["secret", "truth", "nobody", "actually", "really", "shocking"]):
        return "pain_point"
    if any(c.isdigit() for c in t):
        return "statistic"
    if any(w in t for w in ["vs", "compared", "better", "best", "top"]):
        return "bold_claim"
    return "curiosity_gap"


def _titles_similar(a: str, b: str) -> bool:
    """Simple word-overlap similarity check."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap > 0.6


def get_trend_history(hours: int = 168) -> list:
    """Get trend history for the last N hours."""
    history = _load_history()
    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
    return [h for h in history if h.get("timestamp", "") >= cutoff]
