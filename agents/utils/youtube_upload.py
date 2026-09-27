import logging
import os
import hashlib
import time
import threading
from datetime import datetime, timezone
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

import re

logger = logging.getLogger(__name__)

YOUTUBE_DESC_MAX = 5000
YOUTUBE_TITLE_MAX = 100


def _sanitize_metadata(text: str, max_length: int) -> str:
    """Strip chars YouTube rejects in title/description metadata
    (control chars, null bytes, unpaired surrogates) and trim to limits."""
    if not isinstance(text, str):
        text = str(text)
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127))
    cleaned = re.sub(r"[\ud800-\udbff](?![\udc00-\udfff])", "", cleaned)
    cleaned = re.sub(r"(?<![\ud800-\udbff])[\udc00-\udfff]", "", cleaned)
    return cleaned[:max_length]


def _resolve_publish_at(publish_at: str | None) -> str | None:
    """Return None when publish_at is already past, so the upload goes public.

    ponytail: an unparseable value is passed through unchanged, exactly as before
    this was extracted. Upstream should validate; nulling it here would silently
    turn a scheduled upload into an immediate one.
    """
    if not publish_at:
        return None
    try:
        pub_dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
    except ValueError:
        print(f"[YOUTUBE] Could not parse publish_at: {publish_at}")
        return publish_at
    if pub_dt < datetime.now(timezone.utc):
        print(f"[YOUTUBE] publish_at {publish_at} is in the past, uploading as public instead")
        return None
    return publish_at


def _caption_body(video_id: str, default_language: str | None = None) -> dict:
    """Build the caption-track metadata body.

    Dubbed tracks must be labelled with the dubbed language: the SRT handed in is
    already translated, so a hardcoded "en" would mislabel a Hindi/Korean track as
    English. Defaults to en only when no language is supplied.
    """
    code = (default_language or "en").strip().lower()
    if code == "en":
        name = "English"  # source language, deliberately absent from translate.LANGUAGES
    else:
        try:
            # lazy import: translate pulls in the LLM client, unneeded just to read a name
            from utils.translate import LANGUAGES
            name = LANGUAGES.get(code, {}).get("name", code)
        except Exception:  # noqa: BLE001 - never let a label lookup fail an upload
            name = code
    return {
        "snippet": {
            "videoId": video_id,
            "language": code,
            "name": name,
            "isDraft": False,
        }
    }


CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
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


def _force_token_refresh():
    """Proactively refresh YouTube token if expired or expiring within 5 minutes."""
    if not os.path.exists(TOKEN_FILE):
        return
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            print("[YOUTUBE] Token expired, refreshing proactively...")
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as token:
                token.write(creds.to_json())
            print("[YOUTUBE] Token refreshed proactively")
    except Exception as e:
        print(f"[YOUTUBE] Proactive token refresh failed: {e}")


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
                if code in (400, 403, 404):
                    is_retryable = False
                if code == 401:
                    print("[YOUTUBE] 401 on upload, refreshing token and retrying...")
                    try:
                        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
                        if creds and creds.refresh_token:
                            creds.refresh(Request())
                            with open(TOKEN_FILE, "w") as token:
                                token.write(creds.to_json())
                            youtube = build("youtube", "v3", credentials=creds)
                            print("[YOUTUBE] Token refreshed after 401")
                    except Exception as refresh_err:
                        print(f"[YOUTUBE] Token refresh after 401 failed: {refresh_err}")
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
    subtitle_path: str = None,
    default_language: str = None,
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
    _force_token_refresh()
    creds = get_youtube_credentials()
    if not creds:
        return {"success": False, "error": "No YouTube credentials available"}
    youtube = build("youtube", "v3", credentials=creds)

    publish_at = _resolve_publish_at(publish_at)

    privacy_status = "public"
    if publish_at:
        privacy_status = "private"

    title = _sanitize_metadata(title, YOUTUBE_TITLE_MAX)
    description = _sanitize_metadata(description, YOUTUBE_DESC_MAX)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
            # A dubbed upload is not English, so the audio/caption language has
            # to be declared or YouTube mislabels the track and search ignores it.
            "defaultLanguage": default_language or "en",
            "defaultAudioLanguage": default_language or "en",
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
        "upload_time": datetime.now(timezone.utc).isoformat(),
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
            logger.warning("[YOUTUBE] Thumbnail upload failed: %s", e)
            result["thumbnail_set"] = False

    if subtitle_path and os.path.exists(subtitle_path):
        # ponytail: skip the soft CC track only when it would DOUBLE UP on burned-in
        # captions. A localized dub is the exception -- it is muxed onto a clean
        # master with nothing burned, so its translated SRT is the only caption the
        # viewer gets. `default_language` is set for dubs and left None for English,
        # so it is the signal; no extra parameter needed.
        try:
            from utils.subtitle_gen import should_upload_cc
            _is_localized_dub = bool(default_language) and default_language.lower() != "en"
            _upload_cc = _is_localized_dub or should_upload_cc("shorts" if is_shorts else "long")
        except Exception:
            _upload_cc = True
        if _upload_cc:
            caption_success = False
            for attempt in range(3):
                try:
                    youtube.captions().insert(
                        part="snippet",
                        body=_caption_body(video_id, default_language),
                        media_body=MediaFileUpload(subtitle_path, mimetype="text/plain"),
                    ).execute()
                    caption_success = True
                    logger.info("[YOUTUBE] Captions uploaded from: %s", subtitle_path)
                    break
                except HttpError as e:
                    status = e.resp.status if e.resp else 0
                    if status == 403 and attempt < 2:
                        logger.warning("[YOUTUBE] Caption upload 403 (attempt %d/3), retrying in 30s: %s", attempt + 1, e)
                        time.sleep(30)
                    else:
                        logger.warning("[YOUTUBE] Caption upload failed: %s", e)
                        break
            result["caption_set"] = caption_success
        else:
            result["caption_set"] = False
            logger.info("[YOUTUBE] Skipping soft CC upload for %s (SUBTITLE_MODE=burns for shorts)", "shorts" if is_shorts else "long")

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

        # NOTE: impressions / CTR are deliberately NOT faked here. This channel has no
        # Brand Account, so YouTube Analytics rejects the impression metrics outright
        # ("Unknown identifier (impressions)") and `annotationImpressions` returns 0 for
        # every day. `dimensions=video` is also unsupported, so per-video Analytics does
        # not exist for us. Writing ctr=0.0 would be worse than absent — the feedback
        # loop would rank every category on a fabricated 0% CTR. See
        # fetch_channel_daily_views() for the analytics data that IS available.
        # To unlock real CTR: create a Brand Account for this channel in YouTube Studio.
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
