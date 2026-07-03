import os
import sys
import signal
from pathlib import Path
from main import daily_content_job, generate_short_video, generate_long_video, log_event, cleanup_stuck_state
from utils.cleanup_service import cleanup_temp_directories


def _cleanup():
    from utils.firebase_status import reset_agent_statuses, update_pipeline_status
    reset_agent_statuses()
    update_pipeline_status(False, "")
    log_event("CLEANUP", "Pipeline run complete — agent statuses reset")


def main():
    cleanup_stuck_state()
    cleanup_temp_directories()
    from main import update_pipeline_status

    update_pipeline_status(True, "Workflow triggered")
    topic = os.environ.get("TOPIC", "")
    format_type = os.environ.get("FORMAT", "shorts")
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


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: (_cleanup(), sys.exit(1)))
    signal.signal(signal.SIGINT, lambda *_: (_cleanup(), sys.exit(1)))
    main()
