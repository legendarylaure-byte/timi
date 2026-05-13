import os
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

PLANNER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "planner")
os.makedirs(PLANNER_DIR, exist_ok=True)
PLAN_FILE = os.path.join(PLANNER_DIR, "content_plan.json")

PLANNER_SYSTEM_PROMPT = """You are a content planning analyst for a children's animated YouTube channel. Your job is to create a daily content plan that maximizes engagement and channel growth.

Characters available:
- Pixel (robot): Self-Learning, Science for Kids, Tech & AI — energetic, curious
- Nova (star): Bedtime Stories, Mythology Stories, Animated Fables — calm, dreamy
- Ziggy (rainbow): Rhymes & Songs, Colors & Shapes, DIY & Crafts — playful, silly
- Boop (blob): emotions, friendship, social skills
- Sprout (plant): nature, growing, gardening

Rules:
1. Prioritize characters with highest engagement share
2. Avoid repeating the same character twice in one day
3. Mix shorts (under 60s) and longs (8-12 min)
4. Consider seasonal events and trending topics
5. Balance across categories — don't over-use one category
6. If a character has 0 videos, give them a chance (testing new content)

Return ONLY valid JSON:
{
  "plan_date": "YYYY-MM-DD",
  "rationale": "Brief explanation of planning decisions",
  "videos": [
    {
      "title": "Video title",
      "category": "Category name",
      "format": "shorts" or "long",
      "character": "pixel" or "nova" or "ziggy" or "boop" or "sprout",
      "priority": 0-100,
      "reasoning": "Why this video was chosen"
    }
  ]
}

Generate 2-4 shorts and 1-2 longs per day."""


def _load_analytics_context() -> str:
    try:
        analytics_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "analytics", "video_analytics.json"
        )
        if not os.path.exists(analytics_file):
            return ""

        with open(analytics_file) as f:
            data = json.load(f)

        lines = []
        char_stats = data.get("character_stats", {})
        if char_stats:
            total_views = sum(c["total_views"] for c in char_stats.values()) or 1
            lines.append("Character Performance:")
            for char, stats in sorted(char_stats.items(), key=lambda x: x[1]["total_views"], reverse=True):
                share = round(stats["total_views"] / total_views * 100, 1)
                cats = ", ".join(list(stats.get("categories", {}).keys())[:2])
                lines.append(f"  {char}: {stats['video_count']} videos, {stats['total_views']} views ({share}% share), categories: {cats or 'none'}")

        videos = data.get("videos", {})
        if videos:
            recent = [v for v in videos.values()
                      if v.get("created_at", "") >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
            if recent:
                lines.append(f"\nLast 7 days: {len(recent)} videos produced")
                by_char = {}
                for v in recent:
                    c = v.get("character", "unknown")
                    by_char[c] = by_char.get(c, 0) + 1
                lines.append("  Per character: " + ", ".join(f"{c}: {n}" for c, n in by_char.items()))

        daily = data.get("daily_stats", {})
        if daily:
            last_3 = sorted(daily.keys(), reverse=True)[:3]
            lines.append("\nRecent daily stats:")
            for d in last_3:
                s = daily[d]
                lines.append(f"  {d}: {s.get('videos_created', 0)} videos, {s.get('total_views', 0)} views")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to load analytics context: {e}")
        return ""


def _load_calendar_context() -> str:
    try:
        cal_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "calendar", "content_calendar.json"
        )
        if not os.path.exists(cal_file):
            return ""

        with open(cal_file) as f:
            data = json.load(f)

        lines = []
        schedule = data.get("schedule", [])
        recent = [s for s in schedule
                  if s.get("scheduled_date", "") >= (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")]
        if recent:
            lines.append("Recent/Future Schedule:")
            for s in recent[:10]:
                lines.append(f"  [{s['status']}] {s['scheduled_date']} - {s['topic']} ({s['type']})")

        blacklist = data.get("blacklist", [])
        if blacklist:
            lines.append(f"\nBlacklisted topics ({len(blacklist)}):")
            for b in blacklist[-3:]:
                lines.append(f"  {b['topic']}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Failed to load calendar context: {e}")
        return ""


def _get_seasonal_context() -> str:
    month = datetime.now().month
    day = datetime.now().day
    events = {
        1: "New Year, Winter, Martin Luther King Day",
        2: "Valentine's Day, Black History Month, Winter Olympics",
        3: "Spring, St. Patrick's Day, International Women's Day",
        4: "Earth Day, Spring, Easter",
        5: "Mother's Day, Memorial Day, Spring flowers",
        6: "Father's Day, Summer begins, Pride Month",
        7: "Independence Day, Summer vacation, Beach",
        8: "Back to School, Summer ending",
        9: "Autumn begins, Labor Day, Grandparents Day",
        10: "Halloween, Fall activities, Harvest",
        11: "Thanksgiving, Veterans Day, Fall",
        12: "Christmas, Hanukkah, Winter holidays, New Year's Eve",
    }
    return events.get(month, "General content")


def _llm_plan(analytics_context: str, calendar_context: str, seasonal: str) -> Optional[list]:
    from utils.groq_client import generate_completion

    prompt = f"""Create a content plan for {datetime.now().strftime('%Y-%m-%d')}.

Seasonal context: {seasonal}

{analytics_context}

{calendar_context}

Consider which characters and categories need more content based on engagement data.
Avoid topics that appear in the blacklist. If a character has low video count, give them priority."""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=PLANNER_SYSTEM_PROMPT,
            temperature=0.7,
            max_tokens=2000,
        )

        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            plan = json.loads(response[json_start:json_end])
            videos = plan.get("videos", [])
            if videos:
                logger.info(f"LLM planner generated {len(videos)} videos: {plan.get('rationale', '')[:100]}")
                return videos
    except Exception as e:
        logger.warning(f"LLM planner failed: {e}")

    return None


_CATEGORIES = [
    "Self-Learning", "Science for Kids", "Tech & AI",
    "Bedtime Stories", "Mythology Stories", "Animated Fables",
    "Rhymes & Songs", "Colors & Shapes", "DIY & Crafts",
]

_CHARACTER_MAP = {
    "Self-Learning": "pixel",
    "Science for Kids": "pixel",
    "Tech & AI": "pixel",
    "Bedtime Stories": "nova",
    "Mythology Stories": "nova",
    "Animated Fables": "nova",
    "Rhymes & Songs": "ziggy",
    "Colors & Shapes": "ziggy",
    "DIY & Crafts": "ziggy",
}

_CATEGORY_KEYWORDS = {
    "pixel": ["self-learn", "science", "tech", "ai"],
    "nova": ["bedtime", "mythology", "fable", "story"],
    "ziggy": ["rhyme", "song", "color", "shape", "diy", "craft"],
    "boop": ["emotion", "friend", "social"],
    "sprout": ["nature", "garden", "grow", "plant"],
}


def _infer_category_character(category: str) -> str:
    cat_lower = category.lower()
    for char, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in cat_lower for k in keywords):
            return char
    return "pixel"

_SEASONAL_TOPICS = {
    1: ["New Year Counting Fun", "Winter Science Experiments", "Snowflake Shapes & Colors"],
    2: ["Valentine's Heart Shapes", "Love Songs for Kids", "Friendship Stories"],
    3: ["Spring Science Experiments", "Rainbow Colors Song", "St. Patrick's Day Fables"],
    4: ["Earth Day for Kids", "Spring Garden Adventure", "Baby Animals"],
    5: ["Mother's Day Stories", "Spring Flowers Colors", "Space Adventure"],
    6: ["Summer Fun Learning", "Ocean Animals Adventure", "Father's Day Songs"],
    7: ["Independence Day Colors", "Summer Science Camp", "Beach Day Shapes"],
    8: ["Back to School ABCs", "Dinosaur Discovery", "Friendship Stories"],
    9: ["Autumn Leaves Colors", "Harvest Fables", "Grandparents Day Stories"],
    10: ["Halloween Gentle Stories", "Pumpkin Shapes & Colors", "Fall Science"],
    11: ["Thanksgiving Gratitude", "Native American Stories", "Fall Harvest Songs"],
    12: ["Christmas Bedtime Stories", "Snowflake Science", "Winter Wonderland Colors"],
}


def _fallback_plan() -> list:
    month = datetime.now().month
    seasonal_topics = _SEASONAL_TOPICS.get(month, ["Fun Learning Adventures", "Bedtime Dreams", "Colors & Shapes Fun"])

    used_characters = set()
    videos = []

    pairings = [
        (seasonal_topics[0] if len(seasonal_topics) > 0 else "Fun Learning", "Self-Learning", "shorts"),
        (seasonal_topics[1] if len(seasonal_topics) > 1 else "Bedtime Stories", "Bedtime Stories", "shorts"),
        ("Why is the Sky Blue?", "Science for Kids", "shorts"),
        (seasonal_topics[2] if len(seasonal_topics) > 2 else "Rainbow Colors", "Colors & Shapes", "long"),
        ("ABC Phonics Fun", "Rhymes & Songs", "shorts"),
        ("Magical Bedtime Adventure", "Bedtime Stories", "long"),
    ]

    for title, category, fmt in pairings:
        character = _CHARACTER_MAP.get(category, "pixel")
        if character in used_characters and len(videos) < 4:
            alternate = [c for c in _CHARACTER_MAP.values() if c != character]
            if alternate:
                character = alternate[len(videos) % len(alternate)]

        videos.append({
            "title": title,
            "category": category,
            "format": fmt,
            "character": character,
            "priority": max(50, 95 - len(videos) * 5),
            "reasoning": f"Seasonal/educational content for {character}",
        })
        used_characters.add(character)

    return videos


def _load_firestore_video_history() -> dict:
    try:
        from utils.firebase_status import get_firestore_client
        db = get_firestore_client()
        if not db:
            return {}

        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        docs = db.collection("videos").where("created_at", ">=", cutoff).stream()
        counts = {}
        for doc in docs:
            d = doc.to_dict()
            cat = d.get("category", "unknown")
            counts[cat] = counts.get(cat, 0) + 1
        return counts
    except Exception as e:
        logger.debug(f"Could not load Firestore history: {e}")
        return {}


def save_plan(videos: list, rationale: str = ""):
    plan = {
        "plan_date": datetime.now().strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "rationale": rationale,
        "videos": videos,
    }
    try:
        with open(PLAN_FILE, "w") as f:
            json.dump(plan, f, indent=2)
        try:
            from utils.firebase_status import get_firestore_client
            db = get_firestore_client()
            if db:
                db.collection("system").document("content_plan").set(plan)
        except Exception:
            pass
        logger.info(f"Content plan saved: {len(videos)} videos")
    except Exception as e:
        logger.error(f"Failed to save plan: {e}")


def load_plan() -> dict:
    try:
        if os.path.exists(PLAN_FILE):
            with open(PLAN_FILE) as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load plan: {e}")
    return {"videos": []}


def generate_content_plan(force_llm: bool = False) -> list:
    logger.info("Generating content plan...")
    try:
        from utils.firebase_status import update_agent_status
        update_agent_status("scheduler", "working", "Analyzing trends and calendar data")
    except Exception:
        pass

    analytics_context = _load_analytics_context()
    calendar_context = _load_calendar_context()
    seasonal = _get_seasonal_context()

    videos = None
    if force_llm or analytics_context or calendar_context:
        try:
            update_agent_status("scheduler", "working", "Running LLM content planning")
        except Exception:
            pass
        videos = _llm_plan(analytics_context, calendar_context, seasonal)

    if not videos:
        logger.info("LLM plan unavailable, using fallback rule-based plan")
        videos = _fallback_plan()

    video_counts = _load_firestore_video_history()
    if video_counts:
        for v in videos:
            cat = v.get("category", "")
            count_7d = video_counts.get(cat, 0)
            if count_7d >= 3:
                v["priority"] = max(30, v.get("priority", 50) - 20)
                v["reasoning"] += f" (category {cat} had {count_7d} videos in 7 days)"

    videos.sort(key=lambda x: x.get("priority", 50), reverse=True)

    shorts = [v for v in videos if v.get("format") == "shorts"]
    longs = [v for v in videos if v.get("format") == "long"]

    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    selected = shorts[:max(shorts_per_day, 1)] + longs[:max(long_per_day, 1)]
    selected.sort(key=lambda x: x.get("priority", 50), reverse=True)

    used_chars = set()
    deduped = []
    for v in selected:
        char = v.get("character", "pixel")
        if char in used_chars:
            alt_char = [c for c in ["pixel", "nova", "ziggy", "boop", "sprout"] if c != char]
            v["character"] = alt_char[len(deduped) % len(alt_char)]
        used_chars.add(v["character"])
        deduped.append(v)

    rationale = f"Planned {len(deduped)} videos ({len([v for v in deduped if v['format'] == 'shorts'])} shorts, {len([v for v in deduped if v['format'] == 'long'])} longs)"
    save_plan(deduped, rationale)

    logger.info(f"Plan: {rationale}")
    for v in deduped:
        logger.info(f"  [{v['format']}] {v['title']} ({v['category']}) - {v['character']} [priority {v['priority']}]")

    try:
        from utils.firebase_status import update_agent_status
        update_agent_status("scheduler", "completed", f"Planned {len(deduped)} videos for today")
    except Exception:
        pass

    return deduped
