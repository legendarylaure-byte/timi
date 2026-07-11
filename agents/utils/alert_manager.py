"""Centralized alert management — anomaly detection, notification dispatch."""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def send_alert(message: str, severity: str = "info", channels: Optional[list] = None) -> bool:
    """Send an alert through all configured notification channels.

    Args:
        message: Alert message text
        severity: error, warning, info, success, critical
        channels: Override channels (default: telegram + slack if configured)

    Returns:
        True if at least one channel delivered
    """
    if channels is None:
        channels = ["telegram"]

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

    hours_since = (datetime.utcnow() - last_activity).total_seconds() / 3600
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
