import time
from utils.firebase_status import get_firestore_client

CHECKPOINT_COLLECTION = "pipeline_checkpoints"


def save_checkpoint(video_id: str, step: str, state: dict) -> None:
    """Save pipeline progress checkpoint to Firestore."""
    try:
        db = get_firestore_client()
        db.collection(CHECKPOINT_COLLECTION).document(video_id).set({
            "step": step,
            "state": state,
            "updated_at": time.time(),
        })
    except Exception as e:
        print(f"[CHECKPOINT] Failed to save: {e}")


def load_checkpoint(video_id: str) -> dict | None:
    """Load pipeline checkpoint for a video."""
    try:
        db = get_firestore_client()
        doc = db.collection(CHECKPOINT_COLLECTION).document(video_id).get()
        if doc.exists:
            return doc.to_dict()
    except Exception as e:
        print(f"[CHECKPOINT] Failed to load: {e}")
    return None


def clear_checkpoint(video_id: str) -> None:
    """Remove checkpoint after pipeline completes."""
    try:
        db = get_firestore_client()
        db.collection(CHECKPOINT_COLLECTION).document(video_id).delete()
    except Exception as e:
        print(f"[CHECKPOINT] Failed to clear: {e}")
