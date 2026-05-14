import os
import hashlib
import threading
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "youtube_token.json")
_TOKEN_LOCK = threading.Lock()


def get_youtube_credentials():
    global _TOKEN_LOCK
    with _TOKEN_LOCK:
        creds = None
        if os.path.exists(TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("[YOUTUBE] Refreshing expired token...")
                creds.refresh(Request())
                print("[YOUTUBE] Token refreshed successfully")
            else:
                if not CLIENT_ID or not CLIENT_SECRET:
                    print("[YOUTUBE] Missing YOUTUBE_CLIENT_ID or YOUTUBE_CLIENT_SECRET env vars")
                    return None
                print("[YOUTUBE] No valid token found, starting OAuth flow...")
                client_config = {
                    "installed": {
                        "client_id": CLIENT_ID,
                        "client_secret": CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                }
                flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                creds = flow.run_local_server(port=8080, open_browser=True)

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

    return creds


def upload_video_to_youtube(
    video_file: str,
    title: str,
    description: str,
    tags: list,
    thumbnail_file: str = None,
    category_id: str = "27",
    is_shorts: bool = False,
    publish_at: str = None,
) -> dict:
    if not os.path.exists(video_file):
        print(f"[YOUTUBE] Video file not found: {video_file}")
        return {"success": False, "error": f"Video file not found: {video_file}"}
    file_size = os.path.getsize(video_file)
    if file_size == 0:
        print(f"[YOUTUBE] Video file is empty: {video_file}")
        return {"success": False, "error": "Video file is empty"}
    file_hash = hashlib.md5()
    with open(video_file, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            file_hash.update(chunk)
    md5_before = file_hash.hexdigest()
    print(f"[YOUTUBE] Uploading: {title} ({file_size / 1e6:.1f} MB, md5: {md5_before[:12]}...)")
    creds = get_youtube_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    if publish_at:
        try:
            pub_dt = datetime.strptime(publish_at.replace("Z", "").replace("z", ""), "%Y-%m-%dT%H:%M:%S")
            if pub_dt < datetime.utcnow():
                print(f"[YOUTUBE] publish_at {publish_at} is in the past, uploading as public instead")
                publish_at = None
        except ValueError:
            print(f"[YOUTUBE] Could not parse publish_at: {publish_at}")

    privacy_status = "public"
    if publish_at:
        privacy_status = "private"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en",
        },
        "status": {
            "privacyStatus": privacy_status,
            "madeForKids": True,
            "selfDeclaredMadeForKids": True,
        },
    }

    if is_shorts:
        body["snippet"]["title"] = f"#Shorts {title}"
        body["snippet"]["description"] += "\n\n#shorts #kidscontent #vyomaicloud"

    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    if is_shorts:
        video_url = f"https://www.youtube.com/shorts/{video_id}"

    # Post-upload integrity check: verify file hasn't changed during upload
    file_hash = hashlib.md5()
    with open(video_file, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            file_hash.update(chunk)
    md5_after = file_hash.hexdigest()
    if md5_before != md5_after:
        print(f"[YOUTUBE] WARNING: file md5 changed during upload ({md5_before[:12]} → {md5_after[:12]})")
    else:
        print(f"[YOUTUBE] File integrity verified (md5: {md5_before[:12]})")

    if publish_at:
        try:
            youtube.videos().update(
                part="status",
                body={
                    "id": video_id,
                    "status": {
                        "privacyStatus": "private",
                        "publishAt": publish_at,
                        "madeForKids": True,
                        "selfDeclaredMadeForKids": True,
                    },
                },
            ).execute()
            print(f"Video scheduled for {publish_at}")
        except HttpError as e:
            print(f"Failed to set publish time: {e}")

    result = {
        "success": True,
        "platform": "YouTube",
        "video_id": video_id,
        "video_url": video_url,
        "title": title,
        "status": "scheduled" if publish_at else "published",
        "publish_at": publish_at,
        "upload_time": datetime.utcnow().isoformat(),
    }

    if thumbnail_file and os.path.exists(thumbnail_file):
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(thumbnail_file),
            ).execute()
            result["thumbnail_set"] = True
        except HttpError as e:
            print(f"Thumbnail upload failed: {e}")
            result["thumbnail_set"] = False

    print(f"YouTube upload complete: {video_url}")
    return result


def fetch_video_stats(video_id: str) -> dict:
    creds = get_youtube_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    try:
        response = youtube.videos().list(part="statistics,contentDetails", id=video_id).execute()
        if not response.get("items"):
            return {"error": f"Video {video_id} not found"}
        stats = response["items"][0]["statistics"]
        details = response["items"][0].get("contentDetails", {})
        duration_iso = details.get("duration", "PT0S")
        try:
            import re
            match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration_iso)
            if match:
                h, m, s = [int(g) if g else 0 for g in match.groups()]
                duration_seconds = h * 3600 + m * 60 + s
            else:
                duration_seconds = 0
        except Exception:
            duration_seconds = 0
        return {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "favorites": int(stats.get("favoriteCount", 0)),
            "duration_seconds": duration_seconds,
        }
    except HttpError as e:
        print(f"[YOUTUBE] Failed to fetch stats for video {video_id}: {e}")
        return {"error": str(e)}


def get_channel_stats() -> dict:
    creds = get_youtube_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    response = youtube.channels().list(
        part="snippet,statistics",
        mine=True,
    ).execute()

    if response.get("items"):
        channel = response["items"][0]
        return {
            "channel_name": channel["snippet"]["title"],
            "subscribers": channel["statistics"].get("subscriberCount", "0"),
            "total_views": channel["statistics"].get("viewCount", "0"),
            "video_count": channel["statistics"].get("videoCount", "0"),
            "thumbnail": channel["snippet"]["thumbnails"]["default"]["url"],
        }

    return {}


if __name__ == "__main__":
    print("=== YouTube API Test ===")
    try:
        stats = get_channel_stats()
        print("✅ Connected to YouTube!")
        print(f"Channel: {stats.get('channel_name', 'Unknown')}")
        print(f"Subscribers: {stats.get('subscribers', 'N/A')}")
        print(f"Total Views: {stats.get('total_views', 'N/A')}")
        print(f"Videos: {stats.get('video_count', 'N/A')}")
    except Exception as e:
        print(f"❌ YouTube API test failed: {e}")
        print("Run this script once to authenticate with your Google account.")
