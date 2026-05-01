import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

_service_account_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'firebase', 'serviceAccountKey.json')

def get_firestore_client():
    if not firebase_admin._apps:
        cred = credentials.Certificate(_service_account_path)
        firebase_admin.initialize_app(cred, {
            'projectId': os.getenv('FIREBASE_PROJECT_ID', 'timi-childern-stories'),
        })
    return firestore.client()

def update_agent_status(agent_id: str, status: str, action: str = "", error_message: str = ""):
    """Update agent status in Firestore for real-time dashboard updates."""
    db = get_firestore_client()
    doc_ref = db.collection('agent_status').document(agent_id)
    doc_ref.set({
        'agent_id': agent_id,
        'status': status,
        'current_action': action,
        'last_updated': firestore.SERVER_TIMESTAMP,
        'error_message': error_message,
    }, merge=True)
    print(f"[FIRESTORE] Agent '{agent_id}' status: {status} - {action}")

def log_activity(agent_id: str, message: str, level: str = "info"):
    """Add activity log to Firestore for the activity feed."""
    db = get_firestore_client()
    db.collection('activity_logs').add({
        'agent_id': agent_id,
        'message': message,
        'level': level,
        'timestamp': firestore.SERVER_TIMESTAMP,
    })

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

def add_video_record(video_id: str, title: str, format_type: str, status: str = "generating", r2_key: str = ""):
    """Add or update a video record in Firestore."""
    db = get_firestore_client()
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

def update_video_record(video_id: str, data: dict):
    """Update specific fields on an existing video record."""
    db = get_firestore_client()
    doc_ref = db.collection('videos').document(video_id)
    data['updated_at'] = firestore.SERVER_TIMESTAMP
    doc_ref.set(data, merge=True)
    print(f"[FIRESTORE] Updated video '{video_id}' with: {list(data.keys())}")
