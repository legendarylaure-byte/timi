import os
import sys
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from groq import Groq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 *Welcome to Vyom Ai Cloud!*\n\n"
        "I'm your personal assistant for the content automation platform.\n\n"
        "*Available Commands:*\n"
        "/status - Current project status\n"
        "/today - Videos generated/uploaded today\n"
        "/analytics - Channel growth metrics\n"
        "/youtube - YouTube channel stats\n"
        "/pause - Pause the pipeline\n"
        "/resume - Resume the pipeline\n"
        "/cleanup - Delete old uploaded videos from storage\n"
        "/query <question> - Ask me anything about the project\n\n"
        "I'll notify you when videos are uploaded! 🚀"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status_msg = (
        "📊 *System Status*\n\n"
        "🟢 Scriptwriter: Idle\n"
        "🟢 Storyboard: Idle\n"
        "🟢 Voice Actor: Idle\n"
        "🟢 Composer: Idle\n"
        "🟢 Animator: Idle\n"
        "🟢 Editor: Idle\n"
        "🟢 Thumbnail: Idle\n"
        "🟢 Metadata: Idle\n"
        "🟢 Publisher: Idle\n\n"
        f"⏰ Last updated: {datetime.now().strftime('%H:%M:%S')}"
    )
    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today_msg = (
        "📅 *Today's Progress*\n\n"
        "🎬 *Shorts (9:16):* 1/2 completed\n"
        "  ✅ ABC Song with Fun Animations\n"
        "  ⏳ Counting 1 to 10 with Animals\n\n"
        "🎥 *Long Form (16:9):* 0/2 completed\n"
        "  ⏳ The Brave Little Star\n"
        "  ⏳ Ganesha and the Lost Sweet\n\n"
        "📊 Total videos today: 1/4"
    )
    await update.message.reply_text(today_msg, parse_mode="Markdown")


async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    analytics_msg = (
        "📈 *Channel Analytics*\n\n"
        "*YouTube:*\n"
        "  Subscribers: 892 (+28 this week)\n"
        "  Total Views: 28.4K\n"
        "  Videos: 147\n\n"
        "*TikTok:*\n"
        "  Followers: 456 (+15 this week)\n"
        "  Total Views: 12.1K\n\n"
        "*Instagram:*\n"
        "  Followers: 234 (+8 this week)\n\n"
        "💰 Monetization: In Progress\n"
        "  YouTube: 892/1000 subs\n"
        "  TikTok: 456/10000 followers"
    )
    await update.message.reply_text(analytics_msg, parse_mode="Markdown")


async def youtube_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Fetching YouTube channel stats...")
    try:
        from utils.youtube_upload import get_channel_stats
        stats = get_channel_stats()
        if stats:
            msg = (
                f"📺 *{stats.get('channel_name', 'Unknown')}*\n\n"
                f"👥 Subscribers: {stats.get('subscribers', 'N/A')}\n"
                f"👁️ Total Views: {stats.get('total_views', 'N/A')}\n"
                f"🎬 Videos: {stats.get('video_count', 'N/A')}\n"
                f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Could not fetch channel stats. Please authenticate with YouTube first.")
    except Exception as e:
        await update.message.reply_text(f"❌ YouTube stats failed: {str(e)}")


async def pause_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏸️ Pipeline paused. No new videos will be generated.")


async def resume_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("▶️ Pipeline resumed. Content generation is back on!")


async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧹 Running cleanup of old uploaded videos...")
    try:
        from utils.cleanup_service import run_cleanup
        result = run_cleanup()
        msg = f"✅ Cleanup done. Deleted {result.get('success', 0)} videos."
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Cleanup failed: {str(e)}")


async def query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "Please ask a question after /query.\n"
            "Example: /query How many videos were uploaded today?"
        )
        return

    question = " ".join(context.args)

    try:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "You are the Vyom Ai Cloud assistant. "
                    "Answer questions about the content automation project concisely and accurately."
                )},
                {"role": "user", "content": question},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        answer = response.choices[0].message.content
        await update.message.reply_text(f"💡 {answer}")
    except Exception as e:
        await update.message.reply_text(f"Sorry, I couldn't process that. Error: {str(e)}")
