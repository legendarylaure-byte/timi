from utils.content_calendar import (
    schedule_topic, mark_topic_completed, mark_topic_failed, get_retry_queue,
    process_retry, get_calendar_summary, is_blacklisted
)
from utils.analytics_tracker import track_video, update_metrics, get_performance_summary
from utils.thumbnail_gen import generate_thumbnail_image
from utils.health_monitor import start_heartbeat_monitor, check_ollama_health
from utils.description_gen import generate_description
from utils.subtitle_gen import generate_subtitles_for_video
from utils.translate import translate_script
from utils.video_compositor import composite_video
from utils.music_gen import generate_background_music
from utils.voice_gen import generate_voiceover
from utils.stock_video import search_videos_for_scenes
from utils.multi_platform_publisher import multi_platform_publish
from utils.repurposer import batch_reprocess_all_videos
from utils.trend_discovery import discover_trends
from utils.quality_scorer import score_content, predict_performance, check_repetition, evaluate_publish_decision
from utils.cleanup_service import run_cleanup
from utils.firebase_control import AgentControlListener
from utils.firebase_status import (
    update_agent_status,
    log_activity,
    update_pipeline_status,
    add_video_record,
    update_video_record,
    get_firestore_client,
    log_pipeline_error,
)
from crew.thumbnail import create_thumbnail_crew
from crew.storyboard import create_storyboard_crew
from crew.scriptwriter import create_scriptwriter_crew
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
import os
import sys
import json
import re
import asyncio
import time
import warnings
import logging

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

logging.getLogger("grpc").setLevel(logging.ERROR)
logging.getLogger("google.cloud.firestore").setLevel(logging.WARNING)

warnings.filterwarnings("ignore", message=".*fork_posix.*")
warnings.filterwarnings("ignore", message=".*ev_poll_posix.*")
warnings.filterwarnings("ignore", message=".*Detected filter using positional arguments.*")


load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


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

control_listener = AgentControlListener(check_interval=60)

AUTO_APPROVE_THRESHOLD = int(os.getenv("AUTO_APPROVE_THRESHOLD", 80))
ENABLE_MULTI_LANG = os.getenv("ENABLE_MULTI_LANG", "true").lower() == "true"
ENABLE_SUBTITLES = os.getenv("ENABLE_SUBTITLES", "true").lower() == "true"
ENABLE_REVIEW_GATE = os.getenv("ENABLE_REVIEW_GATE", "true").lower() == "true"
MULTI_LANG_CODES = os.getenv("MULTI_LANG_CODES", "es,de,fr").split(",")
PIPELINE_TIMEOUT_MINUTES = int(os.getenv("PIPELINE_TIMEOUT_MINUTES", 30))
MAX_RETRIES_PER_TOPIC = int(os.getenv("MAX_RETRIES_PER_TOPIC", 2))


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
            if "rate_limit" in str(e).lower():
                os.environ['GROQ_RATE_LIMITED'] = '1'
                print(f"[LLM] Groq rate-limited detected in agent step, flagging for Gemini fallback")
            if attempt < max_retries - 1:
                log_event(agent_name, f"Failed (attempt {attempt + 1}/{max_retries}), retrying: {str(e)[:100]}")
                time.sleep(2)
            else:
                update_agent_status(agent_id, "error", f"Failed: {action}", str(e))
                log_activity(agent_id, f"Failed: {action} - {str(e)}", "error")
                log_event(agent_name, f"Failed: {action} - {str(e)}", "error")
                raise


def _clean_scene_keyword(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r'^[#\*\s]+', '', cleaned)
    cleaned = re.sub(r'[\*\#]+', '', cleaned)
    m = re.match(r'(?:Scene\s+\d+[\s:.,-]*|Shot\s+\d+[\s:.,-]*|Chapter\s+\d+[\s:.,-]*)', cleaned, re.IGNORECASE)
    if m:
        cleaned = cleaned[m.end():].strip()
    cleaned = re.sub(r'\([\d\s\-–—,]+(?:seconds?|secs?|s|ms|minutes?|mins?)\)', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\([\d\s\-–—,]+\)', '', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:60] if cleaned else "nature"


def parse_scenes_from_storyboard(storyboard_text: str, format_type: str = "shorts") -> list[dict]:
    try:
        json_match = ""
        if "[" in storyboard_text and "]" in storyboard_text:
            start = storyboard_text.index("[")
            end = storyboard_text.rindex("]") + 1
            json_match = storyboard_text[start:end]
            scenes = json.loads(json_match)
            if isinstance(scenes, list) and len(scenes) > 0:
                return _limit_scenes(scenes, format_type)
    except Exception:
        pass

    lines = storyboard_text.strip().split("\n")
    scenes = []
    in_scene = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        is_scene_header = bool(
            re.match(r'^#{1,3}\s*Scene\s+\d+|^###\s+Scene\s+\d+|^Scene\s+\d+:', stripped, re.IGNORECASE))
        if is_scene_header:
            in_scene = True
            scenes.append({
                "keyword": _clean_scene_keyword(stripped),
                "target_duration": 8.0,
                "description": stripped,
            })
        elif in_scene and any(kw in stripped.lower() for kw in ["camera angle", "character position", "color palette", "background element", "mood"]):  # noqa: E501
            if scenes:
                scenes[-1]["description"] += " " + stripped
    if not scenes:
        for line in lines:
            stripped = line.strip()
            if any(kw in stripped.lower() for kw in ["scene", "shot", "clip"]) and len(stripped) < 100:
                scenes.append({
                    "keyword": stripped[:80],
                    "target_duration": 8.0,
                    "description": stripped,
                })
    if not scenes:
        scenes = [{"keyword": "nature", "target_duration": 8.0, "description": "general scene"}]
    return _limit_scenes(scenes, format_type)


def _limit_scenes(scenes: list[dict], format_type: str) -> list[dict]:
    if format_type == "shorts":
        max_scenes = 12
    else:
        max_scenes = 20
    if len(scenes) > max_scenes:
        step = len(scenes) / max_scenes
        scenes = [scenes[int(i * step)] for i in range(max_scenes)]
        for s in scenes:
            s["target_duration"] = round(s.get("target_duration", 8.0) * (len(scenes) / max_scenes), 1)
    return scenes


def run_video_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int, generate_subs: bool = True, subtitle_lang: str = "en") -> dict:  # noqa: E501
    log_event("PIPELINE", "Step 1: Analyzing storyboard for scene keywords")
    scenes = parse_scenes_from_storyboard(storyboard_text, format_type)
    log_event("PIPELINE", f"Found {len(scenes)} scenes to source video for")

    if format_type == "long":
        min_scenes = max(16, max_duration // 30)
        while len(scenes) < min_scenes:
            scenes.append({"keyword": "transition", "target_duration": 5.0, "description": "transition scene"})
        log_event("PIPELINE", f"Extended to {len(scenes)} scenes for >8min long-form")

    orientation = "portrait" if format_type == "shorts" else "landscape"
    update_agent_status("animator", "working", f"Fetching stock video for {len(scenes)} scenes")
    log_event("ANIMATOR", f"Searching Pexels/Pixabay for {len(scenes)} real video clips")
    log_activity("pipeline", f"Searching stock videos for {len(scenes)} scenes", "info")
    clips = search_videos_for_scenes(scenes, orientation=orientation)
    log_event("ANIMATOR", f"Found {len(clips)}/{len(scenes)} video clips with real motion")
    log_activity("pipeline", f"Found {len(clips)}/{len(scenes)} video clips", "success")
    update_agent_status("animator", "completed", f"Found {len(clips)} video clips")

    if not clips:
        log_pipeline_error(video_id, "No video clips found from any stock video source", "stock_video_search")
        raise Exception("No video clips found. Cannot create video.")

    log_event("PIPELINE", "Step 2: Generating voice-over with Edge TTS")
    update_agent_status("voice", "working", "Generating narration audio")
    is_long = format_type == "long"
    from utils.voice_gen import extract_narration_text
    narration_text = extract_narration_text(script_text, is_long_form=is_long)
    content_type = "bedtime" if "bedtime" in category.lower() else "story" if "story" in category.lower(
    ) or "fable" in category.lower() else "educational" if "science" in category.lower() or "learn" in category.lower() else "general"  # noqa: E501
    voice_result = asyncio.run(generate_voiceover(script_text, content_type=content_type, is_long_form=is_long))
    if not voice_result.get("success"):
        log_pipeline_error(video_id, "Voice-over generation failed", "voice_generation")
        raise Exception("Voice-over generation failed.")
    log_event(
        "VOICE", f"Voice-over: {voice_result['duration']:.1f}s, {voice_result['segments']} segments -> {voice_result['path']}")  # noqa: E501
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
        log_pipeline_error(video_id, "Video compositing failed", "video_compositing")
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
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {  # noqa: E501
                                "topic": topic, "category": category, "format": "shorts", "max_duration": 120})
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
        log_event(
            "QUALITY", f"Score: {quality['overall_score']}/100, Predicted 7D: {prediction['predicted_views_7d']:,} views")  # noqa: E501

        if quality["recommendation"] == "block":
            log_pipeline_error(video_id, f"Blocked by quality score: {quality['overall_score']}", "quality_check")
            add_video_record(video_id, topic, "shorts", "blocked")
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "shorts"})

        video_result = run_video_pipeline(script_text, str(storyboard), category, "shorts", video_id, 120)

        review_decision = apply_review_gate(video_id, topic, "shorts", script_text, quality)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail",
                                   create_thumbnail_crew, {"topic": topic, "format": "shorts"})
        thumbnail_text = str(thumbnail)
        thumb_result = generate_thumbnail_image(
            topic, thumbnail_text, format_type="shorts", output_filename=f"thumb_{video_id}.png")
        thumbnail_path = thumb_result["path"] if thumb_result.get("success") else None
        if not thumbnail_path:
            thumbnail_path = str(thumbnail)
            log_event("THUMBNAIL", "Using text-based thumbnail (image generation fallback)")
        else:
            log_event("THUMBNAIL", f"Generated thumbnail image: {thumbnail_path}")

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
            thumbnail_path=thumbnail_path,
            format_type="shorts",
            platforms=platforms_to_publish,
            publish_at=publish_at,
        )
        publish_status = "scheduled" if publish_at else "Published"
        log_event(
            "PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms")  # noqa: E501

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result["video_path"],
                thumbnail_path=thumbnail_path,
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
        error_msg = str(e)[:500]
        log_pipeline_error(video_id, error_msg, "short_video_pipeline")
        add_video_record(video_id, topic, "shorts", "failed")
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"SHORT video generation FAILED: {error_msg}", "error")
        return False


def generate_long_video(topic: str, category: str, video_id: str, publish_at: str = None):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "long", "generating")
    log_event("PIPELINE", f"Starting LONG video generation: {topic}")
    try:
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, {  # noqa: E501
                                "topic": topic, "category": category, "format": "long", "max_duration": 600})
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
        log_event(
            "QUALITY", f"Score: {quality['overall_score']}/100, Predicted 7D: {prediction['predicted_views_7d']:,} views")  # noqa: E501

        if quality["recommendation"] == "block":
            log_pipeline_error(video_id, f"Blocked by quality score: {quality['overall_score']}", "quality_check")
            add_video_record(video_id, topic, "long", "blocked")
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "long"})

        video_result = run_video_pipeline(script_text, str(storyboard), category, "long", video_id, 600)

        review_decision = apply_review_gate(video_id, topic, "long", script_text, quality)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail",
                                   create_thumbnail_crew, {"topic": topic, "format": "long"})
        thumbnail_text = str(thumbnail)
        thumb_result = generate_thumbnail_image(
            topic, thumbnail_text, format_type="long", output_filename=f"thumb_{video_id}.png")
        thumbnail_path = thumb_result["path"] if thumb_result.get("success") else None
        if not thumbnail_path:
            thumbnail_path = str(thumbnail)
            log_event("THUMBNAIL", "Using text-based thumbnail (image generation fallback)")
        else:
            log_event("THUMBNAIL", f"Generated thumbnail image: {thumbnail_path}")

        desc_result = generate_description(
            title=topic,
            script=script_text,
            category=category,
            format_type="long",
            scenes=parse_scenes_from_storyboard(str(storyboard), "long"),
            channel_name="Vyom Ai Cloud",
        )

        platforms_to_publish = ['youtube', 'facebook']
        publish_result = multi_platform_publish(
            video_id=video_id,
            title=topic,
            description=desc_result.get("full_description", ""),
            video_path=video_result["video_path"],
            thumbnail_path=thumbnail_path,
            format_type="long",
            platforms=platforms_to_publish,
            publish_at=publish_at,
        )
        publish_status = "scheduled" if publish_at else "Published"
        log_event(
            "PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms")  # noqa: E501

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result["video_path"],
                thumbnail_path=thumbnail_path,
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
        error_msg = str(e)[:500]
        log_pipeline_error(video_id, error_msg, "long_video_pipeline")
        add_video_record(video_id, topic, "long", "failed")
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"LONG video generation FAILED: {error_msg}", "error")
        return False


def daily_content_job():
    update_pipeline_status(True)
    log_event("SCHEDULER", "Starting daily content generation")

    log_event("TRENDS", "Discovering trending topics for today")
    update_agent_status("trend_discovery", "working", "Scanning for trending topics")
    try:
        trends = discover_trends()
        update_agent_status("trend_discovery", "completed", f"Found {len(trends)} trending topics")
        log_event("TRENDS", f"Found {len(trends)} trending topics")
    except Exception as e:
        log_event("TRENDS", f"Trend discovery failed: {e}", "error")
        trends = []

    if not trends:
        log_event("SCHEDULER", "No trends found, skipping content generation")
        update_pipeline_status(False)
        return

    top_trends = sorted(trends, key=lambda t: t['score'], reverse=True)[:4]

    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    failed_topics = []
    successful_shorts = 0
    successful_longs = 0

    retry_queue = get_retry_queue()
    if retry_queue:
        log_event("SCHEDULER", f"Processing {len(retry_queue)} retries from queue")
        for retry_entry in retry_queue[:2]:  # Limit retries per run
            process_retry(retry_entry['id'])
            log_event("SCHEDULER", f"Retrying: {retry_entry['topic']}")

    for i in range(shorts_per_day):
        trend = top_trends[i % len(top_trends)]
        if trend['title'] in failed_topics:
            continue
        if is_blacklisted(trend['title']):
            log_event("SCHEDULER", f"Skipping blacklisted topic: {trend['title']}")
            continue
        publish_time = f"{datetime.now().strftime('%Y-%m-%d')}T{6 + i * 2}:00:00Z"
        try:
            success = generate_short_video(trend['title'], trend['category'],
                                           f"short-{datetime.now().strftime('%Y%m%d')}-{i+1}", publish_at=publish_time)
            if success:
                successful_shorts += 1
                track_video(f"short-{datetime.now().strftime('%Y%m%d')}-{i+1}", trend['title'], "shorts", "", 0)
                mark_topic_completed(f"short-{datetime.now().strftime('%Y%m%d')}-{i+1}")
            else:
                failed_topics.append(trend['title'])
                topic_id = schedule_topic(trend['title'], "shorts", priority="high")
                mark_topic_failed(topic_id, "Generation failed")
                log_event("SCHEDULER", f"Topic '{trend['title']}' failed, will skip for next attempt")
        except Exception as e:
            failed_topics.append(trend['title'])
            topic_id = schedule_topic(trend['title'], "shorts", priority="high")
            mark_topic_failed(topic_id, str(e))
            log_event("SCHEDULER", f"Short video '{trend['title']}' crashed: {e}", "error")

    for i in range(long_per_day):
        trend = top_trends[(shorts_per_day + i) % len(top_trends)]
        if trend['title'] in failed_topics:
            continue
        if is_blacklisted(trend['title']):
            log_event("SCHEDULER", f"Skipping blacklisted topic: {trend['title']}")
            continue
        publish_time = f"{datetime.now().strftime('%Y-%m-%d')}T{10 + i * 4}:00:00Z"
        try:
            success = generate_long_video(trend['title'], trend['category'],
                                          f"long-{datetime.now().strftime('%Y%m%d')}-{i+1}", publish_at=publish_time)
            if success:
                successful_longs += 1
                track_video(f"long-{datetime.now().strftime('%Y%m%d')}-{i+1}", trend['title'], "long", "", 0)
                mark_topic_completed(f"long-{datetime.now().strftime('%Y%m%d')}-{i+1}")
            else:
                failed_topics.append(trend['title'])
                topic_id = schedule_topic(trend['title'], "long", priority="high")
                mark_topic_failed(topic_id, "Generation failed")
                log_event("SCHEDULER", f"Topic '{trend['title']}' failed, will skip for next attempt")
        except Exception as e:
            failed_topics.append(trend['title'])
            topic_id = schedule_topic(trend['title'], "long", priority="high")
            mark_topic_failed(topic_id, str(e))
            log_event("SCHEDULER", f"Long video '{trend['title']}' crashed: {e}", "error")

    update_pipeline_status(False)
    total = successful_shorts + successful_longs
    log_event(
        "SCHEDULER", f"Daily content generation complete: {total} videos produced ({successful_shorts} shorts, {successful_longs} longs)")  # noqa: E501

    summary = get_performance_summary(days=7)
    log_event(
        "ANALYTICS", f"7-day summary: {summary['total_videos']} videos, {summary['total_views']} views, avg score: {summary['avg_quality_score']}")  # noqa: E501

    cal_summary = get_calendar_summary(days=7)
    log_event(
        "CALENDAR", f"7-day calendar: {cal_summary['completed']} completed, {cal_summary['failed']} failed, {cal_summary['retry_queue_size']} in retry queue")  # noqa: E501

    if failed_topics:
        log_event("SCHEDULER", f"Failed topics (will retry next run): {', '.join(failed_topics)}")


def daily_repurpose_job():
    log_event("REPURPOSE", "Starting content repurposing scan")
    update_agent_status("repurposer", "working", "Scanning for repurposing opportunities")
    result = batch_reprocess_all_videos()
    update_agent_status("repurposer", "completed", f"Processed {result['processed']} videos")
    log_event(
        "REPURPOSE", f"Repurposed {result['processed']} videos into {sum(v.get('clips', 0) for v in result.get('videos', []))} clips")  # noqa: E501


def daily_cleanup_job():
    log_event("CLEANUP", "Starting auto-cleanup of uploaded videos")
    run_cleanup()
    log_event("CLEANUP", "Auto-cleanup complete")


def scheduled_publish_job():
    """Check for videos scheduled to publish now and process them."""
    try:
        db = get_firestore_client()
        now_iso = datetime.utcnow().isoformat()
        q = db.collection('videos').where('status', '==', 'scheduled').stream()
        published = 0
        for doc in q:
            data = doc.to_dict()
            pub_at = data.get('publish_at', '')
            if pub_at and pub_at <= now_iso:
                log_event("SCHEDULE", f"Publishing scheduled video: {data.get('title', 'unknown')}")
                update_video_record(doc.id, {
                    "status": "uploaded",
                    "published_at": datetime.utcnow().isoformat(),
                })
                published += 1
                video_id = data.get('video_id', doc.id)
                update_metrics(video_id, views=0)
                log_event("ANALYTICS", f"Initialized analytics for video {video_id}")
                log_event("SCHEDULE", f"Video {doc.id} status updated to uploaded")
        if published > 0:
            log_event("SCHEDULE", f"Published {published} scheduled videos")
    except Exception as e:
        if "429" not in str(e):
            log_event("SCHEDULE", f"Scheduled publish check failed: {e}", "error")


def cleanup_stuck_state():
    """Reset agent status on startup. Skips Firestore-heavy cleanup when quota is low."""
    log_event("SYSTEM", "Resetting agent status...")
    for agent_id in AGENT_MAP.values():
        try:
            update_agent_status(agent_id, "idle", "Ready")
        except Exception:
            pass
    log_event("SYSTEM", "All agents reset to idle")


def _handle_pipeline_trigger(topic: str, category: str, format_type: str, trigger_id: str, publish_at: str = None):
    """Handle a pipeline run trigger from the dashboard."""
    scheduled_note = f" (scheduled: {publish_at})" if publish_at else ""
    log_event("TRIGGER", f"Dashboard trigger: {format_type} - {topic} (id: {trigger_id}){scheduled_note}")

    if is_blacklisted(topic):
        log_event("TRIGGER", f"Skipping blacklisted topic: {topic}")
        return

    try:
        video_id = f"trigger-{trigger_id}"
        if format_type == "long":
            success = generate_long_video(topic, category, video_id, publish_at=publish_at)
        else:
            success = generate_short_video(topic, category, video_id, publish_at=publish_at)

        if success:
            track_video(video_id, topic, format_type, "", 0)
            mark_topic_completed(trigger_id)
        else:
            mark_topic_failed(trigger_id, "Generation failed")

        db = get_firestore_client()
        db.collection('pipeline_triggers').document(trigger_id).update({
            'status': 'completed' if success else 'failed',
            'completed_at': time.time(),
        })
        log_event("TRIGGER", f"Pipeline complete: {'SUCCESS' if success else 'FAILED'}")
    except Exception as e:
        log_event("TRIGGER", f"Trigger failed: {e}", "error")
        mark_topic_failed(trigger_id, str(e))
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

    cleanup_stuck_state()

    start_heartbeat_monitor(interval=600)

    log_event("HEALTH", "Checking Ollama health...")
    if check_ollama_health():
        log_event("HEALTH", "Ollama is healthy and responsive")
    else:
        log_event("HEALTH", "WARNING: Ollama health check failed. Will use fallbacks.", "error")

    control_listener.set_trigger_handler(_handle_pipeline_trigger)
    control_listener.start()

    for agent_id in AGENT_MAP.values():
        update_agent_status(agent_id, "idle", "Ready")

    log_event("SYSTEM", f"Multi-language: {ENABLE_MULTI_LANG} ({', '.join(MULTI_LANG_CODES)})")
    log_event("SYSTEM", f"Subtitles: {ENABLE_SUBTITLES}")
    log_event("SYSTEM", f"Review gate: {ENABLE_REVIEW_GATE} (threshold: {AUTO_APPROVE_THRESHOLD})")
    log_event("SYSTEM", f"Pipeline timeout: {PIPELINE_TIMEOUT_MINUTES}min per video")
    log_event("SYSTEM", f"Max retries per topic: {MAX_RETRIES_PER_TOPIC}")

    scheduler = BlockingScheduler()
    scheduler.add_job(daily_content_job, "cron", hour=6, minute=0)
    scheduler.add_job(daily_repurpose_job, "cron", hour=14, minute=0)
    scheduler.add_job(daily_cleanup_job, "cron", hour=4, minute=0)
    scheduler.add_job(scheduled_publish_job, "interval", minutes=15)
    log_event("SCHEDULER", "Daily content job scheduled at 06:00 UTC")
    log_event("SCHEDULER", "Daily repurpose job scheduled at 14:00 UTC")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")
    log_event("SCHEDULER", "Scheduled publish check every 15 minutes")

    try:
        daily_content_job()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_event("SYSTEM", "Agent Orchestrator Shutting Down")
        control_listener.stop()
        update_pipeline_status(False)
