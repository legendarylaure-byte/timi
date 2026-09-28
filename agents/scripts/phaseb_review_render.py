"""Owner-review render for Phase B: exactly one short, render-only, isolated.

Not part of the pipeline -- a review harness. DEMO_RENDER_ONLY=1 short-circuits
_platforms_to_publish() to [], so the video is rendered and measured but can
never reach a platform even if the env guard were misread. Kept to a hardcoded
video_id so it can never collide with a production record.
"""
import glob
import os
import sys

os.environ.setdefault("DEMO_RENDER_ONLY", "1")

from main import generate_short_video  # noqa: E402

TOPIC = "How a transformer actually reads a sentence"
CATEGORY = "AI News"
VIDEO_ID = "phaseb-review-short"

if __name__ == "__main__":
    print(f"RENDER-ONLY review short: {VIDEO_ID} | DEMO_RENDER_ONLY={os.environ['DEMO_RENDER_ONLY']}")
    r = generate_short_video(TOPIC, CATEGORY, VIDEO_ID)

    # generate_short_video() returns a truthy/falsy value, not the record dict --
    # the earlier version of this script assumed a dict and died on
    # `r.get("video_path")` with "'bool' object has no attribute 'get'". Locate
    # the artifact by name instead of trusting a return shape.
    print("returned:", type(r).__name__, r)
    paths = sorted(glob.glob(f"/app/output/{VIDEO_ID}_shorts*.mp4"))
    for p in paths:
        print(f"ARTIFACT {p} ({os.path.getsize(p)} bytes)")
    sys.exit(0 if paths else 1)
