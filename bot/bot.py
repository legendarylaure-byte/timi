import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from handlers import start, status, today, analytics, youtube_stats, pause_pipeline, resume_pipeline, cleanup, query
from notifications import send_upload_notification

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 I'm the Vyom Ai Cloud assistant!\n\n"
        "Use /start to see available commands.\n"
        "Or type /query followed by your question."
    )

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("today", today))
    app.add_handler(CommandHandler("analytics", analytics))
    app.add_handler(CommandHandler("youtube", youtube_stats))
    app.add_handler(CommandHandler("pause", pause_pipeline))
    app.add_handler(CommandHandler("resume", resume_pipeline))
    app.add_handler(CommandHandler("cleanup", cleanup))
    app.add_handler(CommandHandler("query", query))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Vyom Ai Cloud Telegram Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
