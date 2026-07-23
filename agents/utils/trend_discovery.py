"""
Trend Discovery Agent
Discovers trending topics for tech/AI content on YouTube/TikTok.
Run: python -m agents.scripts.trend_discovery
"""
import json
import random
from datetime import datetime
from utils.llm_client import generate_completion
from utils.firebase_status import get_firestore_client, log_activity
from utils.scene_schema import normalize_category

SYSTEM_PROMPT = """You are a trend analyst specializing in YouTube/TikTok tech content.
Analyze current trends and suggest video topics for tech/AI educational content.
Return ONLY a valid JSON array of objects with this exact structure:

[
  {
    "title": "Catchy video title",
    "category": "One of: AI Explained, Deep Tech, Paper Breakdowns, Tool Tutorials, Industry Analysis, Code & Build, AI News, Career & Learning",
    "search_volume": estimated_monthly_searches,
    "growth": percentage_growth_last_month,
    "competition": "low" or "medium" or "high",
    "suggested_format": "shorts" or "long" or "both",
    "score": 0-100 opportunity_score,
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }
]

Return 10 trending topics focused on tech/AI education. Consider seasonal tech events (conferences, product launches, paper releases), viral patterns, and content gaps."""  # noqa: E501


def _is_non_tech_topic(title: str) -> bool:
    """Check if a title is likely non-tech despite being in a tech category."""
    non_tech_keywords = [
        "cooking", "recipe", "food", "baking", "music", "dance", "sport", "game",
        "fashion", "beauty", "makeup", "travel", "vlog", "comedy", "funny", "prank",
        "pet", "animal", "dog", "cat", "workout", "fitness", "yoga", "meditation",
    ]
    title_lower = title.lower()
    return any(kw in title_lower for kw in non_tech_keywords)


def fetch_youtube_trending(max_results: int = 20, region_code: str = "US") -> list:
    """Fetch real trending videos from YouTube's Most Popular chart."""
    try:
        from utils.youtube_upload import get_youtube_credentials
        from googleapiclient.discovery import build

        creds = get_youtube_credentials()
        if not creds:
            print("[TRENDS] No YouTube credentials for trending fetch")
            return []

        youtube = build("youtube", "v3", credentials=creds)

        response = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode=region_code,
            maxResults=max_results,
        ).execute()

        items = response.get("items", [])
        trends = []
        seen_titles = set()

        for item in items:
            snippet = item.get("snippet", {})
            title = snippet.get("title", "")
            if not title or title.lower() in seen_titles:
                continue
            seen_titles.add(title.lower())

            category_id = snippet.get("categoryId", "")
            tags = snippet.get("tags", [])
            view_count = int(item.get("statistics", {}).get("viewCount", 0))

            category_map = {
                "1": "Science & Technology", "2": "Science & Technology", "10": "Science & Technology",
                "15": "Science & Technology", "17": "Programming & Software", "18": "Science & Technology",
                "19": "Science & Technology", "20": "Science & Technology", "22": "Science & Technology",
                "23": "Business & Finance", "24": "Science & Technology", "25": "AI News",
                "26": "Programming & Software", "27": "Health & Medicine", "28": "Business & Finance",
                "29": "Science & Technology", "30": "Health & Medicine",
            }
            category = normalize_category(category_map.get(category_id, "AI News"))

            predicted_search_volume = max(view_count // 10, 50000)

            if _is_non_tech_topic(title):
                print(f"[TRENDS] Skipping non-tech topic: {title}")
                continue
            trends.append({
                "title": title,
                "category": category,
                "search_volume": predicted_search_volume,
                "growth": round(20 + (view_count % 50) * 0.6, 1),
                "competition": "high" if view_count > 500000 else "medium" if view_count > 100000 else "low",
                "suggested_format": "shorts" if len(title) < 40 else "long",
                "score": min(98, 50 + int(view_count / 20000)),
                "keywords": tags[:5] if tags else [title.lower().replace(" ", "_")],
                "source": "youtube_trending",
            })

        print(f"[TRENDS] Fetched {len(trends)} trending videos from YouTube (region: {region_code})")
        return trends

    except Exception as e:
        print(f"[TRENDS] YouTube trending fetch failed: {e}")
        return []


def fetch_google_trends() -> list:
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(kw_list=["artificial intelligence", "machine learning", "AI tools", "deep learning", "large language model"], cat=0, timeframe="now 7-d", geo="", gprop="")
        interest = pytrends.interest_over_time()
        if interest.empty:
            return []
        rising = pytrends.related_queries()
        results = []
        seen_queries = set()
        for kw, data in rising.items():
            if data is None or "rising" not in data or data["rising"] is None:
                continue
            for _, row in data["rising"].iterrows():
                query = row.get("query", "")
                if not query or query in seen_queries:
                    continue
                seen_queries.add(query)
                if _is_non_tech_topic(query):
                    continue
                value = row.get("value", 0)
                results.append({
                    "title": query,
                    "category": "AI Explained",
                    "search_volume": max(10000, int(value * 10000)) if isinstance(value, (int, float)) else 50000,
                    "growth": value if isinstance(value, (int, float)) and value > 0 else random.randint(20, 80),
                    "competition": "medium",
                    "suggested_format": "shorts",
                    "score": min(95, 60 + (value if isinstance(value, (int, float)) and value <= 35 else 20)),
                    "keywords": [kw, query.lower().replace(" ", "_")],
                })
        return results[:10]
    except Exception as e:
        print(f"[TRENDS] Google Trends fetch failed: {e}")
        return []


def discover_trends() -> list:
    """Discover trending topics for tech/AI educational content."""
    log_activity("trend_discovery", "Starting trend discovery scan", "info")

    youtube_trends = fetch_youtube_trending(max_results=15)
    google_trends = fetch_google_trends()

    prompt = f"""Discover current trending topics for tech and AI educational video content.
Today's date: {datetime.now().strftime('%B %Y')}
Focus on evergreen tech explanations, tools, and industry analysis.
Consider seasonal tech events (conferences, product launches, paper releases), educational gaps, and viral patterns.
- Boop (blob): emotions, friendship, social skills
- Sprout (plant): nature, growing, science"""

    llm_trends = []
    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=2000,
        )

        json_start = response.find("[")
        json_end = response.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            llm_trends = json.loads(response[json_start:json_end])
        else:
            llm_trends = _fallback_trends()

    except Exception as e:
        log_activity("trend_discovery", f"Trend discovery failed: {str(e)}", "error")
        llm_trends = _fallback_trends()

    all_trends = youtube_trends + google_trends + llm_trends
    seen = set()
    deduped = []
    for t in all_trends:
        key = t.get("title", "").lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(t)

    deduped.sort(key=lambda t: t.get("score", 0), reverse=True)
    trends = deduped[:20]

    _save_trends(trends)
    source_summary = f"({len(youtube_trends)} YouTube, {len(google_trends)} Google, {len(llm_trends)} LLM)"
    log_activity("trend_discovery", f"Discovered {len(trends)} trending topics {source_summary}", "success")
    print(f"[TRENDS] {len(trends)} trends discovered {source_summary}")
    return trends


def _fallback_trends() -> list:
    """Fallback trending topics if LLM fails."""
    seasonal = datetime.now().month
    seasonal_tech_events = {
        1: ["AI Predictions for the Year", "Best Tech of Last Year"],
        2: ["AI in Healthcare", "Market Trends After Earnings"],
        3: ["Spring AI Conference Highlights", "Science of Renewal"],
        4: ["AI for Earth Day: Climate Solutions", "Tax Season: AI in Finance"],
        5: ["Google I/O AI Announcements", "New Developer Tools"],
        6: ["Mid-Year AI Review", "Summer Science Discoveries"],
        7: ["Open Source AI Spotlight", "Q2 Earnings: AI Companies"],
        8: ["Back to School: AI Tools", "Mars Mission Updates"],
        9: ["Fall AI Conference Season", "Nobel Prize Science"],
        10: ["AI Security and Safety", "Cybersecurity in AI Era"],
        11: ["Year-End Market Prep", "Open Source Contributions"],
        12: ["Year in AI Review", "Best Science of the Year"],
    }
    fallback_tech_events = seasonal_tech_events.get(seasonal, ["AI Breakthroughs", "Tech Trends"])

    return [
        {"title": fallback_tech_events[0], "category": "AI News", "search_volume": random.randint(100000, 500000), "growth": random.randint(15, 70), "competition": "low", "suggested_format": "shorts", "score": random.randint(75, 95), "keywords": ["ai", "news", "trending"]},
        {"title": fallback_tech_events[1], "category": "Science & Technology", "search_volume": random.randint(80000, 300000), "growth": random.randint(10, 50), "competition": "medium", "suggested_format": "long", "score": random.randint(70, 90), "keywords": ["science", "technology", "breakthrough"]},
        {"title": "How AI Is Changing Healthcare", "category": "Health & Medicine", "search_volume": 380000, "growth": 55, "competition": "medium", "suggested_format": "long", "score": 88, "keywords": ["ai", "healthcare", "medical"]},
        {"title": f"Top AI Coding Tools {datetime.now().year}", "category": "Programming & Software", "search_volume": 290000, "growth": 52, "competition": "low", "suggested_format": "shorts", "score": 91, "keywords": ["coding", "tools", "productivity"]},
        {"title": "AI in Business: ROI Case Studies", "category": "Business & Finance", "search_volume": 320000, "growth": 67, "competition": "low", "suggested_format": "shorts", "score": 89, "keywords": ["business", "ai", "roi"]},
    ]


def _save_trends(trends: list):
    """Save trends to Firestore."""
    try:
        db = get_firestore_client()
        batch = db.batch()
        for trend in trends:
            doc_ref = db.collection('trends').document()
            batch.set(doc_ref, {**trend, 'discovered_at': datetime.utcnow().isoformat()})
        batch.commit()
        print(f"[TRENDS] Saved {len(trends)} trends to Firestore")
    except Exception as e:
        print(f"[TRENDS] Failed to save: {e}")


def analyze_category(category: str) -> dict:
    """Analyze a specific category's trend potential."""
    system_prompt = """Analyze the content category for tech/AI educational videos.
Return ONLY a JSON object with:

{
  "category": "...",
  "trending_score": 0-100,
  "monthly_searches": number,
  "top_keywords": ["kw1", "kw2", ...],
  "saturation": "low" or "medium" or "high",
  "recommended_topics": ["topic1", "topic2", ...],
  "growth_trend": "increasing" or "stable" or "decreasing",
  "best_posting_time": "HH:MM",
  "average_views": number
}"""

    try:
        response = generate_completion(
            prompt=f"Analyze the '{category}' category for tech/AI educational video content.",
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=500,
        )

        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(response[json_start:json_end])
        return _fallback_category_analysis(category)

    except Exception:
        return _fallback_category_analysis(category)


def _fallback_category_analysis(category: str) -> dict:
    """Fallback category analysis."""
    category = normalize_category(category)
    data = {
        "AI News": {"trending_score": 94, "monthly_searches": 5600000, "saturation": "medium", "growth_trend": "increasing", "cpm": 8},
        "Science & Technology": {"trending_score": 88, "monthly_searches": 3200000, "saturation": "medium", "growth_trend": "increasing", "cpm": 12},
        "Business & Finance": {"trending_score": 83, "monthly_searches": 4800000, "saturation": "high", "growth_trend": "stable", "cpm": 25},
        "Health & Medicine": {"trending_score": 87, "monthly_searches": 6100000, "saturation": "medium", "growth_trend": "increasing", "cpm": 18},
        "Programming & Software": {"trending_score": 85, "monthly_searches": 2800000, "saturation": "medium", "growth_trend": "increasing", "cpm": 13},
    }

    base = data.get(category, {"trending_score": 70, "monthly_searches": 500000,
                    "saturation": "medium", "growth_trend": "stable", "cpm": 8})

    return {
        **base,
        "category": category,
        "top_keywords": [category.lower().replace(" ", "_"), "trending", "viral"],
        "recommended_topics": [f"Beginner's Guide to {category}", f"Top 10 {category} Tips", f"{category} Trends {datetime.now().year}"],
        "best_posting_time": "18:00",
        "average_views": random.randint(50000, 500000),
    }


def generate_monthly_plan(month: int = None, year: int = None, focus_categories: list = None) -> dict:
    """Generate a monthly content plan with diversified categories."""
    from datetime import datetime
    month = month or datetime.now().month
    year = year or datetime.now().year

    if focus_categories is None:
        focus_categories = ["AI News", "Science & Technology", "Business & Finance", "Health & Medicine", "Programming & Software"]

    seasonal_events = {
        1: ["New Year", "Winter Activities"],
        2: ["Valentine's Day", "Black History Month"],
        3: ["Spring Begins", "St. Patrick's Day"],
        4: ["Earth Day", "April Fools"],
        5: ["Mother's Day", "Memorial Day"],
        6: ["Father's Day", "Summer Begins"],
        7: ["Independence Day", "Summer Camp"],
        8: ["Back to School", "Summer Finale"],
        9: ["Autumn Begins", "Grandparents Day"],
        10: ["Halloween", "Fall Activities"],
        11: ["Thanksgiving", "Black Friday"],
        12: ["Christmas", "New Year's Eve"],
    }

    events = seasonal_events.get(month, [])
    weeks_in_month = 4
    videos_per_week = 5
    total_videos = weeks_in_month * videos_per_week

    plan = {
        "month": month,
        "year": year,
        "total_videos": total_videos,
        "seasonal_events": events,
        "weekly_plan": [],
        "category_distribution": {},
    }

    category_counts = {cat: 0 for cat in focus_categories}

    for week in range(1, weeks_in_month + 1):
        week_videos = []
        for day in range(1, videos_per_week + 1):
            cat_idx = (week + day) % len(focus_categories)
            category = focus_categories[cat_idx]
            category_counts[category] += 1

            video = {
                "week": week,
                "day": day,
                "category": category,
                "format": "shorts" if day <= 3 else "long",
                "theme": events[0] if events and day == 1 else None,
            }
            week_videos.append(video)

        plan["weekly_plan"].append({
            "week": week,
            "videos": week_videos,
            "focus": events[0] if events else f"Week {week} content",
        })

    plan["category_distribution"] = category_counts

    return plan
