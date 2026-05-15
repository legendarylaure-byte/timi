import json
from datetime import datetime, timezone
from utils.firebase_status import get_firestore_client, log_activity


def daily_revenue_job():
    log_activity("revenue_pipeline", "Starting daily revenue computation", "info")
    print("[REVENUE] Starting daily revenue computation")

    try:
        from utils.youtube_analytics_v2 import fetch_revenue_data

        result = fetch_revenue_data(days=30)

        if not result.get("success"):
            print(f"[REVENUE] Revenue fetch failed: {result.get('error', 'unknown')}")
            log_activity("revenue_pipeline", f"Revenue fetch failed: {result.get('error', 'unknown')}", "error")
            return False

        db = get_firestore_client()
        if not db:
            print("[REVENUE] No Firestore client available")
            return False

        total_rev = round(result.get("totalRevenue", 0), 2)
        rpm = round(result.get("rpm", 0), 2)
        revenue_data = {
            "currentMonth": result["currentMonth"],
            "estimatedYearly": result["currentMonth"] * 12,
            "totalRevenue": total_rev,
            "rpm": rpm,
            "platforms": json.dumps([
                {"platform": "YouTube Shorts", "icon": "🔴", "revenue": round(total_rev * 0.7, 2), "percentage": 70, "rpm": round(rpm * 0.8, 2)},  # noqa: E501
                {"platform": "YouTube Long", "icon": "🔴", "revenue": round(total_rev * 0.3, 2), "percentage": 30, "rpm": round(rpm * 1.2, 2)},  # noqa: E501
            ]),
            "dataSource": result.get("dataSource", "estimated"),
            "lastUpdated": datetime.now(timezone.utc).isoformat(),
        }

        db.collection("monetization").document("revenue").set(revenue_data, merge=True)

        ds = revenue_data["dataSource"]
        data_source_label = "YouTube Analytics API" if ds == "youtube_analytics_api" else "estimated (CPM-based)"
        msg = (
            f"Revenue data saved: ${revenue_data['totalRevenue']} total, "
            f"${revenue_data['currentMonth']} this month, "
            f"source: {data_source_label}"
        )
        print(f"[REVENUE] {msg}")
        log_activity("revenue_pipeline", msg, "success")
        return True

    except Exception as e:
        print(f"[REVENUE] Revenue pipeline failed: {e}")
        log_activity("revenue_pipeline", f"Revenue pipeline failed: {e}", "error")
        return False


def save_growth_snapshot():
    db = get_firestore_client()
    if not db:
        return False

    try:
        channel_doc = db.collection("system").document("channel_stats").get()
        if not channel_doc.exists:
            return False

        stats = channel_doc.to_dict()
        snapshot = {
            "subscribers": int(stats.get("subscribers", 0)),
            "total_views": int(stats.get("total_views", 0)),
            "total_watch_hours": float(stats.get("total_watch_hours", 0)),
            "video_count": int(stats.get("video_count", 0)),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        db.collection("system").document("channel_stats").collection("growth_history").add(snapshot)

        print(f"[GROWTH] Snapshot saved: {snapshot['subscribers']} subs, {snapshot['total_watch_hours']:.1f} hours")
        return True

    except Exception as e:
        print(f"[GROWTH] Failed to save snapshot: {e}")
        return False
