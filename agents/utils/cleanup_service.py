from utils.firebase_status import log_activity
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
        # Keep thumbnail if it's in output/, remove if in tmp/
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

    # Step 2: Clean up local temp and old output files
    local_result = cleanup_local_files()

    # Summary
    total_freed_mb = local_result["freed_bytes"] / (1024 * 1024)
    message = (
        "🧹 *Auto-Cleanup Complete*\n\n"
        f"☁️ R2 Deleted: {r2_result.get('success', 0)} videos\n"
        f"📁 Local: {local_result['deleted_files']} files, {local_result['deleted_dirs']} dirs\n"
        f"💾 Freed: {total_freed_mb:.1f}MB\n"
        f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}"
    )

    all_errors = r2_result.get("errors", []) + local_result.get("errors", [])
    if all_errors:
        for err in all_errors[:5]:
            err_msg = err.get("key", err) if isinstance(err, dict) else err
            message += f"\n• `{err_msg}`"

    try:
        from bot.notifications import send_telegram_message
        send_telegram_message(message)
    except Exception:
        print("Failed to send cleanup notification to Telegram")

    return {
        "r2": r2_result,
        "local": local_result,
    }


if __name__ == "__main__":
    run_cleanup()
