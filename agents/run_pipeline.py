import os
import sys
import signal
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from main import daily_content_job, generate_short_video, generate_long_video, log_event, cleanup_stuck_state
from utils.cleanup_service import cleanup_temp_directories


_cleaned_up = False


def _cleanup():
    global _cleaned_up
    if _cleaned_up:
        return
    _cleaned_up = True
    try:
        from utils.firebase_status import reset_agent_statuses, update_pipeline_status
        from utils.subprocess_helper import _cleanup_all_temp
        reset_agent_statuses()
        update_pipeline_status(False, "")
        _cleanup_all_temp()
        log_event("CLEANUP", "Pipeline run complete — agent statuses reset, temp cleaned")
    except Exception as e:
        print(f"[CLEANUP] Cleanup failed: {e}", flush=True)


def main():
    cleanup_stuck_state()
    cleanup_temp_directories()
    from main import update_pipeline_status

    update_pipeline_status(True, "Workflow triggered")
    topic = os.environ.get("TOPIC", "")
    raw_fmt = os.environ.get("FORMAT", "shorts").strip().lower()
    format_type = "shorts" if raw_fmt in ("short", "shorts") else "long"
    category = os.environ.get("CATEGORY", "AI Explained")

    success = False
    try:
        if topic:
            log_event("MANUAL", f"Generating custom video: {topic} ({format_type})")
            if format_type == "shorts":
                success = generate_short_video(topic, category, f"manual-{format_type}")
            else:
                success = generate_long_video(topic, category, f"manual-{format_type}")
            log_event("MANUAL", f"Result: {'SUCCESS' if success else 'FAILED'}")
        else:
            log_event("SCHEDULED", "Running daily content generation")
            success = daily_content_job()
            if not success:
                log_event("SCHEDULED", "Daily content generation produced no videos")
    finally:
        _cleanup()

    if not success:
        sys.exit(1)


def _signal_handler(signum, frame):
    _cleanup()
    sys.exit(1 if signum == signal.SIGTERM else 0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    try:
        main()
    except Exception:
        _cleanup()
        raise
