"""Slack notification integration."""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def send_slack_message(text: str, webhook_url: Optional[str] = None) -> bool:
    """Send a message to Slack via webhook.

    Args:
        text: Message text (supports markdown-lite formatting)
        webhook_url: Override webhook URL, defaults to SLACK_WEBHOOK_URL env var

    Returns:
        True if sent successfully
    """
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        logger.debug("[slack] No SLACK_WEBHOOK_URL configured, skipping")
        return False

    try:
        import requests
        resp = requests.post(
            url,
            json={"text": text, "mrkdwn": True},
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        logger.warning("[slack] Failed (status %d): %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.warning("[slack] Error: %s", e)
        return False


def send_alert_slack(message: str, severity: str = "info") -> bool:
    """Send a formatted alert to Slack with severity prefix."""
    prefix_map = {
        "error": "🚨 *[ERROR]* ",
        "warning": "⚠️ *[WARNING]* ",
        "info": "ℹ️ ",
        "success": "✅ ",
        "critical": "🔥 *[CRITICAL]* ",
    }
    prefix = prefix_map.get(severity, "")
    formatted = f"{prefix}{message}"
    return send_slack_message(formatted)
