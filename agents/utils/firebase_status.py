import os
import time
import random
import json
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from utils.retry import retry
from utils.sanitize import redact

_service_account_path = ''
_env_key = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY', '')
_env_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_PATH', '')
if _env_key:
    _service_account_path = _env_key
elif _env_path:
    _service_account_path = _env_path
else:
    _service_account_path = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'firebase', 'serviceAccountKey.json')
_db = None


@retry(max_attempts=3, base_delay=3.0, backoff=2.0, jitter=True)
def _firestore_op(op_name: str, func):
    """Execute a Firestore operation with retry."""
    return func()

def _retry_firestore(op_name, func, max_retries=3):
    """Backward-compatible wrapper."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * 3 + random.uniform(0, 2)
                print(
                    f"[FIRESTORE] {op_name} failed (attempt {attempt + 1}/{max_retries}), retrying in {wait:.1f}s: {redact(str(e))}")  # noqa: E501
                time.sleep(wait)
            else:
                print(f"[FIRESTORE] {op_name} failed after {max_retries} attempts: {redact(str(e))}")
    return None


def get_firestore_client():
    global _db
    if _db is not None:
        return _db
    sa_path = _service_account_path
    if _env_key:
        try:
            import base64
            key_bytes = base64.b64decode(_env_key)
            cred = credentials.Certificate(json.loads(key_bytes))
        except Exception as e:
            print(f"[FIRESTORE] Failed to parse FIREBASE_SERVICE_ACCOUNT_KEY: {redact(str(e))}")
            return None
    elif os.path.exists(sa_path):
        try:
            cred = credentials.Certificate(sa_path)
        except Exception as e:
            print(f"[FIRESTORE] Failed to load service account file: {redact(str(e))}")
            return None
    else:
        print(f"[FIRESTORE] Service account file not found: {redact(str(sa_path))}")
        return None
    try:
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID', 'timi-childern-stories'),
        })
    except ValueError as e:
        print(f"[FIRESTORE] Firebase init failed: {e}")
        return None
    except Exception as e:
        print(f"[FIRESTORE] Firebase init error: {e}")
        return None
    try:
        _db = firestore.client()
        return _db
    except Exception as e:
        print(f"[FIRESTORE] Failed to create Firestore client: {e}")
        return None


def update_agent_status(agent_id: str, status: str, action: str = "", error_message: str = ""):
    """Update agent status in Firestore for real-time dashboard updates."""
    db = get_firestore_client()
    if db is None:
        return

    def _do():
        doc_ref = db.collection('agent_status').document(agent_id)
        doc_ref.set({
            'agent_id': agent_id,
            'status': status,
            'current_action': action,
            'last_updated': firestore.SERVER_TIMESTAMP,
            'error_message': error_message,
        }, merge=True)
    _retry_firestore(f"Agent '{agent_id}' status update", _do)
    print(f"[FIRESTORE] Agent '{agent_id}' status: {status} - {action}")


def log_activity(agent_id: str, message: str, level: str = "info"):
    """Add activity log to Firestore for the activity feed."""
    print(json.dumps({"timestamp": datetime.utcnow().isoformat(), "level": level.upper(), "agent": agent_id, "message": message, "type": "activity"}))
    db = get_firestore_client()
    if db is None:
        return

    def _do():
        db.collection('activity_logs').add({
            'agent_id': agent_id,
            'message': message,
            'level': level,
            'timestamp': firestore.SERVER_TIMESTAMP,
        })
    _retry_firestore(f"Activity log: {agent_id}", _do)


def is_agent_enabled(agent_id: str) -> bool:
    """Check if agent is enabled (for pause/resume control from dashboard)."""
    try:
        db = get_firestore_client()
        doc_ref = db.collection('agent_status').document(agent_id)
        doc = doc_ref.get()
        if doc.exists:
            return doc.to_dict().get('enabled', True)
        return True
    except Exception:
        return True


def update_pipeline_status(running: bool, current_video: str = "", paused_by_user: bool = False):
    """Update overall pipeline status in Firestore."""
    db = get_firestore_client()
    if db is None:
        return

    def _do():
        doc_ref = db.collection('system').document('pipeline')
        data = {
            'running': running,
            'current_video': current_video,
            'paused_by_user': paused_by_user,
            'last_updated': firestore.SERVER_TIMESTAMP,
        }
        if running:
            data['started_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(data, merge=True)
    _retry_firestore("Pipeline status update", _do)


def add_video_record(video_id: str, title: str, format_type: str, status: str = "generating", r2_key: str = "", category: str = ""):
    """Add or update a video record in Firestore."""
    db = get_firestore_client()
    if db is None:
        return

    def _do():
        doc_ref = db.collection('videos').document(video_id)
        doc_ref.set({
            'video_id': video_id,
            'title': title,
            'format': format_type,
            'status': status,
            'r2_key': r2_key,
            'category': category,
            'views': 0,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }, merge=True)
    _retry_firestore(f"Video record '{video_id}'", _do)


def update_video_record(video_id: str, data: dict):
    """Update specific fields on an existing video record."""
    db = get_firestore_client()
    if db is None:
        return

    def _do():
        doc_ref = db.collection('videos').document(video_id)
        merge_data = dict(data)
        merge_data['updated_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(merge_data, merge=True)
    _retry_firestore(f"Video '{video_id}' update", _do)
    print(f"[FIRESTORE] Updated video '{video_id}' with: {list(data.keys())}")


def update_video_analytics(video_id: str, stats: dict):
    db = get_firestore_client()
    if db is None:
        return

    duration_sec = stats.get('duration_seconds', 0)
    views = stats.get('views', 0)
    estimated_watch_hours = (views * duration_sec) / 3600 if duration_sec > 0 else 0

    def _do():
        doc_ref = db.collection('videos').document(video_id)
        doc_ref.set({
            'views': views,
            'likes': stats.get('likes', 0),
            'comments': stats.get('comments', 0),
            'duration_seconds': duration_sec,
            'estimated_watch_hours': estimated_watch_hours,
            'analytics_updated_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }, merge=True)
        db.collection('videos').document(video_id).collection('analytics_history').add({
            **stats,
            'estimated_watch_hours': estimated_watch_hours,
            'recorded_at': firestore.SERVER_TIMESTAMP,
        })
    _retry_firestore(f"Video analytics '{video_id}'", _do)
    print(f"[FIRESTORE] Analytics updated for video '{video_id}': {views} views, {estimated_watch_hours:.1f} watch hours")


def update_channel_stats(stats: dict):
    db = get_firestore_client()
    if db is None:
        return

    try:
        videos = list(db.collection('videos').where('estimated_watch_hours', '>', 0).stream())
        total_watch_hours = sum(v.to_dict().get('estimated_watch_hours', 0) for v in videos)
    except Exception:
        total_watch_hours = 0

    def _do():
        db.collection('system').document('channel_stats').set({
            **stats,
            'total_watch_hours': total_watch_hours,
            'last_updated': firestore.SERVER_TIMESTAMP,
        }, merge=True)
    _retry_firestore("Channel stats update", _do)
    print(f"[FIRESTORE] Channel stats updated: {stats.get('subscribers', '?')} subs, {total_watch_hours:.1f} watch hours")


OLD_TITLE_PATTERNS = [
    "Magical Bedtime Adventure", "Father's Day Songs", "Fathers Day",
    "Ocean Adventure", "Kids Story", "Children Story",
    "Bedtime Story", "Mythology", "Mythological",
]

TECH_CATEGORIES = [
    "AI Explained", "Deep Tech", "Paper Breakdowns", "Tool Tutorials",
    "Industry Analysis", "Code & Build", "AI News", "Career & Learning",
]


ACTIVITY_TTL_DAYS = 30


def delete_old_activity_logs():
    """Delete activity logs older than ACTIVITY_TTL_DAYS."""
    try:
        db = get_firestore_client()
        cutoff = time.time() - ACTIVITY_TTL_DAYS * 86400
        activities = db.collection('activity_logs').where('timestamp', '<', cutoff).stream()
        deleted = 0
        for doc in activities:
            doc.reference.delete()
            deleted += 1
        if deleted:
            print(f"[CLEANUP] Deleted {deleted} stale activity logs")
        return deleted
    except Exception as e:
        print(f"[CLEANUP] Activity log cleanup failed: {e}")
        return 0


def delete_old_activity_entries(batch_size: int = 500):
    """Delete activity log entries referencing old children's story titles.

    Args:
        batch_size: Max documents to scan per run to avoid OOM on large collections.
    """
    try:
        db = get_firestore_client()
        activities = db.collection('activity_logs').limit(batch_size).stream()
        deleted = 0
        for doc in activities:
            data = doc.to_dict()
            message = (data.get('message', '') or '')
            matches_old = any(p.lower() in message.lower() for p in OLD_TITLE_PATTERNS)
            if matches_old:
                print(f"[CLEANUP] Deleting old activity: {message[:80]}")
                doc.reference.delete()
                deleted += 1
        if deleted:
            print(f"[CLEANUP] Deleted {deleted} old activity log entries")
        return deleted
    except Exception as e:
        print(f"[CLEANUP] Activity entry cleanup failed: {e}")
        return 0


def reset_agent_statuses():
    """Reset all agent status documents to idle/Ready."""
    try:
        db = get_firestore_client()
        agents = db.collection('agent_status').stream()
        reset = 0
        for doc in agents:
            data = doc.to_dict()
            current_status = data.get('status', '')
            current_action = data.get('current_action', '')
            if current_status != 'idle' or ('Magical' in current_action or 'Bedtime' in current_action or 'Father' in current_action or 'Ocean' in current_action or 'Kids' in current_action or 'Children' in current_action or 'Mythology' in current_action):
                doc.reference.set({
                    'status': 'idle',
                    'current_action': 'Ready',
                    'last_updated': firestore.SERVER_TIMESTAMP,
                }, merge=True)
                reset += 1
        if reset:
            print(f"[CLEANUP] Reset {reset} stale agent statuses")
        return reset
    except Exception as e:
        print(f"[CLEANUP] Agent status reset failed: {e}")
        return 0


PIPELINE_TRIGGER_TTL_DAYS = 7


def delete_old_pipeline_triggers():
    """Delete pipeline triggers with old children's story topics and stale completed/failed triggers."""
    try:
        db = get_firestore_client()
        triggers = db.collection('pipeline_triggers').stream()
        deleted = 0
        cutoff = time.time() - PIPELINE_TRIGGER_TTL_DAYS * 86400
        for doc in triggers:
            data = doc.to_dict()
            topic = (data.get('topic', '') or '')
            status = data.get('status', '')
            created_at = data.get('created_at')
            ts = None
            if created_at:
                if hasattr(created_at, 'timestamp'):
                    ts = created_at.timestamp()
                elif isinstance(created_at, (int, float)):
                    ts = created_at
            matches_old = any(p.lower() in topic.lower() for p in OLD_TITLE_PATTERNS)
            is_stale = status in ('completed', 'failed', 'skipped') and ts and ts < cutoff
            if matches_old or is_stale:
                print(f"[CLEANUP] Deleting trigger: {topic} ({status})")
                doc.reference.delete()
                deleted += 1
        if deleted:
            print(f"[CLEANUP] Deleted {deleted} old pipeline triggers")
        return deleted
    except Exception as e:
        print(f"[CLEANUP] Pipeline trigger cleanup failed: {e}")
        return 0


def delete_old_videos():
    """Delete legacy children's story records from Firestore."""
    try:
        db = get_firestore_client()
        snapshot = db.collection('videos').stream()
        deleted = 0
        for doc in snapshot:
            data = doc.to_dict()
            title = (data.get('title', '') or '').strip()
            category = data.get('category', '') or ''
            matches_old = any(p.lower() in title.lower() for p in OLD_TITLE_PATTERNS)
            if matches_old or (category and category not in TECH_CATEGORIES):
                print(f"[CLEANUP] Deleting old video: {title} ({doc.id})")
                doc.reference.delete()
                deleted += 1
        if deleted:
            print(f"[CLEANUP] Deleted {deleted} old video records")
        return deleted
    except Exception as e:
        print(f"[CLEANUP] Failed: {e}")
        return 0


def log_pipeline_error(video_id: str, error: str, step: str = "unknown"):
    """Log a pipeline error to both video record and activity log."""
    db = get_firestore_client()
    if db is None:
        return
    error_msg = str(error)[:500]
    try:
        def _do_video():
            doc_ref = db.collection('videos').document(video_id)
            doc_ref.set({
                'status': 'failed',
                'error': error_msg,
                'failed_step': step,
                'failed_at': datetime.utcnow().isoformat(),
                'updated_at': firestore.SERVER_TIMESTAMP,
            }, merge=True)
        _retry_firestore(f"Error log for '{video_id}'", _do_video)
    except Exception as e:
        print(f"[FIRESTORE] Failed to log error for video '{video_id}': {e}")
    try:
        def _do_log():
            db.collection('activity_logs').add({
                'agent_id': 'pipeline',
                'message': f'FAILED at {step}: {error_msg}',
                'level': 'error',
                'timestamp': firestore.SERVER_TIMESTAMP,
            })
        _retry_firestore("Error activity log", _do_log)
    except Exception as e:
        print(f"[FIRESTORE] Failed to log error activity: {e}")
    print(f"[PIPELINE ERROR] Video '{video_id}' failed at {step}: {error_msg}")
