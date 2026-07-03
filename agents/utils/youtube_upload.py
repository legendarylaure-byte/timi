import os
import hashlib
import time
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
                try:
                    creds = flow.run_local_server(port=8080, open_browser=True)
                except Exception as _oauth_err:
                    print(f"[YOUTUBE] Local server failed ({_oauth_err}), trying console flow...")
                    creds = flow.run_console()

            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())

    return creds


def get_youtube_service() -> object | None:
    creds = get_youtube_credentials()
    if not creds:
        return None
    return build("youtube", "v3", credentials=creds)


def update_youtube_video_title(video_id: str, new_title: str) -> bool:
    try:
        youtube = get_youtube_service()
        if not youtube:
            return False
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        if not response.get("items"):
            print(f"[YOUTUBE] Video {video_id} not found for title update")
            return False
        video = response["items"][0]
        video["snippet"]["title"] = new_title
        update = youtube.videos().update(part="snippet", body=video)
        update.execute()
        print(f"[YOUTUBE] Title updated to: {new_title}")
        return True
    except Exception as e:
        print(f"[YOUTUBE] Title update failed: {e}")
        return False


def _upload_with_retry(
    youtube,
    video_file: str,
    body: dict,
) -> tuple[object, str]:
    """Upload video with retry on transient errors. Returns (response, video_id)."""
    media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    print(f"Upload progress: {int(status.progress() * 100)}%")
            video_id = response["id"]
            return response, video_id
        except (HttpError, ConnectionError, TimeoutError, OSError) as e:
            is_retryable = True
            if isinstance(e, HttpError):
                code = e.resp.status if hasattr(e, 'resp') else 0
                if code in (400, 401, 403, 404):
                    is_retryable = False
            if not is_retryable or attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) * 5
            print(f"[YOUTUBE] Upload failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
            time.sleep(wait)
            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )
    raise RuntimeError("Upload failed after all retries")


def upload_video_to_youtube(
    video_file: str,
    title: str,
    description: str,
    tags: list,
    thumbnail_file: str = None,
    category_id: str = "28",
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
    if not creds:
        return {"success": False, "error": "No YouTube credentials available"}
    youtube = build("youtube", "v3", credentials=creds)

    if publish_at:
        try:
            pub_dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
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
            "madeForKids": False,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }

    response, video_id = _upload_with_retry(youtube, video_file, body)
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

    result = {
        "success": True,
        "platform": "YouTube",
        "video_id": video_id,
        "video_url": video_url,
        "title": title,
        "publish_at": publish_at,
        "upload_time": datetime.utcnow().isoformat(),
    }

    # Set thumbnail BEFORE scheduling so default thumbnail isn't shown if it fails
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

    if publish_at:
        try:
            youtube.videos().update(
                part="status",
                body={
                    "id": video_id,
                    "status": {
                        "privacyStatus": "private",
                        "publishAt": publish_at,
                        "madeForKids": False,
                        "selfDeclaredMadeForKids": False,
                        "containsSyntheticMedia": True,
                    },
                },
            ).execute()
            print(f"Video scheduled for {publish_at}")
            result["status"] = "scheduled"
        except HttpError as e:
            print(f"Failed to set publish time: {e}")
            result["status"] = "published"
    else:
        result["status"] = "published"

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

        result = {
            "views": int(stats.get("viewCount", 0)),
            "likes": int(stats.get("likeCount", 0)),
            "comments": int(stats.get("commentCount", 0)),
            "favorites": int(stats.get("favoriteCount", 0)),
            "duration_seconds": duration_seconds,
        }

        try:
            from googleapiclient.discovery import build as analytics_build
            analytics = analytics_build("youtubeAnalytics", "v2", credentials=creds)
            report = analytics.reports().query(
                ids="channel==MINE",
                startDate="2015-01-01",
                endDate=datetime.utcnow().strftime("%Y-%m-%d"),
                metrics="estimatedImpressions,estimatedClicks,averageViewDuration",
                filters=f"video=={video_id}",
            ).execute()
            rows = report.get("rows", [])
            if rows and len(rows) > 0:
                impressions = int(rows[0][0]) if len(rows[0]) > 0 else 0
                clicks = int(rows[0][1]) if len(rows[0]) > 1 else 0
                avg_view_duration = float(rows[0][2]) if len(rows[0]) > 2 else 0.0
                result["impressions"] = impressions
                result["clicks"] = clicks
                result["ctr"] = round(clicks / max(impressions, 1) * 100, 2)
                result["average_view_duration_seconds"] = round(avg_view_duration, 1)
        except Exception:
            result["impressions"] = 0
            result["clicks"] = 0
            result["ctr"] = 0.0
            result["average_view_duration_seconds"] = 0.0

        return result
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
