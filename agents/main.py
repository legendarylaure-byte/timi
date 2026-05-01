import os
import sys
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from datetime import datetime

load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from crew.scriptwriter import create_scriptwriter_crew
from crew.storyboard import create_storyboard_crew
from crew.voice import create_voice_crew
from crew.composer import create_composer_crew
from crew.animator import create_animator_crew
from crew.editor import create_editor_crew
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

AGENT_MAP = {
    'scriptwriter': 'scriptwriter',
    'storyboard': 'storyboard',
    'voice': 'voice',
    'composer': 'composer',
    'animator': 'animator',
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

def generate_short_video(topic: str, category: str, video_id: str):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "shorts", "generating")
    log_event("PIPELINE", f"Starting SHORT video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {"topic": topic, "category": category, "format": "shorts", "max_duration": 120})
        
        # Quality Score step
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
        voice = run_agent_step("voice", "Voice Actor", "Generating voice-over", create_voice_crew, {"script": str(script)})
        music = run_agent_step("composer", "Composer", "Creating background music", create_composer_crew, {"category": category, "duration": 120})
        animation = run_agent_step("animator", "Animator", "Generating animation frames", create_animator_crew, {"storyboard": str(storyboard), "format": "shorts"})
        video = run_agent_step("editor", "Video Editor", "Compositing video", create_editor_crew, {"animation": str(animation), "voice": str(voice), "music": str(music), "format": "shorts"})
        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "shorts"})
        metadata = run_agent_step("metadata", "Metadata Writer", "Writing metadata", create_metadata_crew, {"script": str(script), "format": "shorts"})
        result = run_agent_step("publisher", "Publisher", "Uploading video", create_publisher_crew, {"video": str(video), "thumbnail": str(thumbnail), "metadata": str(metadata), "format": "shorts"})
        
        # Multi-platform publishing
        update_agent_status("publisher", "working", f"Publishing to platforms: {topic}")
        platforms_to_publish = ['youtube']  # Default, can be configured
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description="",
            video_path=str(video),
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
        
        # Quality Score step
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
        voice = run_agent_step("voice", "Voice Actor", "Generating voice-over", create_voice_crew, {"script": str(script)})
        music = run_agent_step("composer", "Composer", "Creating background music", create_composer_crew, {"category": category, "duration": 300})
        animation = run_agent_step("animator", "Animator", "Generating animation frames", create_animator_crew, {"storyboard": str(storyboard), "format": "long"})
        video = run_agent_step("editor", "Video Editor", "Compositing video", create_editor_crew, {"animation": str(animation), "voice": str(voice), "music": str(music), "format": "long"})
        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "long"})
        metadata = run_agent_step("metadata", "Metadata Writer", "Writing metadata", create_metadata_crew, {"script": str(script), "format": "long"})
        result = run_agent_step("publisher", "Publisher", "Uploading video", create_publisher_crew, {"video": str(video), "thumbnail": str(thumbnail), "metadata": str(metadata), "format": "long"})
        
        # Multi-platform publishing
        update_agent_status("publisher", "working", f"Publishing to platforms: {topic}")
        platforms_to_publish = ['youtube', 'facebook']  # Long form goes to YouTube + Facebook
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description="",
            video_path=str(video),
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
