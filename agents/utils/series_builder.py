import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SERIES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "series")
os.makedirs(SERIES_DIR, exist_ok=True)
SERIES_FILE = os.path.join(SERIES_DIR, "series_plan.json")


def load_series() -> dict:
    if os.path.exists(SERIES_FILE):
        try:
            with open(SERIES_FILE) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load series: {e}")
    return {}


def save_series(series_data: dict):
    with open(SERIES_FILE, "w") as f:
        json.dump(series_data, f, indent=2)


def pick_series_for_category(category: str) -> dict | None:
    series_map = load_series()
    for s in series_map.values():
        if category in s.get("categories", []) and s.get("status") == "active":
            return s
    return None


def register_video_in_series(series_id: str, video_id: str, title: str, part_number: int) -> bool:
    series_map = load_series()
    if series_id not in series_map:
        logger.warning(f"Series {series_id} not found")
        return False
    series = series_map[series_id]
    if "videos" not in series:
        series["videos"] = []
    series["videos"].append({
        "video_id": video_id,
        "title": title,
        "part": part_number,
        "added_at": datetime.utcnow().isoformat(),
    })
    series["current_part"] = part_number
    save_series(series_map)
    return True


def create_youtube_playlist(youtube_service, title: str, description: str = "", privacy: str = "public") -> str | None:
    try:
        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": privacy,
            },
        }
        playlist = youtube_service.playlists().insert(part="snippet,status", body=body).execute()
        playlist_id = playlist["id"]
        logger.info(f"Created YouTube playlist: {title} ({playlist_id})")
        return playlist_id
    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        return None


def add_video_to_playlist(youtube_service, playlist_id: str, video_id: str) -> bool:
    try:
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            }
        }
        youtube_service.playlistItems().insert(part="snippet", body=body).execute()
        logger.info(f"Added {video_id} to playlist {playlist_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add video to playlist: {e}")
        return False


def generate_series_description(series: dict, youtube_channel_url: str = "") -> str:
    parts = sorted(series.get("videos", []), key=lambda v: v["part"])
    desc = f"📚 **{series.get('title', 'Series')}**\n\n"
    if series.get("description"):
        desc += f"{series['description']}\n\n"
    desc += "📖 **Full Playlist:**\n"
    for v in parts:
        url = f"https://www.youtube.com/watch?v={v['video_id']}" if v.get("video_id") else ""
        desc += f"Part {v['part']}: {v['title']} {url}\n".strip() + "\n"
    return desc
