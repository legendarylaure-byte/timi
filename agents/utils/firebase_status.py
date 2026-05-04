import os
import time
import random
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

_service_account_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'firebase', 'serviceAccountKey.json')
_db = None

def _retry_firestore(op_name, func, max_retries=3):
    """Execute a Firestore operation with exponential backoff on quota errors."""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if "429" in str(e) or "Quota" in str(e) or attempt == max_retries - 1:
                if attempt < max_retries - 1:
                    wait = (2 ** attempt) * 3 + random.uniform(0, 2)
                    print(f"[FIRESTORE] {op_name} failed (attempt {attempt + 1}/{max_retries}), retrying in {wait:.1f}s: {e}")
                    time.sleep(wait)
                else:
                    print(f"[FIRESTORE] {op_name} failed after {max_retries} attempts: {e}")
            else:
                raise
    return None

def get_firestore_client():
    global _db
    if _db is not None:
        return _db
    try:
        cred = credentials.Certificate(_service_account_path)
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID', 'timi-childern-stories'),
        })
    except ValueError:
        pass
    _db = firestore.client()
    return _db

def update_agent_status(agent_id: str, status: str, action: str = "", error_message: str = ""):
    """Update agent status in Firestore for real-time dashboard updates."""
    def _do():
        doc_ref = db.collection('agent_status').document(agent_id)
        doc_ref.set({
            'agent_id': agent_id,
            'status': status,
            'current_action': action,
            'last_updated': firestore.SERVER_TIMESTAMP,
            'error_message': error_message,
        }, merge=True)
    db = get_firestore_client()
    _retry_firestore(f"Agent '{agent_id}' status update", _do)
    print(f"[FIRESTORE] Agent '{agent_id}' status: {status} - {action}")

def log_activity(agent_id: str, message: str, level: str = "info"):
    """Add activity log to Firestore for the activity feed."""
    db = get_firestore_client()
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

def add_video_record(video_id: str, title: str, format_type: str, status: str = "generating", r2_key: str = ""):
    """Add or update a video record in Firestore."""
    db = get_firestore_client()
    def _do():
        doc_ref = db.collection('videos').document(video_id)
        doc_ref.set({
            'video_id': video_id,
            'title': title,
            'format': format_type,
            'status': status,
            'r2_key': r2_key,
            'views': 0,
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }, merge=True)
    _retry_firestore(f"Video record '{video_id}'", _do)

def update_video_record(video_id: str, data: dict):
    """Update specific fields on an existing video record."""
    db = get_firestore_client()
    def _do():
        doc_ref = db.collection('videos').document(video_id)
        merge_data = dict(data)
        merge_data['updated_at'] = firestore.SERVER_TIMESTAMP
        doc_ref.set(merge_data, merge=True)
    _retry_firestore(f"Video '{video_id}' update", _do)
    print(f"[FIRESTORE] Updated video '{video_id}' with: {list(data.keys())}")
