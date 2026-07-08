"""
Test publish to Instagram and Facebook only.
Usage: python test_publish.py  (run from agents/ directory)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from utils.multi_platform_publisher import multi_platform_publish

BASE = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(BASE, "output", "test_publish_short.mp4")
THUMB_PATH = os.path.join(BASE, "tmp", "thumbnails", "test_thumb.png")

if not os.path.exists(VIDEO_PATH):
    print(f"Video not found: {VIDEO_PATH}")
    sys.exit(1)

print("=" * 60)
print("Test Publish — Instagram + Facebook")
print("Skipping YouTube (already verified)")
print("Skipping TikTok (waiting for production keys)")
print("=" * 60)

result = multi_platform_publish(
    video_id="test_publish_20260706_v2",
    title="AI is transforming education in 2026",
    description="AI is transforming the way we learn. From personalized tutors to smart classrooms, education will never be the same.",
    video_path=VIDEO_PATH,
    thumbnail_path=THUMB_PATH,
    format_type="shorts",
    platforms=["facebook", "instagram"],
    category="AI Explained",
    cleanup=False,
)

print("\n" + "=" * 60)
print("RESULTS:")
print(f"  Success: {result['success_count']}/{result['total_count']}")
for p, r in result['platforms'].items():
    status = "✅" if r.get('success') else "❌"
    url = r.get('url', r.get('video_url', ''))
    err = r.get('error', '')
    print(f"  {status} {p.title()}: {url or err}")
print("=" * 60)
