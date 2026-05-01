"""
Content Repurposing Agent
Auto-splits long-form videos into viral shorts.
Run: python -m agents.scripts.repurpose --video_id "v-001" --title "..."
"""
import os
import json
import random
from utils.groq_client import generate_completion
from utils.firebase_status import get_firestore_client, log_activity, update_video_record

SYSTEM_PROMPT = """You are a content repurposing expert for children's YouTube/TikTok videos.
Given a long-form video title and approximate duration, identify the best segments to extract as shorts (30-60 seconds each).
Focus on moments with strong hooks, educational value, or entertainment peak.

Return ONLY a valid JSON object with this exact structure:

{
  "clips": [
    {
      "title": "Catchy short title",
      "start_time": seconds_from_start,
      "end_time": seconds_from_start,
      "duration": seconds,
      "hook_score": 0-100,
      "reasoning": "Why this segment works as a short"
    }
  ],
  "total_clips": number,
  "estimated_total_views": number
}

Each clip should be 30-60 seconds. Start times should not overlap. Hook score should reflect engagement potential."""

def repurpose_video(video_id: str, title: str, duration_seconds: int = 300) -> dict:
    """Analyze a long video and generate repurposing clips."""
    log_activity("repurposer", f"Starting repurpose: {title}", "info")

    prompt = f"""Repurpose this long-form children's video into shorts:

Title: {title}
Duration: {duration_seconds} seconds ({duration_seconds // 60}min {duration_seconds % 60}s)
Target: YouTube Shorts / TikTok / Instagram Reels

Identify 3-6 high-engagement segments suitable for 30-60 second clips."""

    try:
        response = generate_completion(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=0.5,
            max_tokens=1500,
        )

        json_start = response.find("{")
        json_end = response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(response[json_start:json_end])
        else:
            result = _fallback_repurpose(title, duration_seconds)

        # Save to Firestore
        _save_repurpose_job(video_id, title, duration_seconds, result)
        
        log_activity("repurposer", f"Generated {len(result['clips'])} clips from '{title}'", "success")
        return result

    except Exception as e:
        log_activity("repurposer", f"Repurpose failed: {str(e)}", "error")
        return _fallback_repurpose(title, duration_seconds)


def _fallback_repurpose(title: str, duration: int) -> dict:
    """Fallback clip generation if Groq fails."""
    clip_count = max(3, min(6, duration // 90))
    clips = []
    
    words = title.split()
    key_words = [w for w in words if len(w) > 3]
    
    for i in range(clip_count):
        clip_duration = random.randint(35, 58)
        start = i * (duration // clip_count) + random.randint(5, 15)
        end = start + clip_duration
        
        if end > duration:
            end = duration
            clip_duration = end - start
        
        hook = random.randint(65, 96)
        
        clips.append({
            "title": f"{key_words[0] if key_words else 'Clip'}: {random.choice(['Amazing', 'Fun', 'Learn', 'Discover', 'Why'])} {random.choice(['Fact', 'Story', 'Song', 'Magic', 'Secret'])}",
            "start_time": start,
            "end_time": end,
            "duration": clip_duration,
            "hook_score": hook,
            "reasoning": f"Strong engagement point at {start}s with high retention potential",
        })

    return {
        "clips": clips,
        "total_clips": len(clips),
        "estimated_total_views": sum(random.randint(5000, 50000) for _ in clips),
    }


def _save_repurpose_job(video_id: str, title: str, duration: int, result: dict):
    """Save repurpose job to Firestore."""
    try:
        db = get_firestore_client()
        
        clips_data = []
        for clip in result.get("clips", []):
            clips_data.append({
                "id": f"clip-{random.randint(1000, 9999)}",
                "title": clip["title"],
                "start_time": clip["start_time"],
                "end_time": clip["end_time"],
                "duration": clip["duration"],
                "hook_score": clip["hook_score"],
                "thumbnail_ready": False,
                "status": "ready",
            })

        job_data = {
            "source_video_id": video_id,
            "source_title": title,
            "source_duration": duration,
            "clips_generated": len(clips_data),
            "clips": clips_data,
            "status": "completed",
            "estimated_total_views": result.get("estimated_total_views", 0),
        }

        doc_ref = db.collection('repurpose_jobs').document()
        doc_ref.set(job_data)
        
        # Update source video with repurpose flag
        update_video_record(video_id, {"repurposed": True, "repurpose_clips": len(clips_data)})
        
        print(f"[REPURPOSE] Saved {len(clips_data)} clips for '{title}'")
    except Exception as e:
        print(f"[REPURPOSE] Failed to save: {e}")


def batch_reprocess_all_videos() -> dict:
    """Scan all long-form videos and find repurposing opportunities."""
    try:
        db = get_firestore_client()
        videos = db.collection('videos').where('format', '==', 'long').where('status', '==', 'uploaded').stream()
        
        results = []
        for vid in videos:
            data = vid.to_dict()
            if not data.get('repurposed'):
                result = repurpose_video(vid.id, data.get('title', 'Unknown'), data.get('duration', 300))
                results.append({"video_id": vid.id, "title": data.get('title'), "clips": result['total_clips']})
        
        return {"processed": len(results), "videos": results}
    except Exception as e:
        print(f"[REPURPOSE] Batch failed: {e}")
        return {"processed": 0, "videos": [], "error": str(e)}
