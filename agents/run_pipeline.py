import os
import sys
from main import daily_content_job, generate_short_video, generate_long_video, log_event


def main():
    topic = os.environ.get('TOPIC', '')
    format_type = os.environ.get('FORMAT', 'shorts')
    category = os.environ.get('CATEGORY', 'Self-Learning')

    if topic:
        log_event('MANUAL', f'Generating custom video: {topic} ({format_type})')
        if format_type == 'shorts':
            success = generate_short_video(topic, category, f'manual-{format_type}')
        else:
            success = generate_long_video(topic, category, f'manual-{format_type}')
        log_event('MANUAL', f'Result: {"SUCCESS" if success else "FAILED"}')
        if not success:
            sys.exit(1)
    else:
        log_event('SCHEDULED', 'Running daily content generation')
        success = daily_content_job()
        if not success:
            log_event('SCHEDULED', 'Daily content generation produced no videos')
            sys.exit(1)


if __name__ == '__main__':
    main()
