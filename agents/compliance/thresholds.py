import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_THRESHOLDS = {
    "youtube": {"subs": 1000, "watch_hours": 4000, "shorts_views": 10_000_000},
    "tiktok": {"followers": 10_000, "views": 100_000},
    "instagram": {"followers": 10_000, "watch_mins": 60_000},
}

_cached_thresholds = None


def get_thresholds() -> dict:
    global _cached_thresholds
    if _cached_thresholds is not None:
        return _cached_thresholds

    try:
        from utils.firebase_status import get_firestore_client

        db = get_firestore_client()
        if db is not None:
            doc_ref = db.collection("config").document("thresholds")
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                _cached_thresholds = {}
                for platform in ("youtube", "tiktok", "instagram"):
                    platform_data = data.get(platform, {})
                    defaults = DEFAULT_THRESHOLDS.get(platform, {})
                    _cached_thresholds[platform] = {
                        k: platform_data.get(k, defaults[k]) for k in defaults
                    }
                return _cached_thresholds
    except Exception as e:
        logger.warning(f"Could not load thresholds from Firestore: {e}")

    _cached_thresholds = dict(DEFAULT_THRESHOLDS)
    return _cached_thresholds


def get_platform_thresholds(platform: str) -> dict:
    return get_thresholds().get(platform, {})
