import re
from utils.youtube_upload import get_youtube_credentials, fetch_video_stats
from utils.firebase_status import get_firestore_client, update_video_analytics, log_activity


def _extract_youtube_id(video_data: dict) -> str:
    for key in ('youtube_id', 'yt_video_id'):
        val = video_data.get(key)
        if val and len(val) == 11:
            return val
    publish_urls = video_data.get('publish_urls', {})
    yt_url = publish_urls.get('youtube', '')
    if yt_url:
        match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', yt_url)
        if match:
            return match.group(1)
    video_url = video_data.get('video_url', '')
    if video_url:
        match = re.search(r'(?:v=|youtu\.be/|shorts/)([a-zA-Z0-9_-]{11})', video_url)
        if match:
            return match.group(1)
    return None


def pull_all_video_analytics(max_videos: int = 50):
    creds = get_youtube_credentials()
    if not creds:
        print("[ANALYTICS] No YouTube credentials available")
        return {"processed": 0, "failed": 0}

    db = get_firestore_client()
    if db is None:
        print("[ANALYTICS] No Firestore client available")
        return {"processed": 0, "failed": 0}

    videos = list(db.collection('videos').order_by('created_at', direction='DESCENDING').limit(max_videos).stream())
    print(f"[ANALYTICS] Scanning {len(videos)} recent videos for YouTube analytics")

    processed = 0
    failed = 0
    for doc in videos:
        data = doc.to_dict()
        video_id = data.get('video_id', doc.id)
        status = data.get('status', '')
        if status not in ('uploaded', 'published', 'scheduled'):
            continue

        youtube_id = _extract_youtube_id(data)
        if not youtube_id:
            print(f"[ANALYTICS] No YouTube ID for video {video_id}, skipping")
            continue

        try:
            stats = fetch_video_stats(youtube_id)
            if "error" in stats:
                failed += 1
                continue
            update_video_analytics(video_id, stats)
            processed += 1
        except Exception as e:
            print(f"[ANALYTICS] Error processing {video_id}: {e}")
            failed += 1

    msg = f"Analytics pull complete: {processed} updated, {failed} failed"
    print(f"[ANALYTICS] {msg}")
    log_activity('analytics', msg)
    return {"processed": processed, "failed": failed}
