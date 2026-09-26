import re
from google.cloud import firestore
from utils.youtube_upload import get_youtube_credentials, fetch_video_stats
from utils.firebase_status import get_firestore_client, update_video_analytics, log_activity, _retry_firestore


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


def fetch_channel_daily_views(days: int = 90) -> list[dict]:
    """Daily channel view trend from YouTube Analytics.

    This is the ONLY analytics shape that works for this channel: `dimensions=day`
    with `metrics=views` returns real data, while `dimensions=video` is rejected
    ("query is not supported") and impression metrics need a Brand Account we don't
    have. So this is what actually feeds the trend/feedback loop.

    Returns a list of {'date': 'YYYY-MM-DD', 'views': int}.
    """
    creds = get_youtube_credentials()
    if not creds:
        return []
    try:
        from googleapiclient.discovery import build
        from datetime import datetime, timedelta, timezone

        analytics = build("youtubeAnalytics", "v2", credentials=creds)
        report = analytics.reports().query(
            ids="channel==MINE",
            startDate=(datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d"),
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="views",
            dimensions="day",
        ).execute()
        return [
            {"date": row[0], "views": int(row[1])}
            for row in report.get("rows", [])
            if len(row) >= 2
        ]
    except Exception as e:
        print(f"[ANALYTICS] daily views pull failed: {e}")
        return []


def pull_all_video_analytics(max_videos: int = 50):
    # NOTE: the caller reads .get("videos") — this dict must carry the rows or the
    # feedback loop silently sees an empty list and never learns anything.
    empty = {"processed": 0, "failed": 0, "videos": []}

    if not get_youtube_credentials():
        print("[ANALYTICS] No YouTube credentials available")
        return empty

    db = get_firestore_client()
    if db is None:
        print("[ANALYTICS] No Firestore client available")
        return empty

    videos = list(db.collection('videos').order_by('created_at', direction='DESCENDING').limit(max_videos).stream())
    print(f"[ANALYTICS] Scanning {len(videos)} recent videos for YouTube analytics")

    processed = 0
    failed = 0
    rows = []
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
            # analyze_recent_performance reads these keys — keep the shape stable.
            rows.append({
                'video_id': video_id,
                'title': data.get('title', ''),
                'category': data.get('category', ''),
                'format': data.get('format', ''),
                'created_at': str(data.get('created_at', '')),
                **{k: v for k, v in stats.items() if k != 'error'},
            })
            processed += 1
        except Exception as e:
            print(f"[ANALYTICS] Error processing {video_id}: {e}")
            failed += 1

    msg = f"Analytics pull complete: {processed} updated, {failed} failed"
    print(f"[ANALYTICS] {msg}")
    log_activity('analytics', msg)

    # Real (if channel-level) trend data — persisted so the feedback loop has a
    # genuine signal instead of only the per-video view counts from the Data API.
    daily = fetch_channel_daily_views(days=90)
    if daily and db is not None:
        total = sum(d['views'] for d in daily)
        recent7 = sum(d['views'] for d in daily[-7:])
        prior7 = sum(d['views'] for d in daily[-14:-7])
        trend_pct = round((recent7 - prior7) / prior7 * 100, 1) if prior7 else 0.0

        def _save_trend():
            db.collection('system').document('channel_analytics_daily').set({
                'daily': daily,
                'total_views_90d': total,
                'views_last_7d': recent7,
                'views_prev_7d': prior7,
                'wow_trend_pct': trend_pct,
                'ctr_available': False,
                'note': 'impressions/CTR need a Brand Account; dimensions=video unsupported',
                'last_updated': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        _retry_firestore("Channel daily trend", _save_trend)
        print(f"[ANALYTICS] 90d trend: {total} views total, 7d={recent7} vs prior7={prior7} ({trend_pct:+.1f}%)")

    return {"processed": processed, "failed": failed, "videos": rows}
