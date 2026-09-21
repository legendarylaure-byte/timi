"""Firestore helpers for the viral news agent config and stats."""
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _get_firestore():
    from utils.firebase_status import get_firestore_client
    return get_firestore_client()


def get_viral_config() -> dict:
    """Read viral agent config from Firestore.

    Returns dict with: active (bool), viral_threshold, viral_hold_threshold,
    viral_cooldown_hours, viral_max_per_day, telegram_bot_token, telegram_chat_id.
    Falls back to env vars if Firestore doc doesn't exist.
    """
    try:
        db = _get_firestore()
        doc = db.collection("viral_news_config").document("settings").get()
        if doc.exists:
            data = doc.to_dict()
            return {
                "active": data.get("active", True),
                "viral_threshold": data.get("viral_threshold", float(os.getenv("VIRAL_THRESHOLD", "60"))),
                "viral_hold_threshold": data.get("viral_hold_threshold", float(os.getenv("VIRAL_HOLD_THRESHOLD", "45"))),
                "viral_cooldown_hours": data.get("viral_cooldown_hours", int(os.getenv("VIRAL_COOLDOWN_HOURS", "6"))),
                "viral_max_per_day": data.get("viral_max_per_day", int(os.getenv("VIRAL_MAX_PER_DAY", "2"))),
                "telegram_bot_token": data.get("telegram_bot_token", os.getenv("TELEGRAM_BOT_TOKEN", "")),
                "telegram_chat_id": data.get("telegram_chat_id", os.getenv("TELEGRAM_CHAT_ID", "")),
                "telegram_notify_on_viral": data.get("telegram_notify_on_viral", True),
                "telegram_notify_on_failure": data.get("telegram_notify_on_failure", True),
                "telegram_notify_on_scheduled": data.get("telegram_notify_on_scheduled", True),
                "telegram_notify_on_error": data.get("telegram_notify_on_error", True),
                "npt_offset_hours": data.get("npt_offset_hours", 5.75),
            }
    except Exception as e:
        logger.warning("[viral_config] Firestore read failed: %s", e)

    # Fallback to env vars
    return {
        "active": True,
        "viral_threshold": float(os.getenv("VIRAL_THRESHOLD", "60")),
        "viral_hold_threshold": float(os.getenv("VIRAL_HOLD_THRESHOLD", "45")),
        "viral_cooldown_hours": int(os.getenv("VIRAL_COOLDOWN_HOURS", "6")),
        "viral_max_per_day": int(os.getenv("VIRAL_MAX_PER_DAY", "2")),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "telegram_notify_on_viral": True,
        "telegram_notify_on_failure": True,
        "telegram_notify_on_scheduled": True,
        "telegram_notify_on_error": True,
        "npt_offset_hours": 5.75,
    }


def set_viral_active(active: bool) -> bool:
    """Toggle the viral agent active/inactive in Firestore.

    Returns True on success.
    """
    try:
        db = _get_firestore()
        now = datetime.now(timezone.utc).isoformat()
        db.collection("viral_news_config").document("settings").set({
            "active": active,
            "last_toggled": now,
            "toggled_by": "dashboard",
        }, merge=True)
        logger.info("[viral_config] Agent set to active=%s", active)
        return True
    except Exception as e:
        logger.error("[viral_config] Failed to toggle active: %s", e)
        return False


def log_viral_activity(event: str, details: dict = None) -> bool:
    """Log an activity event to Firestore for the dashboard.

    Events: scan_complete, viral_posted, scheduled_post, error, toggle, etc.
    """
    try:
        db = _get_firestore()
        doc = {
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        db.collection("viral_news_activity").add(doc)
        return True
    except Exception as e:
        logger.warning("[viral_config] Activity log failed: %s", e)
        return False


def get_viral_stats() -> dict:
    """Get today's viral agent stats from Firestore.

    Returns: {scans_today, posts_today, viral_posts_today, scheduled_posts_today,
              errors_today, last_scan_time, highest_score_today}
    """
    try:
        db = _get_firestore()
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")

        # Count events from today
        docs = db.collection("viral_news_activity").where(
            "timestamp", ">=", f"{today_str}T00:00:00"
        ).stream()

        stats = {
            "scans_today": 0,
            "posts_today": 0,
            "viral_posts_today": 0,
            "scheduled_posts_today": 0,
            "errors_today": 0,
            "last_scan_time": None,
            "highest_score_today": 0,
            "articles_scanned_today": 0,
        }

        for d in docs:
            data = d.to_dict()
            event = data.get("event", "")
            details = data.get("details", {})
            ts = data.get("timestamp", "")

            if event == "scan_complete":
                stats["scans_today"] += 1
                stats["articles_scanned_today"] += details.get("checked", 0)
                stats["last_scan_time"] = ts
                score = details.get("highest_score", 0)
                if score > stats["highest_score_today"]:
                    stats["highest_score_today"] = score
            elif event == "viral_posted":
                stats["viral_posts_today"] += 1
                stats["posts_today"] += 1
            elif event == "scheduled_post":
                stats["scheduled_posts_today"] += 1
                stats["posts_today"] += 1
            elif event == "error":
                stats["errors_today"] += 1

        return stats
    except Exception as e:
        logger.warning("[viral_config] Stats read failed: %s", e)
        return {
            "scans_today": 0, "posts_today": 0, "viral_posts_today": 0,
            "scheduled_posts_today": 0, "errors_today": 0, "last_scan_time": None,
            "highest_score_today": 0, "articles_scanned_today": 0,
        }


def get_viral_posts(limit: int = 20) -> list:
    """Get recent viral posts from Firestore.

    Returns list of post dicts sorted by timestamp (newest first).
    """
    try:
        db = _get_firestore()
        posts = []
        docs = db.collection("viral_news_posts").order_by(
            "posted_at", direction=-1
        ).limit(limit).stream()
        for d in docs:
            data = d.to_dict()
            data["id"] = d.id
            posts.append(data)
        return posts
    except Exception as e:
        logger.warning("[viral_config] Posts read failed: %s", e)
        return []
