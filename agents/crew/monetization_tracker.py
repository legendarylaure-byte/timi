import os
import json
import logging
from datetime import datetime

from utils.llm_helper import get_llm
from crewai import Agent, Task, Crew
from compliance.thresholds import get_platform_thresholds
from firebase_admin import firestore

logger = logging.getLogger(__name__)

MONETIZATION_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "monetization")
MONETIZATION_FILE = os.path.join(MONETIZATION_DATA_DIR, "tracker.json")
os.makedirs(MONETIZATION_DATA_DIR, exist_ok=True)


def load_tracker() -> dict:
    if os.path.exists(MONETIZATION_FILE):
        try:
            with open(MONETIZATION_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "youtube": {"subs": 0, "watch_hours": 0, "shorts_views": 0, "ypp_eligible": False, "ypp_applied": False},
        "tiktok": {"followers": 0, "views": 0, "monetization_eligible": False},
        "instagram": {"followers": 0, "watch_mins": 0, "monetization_eligible": False},
        "alerts": [],
        "weekly_check_ins": [],
    }


def save_tracker(data: dict):
    data["updated_at"] = datetime.utcnow().isoformat()
    with open(MONETIZATION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    _sync_to_firestore(data)


def _sync_to_firestore(data: dict):
    try:
        from utils.firebase_status import get_firestore_client

        db = get_firestore_client()
        if db is None:
            return
        db.collection("system").document("monetization_tracker").set(
            {
                "youtube": data.get("youtube", {}),
                "tiktok": data.get("tiktok", {}),
                "instagram": data.get("instagram", {}),
                "alerts": data.get("alerts", [])[-10:],
                "last_check_in": data.get("weekly_check_ins", [{}])[-1] if data.get("weekly_check_ins") else {},
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        logger.info("[MONETIZATION] Synced tracker to Firestore")
    except Exception as e:
        logger.warning(f"[MONETIZATION] Firestore sync failed: {e}")


def update_platform_metrics(platform: str, metrics: dict):
    tracker = load_tracker()
    if platform not in tracker:
        tracker[platform] = {}
    tracker[platform].update(metrics)
    thresholds = get_platform_thresholds(platform)
    if platform == "youtube":
        subs_ok = tracker[platform].get("subs", 0) >= thresholds.get("subs", 0)
        hours_ok = tracker[platform].get("watch_hours", 0) >= thresholds.get("watch_hours", 0)
        shorts_ok = tracker[platform].get("shorts_views", 0) >= thresholds.get("shorts_views", 0)
        ypp = (subs_ok and hours_ok) or shorts_ok
        tracker[platform]["ypp_eligible"] = ypp
        if ypp and not tracker[platform].get("ypp_applied"):
            tracker["alerts"].append({
                "type": "ypp_eligible",
                "platform": "youtube",
                "message": "YouTube YPP threshold reached! Apply for monetization.",
                "timestamp": datetime.utcnow().isoformat(),
            })
            tracker[platform]["ypp_applied"] = False
    elif platform == "tiktok":
        followers_ok = tracker[platform].get("followers", 0) >= thresholds.get("followers", 0)
        views_ok = tracker[platform].get("views", 0) >= thresholds.get("views", 0)
        eligible = followers_ok and views_ok
        tracker[platform]["monetization_eligible"] = eligible
        if eligible:
            tracker["alerts"].append({
                "type": "monetization_eligible",
                "platform": "tiktok",
                "message": "TikTok Creator Marketplace eligible! Apply for monetization.",
                "timestamp": datetime.utcnow().isoformat(),
            })
    elif platform == "instagram":
        followers_ok = tracker[platform].get("followers", 0) >= thresholds.get("followers", 0)
        mins_ok = tracker[platform].get("watch_mins", 0) >= thresholds.get("watch_mins", 0)
        eligible = followers_ok and mins_ok
        tracker[platform]["monetization_eligible"] = eligible
        if eligible:
            tracker["alerts"].append({
                "type": "monetization_eligible",
                "platform": "instagram",
                "message": "Instagram Bonuses eligible! Apply for monetization.",
                "timestamp": datetime.utcnow().isoformat(),
            })
    save_tracker(tracker)
    return tracker


def weekly_check_in():
    tracker = load_tracker()
    check_in = {
        "date": datetime.utcnow().isoformat(),
        "youtube_subs": tracker.get("youtube", {}).get("subs", 0),
        "youtube_watch_hours": tracker.get("youtube", {}).get("watch_hours", 0),
        "youtube_shorts_views": tracker.get("youtube", {}).get("shorts_views", 0),
        "ypp_eligible": tracker.get("youtube", {}).get("ypp_eligible", False),
        "tiktok_followers": tracker.get("tiktok", {}).get("followers", 0),
        "instagram_followers": tracker.get("instagram", {}).get("followers", 0),
    }
    tracker["weekly_check_ins"].append(check_in)
    save_tracker(tracker)
    return check_in


def get_growth_summary() -> str:
    tracker = load_tracker()
    yt = tracker.get("youtube", {})
    yt_subs = yt.get("subs", 0)
    yt_hours = yt.get("watch_hours", 0)
    yt_shorts = yt.get("shorts_views", 0)
    ypp = yt.get("ypp_eligible", False)
    alerts = tracker.get("alerts", [])
    recent_alerts = [a for a in alerts if a.get("timestamp", "").startswith(datetime.utcnow().strftime("%Y-%m-%d"))]

    lines = [f"YouTube: {yt_subs} subs / {yt_hours}h watch time / {yt_shorts:,} Shorts views"]
    if ypp:
        lines.append("✅ YouTube YPP eligible!")
    else:
        lines.append(f"Subs: {min(100, int(yt_subs/1000*100))}% to 1K goal")
        lines.append(f"Watch Hours: {min(100, int(yt_hours/4000*100))}% to 4K goal")
    if recent_alerts:
        lines.append("\nAlerts:")
        for a in recent_alerts:
            lines.append(f"  🔔 {a['message']}")
    return "\n".join(lines)


def create_monetization_review_crew():
    llm = get_llm(temperature=0.3, max_tokens=2000)

    analyst = Agent(
        role="Monetization Growth Analyst",
        goal="Analyze channel growth trends and provide actionable recommendations to reach monetization thresholds faster",
        backstory="""You are a YouTube monetization strategist who has helped hundreds of channels
reach the YPP threshold. You analyze growth patterns and recommend specific actions
to increase subscribers, watch hours, and views.""",
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    task = Task(
        description=f"""Analyze the current monetization status and provide recommendations.

Current data:
{get_growth_summary()}

Provide recommendations covering:
1. Content strategy adjustments to boost subscriber growth
2. Best video formats for increasing watch time
3. Engagement tactics to improve viewer retention
4. Platform-specific tips for reaching each milestone faster
5. Estimated timeline to monetization at current growth rate

Return recommendations as a concise markdown summary.""",
        expected_output="Markdown summary with growth recommendations.",
        agent=analyst,
    )

    return Crew(agents=[analyst], tasks=[task], verbose=True, memory=False, planning=False, cache=False)
