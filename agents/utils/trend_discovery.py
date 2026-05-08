"""
Trend Discovery Agent
Discovers trending topics for children's content on YouTube/TikTok.
Run: python -m agents.scripts.trend_discovery
"""
import json
import random
from datetime import datetime
from utils.groq_client import generate_completion
from utils.firebase_status import get_firestore_client, log_activity

SYSTEM_PROMPT = """You are a trend analyst specializing in YouTube/TikTok content across multiple niches.
Analyze current trends and suggest video topics for both children's content and global trending categories.
Return ONLY a valid JSON array of objects with this exact structure:

[
  {
    "title": "Catchy video title",
    "category": "One of: Self-Learning, Bedtime Stories, Mythology Stories, Animated Fables, Science for Kids, Rhymes & Songs, Colors & Shapes, Tech & AI, Gaming, Cooking & Food, DIY & Crafts, Health & Wellness, Travel & Adventure, Finance & Business, Comedy & Entertainment, Music & Dance",
    "search_volume": estimated_monthly_searches,
    "growth": percentage_growth_last_month,
    "competition": "low" or "medium" or "high",
    "suggested_format": "shorts" or "long" or "both",
    "score": 0-100 opportunity_score,
    "keywords": ["keyword1", "keyword2", "keyword3"]
  }
]

Return 15 trending topics. Mix children's content (ages 1-9) with global trending categories. Consider seasonal events, viral patterns, and content gaps."""  # noqa: E501


def discover_trends() -> list:
    """Discover trending topics for children's content."""
    log_activity("trend_discovery", "Starting trend discovery scan", "info")

    prompt = f"""Discover current trending topics for children's video content.
Today's date: {datetime.now().strftime('%B %Y')}
Focus on content for ages 1-9.
Consider seasonal trends, educational gaps, and viral patterns."""

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
            trends = json.loads(response[json_start:json_end])
        else:
            trends = _fallback_trends()

        _save_trends(trends)
        log_activity("trend_discovery", f"Discovered {len(trends)} trending topics", "success")
        return trends

    except Exception as e:
        log_activity("trend_discovery", f"Trend discovery failed: {str(e)}", "error")
        return _fallback_trends()


def _fallback_trends() -> list:
    """Fallback trending topics if Groq fails."""
    seasonal = datetime.now().month
    seasonal_topics = {
        1: ["New Year Counting Fun", "Winter Animals Bedtime"],
        2: ["Valentine Colors & Hearts", "Love Songs for Kids"],
        3: ["Spring Science Experiments", "St. Patrick Fables"],
        4: ["Earth Day for Kids", "Spring Rhymes"],
        5: ["Mother's Day Stories", "Space Adventure"],
        6: ["Summer Fun Learning", "Ocean Animals"],
        7: ["Independence Day Colors", "Summer Science Camp"],
        8: ["Back to School ABCs", "Dinosaur Discovery"],
        9: ["Autumn Leaves Colors", "Harvest Fables"],
        10: ["Halloween Gentle Stories", "Pumpkin Shapes"],
        11: ["Thanksgiving Gratitude", "Native American Stories"],
        12: ["Christmas Bedtime Stories", "Snowflake Science"],
    }

    topics = seasonal_topics.get(seasonal, ["Fun Learning Adventures", "Bedtime Dreams"])

    global_trends = [
        {"title": "AI Tools That Will Change 2025", "category": "Tech & AI", "search_volume": 890000, "growth": 120,
            "competition": "medium", "suggested_format": "long", "score": 96, "keywords": ["AI", "tools", "future", "technology"]},  # noqa: E501
        {"title": "5-Minute Healthy Breakfast Ideas", "category": "Cooking & Food", "search_volume": 650000, "growth": 45,  # noqa: E501
            "competition": "low", "suggested_format": "shorts", "score": 88, "keywords": ["breakfast", "healthy", "quick", "recipes"]},  # noqa: E501
        {"title": "Hidden Gems in Southeast Asia", "category": "Travel & Adventure", "search_volume": 420000, "growth": 67,  # noqa: E501
            "competition": "medium", "suggested_format": "long", "score": 85, "keywords": ["travel", "asia", "budget", "adventure"]},  # noqa: E501
        {"title": "10-Minute Home Workout No Equipment", "category": "Health & Wellness", "search_volume": 1200000, "growth": 38,  # noqa: E501
            "competition": "high", "suggested_format": "shorts", "score": 82, "keywords": ["workout", "home", "fitness", "no equipment"]},  # noqa: E501
        {"title": "Beginner's Guide to Crypto Investing", "category": "Finance & Business", "search_volume": 780000, "growth": 55,  # noqa: E501
            "competition": "high", "suggested_format": "long", "score": 79, "keywords": ["crypto", "investing", "beginner", "finance"]},  # noqa: E501
        {"title": "DIY Room Decor Under $20", "category": "DIY & Crafts", "search_volume": 530000, "growth": 42,
            "competition": "low", "suggested_format": "shorts", "score": 91, "keywords": ["DIY", "room decor", "budget", "crafts"]},  # noqa: E501
        {"title": "Funniest Pet Fails Compilation", "category": "Comedy & Entertainment", "search_volume": 2100000, "growth": 28,  # noqa: E501
            "competition": "high", "suggested_format": "shorts", "score": 87, "keywords": ["pets", "funny", "fails", "compilation"]},  # noqa: E501
        {"title": "Learn Guitar in 30 Days", "category": "Music & Dance", "search_volume": 340000, "growth": 51,
            "competition": "medium", "suggested_format": "long", "score": 83, "keywords": ["guitar", "learn", "music", "30 days"]},  # noqa: E501
        {"title": "Top 10 Indie Games You Must Play", "category": "Gaming", "search_volume": 680000, "growth": 73,
            "competition": "medium", "suggested_format": "long", "score": 90, "keywords": ["indie games", "gaming", "top 10", "must play"]},  # noqa: E501
    ]

    kids_trends = [
        {"title": f"{topics[0]}", "category": "Self-Learning", "search_volume": random.randint(100000, 500000), "growth": random.randint(  # noqa: E501
            15, 70), "competition": random.choice(["low", "medium"]), "suggested_format": "shorts", "score": random.randint(75, 95), "keywords": ["learn", "kids", "fun"]},  # noqa: E501
        {"title": f"{topics[1]}", "category": "Bedtime Stories", "search_volume": random.randint(80000, 300000), "growth": random.randint(10, 50), "competition": random.choice(  # noqa: E501
            ["low", "medium", "high"]), "suggested_format": "long", "score": random.randint(70, 90), "keywords": ["bedtime", "sleep", "story"]},  # noqa: E501
        {"title": "Why is the Sky Blue?", "category": "Science for Kids", "search_volume": 410000, "growth": 45,
            "competition": "medium", "suggested_format": "shorts", "score": 94, "keywords": ["sky", "blue", "science", "why"]},  # noqa: E501
        {"title": "ABC Phonics with Animals", "category": "Self-Learning", "search_volume": 245000, "growth": 34,
            "competition": "low", "suggested_format": "shorts", "score": 92, "keywords": ["abc", "phonics", "animals"]},
        {"title": "Counting to 10 with Dinosaurs", "category": "Rhymes & Songs", "search_volume": 290000, "growth": 52,
            "competition": "low", "suggested_format": "shorts", "score": 91, "keywords": ["count", "dinosaurs", "numbers"]},  # noqa: E501
    ]

    return kids_trends + global_trends


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
    system_prompt = """Analyze the content category for children's videos.
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
            prompt=f"Analyze the '{category}' category for children's video content (ages 1-9).",
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
        "Bedtime Stories": {"trending_score": 82, "monthly_searches": 1800000, "saturation": "high", "growth_trend": "stable"},  # noqa: E501
        "Mythology Stories": {"trending_score": 75, "monthly_searches": 450000, "saturation": "low", "growth_trend": "increasing"},  # noqa: E501
        "Animated Fables": {"trending_score": 78, "monthly_searches": 890000, "saturation": "medium", "growth_trend": "stable"},  # noqa: E501
        "Science for Kids": {"trending_score": 91, "monthly_searches": 3200000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
        "Rhymes & Songs": {"trending_score": 85, "monthly_searches": 4500000, "saturation": "high", "growth_trend": "stable"},  # noqa: E501
        "Colors & Shapes": {"trending_score": 79, "monthly_searches": 1200000, "saturation": "medium", "growth_trend": "increasing"},  # noqa: E501
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
        "recommended_topics": [f"Beginner's Guide to {category}", f"Top 10 {category} Tips", f"{category} Trends 2025"],
        "best_posting_time": "18:00",
        "average_views": random.randint(50000, 500000),
    }


def generate_monthly_plan(month: int = None, year: int = None, focus_categories: list = None) -> dict:
    """Generate a monthly content plan with diversified categories."""
    from datetime import datetime
    month = month or datetime.now().month
    year = year or datetime.now().month

    if focus_categories is None:
        focus_categories = ["Self-Learning", "Bedtime Stories",
                            "Science for Kids", "Tech & AI", "Cooking & Food", "DIY & Crafts"]

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
