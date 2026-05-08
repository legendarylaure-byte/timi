import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

ANALYTICS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "analytics")
os.makedirs(ANALYTICS_DIR, exist_ok=True)
ANALYTICS_FILE = os.path.join(ANALYTICS_DIR, "video_analytics.json")

logger = logging.getLogger(__name__)


def load_analytics() -> Dict:
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load analytics: {e}")
    return {"videos": {}, "daily_stats": {}}


def save_analytics(data: Dict):
    try:
        with open(ANALYTICS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save analytics: {e}")


def track_video(video_id: str, title: str, video_type: str, url: str, score: float):
    data = load_analytics()
    now = datetime.now().strftime("%Y-%m-%d")

    if video_id not in data["videos"]:
        data["videos"][video_id] = {
            "title": title,
            "type": video_type,
            "url": url,
            "score": score,
            "created_at": now,
            "metrics": {
                "views": 0,
                "likes": 0,
                "comments": 0,
                "watch_time_seconds": 0,
                "ctr": 0.0,
                "subscribers_gained": 0
            }
        }

    if now not in data["daily_stats"]:
        data["daily_stats"][now] = {
            "videos_created": 0,
            "shorts": 0,
            "longs": 0,
            "avg_score": 0.0,
            "total_views": 0
        }

    data["daily_stats"][now]["videos_created"] += 1
    if video_type == "shorts":
        data["daily_stats"][now]["shorts"] += 1
    else:
        data["daily_stats"][now]["longs"] += 1

    save_analytics(data)
    logger.info(f"Tracked video: {title} ({video_type}) - Score: {score}")


def update_metrics(video_id: str, views: int, likes: int = 0, comments: int = 0,
                   watch_time_seconds: int = 0, ctr: float = 0.0, subscribers_gained: int = 0):
    data = load_analytics()

    if video_id in data["videos"]:
        metrics = data["videos"][video_id]["metrics"]
        metrics["views"] = views
        metrics["likes"] = likes
        metrics["comments"] = comments
        metrics["watch_time_seconds"] = watch_time_seconds
        metrics["ctr"] = ctr
        metrics["subscribers_gained"] = subscribers_gained

        date_str = data["videos"][video_id]["created_at"]
        if date_str in data["daily_stats"]:
            data["daily_stats"][date_str]["total_views"] += views - metrics.get("views", 0)

        save_analytics(data)
        logger.info(f"Updated metrics for {video_id}: {views} views, {ctr}% CTR")
        return True

    logger.warning(f"Video {video_id} not found in analytics")
    return False


def get_performance_summary(days: int = 7) -> Dict:
    data = load_analytics()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    total_views = 0
    total_videos = 0
    total_score = 0
    best_video = None
    best_score = 0

    for video_id, video_data in data["videos"].items():
        if video_data["created_at"] >= cutoff:
            total_views += video_data["metrics"]["views"]
            total_videos += 1
            total_score += video_data["score"]

            if video_data["score"] > best_score:
                best_score = video_data["score"]
                best_video = video_data["title"]

    avg_score = total_score / total_videos if total_videos > 0 else 0

    return {
        "period_days": days,
        "total_videos": total_videos,
        "total_views": total_views,
        "avg_quality_score": round(avg_score, 2),
        "best_performing": best_video,
        "best_score": best_score
    }


def get_top_performing_videos(limit: int = 5, days: int = 30) -> List[Dict]:
    data = load_analytics()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    videos = []
    for video_id, video_data in data["videos"].items():
        if video_data["created_at"] >= cutoff:
            videos.append({
                "id": video_id,
                "title": video_data["title"],
                "type": video_data["type"],
                "score": video_data["score"],
                "views": video_data["metrics"]["views"],
                "ctr": video_data["metrics"]["ctr"],
                "url": video_data["url"]
            })

    videos.sort(key=lambda x: x["views"], reverse=True)
    return videos[:limit]


def calculate_engagement_rate(video_id: str) -> float:
    data = load_analytics()

    if video_id in data["videos"]:
        metrics = data["videos"][video_id]["metrics"]
        views = metrics["views"]
        if views == 0:
            return 0.0
        engagement = (metrics["likes"] + metrics["comments"]) / views * 100
        return round(engagement, 2)

    return 0.0
