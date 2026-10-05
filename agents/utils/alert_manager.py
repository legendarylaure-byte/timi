"""Centralized alert management — anomaly detection, notification dispatch."""
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Per-type cooldown. The overnight guards run every 15 minutes, so without this
# a single real outage would send the same Slack message ~52 times a night
# (15:05 -> 04:00). Only guards that pass alert_type are throttled; everything
# else keeps its fire-every-call behaviour.
#
# ponytail: in-process, so a container restart re-arms every cooldown. That is
# acceptable here -- the pipeline is one long-running container and a restart is
# itself worth an alert -- but move this dict to Firestore if alerts ever have
# to survive a restart without re-notifying.
ALERT_COOLDOWN_HOURS = float(os.getenv("ALERT_COOLDOWN_HOURS", "6"))
_alert_last_sent: dict = {}


def send_alert(
    message: str,
    severity: str = "info",
    channels: Optional[list] = None,
    alert_type: Optional[str] = None,
) -> bool:
    """Send an alert through all configured notification channels.

    Args:
        message: Alert message text
        severity: error, warning, info, success, critical
        channels: Override channels (default: telegram + slack if configured)
        alert_type: Cooldown key. When set, repeats inside ALERT_COOLDOWN_HOURS
            are suppressed, so a polling guard cannot become an alert storm.
            None (the default) means always send.

    Returns:
        True if at least one channel delivered. False when suppressed by the
        cooldown or when every channel failed -- neither means the message
        actually reached a human.
    """
    if alert_type:
        last = _alert_last_sent.get(alert_type)
        if last is not None and (time.time() - last) < ALERT_COOLDOWN_HOURS * 3600:
            logger.info(
                "[alert] suppressed %r (cooldown %.1fh)", alert_type, ALERT_COOLDOWN_HOURS
            )
            return False
    if channels is None:
        # Slack is the only reliably-working channel (telegram needs bot/notifications.py).
        channels = []
        if os.getenv("SLACK_WEBHOOK_URL"):
            channels.append("slack")

    if os.getenv("SLACK_WEBHOOK_URL"):
        if "slack" not in channels:
            channels.append("slack")

    delivered = False
    for channel in channels:
        try:
            if channel == "telegram":
                from bot.notifications import send_telegram_message
                send_telegram_message(f"[{severity.upper()}] {message}")
                delivered = True
            elif channel == "slack":
                from utils.slack_notifier import send_alert_slack
                send_alert_slack(message, severity)
                delivered = True
        except Exception as e:
            logger.warning("[alert] Failed to send via %s: %s", channel, e)

    # Stamp only after a real delivery, so a channel outage does not start a
    # cooldown that then swallows the retry once the channel recovers.
    if alert_type and delivered:
        _alert_last_sent[alert_type] = time.time()

    return delivered


def check_view_anomaly(video_id: str, actual_views: int, predicted_views: int, threshold_pct: float = 0.3) -> Optional[dict]:
    """Check if actual views deviate significantly from prediction.

    Args:
        video_id: Video identifier
        actual_views: Actual view count
        predicted_views: Predicted view count
        threshold_pct: Deviation threshold (default 30%)

    Returns:
        Alert dict if anomalous, None otherwise
    """
    if predicted_views <= 0:
        return None

    deviation = abs(actual_views - predicted_views) / predicted_views
    if deviation > threshold_pct:
        direction = "below" if actual_views < predicted_views else "above"
        return {
            "type": "view_anomaly",
            "video_id": video_id,
            "severity": "warning",
            "actual_views": actual_views,
            "predicted_views": predicted_views,
            "deviation_pct": round(deviation * 100, 1),
            "direction": direction,
            "message": f"Video {video_id}: {actual_views} views ({deviation*100:.0f}% {direction} predicted {predicted_views})",
        }
    return None


def check_pipeline_health_alert(success_rate: float, threshold: float = 0.8, min_runs: int = 5) -> Optional[dict]:
    """Check if pipeline success rate drops below threshold.

    Args:
        success_rate: Fraction of successful runs (0.0 - 1.0)
        threshold: Minimum acceptable success rate
        min_runs: Minimum number of runs before alerting

    Returns:
        Alert dict if unhealthy, None otherwise
    """
    if success_rate < threshold:
        return {
            "type": "pipeline_health",
            "severity": "error",
            "success_rate": round(success_rate * 100, 1),
            "threshold": round(threshold * 100, 1),
            "message": f"Pipeline success rate {success_rate*100:.0f}% below {threshold*100:.0f}% threshold",
        }
    return None


def check_monetization_milestone(current_subs: int, milestones: list = None) -> Optional[dict]:
    """Check if a monetization milestone has been reached.

    Args:
        current_subs: Current subscriber count
        milestones: List of milestone subscriber counts

    Returns:
        Alert dict if milestone reached, None otherwise
    """
    if milestones is None:
        milestones = [100, 500, 1000, 5000, 10000, 50000, 100000]

    for m in milestones:
        if current_subs >= m:
            return {
                "type": "monetization_milestone",
                "severity": "success",
                "subscribers": current_subs,
                "milestone": m,
                "message": f"🎉 Reached {m} subscribers! Current: {current_subs}",
            }
    return None


def check_staleness(last_activity: Optional[datetime], max_hours: int = 24) -> Optional[dict]:
    """Check if the system has been inactive for too long.

    Args:
        last_activity: Datetime of last activity
        max_hours: Maximum acceptable inactivity

    Returns:
        Alert dict if stale, None otherwise
    """
    if last_activity is None:
        return None

    # Accept a naive datetime as UTC. Firestore timestamps, datetime.utcnow()
    # and several persisted records are all naive; subtracting one from
    # datetime.now(timezone.utc) raises TypeError, and that single unguarded
    # line silenced every guard scheduled after it in daily_analytics_job.
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    hours_since = (now - last_activity).total_seconds() / 3600
    if hours_since > max_hours:
        return {
            "type": "staleness",
            "severity": "warning",
            "hours_since": round(hours_since, 1),
            "max_hours": max_hours,
            "message": f"No activity for {hours_since:.0f}h (max {max_hours}h)",
        }
    return None


def process_alerts(video_id: str, actual_views: int, predicted_views: int,
                   success_rate: float, current_subs: int,
                   last_activity: Optional[datetime] = None) -> list[dict]:
    """Run all anomaly checks and send alerts for triggered ones.

    Returns list of triggered alerts.
    """
    alerts = []

    view_check = check_view_anomaly(video_id, actual_views, predicted_views)
    if view_check:
        alerts.append(view_check)

    health_check = check_pipeline_health_alert(success_rate)
    if health_check:
        alerts.append(health_check)

    milestone_check = check_monetization_milestone(current_subs)
    if milestone_check:
        alerts.append(milestone_check)

    if last_activity:
        staleness_check = check_staleness(last_activity)
        if staleness_check:
            alerts.append(staleness_check)

    for alert in alerts:
        send_alert(alert["message"], alert["severity"])
        logger.info("[alert] Triggered: %s", alert["message"])

    return alerts


# Formats actually stored on the videos collection. The old inline guard
# compared against "short", which matches nothing, so its per-format counts
# were always zero even when the total happened to be right.
_PUBLISHED_STATUSES = frozenset(
    ("uploaded", "scheduled", "published", "completed", "publishing")
)
_PUBLISHED_FORMATS = frozenset(
    ("short", "shorts", "Short", "Shorts", "long", "Long", "pillar", "news")
)


def _classify_format(video: dict) -> Optional[str]:
    """Return 'short' or 'long' for a video doc, or None if undeterminable."""
    for key in ("format", "video_format", "type"):
        raw = video.get(key)
        if isinstance(raw, str) and raw.strip():
            val = raw.strip().lower()
            if val in ("short", "shorts"):
                return "short"
            if val in ("long", "longs", "pillar", "news", "documentary"):
                return "long"
    # Fall back to the id, which encodes it: short-20260926-1 / long-...
    vid = str(video.get("video_id") or video.get("id") or "")
    if vid.startswith("short"):
        return "short"
    if vid.startswith("long"):
        return "long"
    return None


def _run_date(video: dict) -> str:
    """The run's date, taken from the id so a roll is counted as one run.

    ids are `<format>-YYYYMMDD-n`, so the date is always in the string even when
    created_at is missing or was written by a different process.
    """
    vid = str(video.get("video_id") or video.get("id") or "")
    parts = vid.split("-")
    for p in parts:
        if len(p) == 8 and p.isdigit():
            return f"{p[0:4]}-{p[4:6]}-{p[6:8]}"
    created = video.get("created_at")
    if isinstance(created, datetime):
        return created.strftime("%Y-%m-%d")
    return ""


def check_daily_volume(videos, slate: dict) -> Optional[dict]:
    """Compare the most recent run's published videos against the expected slate.

    `videos` is any iterable of video docs; only the newest run date is judged,
    so a partially-finished current run does not permanently poison the count.

    Run dates come from *every* doc, not just published ones. Filtering first
    would mean a run in which all five pipelines failed leaves no date at all,
    and the guard would fall back to judging yesterday -- which was complete --
    and report nothing. That is the exact failure this function exists to catch.

    Returns an alert dict on shortfall, else None.
    """
    # date -> all docs seen for that run
    all_by_date: dict = {}
    # date -> published docs only
    pub_by_date: dict = {}
    for v in videos or []:
        if not isinstance(v, dict):
            continue
        d = _run_date(v)
        if not d:
            continue
        all_by_date.setdefault(d, []).append(v)
        if v.get("status") in _PUBLISHED_STATUSES:
            pub_by_date.setdefault(d, []).append(v)

    target = int(slate.get("total", 0) or 0)
    target_short = int(slate.get("shorts", 0) or 0)
    target_long = int(slate.get("longs", 0) or 0)

    if not all_by_date:
        return {
            "type": "daily_volume",
            "severity": "error",
            "message": (
                f"Missed-slot warning: no videos found for the last run "
                f"(expected {target} = {target_short} short + {target_long} long)"
            ),
            "detail": {"run_date": None, "published": 0, "target": target},
        }

    run_date = max(all_by_date)
    docs = pub_by_date.get(run_date, [])

    shorts = longs = other = 0
    for v in docs:
        fmt = _classify_format(v)
        if fmt == "short":
            shorts += 1
        elif fmt == "long":
            longs += 1
        else:
            other += 1

    published = len(docs)
    target_total = target or (target_short + target_long)

    if published >= target_total and shorts >= target_short and longs >= target_long:
        return None

    missing = []
    if shorts < target_short:
        missing.append(f"{target_short - shorts} short")
    if longs < target_long:
        missing.append(f"{target_long - longs} long")
    if not missing:
        missing.append(f"{target_total - published} total")

    return {
        "type": "daily_volume",
        # Nothing published at all is a hard failure, not a warning.
        "severity": "error" if published == 0 else "warning",
        "message": (
            f"Missed-slot warning for {run_date}: {published}/{target_total} published "
            f"(shorts {shorts}/{target_short}, longs {longs}/{target_long}); "
            f"missing {' + '.join(missing)}"
        ),
        "detail": {
            "run_date": run_date,
            "published": published,
            "target": target_total,
            "target_short": target_short,
            "target_long": target_long,
            "shorts": shorts,
            "longs": longs,
            "unclassified": other,
            "docs_seen": len(all_by_date[run_date]),
        },
    }


def check_run_produced_today(
    count: int,
    deadline_hour: int = 16,
    now_hour: Optional[int] = None,
) -> Optional[dict]:
    """Alert when today's run produced nothing at all, past the deadline.

    `count` is every video doc created today, regardless of publish status: this
    guard asks "did the run happen", not "did publishing succeed" -- that is
    check_daily_volume's job. Any doc counts, so a run that renders but fails to
    upload still counts as having run.

    This exists because check_daily_volume cannot cover the overnight gap. It
    fires only at zero published within a 26-hour window, so a run that dies at
    15:05 stays silent until roughly the next day's window closes -- about 24
    hours. This one fires the same evening.

    Before `deadline_hour` it always returns None: at 08:00 the day's run has
    not been attempted yet, and alerting then would be a guaranteed false alarm.

    Returns an alert dict, or None.
    """
    if now_hour is None:
        now_hour = datetime.now(timezone.utc).hour
    if now_hour < deadline_hour:
        return None
    if count > 0:
        return None

    return {
        "type": "run_produced_nothing",
        "severity": "error",
        "message": (
            f"No videos produced today (past {deadline_hour}:00 UTC). "
            "The scheduled run produced nothing."
        ),
        "detail": {"count": 0, "deadline_hour": deadline_hour, "now_hour": now_hour},
    }
