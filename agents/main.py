import os
import sys
import json
import asyncio
import time
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
    get_firestore_client,
)
from utils.firebase_control import AgentControlListener
from utils.cleanup_service import run_cleanup
from utils.quality_scorer import score_content, predict_performance, check_repetition, evaluate_publish_decision
from utils.trend_discovery import discover_trends
from utils.repurposer import batch_reprocess_all_videos
from utils.multi_platform_publisher import multi_platform_publish
from utils.stock_video import search_videos_for_scenes
from utils.voice_gen import generate_voiceover
from utils.music_gen import generate_background_music
from utils.video_compositor import composite_video, add_chapter_markers
from utils.translate import translate_script, get_voice_for_language
from utils.subtitle_gen import generate_subtitles_for_video
from utils.description_gen import generate_description, get_coppa_metadata

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

control_listener = AgentControlListener(check_interval=15)

AUTO_APPROVE_THRESHOLD = int(os.getenv("AUTO_APPROVE_THRESHOLD", 80))
ENABLE_MULTI_LANG = os.getenv("ENABLE_MULTI_LANG", "true").lower() == "true"
ENABLE_SUBTITLES = os.getenv("ENABLE_SUBTITLES", "true").lower() == "true"
ENABLE_REVIEW_GATE = os.getenv("ENABLE_REVIEW_GATE", "true").lower() == "true"
MULTI_LANG_CODES = os.getenv("MULTI_LANG_CODES", "es,de,fr").split(",")

def log_event(agent: str, message: str, level: str = "info"):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [{level.upper()}] [{agent}] {message}")

def run_agent_step(agent_id: str, agent_name: str, action: str, crew_factory, inputs: dict, max_retries: int = 2):
    if control_listener.is_paused(agent_id):
        log_event(agent_name, "Skipped (paused by user)")
        update_agent_status(agent_id, "idle", "Paused by user")
        return None

    update_agent_status(agent_id, "working", action)
    log_event(agent_name, action)
    log_activity(agent_id, action, "info")

    for attempt in range(max_retries):
        try:
            crew = crew_factory()
            result = crew.kickoff(inputs=inputs)
            update_agent_status(agent_id, "completed", f"Completed: {action}")
            log_activity(agent_id, f"Completed: {action}", "success")
            log_event(agent_name, f"Completed: {action}")
            return result
        except Exception as e:
            if attempt < max_retries - 1:
                log_event(agent_name, f"Failed (attempt {attempt + 1}/{max_retries}), retrying: {str(e)[:100]}")
                time.sleep(2)
            else:
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

def run_video_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int, generate_subs: bool = True, subtitle_lang: str = "en") -> dict:
    log_event("PIPELINE", "Step 1: Analyzing storyboard for scene keywords")
    scenes = parse_scenes_from_storyboard(storyboard_text)
    log_event("PIPELINE", f"Found {len(scenes)} scenes to source video for")

    if format_type == "long":
        min_scenes = max(16, max_duration // 30)
        while len(scenes) < min_scenes:
            scenes.append({"keyword": "transition", "target_duration": 5.0, "description": "transition scene"})
        log_event("PIPELINE", f"Extended to {len(scenes)} scenes for >8min long-form")

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
    from utils.voice_gen import extract_narration_text, get_voice_settings
    narration_text = extract_narration_text(script_text)
    content_type = "bedtime" if "bedtime" in category.lower() else "story" if "story" in category.lower() or "fable" in category.lower() else "educational" if "science" in category.lower() or "learn" in category.lower() else "general"
    voice_result = asyncio.run(generate_voiceover(script_text, content_type=content_type))
    if not voice_result.get("success"):
        raise Exception("Voice-over generation failed.")
    log_event("VOICE", f"Voice-over: {voice_result['duration']:.1f}s, {voice_result['segments']} segments -> {voice_result['path']}")
    update_agent_status("voice", "completed", f"Voice-over {voice_result['duration']:.1f}s")

    subtitle_path = None
    if generate_subs and ENABLE_SUBTITLES and voice_result.get("timing_file"):
        log_event("PIPELINE", "Step 2.5: Generating subtitles")
        update_agent_status("voice", "working", "Generating subtitles from voice timing")
        sub_result = generate_subtitles_for_video(
            timing_file=voice_result["timing_file"],
            full_text=narration_text,
            language=subtitle_lang,
        )
        subtitle_path = sub_result.get("srt")
        if subtitle_path:
            log_event("VOICE", f"Subtitles generated: {subtitle_path}")

    total_video_duration = sum(c["duration"] for c in clips)
    log_event("PIPELINE", "Step 3: Generating background music")
    update_agent_status("composer", "working", "Creating background music")
    music_result = generate_background_music(category, duration=total_video_duration)
    music_path = music_result.get("path")
    log_event("COMPOSER", f"Music: {music_result.get('mood', 'unknown')} mood -> {music_path}")
    update_agent_status("composer", "completed", f"Music generated ({music_result.get('mood')})")

    chapters = None
    if format_type == "long" and scenes:
        chapters = []
        current_time = 0
        for i, scene in enumerate(scenes[:len(clips)]):
            clip_dur = clips[i]["duration"] if i < len(clips) else 5.0
            chapters.append({
                "start_time": current_time,
                "end_time": current_time + clip_dur,
                "title": scene.get("keyword", f"Chapter {i+1}"),
            })
            current_time += clip_dur
        log_event("PIPELINE", f"Generated {len(chapters)} chapter markers")

    log_event("PIPELINE", "Step 4: Compositing final video")
    update_agent_status("editor", "working", "Compositing video with FFmpeg")
    final_path = composite_video(
        clips=clips,
        voice_path=voice_result["path"],
        music_path=music_path,
        format_type=format_type,
        video_id=video_id,
        subtitle_path=subtitle_path,
        chapters=chapters,
        category=category,
    )
    if not final_path:
        raise Exception("Video compositing failed.")
    log_event("EDITOR", f"Final video: {final_path}")
    update_agent_status("editor", "completed", f"Video composited -> {final_path}")

    return {
        "video_path": final_path,
        "voice_path": voice_result["path"],
        "music_path": music_path,
        "subtitle_path": subtitle_path,
        "clips_used": len(clips),
        "duration": total_video_duration,
        "chapters": chapters,
    }

def apply_review_gate(video_id: str, topic: str, format_type: str, script_text: str, quality: dict):
    if not ENABLE_REVIEW_GATE:
        log_event("REVIEW", "Review gate disabled - auto-publishing")
        return "auto_approve"

    repetition = check_repetition(script_text, topic)
    log_event("REVIEW", f"Repetition check: max_similarity={repetition.get('max_similarity', 0):.0%}")

    decision = evaluate_publish_decision(quality, repetition, AUTO_APPROVE_THRESHOLD)
    log_event("REVIEW", f"Decision: {decision['action']} - {decision['reason']}")

    update_video_record(video_id, {
        "review_status": decision["action"],
        "review_reason": decision["reason"],
        "repetition_check": repetition,
        "reviewed_at": datetime.utcnow().isoformat(),
    })

    if decision["action"] == "block":
        add_video_record(video_id, topic, format_type, "blocked_review")
        log_event("REVIEW", f"BLOCKED: {topic}")
        return "block"
    elif decision["action"] == "manual_review":
        add_video_record(video_id, topic, format_type, "pending_review")
        log_event("REVIEW", f"PENDING REVIEW: {topic}")
        return "pending_review"

    return "auto_approve"

def generate_short_video(topic: str, category: str, video_id: str, publish_at: str = None):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "shorts", "generating")
    log_event("PIPELINE", f"Starting SHORT video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {"topic": topic, "category": category, "format": "shorts", "max_duration": 120})
        script_text = str(script)

        update_agent_status("quality_scorer", "working", f"Scoring: {topic}")
        quality = score_content(script_text, topic, category, "shorts")
        prediction = predict_performance(topic, category, "shorts", script_text)
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

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard", create_storyboard_crew, {"script": script_text})

        video_result = run_video_pipeline(script_text, str(storyboard), category, "shorts", video_id, 120)

        review_decision = apply_review_gate(video_id, topic, "shorts", script_text, quality)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "shorts"})

        desc_result = generate_description(
            title=topic,
            script=script_text,
            category=category,
            format_type="shorts",
            channel_name="Vyom Ai Cloud",
        )

        platforms_to_publish = ['youtube']
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description=desc_result.get("full_description", ""),
            video_path=video_result["video_path"],
            thumbnail_path=str(thumbnail),
            format_type="shorts",
            platforms=platforms_to_publish,
            publish_at=publish_at,
        )
        publish_status = "scheduled" if publish_at else "Published"
        log_event("PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms")

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result["video_path"],
                thumbnail_path=str(thumbnail),
                voice_path=video_result.get("voice_path"),
                music_path=video_result.get("music_path"),
                subtitle_path=video_result.get("subtitle_path"),
            )

        if ENABLE_MULTI_LANG:
            log_event("PIPELINE", "Generating multi-language versions")
            translations = {}
            for lang_code in MULTI_LANG_CODES:
                try:
                    translations[lang_code] = translate_script(script_text, lang_code, title=topic)
                except Exception as e:
                    log_event("TRANSLATE", f"Failed {lang_code}: {e}")

            if translations:
                update_video_record(video_id, {
                    "translations": {k: v.get("title", "") for k, v in translations.items()},
                })

        youtube_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        update_video_record(video_id, {
            "status": "scheduled" if publish_at else "uploaded",
            "youtube_url": youtube_url,
            "publish_at": publish_at,
        })
        log_event("PIPELINE", f"SHORT video generation SUCCESS: {topic}")
        update_pipeline_status(False)
        return True
    except Exception as e:
        add_video_record(video_id, topic, "shorts", "failed")
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"SHORT video generation FAILED: {str(e)}", "error")
        return False

def generate_long_video(topic: str, category: str, video_id: str, publish_at: str = None):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "long", "generating")
    log_event("PIPELINE", f"Starting LONG video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {"topic": topic, "category": category, "format": "long", "max_duration": 600})
        script_text = str(script)

        update_agent_status("quality_scorer", "working", f"Scoring: {topic}")
        quality = score_content(script_text, topic, category, "long")
        prediction = predict_performance(topic, category, "long", script_text)
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

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard", create_storyboard_crew, {"script": script_text})

        video_result = run_video_pipeline(script_text, str(storyboard), category, "long", video_id, 600)

        review_decision = apply_review_gate(video_id, topic, "long", script_text, quality)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail", create_thumbnail_crew, {"topic": topic, "format": "long"})

        desc_result = generate_description(
            title=topic,
            script=script_text,
            category=category,
            format_type="long",
            scenes=parse_scenes_from_storyboard(str(storyboard)),
            channel_name="Vyom Ai Cloud",
        )

        platforms_to_publish = ['youtube', 'facebook']
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description=desc_result.get("full_description", ""),
            video_path=video_result["video_path"],
            thumbnail_path=str(thumbnail),
            format_type="long",
            platforms=platforms_to_publish,
            publish_at=publish_at,
        )
        publish_status = "scheduled" if publish_at else "Published"
        log_event("PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms")

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result["video_path"],
                thumbnail_path=str(thumbnail),
                voice_path=video_result.get("voice_path"),
                music_path=video_result.get("music_path"),
                subtitle_path=video_result.get("subtitle_path"),
            )

        update_video_record(video_id, {
            "script": script_text,
            "subtitle_path": video_result.get("subtitle_path"),
            "chapters": video_result.get("chapters"),
            "is_above_8min": video_result.get("duration", 0) >= 480,
        })

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

    log_event("TRENDS", "Discovering trending topics for today")
    update_agent_status("trend_discovery", "working", "Scanning for trending topics")
    trends = discover_trends()
    update_agent_status("trend_discovery", "completed", f"Found {len(trends)} trending topics")
    log_event("TRENDS", f"Found {len(trends)} trending topics")

    top_trends = sorted(trends, key=lambda t: t['score'], reverse=True)[:4]

    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    for i in range(shorts_per_day):
        trend = top_trends[i % len(top_trends)]
        publish_time = f"{datetime.now().strftime('%Y-%m-%d')}T{6 + i * 2}:00:00Z"
        generate_short_video(trend['title'], trend['category'], f"short-{datetime.now().strftime('%Y%m%d')}-{i+1}", publish_at=publish_time)

    for i in range(long_per_day):
        trend = top_trends[(shorts_per_day + i) % len(top_trends)]
        publish_time = f"{datetime.now().strftime('%Y-%m-%d')}T{10 + i * 4}:00:00Z"
        generate_long_video(trend['title'], trend['category'], f"long-{datetime.now().strftime('%Y%m%d')}-{i+1}", publish_at=publish_time)

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

def scheduled_publish_job():
    """Check for videos scheduled to publish now and process them."""
    try:
        db = get_firestore_client()
        now = time.time()
        q = db.collection('videos').where('status', '==', 'scheduled').where('publish_at', '<=', datetime.utcnow().isoformat()).stream()
        for doc in q:
            data = doc.to_dict()
            log_event("SCHEDULE", f"Publishing scheduled video: {data.get('title', 'unknown')}")
            # YouTube handles scheduled publishing via publishAt, so we just update status
            update_video_record(doc.id, {
                "status": "uploaded",
                "published_at": datetime.utcnow().isoformat(),
            })
            log_event("SCHEDULE", f"Video {doc.id} status updated to uploaded")
    except Exception as e:
        log_event("SCHEDULE", f"Scheduled publish check failed: {e}", "error")

def _handle_pipeline_trigger(topic: str, category: str, format_type: str, trigger_id: str, publish_at: str = None):
    """Handle a pipeline run trigger from the dashboard."""
    scheduled_note = f" (scheduled: {publish_at})" if publish_at else ""
    log_event("TRIGGER", f"Dashboard trigger: {format_type} - {topic} (id: {trigger_id}){scheduled_note}")
    try:
        video_id = f"trigger-{trigger_id}"
        if format_type == "long":
            success = generate_long_video(topic, category, video_id, publish_at=publish_at)
        else:
            success = generate_short_video(topic, category, video_id, publish_at=publish_at)

        db = get_firestore_client()
        db.collection('pipeline_triggers').document(trigger_id).update({
            'status': 'completed' if success else 'failed',
            'completed_at': time.time(),
        })
        log_event("TRIGGER", f"Pipeline complete: {'SUCCESS' if success else 'FAILED'}")
    except Exception as e:
        log_event("TRIGGER", f"Trigger failed: {e}", "error")
        try:
            db = get_firestore_client()
            db.collection('pipeline_triggers').document(trigger_id).update({
                'status': 'failed',
                'error': str(e),
                'completed_at': time.time(),
            })
        except Exception:
            pass

if __name__ == "__main__":
    log_event("SYSTEM", "Vyom Ai Cloud - Agent Orchestrator Starting")

    control_listener.set_trigger_handler(_handle_pipeline_trigger)
    control_listener.start()

    for agent_id in AGENT_MAP.values():
        update_agent_status(agent_id, "idle", "Ready")

    log_event("SYSTEM", f"Multi-language: {ENABLE_MULTI_LANG} ({', '.join(MULTI_LANG_CODES)})")
    log_event("SYSTEM", f"Subtitles: {ENABLE_SUBTITLES}")
    log_event("SYSTEM", f"Review gate: {ENABLE_REVIEW_GATE} (threshold: {AUTO_APPROVE_THRESHOLD})")

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_content_job, "cron", hour=6, minute=0)
    scheduler.add_job(daily_repurpose_job, "cron", hour=14, minute=0)
    scheduler.add_job(daily_cleanup_job, "cron", hour=4, minute=0)
    scheduler.add_job(scheduled_publish_job, "interval", minutes=5)
    log_event("SCHEDULER", "Daily content job scheduled at 06:00 UTC")
    log_event("SCHEDULER", "Daily repurpose job scheduled at 14:00 UTC")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")
    log_event("SCHEDULER", "Scheduled publish check every 5 minutes")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")

    try:
        daily_content_job()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_event("SYSTEM", "Agent Orchestrator Shutting Down")
        control_listener.stop()
        update_pipeline_status(False)
