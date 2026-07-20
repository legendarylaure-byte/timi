from utils.firebase_status import log_activity, delete_old_videos, delete_old_activity_logs, delete_old_activity_entries, delete_old_pipeline_triggers, reset_agent_statuses
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def cleanup_local_files(max_age_hours: int = 24, keep_output_hours: int = 48) -> dict:
    """Clean up local temp and old output files after successful uploads.

    Args:
        max_age_hours: Delete temp files older than this.
        keep_output_hours: Keep output files for this long before deleting.

    Returns:
        dict with counts of deleted files and freed space.
    """
    agents_dir = Path(PROJECT_ROOT)
    tmp_dir = agents_dir / "tmp"
    output_dir = agents_dir / "output"

    result = {"deleted_files": 0, "deleted_dirs": 0, "freed_bytes": 0, "errors": []}

    now = datetime.now()

    # Clean tmp/ directory aggressively (all subdirs: voice/, subtitles/, compositor/, etc.)
    if tmp_dir.exists():
        for item in tmp_dir.rglob("*"):
            try:
                if item.is_file():
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    age_hours = (now - mtime).total_seconds() / 3600
                    if age_hours >= max_age_hours:
                        size = item.stat().st_size
                        item.unlink()
                        result["deleted_files"] += 1
                        result["freed_bytes"] += size
                elif item.is_dir() and item != tmp_dir:
                    # Remove empty subdirectories
                    if not any(item.iterdir()):
                        item.rmdir()
                        result["deleted_dirs"] += 1
            except Exception as e:
                result["errors"].append(f"tmp/{item.name}: {e}")

    # Clean output/ directory more conservatively
    if output_dir.exists():
        for item in output_dir.iterdir():
            try:
                if item.is_file():
                    mtime = datetime.fromtimestamp(item.stat().st_mtime)
                    age_hours = (now - mtime).total_seconds() / 3600
                    if age_hours >= keep_output_hours:
                        size = item.stat().st_size
                        item.unlink()
                        result["deleted_files"] += 1
                        result["freed_bytes"] += size
            except Exception as e:
                result["errors"].append(f"output/{item.name}: {e}")

    freed_mb = result["freed_bytes"] / (1024 * 1024)
    log_activity(
        "cleanup", f"Local cleanup: {result['deleted_files']} files, {result['deleted_dirs']} dirs, {freed_mb:.1f}MB freed", "success")  # noqa: E501
    print(
        f"[cleanup] Local cleanup complete: {result['deleted_files']} files, {result['deleted_dirs']} dirs, {freed_mb:.1f}MB freed")  # noqa: E501
    return result


def cleanup_old_checkpoints(max_age_hours: int = 168) -> dict:
    """Delete old pipeline checkpoint files from the project root.

    Args:
        max_age_hours: Delete checkpoint files older than this (default 7 days).

    Returns:
        dict with count of deleted files and errors.
    """
    result = {"deleted": 0, "freed_bytes": 0, "errors": []}
    agents_dir = Path(PROJECT_ROOT)

    now = datetime.now()
    for fpath in agents_dir.glob("checkpoint_*.json"):
        try:
            mtime = datetime.fromtimestamp(fpath.stat().st_mtime)
            age_hours = (now - mtime).total_seconds() / 3600
            if age_hours >= max_age_hours:
                size = fpath.stat().st_size
                fpath.unlink()
                result["deleted"] += 1
                result["freed_bytes"] += size
                print(f"[cleanup] Deleted old checkpoint: {fpath.name}")
        except Exception as e:
            result["errors"].append(str(e))

    if result["deleted"]:
        log_activity("cleanup", f"Deleted {result['deleted']} old checkpoint files", "info")
    return result


def cleanup_temp_directories() -> dict:
    """Remove ALL temporary directories to ensure a clean slate for each run."""
    result = {"deleted_files": 0, "deleted_dirs": 0, "freed_bytes": 0, "errors": []}
    agents_dir = Path(PROJECT_ROOT)

    subdirs = ["tmp/compositor", "tmp/asset_router", "tmp/music", "tmp/voice",
               "tmp/subtitles", "tmp/screencaps", "tmp/blender_cache", "tmp/blender_render", "tmp/clips"]

    for rel_path in subdirs:
        target = agents_dir / rel_path
        if target.exists():
            for item in target.rglob("*"):
                try:
                    if item.is_file():
                        size = item.stat().st_size
                        item.unlink()
                        result["deleted_files"] += 1
                        result["freed_bytes"] += size
                except Exception as e:
                    result["errors"].append(f"{rel_path}/{item.name}: {e}")
            for item in sorted(target.rglob("*"), key=lambda p: len(str(p)), reverse=True):
                try:
                    if item.is_dir() and item != target:
                        item.rmdir()
                        result["deleted_dirs"] += 1
                except Exception:
                    pass

    return result


def cleanup_after_upload(video_path: str, thumbnail_path: str = None, voice_path: str = None, music_path: str = None, subtitle_path: str = None) -> dict:  # noqa: E501
    """Immediately clean up source/intermediate files after a successful upload.

    Keeps the final output video but removes intermediate temp files.
    """
    result = {"deleted": [], "freed_bytes": 0, "errors": []}

    files_to_remove = []
    if voice_path and os.path.exists(voice_path):
        files_to_remove.append(voice_path)
    if music_path and os.path.exists(music_path):
        files_to_remove.append(music_path)
    if subtitle_path and os.path.exists(subtitle_path):
        files_to_remove.append(subtitle_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        if "tmp" in thumbnail_path:
            files_to_remove.append(thumbnail_path)

    for fpath in files_to_remove:
        try:
            size = os.path.getsize(fpath)
            os.remove(fpath)
            result["deleted"].append(fpath)
            result["freed_bytes"] += size
            print(f"[cleanup] Removed: {fpath} ({size / 1024:.1f}KB)")
        except Exception as e:
            result["errors"].append(f"{fpath}: {e}")

    freed_mb = result["freed_bytes"] / (1024 * 1024)
    print(f"[cleanup] Post-upload cleanup: {len(result['deleted'])} files removed, {freed_mb:.1f}MB freed")
    return result


def run_cleanup():
    print(f"[{datetime.now()}] Starting video cleanup...")

    # Step 0a: Reset stale agent statuses
    try:
        reset = reset_agent_statuses()
        if reset:
            print(f"[cleanup] Reset {reset} stale agent statuses")
    except Exception as e:
        print(f"[cleanup] Agent status reset skipped: {e}")

    # Step 0a2: Clean up old pipeline triggers
    try:
        purged = delete_old_pipeline_triggers()
        if purged:
            print(f"[cleanup] Purged {purged} old pipeline triggers")
    except Exception as e:
        print(f"[cleanup] Pipeline trigger cleanup skipped: {e}")

    # Step 0b: Clean up old activity entries
    try:
        deleted_activity = delete_old_activity_entries()
        if deleted_activity:
            print(f"[cleanup] Deleted {deleted_activity} old activity entries")
    except Exception as e:
        print(f"[cleanup] Activity entry cleanup skipped: {e}")

    # Step 0c: Clean up old video records
    try:
        deleted = delete_old_videos()
        if deleted:
            print(f"[cleanup] Deleted {deleted} old video records from Firestore")
    except Exception as e:
        print(f"[cleanup] Video cleanup skipped: {e}")

    # Step 0d: Delete stale activity logs (TTL-based)
    try:
        stale = delete_old_activity_logs()
        if stale:
            print(f"[cleanup] Deleted {stale} stale activity logs")
    except Exception as e:
        print(f"[cleanup] Stale log cleanup skipped: {e}")

    # Step 1: Clean up R2 cloud videos
    r2_result = {"success": 0, "failed": 0, "errors": []}
    try:
        from utils.r2_storage import cleanup_old_videos, list_pending_deletion
        pending = list_pending_deletion()
        if pending:
            r2_result = cleanup_old_videos()
        else:
            print("No R2 videos pending deletion.")
    except Exception as e:
        print(f"R2 cleanup skipped: {e}")

    # Step 2: Clean up old checkpoint files
    try:
        checkpoint_result = cleanup_old_checkpoints()
        if checkpoint_result["deleted"]:
            print(f"[cleanup] Deleted {checkpoint_result['deleted']} old checkpoint files ({checkpoint_result['freed_bytes'] / 1024:.1f}KB)")
    except Exception as e:
        print(f"[cleanup] Checkpoint cleanup skipped: {e}")
        checkpoint_result = {"deleted": 0, "freed_bytes": 0, "errors": []}

    # Step 2b: Clean up orphan R2 objects (no matching Firestore record)
    try:
        from utils.r2_storage import delete_orphan_r2_objects
        orphan_result = delete_orphan_r2_objects()
        if orphan_result["deleted"]:
            print(f"[cleanup] Deleted {orphan_result['deleted']} orphan R2 objects")
    except Exception as e:
        print(f"[cleanup] R2 orphan cleanup skipped: {e}")
        orphan_result = {"deleted": 0, "failed": 0, "errors": [], "scanned": 0}

    # Step 3: Clean up local temp and old output files
    local_result = cleanup_local_files()

    # Summary
    orphan_deleted = orphan_result.get("deleted", 0)
    checkpoint_freed = checkpoint_result.get("freed_bytes", 0)
    total_freed_mb = (local_result["freed_bytes"] + checkpoint_freed) / (1024 * 1024)
    message = (
        "🧹 *Auto-Cleanup Complete*\n\n"
        f"☁️ R2 Deleted: {r2_result.get('success', 0)} auto-delete, {orphan_deleted} orphan\n"
        f"📁 Local: {local_result['deleted_files']} files, {local_result['deleted_dirs']} dirs\n"
        f"📝 Checkpoints: {checkpoint_result['deleted']} deleted\n"
        f"💾 Freed: {total_freed_mb:.1f}MB\n"
        f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
    )

    all_errors = r2_result.get("errors", []) + local_result.get("errors", []) + orphan_result.get("errors", []) + checkpoint_result.get("errors", [])
    if all_errors:
        for err in all_errors[:5]:
            err_msg = err.get("key", err) if isinstance(err, dict) else err
            message += f"\n• `{err_msg}`"

    try:
        from bot.notifications import send_telegram_message
        send_telegram_message(message)
    except ImportError:
        print("[cleanup] bot.notifications not available (cross-module import skipped — run from project root)")
    except Exception as e:
        print(f"[cleanup] Failed to send Telegram notification: {e}")

    return {
        "r2": r2_result,
        "local": local_result,
    }


if __name__ == "__main__":
    run_cleanup()
