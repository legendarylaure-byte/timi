import os
import logging
import traceback
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from telegram.ext.filters import MessageFilter
from handlers import start, status, today, analytics, youtube_stats, pause_pipeline, resume_pipeline, cleanup, query

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 I'm the Vyom Ai Cloud assistant!\n\n"
        "Use /start to see available commands.\n"
        "Or type /query followed by your question."
    )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception in bot handler", exc_info=context.error)
    tb = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
    logger.error(f"Traceback:\n{tb}")
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ Something went wrong internally. The error has been logged."
            )
        except Exception:
            pass


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        return

    app = (
        ApplicationBuilder()
        .token(token)
        .rate_limiter(enabled=True)
        .build()
    )

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
    app.add_error_handler(error_handler)

    print("🤖 Vyom Ai Cloud Telegram Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
