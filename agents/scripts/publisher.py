"""
Standalone Multi-Platform Publisher Script
Run: python -m agents.scripts.publisher --title "..." --platforms youtube,tiktok,instagram
"""
import argparse
import json
from agents.utils.multi_platform_publisher import multi_platform_publish


def main():
    parser = argparse.ArgumentParser(description='Multi-Platform Publisher')
    parser.add_argument('--title', required=True, help='Video title')
    parser.add_argument('--description', default='', help='Video description')
    parser.add_argument('--video', default='/tmp/video.mp4', help='Video file path')
    # TikTok rejects watermarked submissions, so it needs its own watermark-free
    # file. Without this the publisher fails closed on TikTok with a message
    # naming the fix but no way to act on it from the command line.
    parser.add_argument('--tiktok-video', help='Watermark-free video path (required for TikTok)')
    parser.add_argument('--thumbnail', default='/tmp/thumb.jpg', help='Thumbnail file path')
    parser.add_argument('--format', default='shorts', choices=['shorts', 'long'], help='Video format')
    parser.add_argument('--platforms', default='youtube', help='Comma-separated platforms')
    parser.add_argument('--video_id', default='temp-video', help='Video ID')
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(',')]

    # ponytail: `--schedule` used to write a doc into the `upload_queue` collection
    # that nothing ever dequeued, so it only ever looked like a queue. Publishing a
    # now-scheduled upload still goes through publish_at / APScheduler, so there is
    # no queue to write to. Removed rather than left as a write-only UI.
    print(f"\n📤 Publishing '{args.title}' to: {', '.join(platforms)}")
    result = multi_platform_publish(
        video_id=args.video_id,
        title=args.title,
        description=args.description,
        video_path=args.video,
        tiktok_path=args.tiktok_video,
        thumbnail_path=args.thumbnail,
        format_type=args.format,
        platforms=platforms,
    )

    print("\nResults:")
    for platform, r in result['platforms'].items():
        status = '✅' if r.get('success') else '❌'
        print(f"  {status} {platform}: {r.get('url', r.get('error', ''))}")

    print(f"\nSuccess: {result['success_count']}/{result['total_count']}")
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
