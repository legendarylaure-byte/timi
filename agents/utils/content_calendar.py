import os
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List

CALENDAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "calendar")
os.makedirs(CALENDAR_DIR, exist_ok=True)
CALENDAR_FILE = os.path.join(CALENDAR_DIR, "content_calendar.json")
RETRY_FILE = os.path.join(CALENDAR_DIR, "retry_queue.json")

logger = logging.getLogger(__name__)


def load_calendar() -> Dict:
    if os.path.exists(CALENDAR_FILE):
        try:
            with open(CALENDAR_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load calendar: {e}")
    return {"schedule": [], "topics": [], "blacklist": []}


def save_calendar(data: Dict):
    try:
        with open(CALENDAR_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save calendar: {e}")


def load_retry_queue() -> Dict:
    if os.path.exists(RETRY_FILE):
        try:
            with open(RETRY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load retry queue: {e}")
    return {"queue": [], "max_retries": 3, "retry_delay_minutes": 5}


def save_retry_queue(data: Dict):
    try:
        with open(RETRY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save retry queue: {e}")


def schedule_topic(topic: str, video_type: str, scheduled_date: str = None, priority: str = "normal"):
    calendar = load_calendar()

    if scheduled_date is None:
        scheduled_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

    entry = {
        "id": f"topic_{int(time.time())}",
        "topic": topic,
        "type": video_type,
        "scheduled_date": scheduled_date,
        "priority": priority,
        "status": "scheduled",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "retry_count": 0
    }

    calendar["schedule"].append(entry)
    calendar["schedule"].sort(key=lambda x: x["scheduled_date"])

    save_calendar(calendar)
    logger.info(f"Scheduled {video_type}: {topic} for {scheduled_date}")
    return entry["id"]


def get_todays_topics() -> List[Dict]:
    calendar = load_calendar()
    today = datetime.now().strftime("%Y-%m-%d")

    return [
        entry for entry in calendar["schedule"]
        if entry["scheduled_date"] == today and entry["status"] == "scheduled"
    ]


def mark_topic_completed(topic_id: str, video_url: str = None):
    calendar = load_calendar()

    for entry in calendar["schedule"]:
        if entry["id"] == topic_id:
            entry["status"] = "completed"
            entry["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if video_url:
                entry["video_url"] = video_url
            save_calendar(calendar)
            logger.info(f"Marked topic {topic_id} as completed")
            return True

    logger.warning(f"Topic {topic_id} not found in calendar")
    return False


def mark_topic_failed(topic_id: str, error: str = ""):
    calendar = load_calendar()
    retry_queue = load_retry_queue()

    for entry in calendar["schedule"]:
        if entry["id"] == topic_id:
            entry["retry_count"] = entry.get("retry_count", 0) + 1
            entry["last_error"] = error

            if entry["retry_count"] >= retry_queue["max_retries"]:
                entry["status"] = "failed"
                entry["failed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.warning(f"Topic {topic_id} failed after {entry['retry_count']} retries")
            else:
                retry_entry = {
                    "id": topic_id,
                    "topic": entry["topic"],
                    "type": entry["type"],
                    "retry_count": entry["retry_count"],
                    "next_retry": (datetime.now() + timedelta(minutes=retry_queue["retry_delay_minutes"])).strftime("%Y-%m-%d %H:%M:%S"),  # noqa: E501
                    "error": error
                }
                retry_queue["queue"].append(retry_entry)
                save_retry_queue(retry_queue)
                logger.info(f"Added topic {topic_id} to retry queue (attempt {entry['retry_count']})")

            save_calendar(calendar)
            return True

    return False


def get_retry_queue() -> List[Dict]:
    retry_queue = load_retry_queue()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    due_retries = [
        entry for entry in retry_queue["queue"]
        if entry["next_retry"] <= now
    ]

    return due_retries


def process_retry(topic_id: str):
    retry_queue = load_retry_queue()

    retry_queue["queue"] = [
        entry for entry in retry_queue["queue"]
        if entry["id"] != topic_id
    ]

    save_retry_queue(retry_queue)

    calendar = load_calendar()
    for entry in calendar["schedule"]:
        if entry["id"] == topic_id:
            entry["status"] = "scheduled"
            entry["scheduled_date"] = datetime.now().strftime("%Y-%m-%d")
            break

    save_calendar(calendar)
    logger.info(f"Processing retry for topic {topic_id}")
    return True


def add_to_blacklist(topic: str, reason: str = ""):
    calendar = load_calendar()

    blacklist_entry = {
        "topic": topic,
        "reason": reason,
        "added_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    calendar["blacklist"].append(blacklist_entry)
    save_calendar(calendar)
    logger.info(f"Added to blacklist: {topic}")


def is_blacklisted(topic: str) -> bool:
    calendar = load_calendar()

    for entry in calendar["blacklist"]:
        if entry["topic"].lower() in topic.lower() or topic.lower() in entry["topic"].lower():
            return True

    return False


def get_calendar_summary(days: int = 7) -> Dict:
    calendar = load_calendar()
    today = datetime.now()

    scheduled = 0
    completed = 0
    failed = 0

    for entry in calendar["schedule"]:
        entry_date = datetime.strptime(entry["scheduled_date"], "%Y-%m-%d")
        if (today - entry_date).days <= days:
            if entry["status"] == "scheduled":
                scheduled += 1
            elif entry["status"] == "completed":
                completed += 1
            elif entry["status"] == "failed":
                failed += 1

    return {
        "period_days": days,
        "scheduled": scheduled,
        "completed": completed,
        "failed": failed,
        "retry_queue_size": len(load_retry_queue()["queue"]),
        "blacklist_size": len(calendar["blacklist"])
    }
