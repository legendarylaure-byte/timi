import os
import requests
from datetime import datetime

def send_telegram_message(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram credentials not set")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print(f"Telegram notification sent to {chat_id}")
    except Exception as e:
        print(f"Failed to send Telegram notification: {e}")

def send_upload_notification(video_data: dict):
    title = video_data.get("title", "Unknown")
    format_type = video_data.get("format", "unknown")
    duration = video_data.get("duration", "unknown")
    platforms = video_data.get("platforms", {})

    platform_links = "\n".join(
        [f"• *{name}:* {url}" for name, url in platforms.items()]
    )

    message = (
        f"🎬 *Video Uploaded Successfully!*\n\n"
        f"*Title:* {title}\n"
        f"*Format:* {format_type.upper()}\n"
        f"*Duration:* {duration}s\n"
        f"*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"*Links:*\n{platform_links}\n\n"
        f"📊 Metadata has been optimized for maximum reach.\n"
        f"🚀 Sharing to all platforms now!"
    )

    send_telegram_message(message)

def send_error_notification(error: str, context: str = ""):
    message = (
        f"🚨 *Alert: Pipeline Error*\n\n"
        f"*Context:* {context}\n"
        f"*Error:* {error}\n\n"
        f"Please check the dashboard for details."
    )

    send_telegram_message(message)
