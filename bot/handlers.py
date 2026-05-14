import os
import sys
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes
from telegram.helpers import escape_markdown
from groq import Groq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'agents'))

from agents.utils.firebase_status import get_firestore_client
from utils.youtube_upload import get_channel_stats


def _get_firestore():
    try:
        return get_firestore_client()
    except Exception:
        return None


async def _safe_reply(update: Update, text: str, parse_mode: str = "Markdown"):
    try:
        MAX_LEN = 4000
        if len(text) > MAX_LEN:
            text = text[:MAX_LEN-3] + "..."
        await update.message.reply_text(text, parse_mode=parse_mode)
    except Exception as e:
        try:
            await update.message.reply_text(f"Error sending response: {e}")
        except Exception:
            pass


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_reply(
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
        "I'll notify you when videos are uploaded!"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _get_firestore()
        if db is None:
            await _safe_reply("📊 *System Status*\n\n⚠️ Firestore not available. Run the bot from the agents directory.")
            return

        agent_ids = ['scriptwriter', 'storyboard', 'voice', 'composer', 'animator', 'editor', 'thumbnail', 'metadata', 'publisher']
        agent_labels = {
            'scriptwriter': 'Scriptwriter', 'storyboard': 'Storyboard', 'voice': 'Voice Actor',
            'composer': 'Composer', 'animator': 'Animator', 'editor': 'Editor',
            'thumbnail': 'Thumbnail', 'metadata': 'Metadata', 'publisher': 'Publisher',
        }
        lines = []
        for aid in agent_ids:
            doc = db.collection('agent_status').document(aid).get()
            if doc.exists:
                d = doc.to_dict()
                status_icon = '🟢' if d.get('status') == 'completed' or d.get('status') == 'idle' else '🟡' if d.get('status') == 'working' else '🔴'
                task = d.get('current_action', '')
                task_str = f" — _{task}_" if task else ""
                lines.append(f"{status_icon} {agent_labels[aid]}: {d.get('status', 'unknown').title()}{task_str}")
            else:
                lines.append(f"⚪ {agent_labels[aid]}: Unknown")

        pipeline_doc = db.collection('system').document('pipeline').get()
        pipeline_status = "Running" if pipeline_doc.exists and pipeline_doc.to_dict().get('running') else "Paused" if pipeline_doc.exists and pipeline_doc.to_dict().get('paused_by_user') else "Idle"

        msg = (
            "📊 *System Status*\n\n"
            f"🔧 Pipeline: *{pipeline_status}*\n\n"
            + "\n".join(lines) +
            f"\n\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
        )
        await _safe_reply(msg)
    except Exception as e:
        await _safe_reply(f"❌ Failed to get status: {str(e)}")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _get_firestore()
        if db is None:
            await _safe_reply("📅 *Today's Progress*\n\n⚠️ Firestore not available.")
            return

        today_str = datetime.now().strftime('%Y-%m-%d')
        docs = list(db.collection('videos').order_by('created_at', direction='DESCENDING').limit(50).stream())
        todays_videos = []
        for doc in docs:
            data = doc.to_dict()
            created = data.get('created_at')
            if created and hasattr(created, 'strftime'):
                doc_date = created.strftime('%Y-%m-%d')
            elif created and isinstance(created, str):
                doc_date = created[:10]
            else:
                continue
            if doc_date == today_str:
                todays_videos.append(data)

        shorts = [v for v in todays_videos if v.get('format') == 'shorts']
        longs = [v for v in todays_videos if v.get('format') != 'shorts']
        shorts_done = sum(1 for v in shorts if v.get('status') in ('uploaded', 'published'))
        longs_done = sum(1 for v in longs if v.get('status') in ('uploaded', 'published'))

        def fmt_videos(videos):
            if not videos:
                return "  _None yet_"
            return "\n".join(
                f"  {'✅' if v.get('status') in ('uploaded', 'published') else '⏳'} {v.get('title', 'Untitled')}"
                for v in videos
            )

        msg = (
            "📅 *Today's Progress*\n\n"
            f"🎬 *Shorts:* {shorts_done}/{len(shorts)} completed\n"
            f"{fmt_videos(shorts)}\n\n"
            f"🎥 *Long Form:* {longs_done}/{len(longs)} completed\n"
            f"{fmt_videos(longs)}\n\n"
            f"📊 Total: {shorts_done + longs_done}/{len(todays_videos)}"
        )
        await _safe_reply(msg)
    except Exception as e:
        await _safe_reply(f"❌ Failed to get today's progress: {str(e)}")


async def analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _get_firestore()
        if db is None:
            await _safe_reply("📈 *Channel Analytics*\n\n⚠️ Firestore not available.")
            return

        channel_doc = db.collection('system').document('channel_stats').get()
        channel = channel_doc.to_dict() if channel_doc.exists else {}

        videos_docs = list(db.collection('videos').order_by('created_at', direction='DESCENDING').limit(100).stream())
        total_views = sum(d.to_dict().get('views', 0) for d in videos_docs)
        total_likes = sum(d.to_dict().get('likes', 0) for d in videos_docs)
        total_comments = sum(d.to_dict().get('comments', 0) for d in videos_docs)
        published = sum(1 for d in videos_docs if d.to_dict().get('status') in ('uploaded', 'published'))

        subs = channel.get('subscribers', 'N/A')
        channel_views = channel.get('total_views', 'N/A')
        video_count = channel.get('video_count', str(published))

        msg = (
            "📈 *Channel Analytics*\n\n"
            f"*YouTube:*\n"
            f"  Subscribers: {subs}\n"
            f"  Total Views: {channel_views}\n"
            f"  Videos: {video_count}\n\n"
            f"*Published Content:*\n"
            f"  Videos: {published}\n"
            f"  Lifetime Views: {total_views:,}\n"
            f"  Lifetime Likes: {total_likes:,}\n"
            f"  Lifetime Comments: {total_comments:,}\n\n"
            f"⏰ Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await _safe_reply(msg)
    except Exception as e:
        await _safe_reply(f"❌ Failed to get analytics: {str(e)}")


async def youtube_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_reply("📊 Fetching YouTube channel stats...")
    try:
        stats = get_channel_stats()
        if stats:
            msg = (
                f"📺 *{stats.get('channel_name', 'Unknown')}*\n\n"
                f"👥 Subscribers: {stats.get('subscribers', 'N/A')}\n"
                f"👁️ Total Views: {stats.get('total_views', 'N/A')}\n"
                f"🎬 Videos: {stats.get('video_count', 'N/A')}\n"
                f"\n⏰ Updated: {datetime.now().strftime('%H:%M:%S')}"
            )
            await _safe_reply(msg)
        else:
            await _safe_reply("❌ Could not fetch channel stats. Please authenticate with YouTube first.")
    except Exception as e:
        await _safe_reply(f"❌ YouTube stats failed: {str(e)}")


async def pause_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _get_firestore()
        if db is not None:
            from firebase_admin import firestore
            db.collection('system').document('pipeline').set({
                'running': False,
                'paused_by_user': True,
                'last_updated': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        await _safe_reply("⏸️ Pipeline paused. No new videos will be generated.")
    except Exception as e:
        await _safe_reply(f"❌ Failed to pause pipeline: {str(e)}")


async def resume_pipeline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        db = _get_firestore()
        if db is not None:
            from firebase_admin import firestore
            db.collection('system').document('pipeline').set({
                'running': True,
                'paused_by_user': False,
                'last_updated': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        await _safe_reply("▶️ Pipeline resumed. Content generation is back on!")
    except Exception as e:
        await _safe_reply(f"❌ Failed to resume pipeline: {str(e)}")


async def cleanup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _safe_reply("🧹 Running cleanup of old uploaded videos...")
    try:
        from utils.cleanup_service import run_cleanup
        result = run_cleanup()
        r2_result = result.get('r2', {})
        deleted = r2_result.get('success', 0)
        local_result = result.get('local', {})
        await _safe_reply(f"✅ Cleanup done. Deleted {deleted} R2 objects. Local: {local_result}")
    except Exception as e:
        await _safe_reply(f"❌ Cleanup failed: {str(e)}")


async def query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await _safe_reply(
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
        safe_answer = escape_markdown(answer, version=2)
        await _safe_reply(f"💡 {safe_answer}", parse_mode="MarkdownV2")
    except Exception as e:
        await _safe_reply(f"Sorry, I couldn't process that. Error: {str(e)}")
