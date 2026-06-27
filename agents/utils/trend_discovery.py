"""
Trend Discovery Agent
Discovers trending topics for tech/AI content on YouTube/TikTok.
Run: python -m agents.scripts.trend_discovery
"""
import json
import random
from datetime import datetime
from utils.groq_client import generate_completion
from utils.firebase_status import get_firestore_client, log_activity

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
                "1": "AI Explained", "2": "Deep Tech", "10": "AI News",
                "15": "Gaming", "17": "Code & Build", "18": "Industry Analysis",
                "19": "Career & Learning", "20": "Gaming", "22": "Industry Analysis",
                "23": "Industry Analysis", "24": "Industry Analysis", "25": "AI News",
                "26": "Tool Tutorials", "27": "AI Explained", "28": "Deep Tech",
                "29": "Career & Learning", "30": "Industry Analysis",
            }
            category = category_map.get(category_id, "AI Explained")

            predicted_search_volume = max(view_count // 5, 100000)

            trends.append({
                "title": title,
                "category": category,
                "search_volume": predicted_search_volume,
                "growth": round((view_count % 100) * 0.5 + 20, 1),
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


def discover_trends() -> list:
    """Discover trending topics for tech/AI educational content."""
    log_activity("trend_discovery", "Starting trend discovery scan", "info")

    youtube_trends = fetch_youtube_trending(max_results=15)

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

    all_trends = youtube_trends + llm_trends
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
    source_summary = f"({len(youtube_trends)} YouTube, {len(llm_trends)} LLM)"
    log_activity("trend_discovery", f"Discovered {len(trends)} trending topics {source_summary}", "success")
    print(f"[TRENDS] {len(trends)} trends discovered {source_summary}")
    return trends


def _fallback_trends() -> list:
    """Fallback trending topics if Groq fails."""
    seasonal = datetime.now().month
    seasonal_tech_events = {
        1: ["AI Predictions for the New Year", "Tech Resolutions for Developers"],
        2: ["Groundbreaking AI Research This Month", "Open Source Projects to Watch"],
        3: ["Spring AI Breakthroughs", "Tech Conference Season Preview"],
        4: ["Climate Tech and AI for Earth Day", "Spring Tech Releases Roundup"],
        5: ["Summer AI Learning Paths", "Tech Conference Highlights"],
        6: ["Mid-Year AI Trends Report", "Frameworks and Tools Update"],
        7: ["Independence Day Tech History", "Summer Open Source Projects"],
        8: ["Back to School AI Tools", "Fall Tech Predictions and Roadmaps"],
        9: ["Autumn AI Research Roundup", "Developer Tools Harvest Season"],
        10: ["Cybersecurity in the AI Era", "Halloween Tech Horror Stories"],
        11: ["Thanksgiving AI: What We're Grateful For", "AI Safety and Ethics Check-in"],
        12: ["Christmas Tech Gift Guide for Devs", "Year in AI Review and Retrospective"],
    }
    fallback_tech_events = seasonal_tech_events.get(seasonal, ["AI Breakthroughs", "Tech Trends"])

    return [
        {"title": f"{fallback_tech_events[0] if len(fallback_tech_events) > 0 else 'AI Trends'}", "category": "AI Explained", "search_volume": random.randint(100000, 500000), "growth": random.randint(  # noqa: E501
            15, 70), "competition": random.choice(["low", "medium"]), "suggested_format": "shorts", "score": random.randint(75, 95), "keywords": ["ai", "explained", "tech"]},  # noqa: E501
        {"title": f"{fallback_tech_events[1] if len(fallback_tech_events) > 1 else 'Deep Tech Insights'}", "category": "Deep Tech", "search_volume": random.randint(80000, 300000), "growth": random.randint(10, 50), "competition": random.choice(  # noqa: E501
            ["low", "medium", "high"]), "suggested_format": "long", "score": random.randint(70, 90), "keywords": ["deep", "tech", "explained"]},  # noqa: E501
        {"title": "How Transformers Work", "category": "AI Explained", "search_volume": 410000, "growth": 45,
            "competition": "medium", "suggested_format": "shorts", "score": 94, "keywords": ["transformer", "attention", "neural"]},  # noqa: E501
        {"title": f"Top 5 AI Tools {datetime.now().year}", "category": "Tool Tutorials", "search_volume": 245000, "growth": 34,  # noqa: E501
            "competition": "low", "suggested_format": "shorts", "score": 92, "keywords": ["tools", "ai", "productivity"]},  # noqa: E501
        {"title": "Python for Machine Learning", "category": "Code & Build", "search_volume": 290000, "growth": 52,
            "competition": "low", "suggested_format": "shorts", "score": 91, "keywords": ["python", "ml", "tutorial"]},  # noqa: E501
        {"title": "LangChain vs LlamaIndex Compared", "category": "Code & Build", "search_volume": 320000, "growth": 67,
            "competition": "low", "suggested_format": "shorts", "score": 89, "keywords": ["langchain", "llamaindex", "llm", "framework"]},  # noqa: E501
        {"title": "Fine-Tuning LLMs on Your Own Data", "category": "Deep Tech", "search_volume": 380000, "growth": 55,
            "competition": "medium", "suggested_format": "long", "score": 88, "keywords": ["fine-tuning", "llm", "machine learning"]},  # noqa: E501
        {"title": "RAG Architecture Explained Simply", "category": "AI Explained", "search_volume": 310000, "growth": 72,
            "competition": "medium", "suggested_format": "shorts", "score": 90, "keywords": ["rag", "retrieval", "augmented", "generation"]},  # noqa: E501
        {"title": "AI Safety and Alignment Explained", "category": "AI Explained", "search_volume": 275000, "growth": 41,
            "competition": "low", "suggested_format": "long", "score": 87, "keywords": ["ai safety", "alignment", "ethics"]},  # noqa: E501
        {"title": "Building AI Agents with CrewAI", "category": "Code & Build", "search_volume": 260000, "growth": 88,
            "competition": "low", "suggested_format": "shorts", "score": 93, "keywords": ["crewai", "agents", "ai", "tutorial"]},  # noqa: E501
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
    data = {
        "Self-Learning": {"trending_score": 88, "monthly_searches": 2100000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "AI Explained": {"trending_score": 94, "monthly_searches": 5600000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Deep Tech": {"trending_score": 82, "monthly_searches": 1200000, "saturation": "low", "growth_trend": "increasing"},  # noqa: E501
        "Paper Breakdowns": {"trending_score": 78, "monthly_searches": 890000, "saturation": "low", "growth_trend": "increasing"},  # noqa: E501
        "Tech Tutorials": {"trending_score": 88, "monthly_searches": 3200000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Code & Build": {"trending_score": 85, "monthly_searches": 2800000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Industry Analysis": {"trending_score": 80, "monthly_searches": 1500000, "saturation": "medium", "growth_trend": "stable"},  # noqa: E501
        "Tech & AI": {"trending_score": 95, "monthly_searches": 5600000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Gaming": {"trending_score": 89, "monthly_searches": 8900000, "saturation": "high", "growth_trend": "stable"},
        "Cooking & Food": {"trending_score": 84, "monthly_searches": 4200000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "DIY & Crafts": {"trending_score": 81, "monthly_searches": 2800000, "saturation": "low", "growth_trend": "increasing"},  # noqa: E501
        "Health & Wellness": {"trending_score": 87, "monthly_searches": 6100000, "saturation": "high", "growth_trend": "stable"},  # noqa: E501
        "Travel & Adventure": {"trending_score": 76, "monthly_searches": 3400000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Finance & Business": {"trending_score": 83, "monthly_searches": 4800000, "saturation": "high", "growth_trend": "stable"},  # noqa: E501
        "Comedy & Entertainment": {"trending_score": 92, "monthly_searches": 12000000, "saturation": "high", "growth_trend": "stable"},  # noqa: E501
        "Music & Dance": {"trending_score": 80, "monthly_searches": 5200000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
    }

    base = data.get(category, {"trending_score": 70, "monthly_searches": 500000,
                    "saturation": "medium", "growth_trend": "stable"})

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
        focus_categories = ["AI Explained", "Deep Tech",
                            "Paper Breakdowns", "Tech Tutorials", "Code & Build", "Industry Analysis"]

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
