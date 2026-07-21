"""Retry YouTube upload for videos that failed due to title-dict bug."""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

from dotenv import load_dotenv
load_dotenv()

from firebase_admin import credentials, firestore, initialize_app
import firebase_admin

VIDEOS = [
    {
        "id": "short-20260720-1",
        "title": "How do LLMs power medical AI?",
        "category": "AI Explained",
        "format": "shorts",
        "path": "/Users/Ai Mark/timi/agents/output/short-20260720-1_shorts.mp4",
    },
    {
        "id": "short-20260720-2",
        "title": "Is Open Source for YOU?",
        "category": "Open Source",
        "format": "shorts",
        "path": "/Users/Ai Mark/timi/agents/output/short-20260720-2_shorts.mp4",
    },
    {
        "id": "long-20260720-1",
        "title": "Stuck? Build AI Projects This Weekend!",
        "category": "AI Tutorials",
        "format": "long",
        "path": "/Users/Ai Mark/timi/agents/output/long-20260720-1_long.mp4",
    },
]

def gen_thumbnail(video_path):
    out = tempfile.mktemp(suffix='.jpg', dir='/tmp')
    subprocess.run(['/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg', '-y', '-i', video_path,
                    '-vframes', '1', '-q:v', '2', out],
                   capture_output=True, timeout=30)
    return out if os.path.getsize(out) > 1000 else None

def main():
    cred_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS',
                          '/Users/Ai Mark/timi/keys/timi-childern-stories-firebase-adminsdk-fbsvc-1997849771.json')
    cred = credentials.Certificate(cred_path)
    initialize_app(cred)
    db = firestore.client()

    from multi_platform_publisher import upload_to_platform, log_activity

    for v in VIDEOS:
        video_id = v["id"]
        doc = db.collection('videos').document(video_id).get()
        meta = doc.to_dict() if doc.exists else {}

        title = meta.get('title', v["title"])
        if isinstance(title, dict):
            title = title.get('title', v["title"])

        desc = meta.get('description', f"AI-powered {v['format']} video about {v['title']}.")
        if isinstance(desc, dict):
            desc = desc.get('description', str(desc))

        tags = meta.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]

        print(f"\n{'='*60}")
        print(f"Publishing {video_id}: {title}")
        print(f"  Format: {v['format']}, Category: {v['category']}")
        print(f"  File: {v['path']} ({os.path.getsize(v['path']) // 1024 // 1024}MB)")
        print(f"  Description: {desc[:100]}...")
        print(f"  Tags: {tags}")

        thumb = gen_thumbnail(v['path'])
        print(f"  Thumbnail: {thumb}")

        result = upload_to_platform(
            'youtube', title, desc, v['path'], thumb or '',
            format_type=v['format'], tags=tags
        )
        if result.get('success'):
            url = result.get('url', result.get('video_url', ''))
            print(f"  ✅ Published! {url}")
            db.collection('videos').document(video_id).update({
                'youtube_url': url,
                'youtube_id': result.get('video_id', ''),
                'status': 'published',
            })
        else:
            print(f"  ❌ Failed: {result.get('error', 'unknown')}")

if __name__ == '__main__':
    main()
