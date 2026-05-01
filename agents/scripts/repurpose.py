"""
Standalone Repurposing Script
Run: python -m agents.scripts.repurpose --title "..." --duration 300
"""
import argparse
import json
from agents.utils.repurposer import repurpose_video, batch_reprocess_all_videos

def main():
    parser = argparse.ArgumentParser(description='Content Repurposing Agent')
    parser.add_argument('--title', help='Video title')
    parser.add_argument('--duration', type=int, default=300, help='Video duration in seconds')
    parser.add_argument('--video_id', default='temp-video', help='Video ID')
    parser.add_argument('--batch', action='store_true', help='Batch process all videos')
    args = parser.parse_args()

    if args.batch:
        print("\n📦 Batch processing all long-form videos...")
        result = batch_reprocess_all_videos()
        print(json.dumps(result, indent=2, default=str))
    elif args.title:
        print(f"\n✂️ Repurposing: {args.title}")
        result = repurpose_video(args.video_id, args.title, args.duration)
        print(f"\nGenerated {result['total_clips']} clips:")
        for clip in result['clips']:
            print(f"  🎬 {clip['title']}")
            print(f"     {clip['start_time']}s - {clip['end_time']}s ({clip['duration']}s) | Hook: {clip['hook_score']}/100")
            print(f"     {clip.get('reasoning', '')}")
            print()
        print(f"Estimated total views: {result.get('estimated_total_views', 0):,}")
        print(json.dumps(result, indent=2, default=str))
    else:
        print("Use --title or --batch flag. Run with --help for options.")

if __name__ == '__main__':
    main()
