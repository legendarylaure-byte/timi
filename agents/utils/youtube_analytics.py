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


def fetch_video_avd(youtube_id: str) -> float:
    """Per-video average view duration (seconds) via the Analytics API.

    Returns 0.0 when no rows exist (this channel has no per-video analytics
    rows at all — verified 09-29), so callers must fall back to the channel
    daily AVD rather than treating 0 as a real measurement.
    """
    if not youtube_id:
        return 0.0
    creds = get_youtube_credentials()
    if not creds:
        return 0.0
    try:
        from googleapiclient.discovery import build
        from datetime import datetime, timedelta, timezone

        analytics = build("youtubeAnalytics", "v2", credentials=creds)
        report = analytics.reports().query(
            ids="channel==MINE",
            startDate=(datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d"),
            endDate=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            metrics="averageViewDuration",
            dimensions="video",
            filters=f"video=={youtube_id}",
        ).execute()
        rows = report.get("rows") or []
        return float(rows[0][1]) if rows else 0.0
    except Exception as e:
        print(f"[ANALYTICS] per-video AVD failed for {youtube_id}: {e}")
        return 0.0


def fetch_channel_daily_views(days: int = 90) -> list[dict]:
    """Daily channel view trend from YouTube Analytics.

    This is the ONLY analytics shape that works for this channel: `dimensions=day`
    with `metrics=views` returns real data, while `dimensions=video` is rejected
    ("query is not supported") and impression metrics need a Brand Account we
    don't have. `averageViewDuration` IS available at the channel/day grain
    (verified 09-29) and is the only real retention signal for this channel —
    per-video AVD returns no rows. So this is what actually feeds the
    trend/feedback loop.

    Returns a list of {'date': 'YYYY-MM-DD', 'views': int, 'avg_view_duration_seconds': float}.
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
            metrics="views,averageViewDuration",
            dimensions="day",
        ).execute()
        return [
            {"date": row[0], "views": int(row[1]), "avg_view_duration_seconds": float(row[2]) if len(row) > 2 else 0.0}
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
            if "average_view_duration_seconds" not in stats:
                # Best-effort real per-video AVD; 0.0 means "no rows", which
                # update_video_analytics treats as unknown, not a measurement.
                avd = fetch_video_avd(youtube_id)
                if avd > 0:
                    stats["average_view_duration_seconds"] = avd
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
        avd_7d = round(sum(d.get('avg_view_duration_seconds', 0.0) for d in daily[-7:]) / 7, 1) if daily[-7:] else 0.0

        def _save_trend():
            db.collection('system').document('channel_analytics_daily').set({
                'daily': daily,
                'total_views_90d': total,
                'views_last_7d': recent7,
                'views_prev_7d': prior7,
                'wow_trend_pct': trend_pct,
                'avg_view_duration_7d': avd_7d,
                'ctr_available': False,
                'note': 'impressions/CTR need a Brand Account; per-video AVD returns no rows, so avg_view_duration_7d is the only genuine retention signal',
                'last_updated': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        _retry_firestore("Channel daily trend", _save_trend)
        print(f"[ANALYTICS] 90d trend: {total} views total, 7d={recent7} vs prior7={prior7} ({trend_pct:+.1f}%), avd_7d={avd_7d}s")

    return {"processed": processed, "failed": failed, "videos": rows}
