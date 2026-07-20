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


def _llm_plan(analytics_context: str, calendar_context: str, seasonal: str, extra_context: str = "") -> Optional[list]:
    from utils.llm_client import generate_completion

    extra_section = f"\nAdditional context:\n{extra_context}\n" if extra_context else ""
    prompt = f"""Create a content plan for {datetime.now().strftime('%Y-%m-%d')}.

Seasonal context: {seasonal}

{analytics_context}

{calendar_context}
{extra_section}
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


from utils.scene_schema import VALID_CATEGORIES as _CATEGORIES

CONTENT_PILLARS = {
    "AI Foundations": {
        "description": "Foundational AI/ML concepts — neural networks, backpropagation, gradient descent",
        "series": ["Neural Networks Explained", "How Backpropagation Works", "Gradient Descent Visualized"],
        "ratio": 0.05,
    },
    "LLM Internals": {
        "description": "How LLMs work — tokenization, embeddings, attention, transformers, generation",
        "series": ["How LLMs Actually Work", "Attention Is All You Need", "From Token to Text"],
        "ratio": 0.05,
    },
    "Training & Data": {
        "description": "Training pipelines — RLHF, fine-tuning, LoRA, datasets, evaluation",
        "series": ["How AI Learns", "Data Pipeline Secrets", "Training at Scale"],
        "ratio": 0.04,
    },
    "AI Systems": {
        "description": "Systems — RAG, agents, multi-modal, deployment, best practices",
        "series": ["Building RAG Systems", "AI Agent Architecture", "Multi-Modal AI"],
        "ratio": 0.04,
    },
    "AI Explained": {
        "description": "Quick AI/ML concept explainers for beginners",
        "series": ["How Diffusion Works", "Transformer Architecture Explained", "Understanding LLMs"],
        "ratio": 0.08,
    },
    "Science & Technology": {
        "description": "Science discoveries, tech innovations, research breakthroughs",
        "series": ["Science Behind the Headlines", "Tech That Changed the World", "Future Technologies"],
        "ratio": 0.10,
    },
    "Space & Astronomy": {
        "description": "Space exploration, astronomy, cosmology, planetary science",
        "series": ["Journey Through Space", "The Solar System", "Cosmic Mysteries"],
        "ratio": 0.08,
    },
    "Nature & Wildlife": {
        "description": "Nature documentaries, wildlife, environmental science, conservation",
        "series": ["Wild Earth", "Animal Intelligence", "Ecosystems Explained"],
        "ratio": 0.08,
    },
    "History & Biography": {
        "description": "Historical events, biographies, ancient civilizations, world history",
        "series": ["History Untold", "Great Minds", "Civilizations Rising"],
        "ratio": 0.08,
    },
    "Health & Medicine": {
        "description": "Health science, medical breakthroughs, nutrition, wellness",
        "series": ["Body Science", "Medical Breakthroughs", "The Science of Health"],
        "ratio": 0.06,
    },
    "Business & Finance": {
        "description": "Business strategy, economics, markets, entrepreneurship",
        "series": ["Market Forces", "Startup Stories", "Economics Made Simple"],
        "ratio": 0.06,
    },
    "Programming & Software": {
        "description": "Code tutorials, software engineering, development tools",
        "series": ["Build a RAG App", "AI Agent Tutorial", "Fine-Tuning Guide"],
        "ratio": 0.08,
    },
    "Engineering & Innovation": {
        "description": "Engineering marvels, industrial design, technological breakthroughs",
        "series": ["How Things Work", "Engineering Marvels", "Innovation That Changed Us"],
        "ratio": 0.06,
    },
    "Mathematics & Logic": {
        "description": "Math concepts, logic puzzles, number theory, geometry",
        "series": ["Math in Nature", "Logic Puzzles Decoded", "The Beauty of Numbers"],
        "ratio": 0.05,
    },
    "Philosophy & Psychology": {
        "description": "Philosophical ideas, cognitive science, human behavior",
        "series": ["Thinking Deeply", "The Mind Explained", "Philosophy for Life"],
        "ratio": 0.05,
    },
    "AI News": {
        "description": "Latest AI developments and updates",
        "series": ["This Week in AI", "Model Release Roundup", "Funding & Acquisition News"],
        "ratio": 0.06,
    },
    "Tool Tutorials": {
        "description": "Software tool guides, productivity hacks, workflow tutorials",
        "series": ["Cursor IDE Mastery", "Productivity Tool Stack", "DevOps Essentials"],
        "ratio": 0.04,
    },
    "Paper Breakdowns": {
        "description": "Academic paper summaries, research analysis",
        "series": ["Paper of the Week", "Research Deep Dive", "Citation Analysis"],
        "ratio": 0.03,
    },
    "Career & Learning": {
        "description": "Career advice, learning paths, skill development",
        "series": ["Learning Roadmap", "Skill Stack Guide", "Career Pivot Stories"],
        "ratio": 0.03,
    },
}

PILLAR_NAMES = list(CONTENT_PILLARS.keys())

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

    category_cycle = PILLAR_NAMES
    videos = []

    for i, title in enumerate(seasonal_topics[:4]):
        pillar_name = category_cycle[i % len(category_cycle)]
        pillar = CONTENT_PILLARS.get(pillar_name, {})
        series_list = pillar.get("series", [])
        series_name = series_list[i // len(category_cycle) % len(series_list)] if series_list else ""
        fmt = "shorts" if i < 2 else "long"
        videos.append({
            "title": title,
            "category": pillar_name,
            "format": fmt,
            "priority": max(50, 95 - i * 5),
            "reasoning": f"Content pillar: {pillar.get('description', pillar_name)}",
        })

    return videos


def build_series_plan() -> list[dict]:
    """Build a plan of series-based videos from content pillars."""
    series_plan = []
    for pillar_name, pillar in CONTENT_PILLARS.items():
        for series_title in pillar.get("series", []):
            series_plan.append({
                "series_title": series_title,
                "pillar": pillar_name,
                "format": "long" if "Explained" in pillar_name or "Deep" in pillar_name else "shorts",
                "completed_parts": 0,
            })
    return series_plan


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


def _load_analytics_weighting() -> dict:
    """Load best_category from analytics feedback for priority weighting."""
    try:
        fb_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "analytics", "feedback_loop.json"
        )
        if os.path.exists(fb_path):
            with open(fb_path) as f:
                fb = json.load(f)
            insights = fb.get("active_insights", {})
            best_cat = insights.get("best_category")
            if best_cat:
                logger.info("[planner] Analytics weighting: boosting '%s' priority", best_cat)
                return {"best_category": best_cat}
    except Exception as e:
        logger.debug("[planner] Could not load analytics weighting: %s", e)
    return {}


def _apply_pillar_balance(plan: list) -> list:
    """Swap overrepresented pillar categories for underrepresented ones."""
    try:
        from utils.pillar_manager import get_pillar_balance, get_underrepresented_pillars
        balance = get_pillar_balance()
        underrepresented = get_underrepresented_pillars(min_gap=-0.02)

        if not underrepresented:
            return plan

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
            logger.info("[planner] Pillar-balance swap: %d categories adjusted", swap_count)
        return plan
    except Exception as e:
        logger.debug("[planner] Pillar balance skipped: %s", e)
        return plan


def generate_content_plan(force_llm: bool = False, slot: str = "", extra_context: str = "") -> list:
    logger.info("Generating content plan...")
    try:
        from utils.firebase_status import update_agent_status
        update_agent_status("scheduler", "working", "Analyzing trends and calendar data")
    except Exception:
        pass

    analytics_context = _load_analytics_context()
    calendar_context = _load_calendar_context()
    seasonal = _get_seasonal_context()

    analytics_weighting = _load_analytics_weighting()

    videos = None
    if force_llm or analytics_context or calendar_context:
        try:
            update_agent_status("scheduler", "working", "Running LLM content planning")
        except Exception:
            pass
        videos = _llm_plan(analytics_context, calendar_context, seasonal, extra_context)

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

    best_cat = analytics_weighting.get("best_category")
    if best_cat:
        for v in videos:
            if v.get("category") == best_cat:
                v["priority"] = min(100, v.get("priority", 50) + 15)
                v["reasoning"] += f" (analytics-weighted: {best_cat} is best category)"

    videos = _apply_pillar_balance(videos)

    videos.sort(key=lambda x: x.get("priority", 50), reverse=True)

    shorts = [v for v in videos if v.get("format") == "shorts"]
    longs = [v for v in videos if v.get("format") == "long"]

    slot_allocs = {
        "morning": {"shorts": 2, "longs": 0},
        "afternoon": {"shorts": 1, "longs": 0},
        "evening": {"shorts": 0, "longs": 1},
    }
    alloc = slot_allocs.get(slot, {"shorts": 1, "longs": 0})
    shorts_per_day = alloc["shorts"]
    long_per_day = alloc["longs"]

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
