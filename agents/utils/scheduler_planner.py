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

PLANNER_SYSTEM_PROMPT = """You are a content planning analyst for a tech educational YouTube channel. Your job is to create a daily content plan that maximizes engagement and channel growth.

Rules:
1. Mix shorts (under 60s) and longs (3-8 min)
2. Prioritize topics with highest engagement from analytics
3. Consider seasonal tech events (conferences, product launches, paper releases)
4. Balance across categories — don't over-use one category
5. Follow trending AI/tech topics on social media
6. Avoid repetitive topics within the same week

Return ONLY valid JSON:
{
  "plan_date": "YYYY-MM-DD",
  "rationale": "Brief explanation of planning decisions",
  "videos": [
    {
      "title": "Video title",
      "category": "Category name",
      "format": "shorts" or "long",
      "priority": 0-100,
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
        videos = data.get("videos", {})
        if videos:
            recent = [v for v in videos.values()
                      if v.get("created_at", "") >= (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")]
            if recent:
                lines.append(f"\nLast 7 days: {len(recent)} videos produced")

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

Consider which categories need more content based on engagement data.
Avoid topics that appear in the blacklist. Prioritize underrepresented categories."""

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
    "AI Explained", "Deep Tech", "Paper Breakdowns",
    "Tool Tutorials", "Industry Analysis", "Code & Build",
    "AI News", "Career & Learning",
]

_SEASONAL_TOPICS = {
    1: ["AI Predictions for New Year", "Best Tech of Previous Year", "Getting Started with AI"],
    2: ["AI Love: Valentine's Tech", "Machine Learning Basics", "Neural Networks Explained"],
    3: ["Spring Tech Updates", "GTC Conference Highlights", "Open Source AI News"],
    4: ["Earth Day: AI for Climate", "Tech Conference Season", "AI in Sustainability"],
    5: ["Google I/O Highlights", "Summer Internship Tips", "AI Tools Roundup"],
    6: ["Mid-Year AI Review", "Best Coding Practices", "Tech Career Roadmap"],
    7: ["Open Source Spotlight", "AI in Healthcare", "Build Weekend Projects"],
    8: ["Back to Tech: Learn AI", "Fall Tech Predictions", "Study Tools Powered by AI"],
    9: ["Tech Conference Season", "AI Ethics Discussion", "Research Paper Highlights"],
    10: ["Halloween Tech Special", "AI Security", "Fall Product Releases"],
    11: ["Thanksgiving: AI Gratitude", "Open Source Contributions", "Year-End Tech Wrap"],
    12: ["Year in AI Review", "Best Tech of the Year", "Holiday Tech Gift Guide"],
}


def _fallback_plan() -> list:
    month = datetime.now().month
    seasonal_topics = _SEASONAL_TOPICS.get(month, ["AI News", "Tool Tutorial", "Tech Explained"])

    category_cycle = ["AI Explained", "Tool Tutorials", "Code & Build", "Industry Analysis", "Deep Tech", "Paper Breakdowns"]
    videos = []

    for i, title in enumerate(seasonal_topics[:4]):
        category = category_cycle[i % len(category_cycle)]
        fmt = "shorts" if i < 2 else "long"
        videos.append({
            "title": title,
            "category": category,
            "format": fmt,
            "priority": max(50, 95 - i * 5),
            "reasoning": f"Seasonal/trending tech content in {category}",
        })

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

    deduped = selected[:]

    rationale = f"Planned {len(deduped)} videos ({len([v for v in deduped if v['format'] == 'shorts'])} shorts, {len([v for v in deduped if v['format'] == 'long'])} longs)"
    save_plan(deduped, rationale)

    logger.info(f"Plan: {rationale}")
    for v in deduped:
        logger.info(f"  [{v['format']}] {v['title']} ({v['category']}) [priority {v['priority']}]")

    try:
        from utils.firebase_status import update_agent_status
        update_agent_status("scheduler", "completed", f"Planned {len(deduped)} videos for today")
    except Exception:
        pass

    return deduped
