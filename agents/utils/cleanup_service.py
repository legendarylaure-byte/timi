import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from utils.r2_storage import cleanup_old_videos, list_pending_deletion

BOT_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), "bot")
sys.path.insert(0, os.path.dirname(PROJECT_ROOT))
from bot.notifications import send_telegram_message

def run_cleanup():
    print(f"[{datetime.now()}] Starting video cleanup...")

    pending = list_pending_deletion()
    if not pending:
        print("No videos pending deletion.")
        return {"status": "ok", "message": "Nothing to clean up"}

    result = cleanup_old_videos()

    message = (
        "🧹 *Auto-Cleanup Complete*\n\n"
        f"✅ Deleted: {result['success']} videos\n"
        f"❌ Failed: {result['failed']}\n"
        f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
    )

    if result["errors"]:
        for err in result["errors"]:
            message += f"\n• `{err['key']}`: {err['error']}"

    try:
        send_telegram_message(message)
    except Exception:
        print("Failed to send cleanup notification to Telegram")

    return result

if __name__ == "__main__":
    run_cleanup()
