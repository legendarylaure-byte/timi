import logging

from crewai import Agent, Task, Crew
from utils.llm_helper import get_llm
from utils.series_builder import save_series

logger = logging.getLogger(__name__)


def create_series_planner_crew(topic: str = "", category: str = ""):
    llm = get_llm(temperature=0.7, max_tokens=3000)

    planner = Agent(
        role="Content Series Strategist",
        goal="Plan multi-part educational series that maximize watch time and subscriber growth",
        backstory="""You are a YouTube content strategist specializing in tech education series.
You plan multi-part series that keep viewers watching across multiple videos,
increase channel authority, and boost algorithmic recommendations.
You know that series get 2-3x better retention than standalone videos.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    task = Task(
        description=f"""Design a 3-5 part educational video series about:

Topic: {topic}
Category: {category}

Requirements:
1. Each part should cover a distinct subtopic that builds on the previous
2. Each video should be educational and evergreen
3. Include a logical progression (beginner → advanced)
4. Each part should have a clear "what you'll learn" value prop
5. Total series should be 3-5 parts

Return EXACTLY this JSON:
{{
  "series_id": "short-hyphenated-id",
  "title": "Series Title",
  "description": "Series overview description (2-3 sentences)",
  "categories": ["{category}"],
  "parts": [
    {{
      "part": 1,
      "title": "Part 1 title",
      "description": "What this part covers",
      "estimated_duration": "shorts|long"
    }}
  ],
  "target_audience": "Beginner|Intermediate|Advanced",
  "estimated_total_watch_time_minutes": 15
}}""",
        expected_output="JSON object with series plan.",
        agent=planner,
    )

    return Crew(agents=[planner], tasks=[task], verbose=True)


def save_series_plan(series_data: dict):
    existing = {}
    try:
        from utils.series_builder import load_series
        existing = load_series()
    except Exception:
        pass
    series_id = series_data.get("series_id", f"series-{len(existing) + 1}")
    series_data["status"] = "active"
    series_data["current_part"] = 0
    series_data["videos"] = []
    existing[series_id] = series_data
    save_series(existing)

    _sync_plan_to_firestore(series_id, series_data)

    return series_id


def _sync_plan_to_firestore(series_id: str, series_data: dict):
    try:
        from utils.firebase_status import get_firestore_client
        from firebase_admin import firestore

        db = get_firestore_client()
        if db is None:
            return
        db.collection("series_plans").document(series_id).set(
            {
                "series_id": series_id,
                "title": series_data.get("title", ""),
                "description": series_data.get("description", ""),
                "categories": series_data.get("categories", []),
                "parts": series_data.get("parts", []),
                "target_audience": series_data.get("target_audience", ""),
                "estimated_total_watch_time_minutes": series_data.get(
                    "estimated_total_watch_time_minutes", 0
                ),
                "status": "active",
                "current_part": 0,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
        logger.info(f"[SERIES] Synced plan '{series_id}' to Firestore")
    except Exception as e:
        logger.warning(f"[SERIES] Firestore sync failed: {e}")
