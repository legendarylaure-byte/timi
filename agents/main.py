import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crew.scriptwriter import create_scriptwriter_crew
from crew.storyboard import create_storyboard_crew
from crew.animator import create_animator_crew
from crew.thumbnail import create_thumbnail_crew
from crew.metadata import create_metadata_crew
from crew.publisher import create_publisher_crew
from utils.firebase_status import (
    update_agent_status,
    log_activity,
    is_agent_enabled,
    update_pipeline_status,
    add_video_record,
    update_video_record,
)
from utils.firebase_control import AgentControlListener
from utils.cleanup_service import run_cleanup
from utils.quality_scorer import score_content, predict_performance
from utils.trend_discovery import discover_trends
from utils.repurposer import batch_reprocess_all_videos
from utils.multi_platform_publisher import multi_platform_publish
from utils.stock_video import search_videos_for_scenes
from utils.voice_gen import generate_voiceover
from utils.music_gen import generate_background_music
from utils.video_compositor import composite_video

AGENT_MAP = {
    'scriptwriter': 'scriptwriter',
    'storyboard': 'storyboard',
    'voice': 'voice',
    'animator': 'animator',
    'composer': 'composer',
    'editor': 'editor',
    'thumbnail': 'thumbnail',
    'metadata': 'metadata',
    'publisher': 'publisher',
}

control_listener = AgentControlListener(check_interval=5)

def log_event(agent: str, message: str, level: str = "info"):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] [{agent}] {message}")

def run_agent_step(agent_id: str, agent_name: str, action: str, crew_factory, inputs: dict):
    if control_listener.is_paused(agent_id):
        log_event(agent_name, "Skipped (paused by user)")
        update_agent_status(agent_id, "idle", "Paused by user")
        return None

    update_agent_status(agent_id, "working", action)
    log_event(agent_name, action)
    log_activity(agent_id, action, "info")

    try:
        crew = crew_factory()
        result = crew.kickoff(inputs=inputs)
        update_agent_status(agent_id, "completed", f"Completed: {action}")
        log_activity(agent_id, f"Completed: {action}", "success")
        log_event(agent_name, f"Completed: {action}")
        return result
    except Exception as e:
        update_agent_status(agent_id, "error", f"Failed: {action}", str(e))
        log_activity(agent_id, f"Failed: {action} - {str(e)}", "error")
        log_event(agent_name, f"Failed: {action} - {str(e)}", "error")
        raise

def parse_scenes_from_storyboard(storyboard_text: str) -> list[dict]:
    try:
        json_match = ""
        if "[" in storyboard_text and "]" in storyboard_text:
            start = storyboard_text.index("[")
            end = storyboard_text.rindex("]") + 1
            json_match = storyboard_text[start:end]
            scenes = json.loads(json_match)
            if isinstance(scenes, list) and len(scenes) > 0:
                return scenes
    except Exception:
        pass

    lines = storyboard_text.strip().split("\n")
    scenes = []
    for i, line in enumerate(lines):
        if any(kw in line.lower() for kw in ["scene", "shot", "clip"]):
            scenes.append({
                "keyword": line.strip()[:50],
                "target_duration": 5.0,
                "description": line.strip(),
            })
    if not scenes:
        scenes = [{"keyword": "nature", "target_duration": 5.0, "description": "general scene"}]
    return scenes

def run_video_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int) -> dict:
    log_event("PIPELINE", "Step 1: Analyzing storyboard for scene keywords")
    scenes = parse_scenes_from_storyboard(storyboard_text)
    log_event("PIPELINE", f"Found {len(scenes)} scenes to source video for")

    orientation = "portrait" if format_type == "shorts" else "landscape"
    update_agent_status("animator", "working", f"Fetching stock video for {len(scenes)} scenes")
    log_event("ANIMATOR", f"Searching Pexels/Pixabay for {len(scenes)} real video clips")
    clips = search_videos_for_scenes(scenes, orientation=orientation)
    log_event("ANIMATOR", f"Found {len(clips)}/{len(scenes)} video clips with real motion")
    update_agent_status("animator", "completed", f"Found {len(clips)} video clips")

    if not clips:
        raise Exception("No video clips found. Cannot create video.")

    log_event("PIPELINE", "Step 2: Generating voice-over with Edge TTS")
    update_agent_status("voice", "working", "Generating narration audio")
    voice_result = asyncio.run(generate_voiceover(script_text))
    if not voice_result.get("success"):
        raise Exception("Voice-over generation failed.")
    log_event("VOICE", f"Voice-over: {voice_result['duration']:.1f}s, {voice_result['segments']} segments -> {voice_result['path']}")
    update_agent_status("voice", "completed", f"Voice-over {voice_result['duration']:.1f}s")

    total_video_duration = sum(c["duration"] for c in clips)
    log_event("PIPELINE", "Step 3: Generating background music")
    update_agent_status("composer", "working", "Creating background music")
    music_result = generate_background_music(category, duration=total_video_duration)
    music_path = music_result.get("path")
    log_event("COMPOSER", f"Music: {music_result.get('mood', 'unknown')} mood -> {music_path}")
    update_agent_status("composer", "completed", f"Music generated ({music_result.get('mood')})")

    log_event("PIPELINE", "Step 4: Compositing final video")
    update_agent_status("editor", "working", "Compositing video with FFmpeg")
    final_path = composite_video(
        clips=clips,
        voice_path=voice_result["path"],
        music_path=music_path,
        format_type=format_type,
        video_id=video_id,
    )
    if not final_path:
        raise Exception("Video compositing failed.")
    log_event("EDITOR", f"Final video: {final_path}")
    update_agent_status("editor", "completed", f"Video composited -> {final_path}")

    return {
        "video_path": final_path,
        "voice_path": voice_result["path"],
        "music_path": music_path,
        "clips_used": len(clips),
        "duration": total_video_duration,
    }

def generate_short_video(topic: str, category: str, video_id: str):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "shorts", "generating")
    log_event("PIPELINE", f"Starting SHORT video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {"topic": topic, "category": category, "format": "shorts", "max_duration": 120})

        update_agent_status("quality_scorer", "working", f"Scoring: {topic}")
        quality = score_content(str(script), topic, category, "shorts")
        prediction = predict_performance(topic, category, "shorts", str(script))
        update_video_record(video_id, {
            "quality_score": quality["overall_score"],
            "quality_breakdown": quality.get("breakdown", {}),
            "predicted_views_7d": prediction["predicted_views_7d"],
            "predicted_views_30d": prediction["predicted_views_30d"],
            "virality_score": prediction["virality_score"],
        })
        log_event("QUALITY", f"Score: {quality['overall_score']}/100, Predicted 7D: {prediction['predicted_views_7d']:,} views")

        if quality["recommendation"] == "block":
            add_video_record(video_id, topic, "shorts", "blocked")
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard", create_storyboard_crew, {"script": str(script)})

        video_result = run_video_pipeline(str(script), str(storyboard), category, "shorts", video_id, 120)

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "shorts"})
        metadata = run_agent_step("metadata", "Metadata Writer", "Writing metadata", create_metadata_crew, {"script": str(script), "format": "shorts"})

        update_agent_status("publisher", "working", f"Publishing to platforms: {topic}")
        platforms_to_publish = ['youtube']
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description="",
            video_path=video_result["video_path"],
            thumbnail_path=str(thumbnail),
            format_type="shorts",
            platforms=platforms_to_publish,
        )
        log_event("PUBLISH", f"Published to {publish_result['success_count']}/{publish_result['total_count']} platforms")

        add_video_record(video_id, topic, "shorts", "uploaded")
        log_event("PIPELINE", f"SHORT video generation SUCCESS: {topic}")
        update_pipeline_status(False)
        return True
    except Exception as e:
        add_video_record(video_id, topic, "shorts", "failed")
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"SHORT video generation FAILED: {str(e)}", "error")
        return False

def generate_long_video(topic: str, category: str, video_id: str):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "long", "generating")
    log_event("PIPELINE", f"Starting LONG video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {"topic": topic, "category": category, "format": "long", "max_duration": 300})

        update_agent_status("quality_scorer", "working", f"Scoring: {topic}")
        quality = score_content(str(script), topic, category, "long")
        prediction = predict_performance(topic, category, "long", str(script))
        update_video_record(video_id, {
            "quality_score": quality["overall_score"],
            "quality_breakdown": quality.get("breakdown", {}),
            "predicted_views_7d": prediction["predicted_views_7d"],
            "predicted_views_30d": prediction["predicted_views_30d"],
            "virality_score": prediction["virality_score"],
        })
        log_event("QUALITY", f"Score: {quality['overall_score']}/100, Predicted 7D: {prediction['predicted_views_7d']:,} views")

        if quality["recommendation"] == "block":
            add_video_record(video_id, topic, "long", "blocked")
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard", create_storyboard_crew, {"script": str(script)})

        video_result = run_video_pipeline(str(script), str(storyboard), category, "long", video_id, 300)

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "long"})
        metadata = run_agent_step("metadata", "Metadata Writer", "Writing metadata", create_metadata_crew, {"script": str(script), "format": "long"})

        update_agent_status("publisher", "working", f"Publishing to platforms: {topic}")
        platforms_to_publish = ['youtube', 'facebook']
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description="",
            video_path=video_result["video_path"],
            thumbnail_path=str(thumbnail),
            format_type="long",
            platforms=platforms_to_publish,
        )
        log_event("PUBLISH", f"Published to {publish_result['success_count']}/{publish_result['total_count']} platforms")

        add_video_record(video_id, topic, "long", "uploaded")
        log_event("PIPELINE", f"LONG video generation SUCCESS: {topic}")
        update_pipeline_status(False)
        return True
    except Exception as e:
        add_video_record(video_id, topic, "long", "failed")
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"LONG video generation FAILED: {str(e)}", "error")
        return False

def daily_content_job():
    update_pipeline_status(True)
    log_event("SCHEDULER", "Starting daily content generation")
    
    # Discover trending topics first
    log_event("TRENDS", "Discovering trending topics for today")
    update_agent_status("trend_discovery", "working", "Scanning for trending topics")
    trends = discover_trends()
    update_agent_status("trend_discovery", "completed", f"Found {len(trends)} trending topics")
    log_event("TRENDS", f"Found {len(trends)} trending topics")
    
    # Pick top trending topics for today's content
    top_trends = sorted(trends, key=lambda t: t['score'], reverse=True)[:4]
    
    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    for i in range(shorts_per_day):
        trend = top_trends[i % len(top_trends)]
        generate_short_video(trend['title'], trend['category'], f"short-{datetime.now().strftime('%Y%m%d')}-{i+1}")

    for i in range(long_per_day):
        trend = top_trends[(shorts_per_day + i) % len(top_trends)]
        generate_long_video(trend['title'], trend['category'], f"long-{datetime.now().strftime('%Y%m%d')}-{i+1}")

    update_pipeline_status(False)
    log_event("SCHEDULER", "Daily content generation complete")

def daily_repurpose_job():
    log_event("REPURPOSE", "Starting content repurposing scan")
    update_agent_status("repurposer", "working", "Scanning for repurposing opportunities")
    result = batch_reprocess_all_videos()
    update_agent_status("repurposer", "completed", f"Processed {result['processed']} videos")
    log_event("REPURPOSE", f"Repurposed {result['processed']} videos into {sum(v.get('clips', 0) for v in result.get('videos', []))} clips")

def daily_cleanup_job():
    log_event("CLEANUP", "Starting auto-cleanup of uploaded videos")
    run_cleanup()
    log_event("CLEANUP", "Auto-cleanup complete")

if __name__ == "__main__":
    log_event("SYSTEM", "Vyom Ai Cloud - Agent Orchestrator Starting")

    control_listener.start()

    for agent_id in AGENT_MAP.values():
        update_agent_status(agent_id, "idle", "Ready")

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_content_job, "cron", hour=6, minute=0)
    scheduler.add_job(daily_repurpose_job, "cron", hour=14, minute=0)
    scheduler.add_job(daily_cleanup_job, "cron", hour=4, minute=0)
    log_event("SCHEDULER", "Daily content job scheduled at 06:00 UTC")
    log_event("SCHEDULER", "Daily repurpose job scheduled at 14:00 UTC")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")

    try:
        daily_content_job()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_event("SYSTEM", "Agent Orchestrator Shutting Down")
        control_listener.stop()
        update_pipeline_status(False)
