import os
import json
import logging
from datetime import datetime
from typing import Optional

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
    series["total_parts"] = max(series.get("total_parts", 0), part_number)
    save_series(series_map)

    try:
        from utils.knowledge_graph import add_topic, add_relationship
        series_tid = series.get("title", "").lower().replace(" ", "_")
        topic_tid = title.lower().replace(" ", "_").replace("?", "").replace("/", "_")
        add_topic(topic_id=series_tid, title=series.get("title", ""), category=series.get("categories", [""])[0])
        add_topic(topic_id=topic_tid, title=title, category=series.get("categories", [""])[0], video_id=video_id)
        add_relationship(from_topic=topic_tid, to_topic=series_tid, rel_type="related")
        if part_number > 1:
            prev_videos = [v for v in series.get("videos", []) if v["part"] == part_number - 1]
            if prev_videos:
                prev_tid = prev_videos[0]["title"].lower().replace(" ", "_").replace("?", "").replace("/", "_")
                add_relationship(from_topic=topic_tid, to_topic=prev_tid, rel_type="builds_on")
    except Exception as e:
        logger.debug(f"[SERIES] KG sync failed: {e}")

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


def sync_playlist(series_id: str, youtube_service) -> bool:
    series_map = load_series()
    if series_id not in series_map:
        logger.warning(f"Series {series_id} not found for playlist sync")
        return False

    series = series_map[series_id]
    playlist_id = series.get("playlist_id")

    if not playlist_id:
        playlist_id = create_youtube_playlist(
            youtube_service,
            title=series.get("title", "Untitled Series"),
            description=generate_series_description(series),
        )
        if playlist_id:
            series["playlist_id"] = playlist_id
            save_series(series_map)
        else:
            return False

    for v in sorted(series.get("videos", []), key=lambda x: x["part"]):
        if not v.get("playlist_added") and v.get("video_id"):
            if add_video_to_playlist(youtube_service, playlist_id, v["video_id"]):
                v["playlist_added"] = True
                save_series(series_map)

    return True


def generate_series_description(series: dict, youtube_channel_url: str = "") -> str:
    parts = sorted(series.get("videos", []), key=lambda v: v["part"])
    desc = f"📚 **{series.get('title', 'Series')}**\n\n"
    if series.get("description"):
        desc += f"{series['description']}\n\n"
    total = series.get("total_parts", 0) or len(parts)
    desc += f"📖 **Full Playlist ({len(parts)}/{total} episodes):**\n"
    for v in parts:
        url = f"https://www.youtube.com/watch?v={v['video_id']}" if v.get("video_id") else ""
        desc += f"Part {v['part']}: {v['title']} {url}\n".strip() + "\n"
    return desc


def build_continuity_text(series: dict, current_part: int) -> str:
    parts = sorted(series.get("videos", []), key=lambda v: v["part"])
    prev = [v for v in parts if v["part"] < current_part]

    if not prev:
        return ""

    lines = []
    for v in prev[-3:]:
        lines.append(f"In Part {v['part']}, we covered {v['title']}.")
    lines.append(f"This is Part {current_part} — building on what we've learned.")

    return " ".join(lines)


def get_series_progress(series_id: str) -> dict:
    series_map = load_series()
    if series_id not in series_map:
        return {}

    series = series_map[series_id]
    videos = series.get("videos", [])
    total = series.get("total_parts", 0) or len(videos)

    return {
        "series_id": series_id,
        "title": series.get("title", ""),
        "status": series.get("status", "active"),
        "current_part": series.get("current_part", 0),
        "total_parts": total,
        "episodes_published": len(videos),
        "progress_pct": round(len(videos) / max(total, 1) * 100, 1) if total > 0 else 0,
        "has_playlist": bool(series.get("playlist_id")),
        "remaining": max(0, total - len(videos)),
    }


def create_series(
    series_id: str,
    title: str,
    description: str = "",
    categories: list[str] | None = None,
    total_parts: int = 5,
    thumbnail_template: str = "",
) -> dict:
    series_map = load_series()
    if series_id in series_map:
        logger.warning(f"Series {series_id} already exists")
        return series_map[series_id]

    series = {
        "series_id": series_id,
        "title": title,
        "description": description,
        "categories": categories or ["AI Explained"],
        "status": "active",
        "current_part": 0,
        "total_parts": total_parts,
        "videos": [],
        "playlist_id": None,
        "thumbnail_template": thumbnail_template,
        "outro_text": f"Subscribe for the next part of {title}!",
        "created_at": datetime.utcnow().isoformat(),
    }
    series_map[series_id] = series
    save_series(series_map)
    logger.info(f"[SERIES] Created series: {title} ({total_parts} parts)")
    return series


def generate_part_title(series_id: str, part_num: int, base_title: str = "") -> str:
    series_map = load_series()
    if series_id not in series_map:
        return base_title or f"Part {part_num}"

    series_title = series_map[series_id].get("title", "")
    subtitle = series_map[series_id].get("subtitle", "")

    if part_num == 1:
        return f"{series_title}: {subtitle or 'Introduction'}" if subtitle else f"{series_title} — Explained Simply"
    elif part_num == series_map[series_id].get("total_parts", 5):
        return f"{series_title} Part {part_num}: {base_title or 'Finale'}"
    else:
        suffix = base_title if base_title else f"Part {part_num}"
        return f"{series_title} Part {part_num}: {suffix}"
