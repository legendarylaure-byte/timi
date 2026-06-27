import os
import sentry_sdk
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
)
sentry_sdk.set_tag("service", "pipeline")

from utils.content_calendar import (
    schedule_topic, mark_topic_completed, mark_topic_failed, get_retry_queue,
    process_retry, get_calendar_summary, is_blacklisted
)
from utils.analytics_tracker import track_video, update_metrics, get_performance_summary
from utils.scheduler_planner import generate_content_plan
from utils.thumbnail_gen import generate_thumbnail_image
from utils.health_monitor import start_heartbeat_monitor, start_health_server, check_ollama_health
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
    update_channel_stats,
)
from crew.thumbnail import create_thumbnail_crew
from crew.storyboard import create_storyboard_crew
from crew.scriptwriter import create_scriptwriter_crew
from crew.title_optimizer import create_title_optimizer_crew
from crew.virality_analyst import create_virality_analyst_crew, get_virality_threshold
from crew.monetization_tracker import create_monetization_review_crew, weekly_check_in, get_growth_summary
from utils.engagement_manager import append_comment_prompt_to_script
from compliance.hook_scorer import score_hook, enforce_rewrite
from compliance.content_safety import check_content_safety
from compliance.platform_policy import check_platform_compliance
from utils.title_tester import TitleTester
from utils.analytics_feedback import analyze_recent_performance, get_optimization_prompt_injection
from utils.llm_helper import force_fallback
from utils.series_builder import register_video_in_series
from utils.checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint
from utils.title_optimizer import pick_best_title
from crew.affiliate_manager import build_affiliate_section
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


def _extract_json(data):
    import json, re
    if isinstance(data, dict):
        return data
    json_dict = getattr(data, 'json_dict', None)
    if isinstance(json_dict, dict):
        return json_dict
    raw = getattr(data, 'raw', data)
    text = raw if isinstance(raw, str) else str(raw)
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if m:
        text = m.group(1)
    first = text.find('{')
    if first < 0:
        first_q = text.find('"')
        if first_q >= 0:
            text = '{' + text[first_q:] + '}'
        else:
            text = '{' + text + '}'
        return json.loads(text)
    text = text[first:]
    candidates = [i for i, ch in enumerate(text) if ch == '}']
    text = re.sub(r'(?<=:)\s*True\b', ' true', text)
    text = re.sub(r'(?<=:)\s*False\b', ' false', text)
    text = re.sub(r'(?<=:)\s*None\b', ' null', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    for pos in reversed(candidates):
        try:
            return json.loads(text[:pos+1])
        except json.JSONDecodeError:
            continue
    raise ValueError(f"Failed to parse crew output: {repr(text[:200])}")


def _execute_single_task(crew_factory, inputs=None, **factory_kwargs):
    crew = crew_factory(**factory_kwargs)
    for attempt in range(2):
        try:
            result = crew.kickoff(inputs=inputs or {})
            raw = getattr(result, 'raw', str(result))
            if raw and len(raw) > 20:
                return raw
        except Exception as e:
            if 'rate_limit' in str(e).lower() and attempt == 0:
                import json as _json
                print(_json.dumps({"level": "WARN", "agent": "LLM", "message": "Rate-limited in _execute_single_task, sleeping 5s then retrying"}))
                time.sleep(5)
                continue
            break
    from crewai import Task as CrewAITask
    agent = crew.agents[0]
    task = crew.tasks[0]
    desc = task.description
    for key, val in (inputs or {}).items():
        desc = desc.replace('{' + key + '}', str(val))
    new_task = CrewAITask(
        description=desc,
        expected_output=task.expected_output,
        agent=agent,
    )
    result = agent.execute_task(task=new_task, context=None, tools=None)
    return result or ""


def _run_async(coro):
    """Run an async coroutine safely, even from a threaded context with a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


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
    'analytics': 'analytics',
    'scheduler': 'scheduler',
}

control_listener = AgentControlListener(check_interval=60)

AUTO_APPROVE_THRESHOLD = int(os.getenv("AUTO_APPROVE_THRESHOLD", 80))
ENABLE_MULTI_LANG = os.getenv("ENABLE_MULTI_LANG", "true").lower() == "true"
ENABLE_SUBTITLES = os.getenv("ENABLE_SUBTITLES", "true").lower() == "true"
ENABLE_REVIEW_GATE = os.getenv("ENABLE_REVIEW_GATE", "true").lower() == "true"
ENABLE_DIRECTOR_REVIEW = os.getenv("ENABLE_DIRECTOR_REVIEW", "true").lower() == "true"
MULTI_LANG_CODES = os.getenv("MULTI_LANG_CODES", "es,de,fr").split(",")
PIPELINE_TIMEOUT_MINUTES = int(os.getenv("PIPELINE_TIMEOUT_MINUTES", 30))
MAX_RETRIES_PER_TOPIC = int(os.getenv("MAX_RETRIES_PER_TOPIC", 2))
USE_ANIMATION_ENGINE = os.getenv("USE_ANIMATION_ENGINE", "true").lower() == "true"
LONG_MAX_DURATION = int(os.getenv("LONG_MAX_DURATION", 600))


def _run_with_timeout(func, args, timeout_minutes: int):
    """Run a synchronous function with a timeout. Raises TimeoutError if exceeded."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func, *args)
        return future.result(timeout=timeout_minutes * 60)


def log_event(agent: str, message: str, level: str = "info"):
    import json as _json
    print(_json.dumps({"timestamp": datetime.now().isoformat(), "level": level.upper(), "agent": agent, "message": message}))


def run_agent_step(agent_id: str, agent_name: str, action: str, crew_factory, inputs: dict, max_retries: int = 2, timeout_minutes: int = 15):
    if control_listener.is_paused(agent_id):
        log_event(agent_name, "Skipped (paused by user)")
        update_agent_status(agent_id, "idle", "Paused by user")
        return None

    update_agent_status(agent_id, "working", action)
    log_event(agent_name, action)
    log_activity(agent_id, action, "info")

    for attempt in range(max_retries):
        try:
            crew = crew_factory(**inputs)
            def _kick():
                return crew.kickoff(inputs=inputs)
            result = _run_with_timeout(_kick, (), timeout_minutes)
            update_agent_status(agent_id, "completed", f"Completed: {action}")
            log_activity(agent_id, f"Completed: {action}", "success")
            log_event(agent_name, f"Completed: {action}")
            return result
        except Exception as e:
            err_str = str(e)
            if "rate_limit" in err_str.lower():
                os.environ['GROQ_RATE_LIMITED'] = '1'
                log_event(agent_name, "Groq rate-limited, flagging for fallback", "warn")
            if "Invalid response from LLM call" in err_str:
                log_event(agent_name, "LLM returned empty response — forcing provider fallback", "warn")
                force_fallback()
            if "TimeoutError" in type(e).__name__ or "timed out" in err_str.lower():
                log_event(agent_name, f"Timed out after {timeout_minutes}min", "error")
            if attempt < max_retries - 1:
                log_event(agent_name, f"Failed (attempt {attempt + 1}/{max_retries}), retrying: {err_str[:120]}")
                time.sleep(2)
            else:
                update_agent_status(agent_id, "error", f"Failed: {action}", err_str)
                log_activity(agent_id, f"Failed: {action} - {err_str}", "error")
                log_event(agent_name, f"Failed: {action} - {err_str}", "error")
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
    except Exception as e:
        log_event("PIPELINE", f"Storyboard JSON parse failed, falling back to line parser: {e}", "debug")

    lines = storyboard_text.strip().split("\n")
    scenes = []
    in_scene = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        is_scene_header = bool(
            re.match(r'^#{1,3}\s*Scene\s+\d+|^###\s+Scene\s+\d+|^Scene\s+\d+:|^--SCENE\s+\d+', stripped, re.IGNORECASE))
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
        original_count = len(scenes)
        step = original_count / max_scenes
        scenes = [scenes[int(i * step)] for i in range(max_scenes)]
        for s in scenes:
            s["target_duration"] = round(s.get("target_duration", 8.0) * (original_count / max_scenes), 1)
    return scenes


def _run_stock_footage_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int) -> tuple[list[dict], list[dict], float]:  # noqa: E501
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
    total_duration = sum(c["duration"] for c in clips)
    return scenes, clips, total_duration


def _run_asset_router_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str) -> tuple[list[dict], list[dict], float]:  # noqa: E501
    from utils.asset_router import dispatch_scenes
    from utils.scene_parser import parse_script_to_scenes
    from utils.series_router import inject_intro_outro
    scenes = parse_script_to_scenes(script_text, title=video_id, category=category, format_type=format_type, storyboard_text=str(storyboard_text))
    scenes = inject_intro_outro(scenes, category, format_type)
    log_event("PIPELINE", f"Asset Router: {len(scenes)} scenes")
    update_agent_status("animator", "working", f"Dispatching {len(scenes)} scenes via Asset Router")
    clips = dispatch_scenes(scenes, video_id, format_type)
    log_event("ASSET_ROUTER", f"Generated {len(clips)} assets from {len(scenes)} scenes")
    update_agent_status("animator", "completed", f"Generated {len(clips)} video assets")
    total_duration = sum(c.get("duration", 8.0) for c in clips)
    return scenes, clips, total_duration


def run_video_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int, generate_subs: bool = True, subtitle_lang: str = "en") -> dict:  # noqa: E501
    log_event("PIPELINE", "Step 1: Parsing storyboard into scenes")
    use_asset_router = USE_ANIMATION_ENGINE

    if use_asset_router:
        scenes, clips, total_video_duration = _run_asset_router_pipeline(script_text, storyboard_text, category, format_type, video_id)
    else:
        scenes, clips, total_video_duration = _run_stock_footage_pipeline(script_text, storyboard_text, category, format_type, video_id, max_duration)

    log_event("PIPELINE", "Step 1.5: Assigning sound effects to scenes")
    try:
        from utils.sfx_generator import load_sfx_scene_assignments
        scenes = load_sfx_scene_assignments(scenes)
        log_event("SFX", f"Assigned SFX to {sum(1 for s in scenes if s.get('sfx'))} scenes")
    except Exception as e:
        log_event("SFX", f"SFX assignment skipped: {e}", "debug")

    log_event("PIPELINE", "Step 2: Generating voice-over with Edge TTS")
    update_agent_status("voice", "working", "Generating narration audio")
    is_long = format_type == "long"
    from utils.voice_gen import extract_narration_text
    narration_text = extract_narration_text(script_text, is_long_form=is_long)
    voice_result = _run_async(generate_voiceover(script_text, content_type="educational", is_long_form=is_long))
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
    if use_asset_router and voice_result.get("timing_file"):
        log_event("PIPELINE", "Step 2.75: Processing word spotlights")
        try:
            from utils.text_animator import process_spotlights
            scenes = process_spotlights(scenes, voice_result["timing_file"], narration_text)
        except Exception as e:
            log_event("SPOTLIGHT", f"Word spotlights skipped: {e}", "debug")

    log_event("PIPELINE", "Step 3: Generating background music")
    update_agent_status("composer", "working", "Creating background music")
    scene_moods = [s.get("music_mood", "happy") for s in scenes if isinstance(s, dict) and s.get("music_mood")]
    music_result = generate_background_music(category, duration=total_video_duration, scene_moods=scene_moods if scene_moods else None)
    music_path = music_result.get("path")
    if not music_path:
        log_event("COMPOSER", "Music generation failed — continuing without background music", "warn")
    else:
        log_event("COMPOSER", f"Music: {music_result.get('mood', 'unknown')} mood -> {music_path}")
    update_agent_status("composer", "completed", f"Music generated ({music_result.get('mood')})")

    chapters = None
    if format_type == "long":
        chapters = []
        current_time = 0
        if use_asset_router and scenes:
            for i, s in enumerate(scenes):
                dur = s.get("duration", s.get("target_duration", 8.0))
                chapters.append({"start_time": current_time, "end_time": current_time + dur, "title": s.get("keyword", s.get("scene_title", f"Chapter {i+1}"))})
                current_time += dur
        elif clips and scenes:
            clip_count = len(clips)
            for i, scene in enumerate(scenes[:clip_count]):
                clip_dur = clips[i]["duration"] if i < len(clips) else 5.0
                chapters.append({"start_time": current_time, "end_time": current_time + clip_dur, "title": scene.get("keyword", f"Chapter {i+1}")})
                current_time += clip_dur
        log_event("PIPELINE", f"Generated {len(chapters)} chapter markers")

    log_event("PIPELINE", "Step 4: Compositing final video")
    anim_label = " with Asset Router" if use_asset_router else " with FFmpeg"
    update_agent_status("editor", "working", f"Compositing video{anim_label}")

    if use_asset_router:
        final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes)
    else:
        final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes)

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


def apply_review_gate(video_id: str, topic: str, format_type: str, script_text: str, quality: dict, category: str = ""):
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
        add_video_record(video_id, topic, format_type, "blocked_review", category=category)
        log_event("REVIEW", f"BLOCKED: {topic}")
        return "block"
    elif decision["action"] == "manual_review":
        add_video_record(video_id, topic, format_type, "pending_review", category=category)
        log_event("REVIEW", f"PENDING REVIEW: {topic}")
        return "pending_review"

    return "auto_approve"


def run_director_review(stage: str, topic: str, category: str, format_type: str, script: str, storyboard: str = "") -> dict:
    if not ENABLE_DIRECTOR_REVIEW:
        return {"decision": "pass", "score": 100, "issues": [], "feedback": "Director review disabled"}
    try:
        from crew.director import create_director_crew
        raw = _execute_single_task(create_director_crew, {
            "script": script,
            "storyboard": storyboard or "N/A",
            "category": category,
            "format": format_type,
            "topic": topic,
        })
        review = _extract_json(raw)
        log_event("DIRECTOR", f"[{stage}] Score: {review.get('score', 0)}/100, Decision: {review.get('decision', 'unknown')}")
        if review.get("issues"):
            for issue in review["issues"][:3]:
                log_event("DIRECTOR", f"  Issue [{issue.get('severity','info')}]: {issue.get('description','')[:120]}")
        return review
    except Exception as e:
        log_event("DIRECTOR", f"[{stage}] Review failed: {e}", "error")
        return {"decision": "block", "score": 0, "issues": [{"severity": "error", "description": f"Review unavailable: {e}"}], "feedback": "Auto-blocked (review unavailable)", "error": str(e)}


def generate_short_video(topic: str, category: str, video_id: str, publish_at: str = None):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "shorts", "generating", category=category)
    log_event("PIPELINE", f"Starting SHORT video generation: {topic}")

    cp = load_checkpoint(video_id)
    if cp:
        log_event("CHECKPOINT", f"Resuming from step: {cp.get('step', 'unknown')}")

    failed_step = "setup"
    try:
        failed_step = "scriptwriting"
        opt_injection = get_optimization_prompt_injection()
        script_kwargs = {"topic": topic, "category": category, "format": "shorts", "max_duration": 120}
        if opt_injection:
            script_kwargs["extra_context"] = opt_injection
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, script_kwargs, timeout_minutes=20)  # noqa: E501
        script_text = str(script)
        save_checkpoint(video_id, "scriptwriting", {"script_preview": script_text[:200]})

        failed_step = "hook_scoring"
        hook_score_result = score_hook(script_text)
        if hook_score_result["score"] < 60:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — enforcing rewrite")
            script_text = enforce_rewrite(script_text)
            recheck = score_hook(script_text)
            log_event("HOOK", f"Hook re-scored: {recheck['score']}/100 after rewrite")
            if recheck["score"] < hook_score_result["score"]:
                log_event("HOOK", f"Hook score dropped ({hook_score_result['score']}→{recheck['score']}), keeping original", "warn")
                script_text = str(script)
        else:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — passed")

        failed_step = "compliance_check"
        safety = check_content_safety(script_text)
        if safety.get("has_issues", False):
            issues = safety.get("issues", [])
            log_event("COMPLIANCE", f"Content safety issues found: {len(issues)}", "warn")
            for issue in issues[:3]:
                log_event("COMPLIANCE", f"  [{issue['severity']}] {issue.get('message', '')[:100]}")
            if any(i.get("severity") == "error" for i in issues):
                log_pipeline_error(video_id, "Blocked by content safety check", "compliance")
                add_video_record(video_id, topic, "shorts", "blocked_compliance", category=category)
                log_event("COMPLIANCE", f"BLOCKED: {topic} (content safety)")
                update_pipeline_status(False)
                return False
        platform_compliance = check_platform_compliance({"title": topic, "script": script_text}, category)
        if platform_compliance:
            for w in platform_compliance:
                log_event("COMPLIANCE", f"Platform warning: {w[:100]}", "warn")

        failed_step = "engagement_cta"
        script_text = append_comment_prompt_to_script(script_text, topic, "shorts")
        log_event("ENGAGEMENT", "Comment CTA injected into script")

        failed_step = "quality_scoring"
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
            add_video_record(video_id, topic, "shorts", "blocked", category=category)
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        failed_step = "virality_analysis"
        try:
            raw = _execute_single_task(create_virality_analyst_crew, {"script": script_text, "title": topic, "category": category, "format_type": "shorts"}, script=script_text, title=topic, category=category, format_type="shorts")
            virality_result = _extract_json(raw)
            v_score = virality_result.get("overall_virality_score", 70)
            update_video_record(video_id, {"virality_prediction": virality_result})
            if v_score < get_virality_threshold():
                log_event("VIRALITY", f"Virality score {v_score}/100 below threshold — blocking")
                log_pipeline_error(video_id, f"Blocked by virality analyst: {v_score}/100", "virality")
                add_video_record(video_id, topic, "shorts", "blocked_virality", category=category)
                update_pipeline_status(False)
                return False
            log_event("VIRALITY", f"Virality score: {v_score}/100 — approved")
        except Exception as e:
            log_event("VIRALITY", f"Virality analysis CRASHED: {e}", "error")
            log_pipeline_error(video_id, f"Virality analysis failed: {e}", "virality")
        save_checkpoint(video_id, "quality_scoring", {"quality_score": quality["overall_score"]})

        failed_step = "director_script_review"
        script_review = run_director_review("script", topic, category, "shorts", script_text)
        if script_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (script): {script_review.get('feedback', '')[:200]}", "director_review")
            add_video_record(video_id, topic, "shorts", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at script review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "storyboarding"
        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "shorts"})

        failed_step = "director_storyboard_review"
        sb_review = run_director_review("storyboard", topic, category, "shorts", script_text, str(storyboard))
        if sb_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (storyboard)", "director_review")
            add_video_record(video_id, topic, "shorts", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at storyboard review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "video_pipeline"
        video_result = run_video_pipeline(script_text, str(storyboard), category, "shorts", video_id, 120)
        save_checkpoint(video_id, "video_pipeline", {"video_path": video_result.get("video_path", "")})

        failed_step = "review_gate"
        review_decision = apply_review_gate(video_id, topic, "shorts", script_text, quality, category)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        failed_step = "director_final_review"
        final_review = run_director_review("final", topic, category, "shorts", script_text, str(storyboard))
        if final_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (final)", "director_review")
            add_video_record(video_id, topic, "shorts", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at final review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "thumbnail"
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

        failed_step = "description"
        desc_result = generate_description(
            title=topic,
            script=script_text,
            category=category,
            format_type="shorts",
            channel_name="Vyom Ai Cloud",
        )
        affiliate_text = build_affiliate_section(script_text, category)
        full_desc = desc_result.get("full_description", "")
        if affiliate_text and affiliate_text not in full_desc:
            full_desc += affiliate_text
            desc_result["full_description"] = full_desc

        failed_step = "title_optimization"
        title_variants = []
        try:
            raw = _execute_single_task(create_title_optimizer_crew, {"script": script_text, "topic": topic, "category": category, "format_type": "shorts"}, script=script_text, topic=topic, category=category, format_type="shorts")
            title_result = _extract_json(raw)
            title_variants = title_result.get("variants", [])
            log_event("TITLE", f"Generated {len(title_variants)} title variants via CrewAI")
        except Exception as e:
            log_event("TITLE", f"CrewAI title optimization failed: {e}", "warn")
        if not title_variants:
            try:
                title_variants = [pick_best_title(topic, keywords=[category], count=5)]
                log_event("TITLE", f"Fallback title generated: '{title_variants[0]}'")
            except Exception as fallback_err:
                log_event("TITLE", f"Fallback title gen failed: {fallback_err}", "debug")

        failed_step = "publishing"
        platforms_to_publish = ['youtube', 'tiktok', 'instagram']
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
        save_checkpoint(video_id, "publishing", {"publish_count": publish_result.get("success_count", 0)})

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

        failed_step = "title_tester"
        youtube_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        youtube_id = None
        if youtube_url and 'watch?v=' in youtube_url:
            youtube_id = youtube_url.split('watch?v=')[-1].split('&')[0]
        if youtube_id and title_variants:
            try:
                tester = TitleTester(youtube_api_update_func=None)
                full_title = topic
                tester.start_test(video_id, full_title, title_variants)
                log_event("TITLE", f"Title A/B test started for {video_id}")
            except Exception as e:
                log_event("TITLE", f"Title tester init skipped: {e}", "debug")

        failed_step = "series_registration"
        try:
            from utils.series_builder import pick_series_for_category
            series = pick_series_for_category(category)
            if series:
                youtube_service = publish_result.get('platforms', {}).get('youtube', {}).get('service')
                series_id = series.get("series_id", "")
                part_num = series.get("current_part", 0) + 1
                register_video_in_series(series_id, youtube_id or video_id, topic, part_num)
                log_event("SERIES", f"Registered {topic} as {series.get('title')} Part {part_num}")
        except Exception as e:
            log_event("SERIES", f"Series registration skipped: {e}", "debug")

        failed_step = "finalizing"
        update_video_record(video_id, {
            "status": "scheduled" if publish_at else "uploaded",
            "youtube_url": youtube_url,
            "publish_at": publish_at,
        })
        log_event("PIPELINE", f"SHORT video generation SUCCESS: {topic}")
        update_pipeline_status(False)
        clear_checkpoint(video_id)
        try:
            from bot.notifications import send_upload_notification
            video_dur = video_result.get("duration", 0)
            send_upload_notification({
                "title": topic, "format": "shorts", "duration": video_dur,
                "platforms": publish_result.get("platforms", {}),
            })
        except Exception:
            log_event("NOTIFY", "Upload notification skipped", "debug")
        return True
    except Exception as e:
        error_msg = str(e)[:500]
        log_pipeline_error(video_id, f"[{failed_step}] {error_msg}", "short_video_pipeline")
        add_video_record(video_id, topic, "shorts", "failed", category=category)
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"SHORT video FAILED at {failed_step}: {error_msg}", "error")
        clear_checkpoint(video_id)
        log_event("CLEANUP", "Intermediate files cleaned by scheduled daily_cleanup_job")
        try:
            from bot.notifications import send_error_notification
            send_error_notification(error_msg, f"short_video/{failed_step}: {topic}")
        except Exception:
            pass
        return False


def generate_long_video(topic: str, category: str, video_id: str, publish_at: str = None):
    update_pipeline_status(True, video_id)
    add_video_record(video_id, topic, "long", "generating", category=category)
    log_event("PIPELINE", f"Starting LONG video generation: {topic}")

    cp = load_checkpoint(video_id)
    if cp:
        log_event("CHECKPOINT", f"Resuming from step: {cp.get('step', 'unknown')}")

    failed_step = "setup"
    try:
        failed_step = "scriptwriting"
        opt_injection = get_optimization_prompt_injection()
        script_kwargs = {"topic": topic, "category": category, "format": "long", "max_duration": 600}
        if opt_injection:
            script_kwargs["extra_context"] = opt_injection
        script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, script_kwargs, timeout_minutes=30)  # noqa: E501
        script_text = str(script)
        save_checkpoint(video_id, "scriptwriting", {"script_preview": script_text[:200]})

        failed_step = "hook_scoring"
        hook_score_result = score_hook(script_text)
        if hook_score_result["score"] < 60:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — enforcing rewrite")
            script_text = enforce_rewrite(script_text)
            recheck = score_hook(script_text)
            log_event("HOOK", f"Hook re-scored: {recheck['score']}/100 after rewrite")
            if recheck["score"] < hook_score_result["score"]:
                log_event("HOOK", f"Hook score dropped ({hook_score_result['score']}→{recheck['score']}), keeping original", "warn")
                script_text = str(script)
        else:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — passed")

        failed_step = "compliance_check"
        safety = check_content_safety(script_text)
        if safety.get("has_issues", False):
            issues = safety.get("issues", [])
            log_event("COMPLIANCE", f"Content safety issues found: {len(issues)}")
            for issue in issues[:3]:
                log_event("COMPLIANCE", f"  [{issue['severity']}] {issue.get('message', '')[:100]}")
            if any(i.get("severity") == "error" for i in issues):
                log_pipeline_error(video_id, "Blocked by content safety check", "compliance")
                add_video_record(video_id, topic, "long", "blocked_compliance", category=category)
                log_event("COMPLIANCE", f"BLOCKED: {topic} (content safety)")
                update_pipeline_status(False)
                return False
        platform_compliance = check_platform_compliance({"title": topic, "script": script_text}, category)
        if platform_compliance:
            for w in platform_compliance:
                log_event("COMPLIANCE", f"Platform warning: {w[:100]}", "warn")

        failed_step = "engagement_cta"
        script_text = append_comment_prompt_to_script(script_text, topic, "long")
        log_event("ENGAGEMENT", "Comment CTA injected into script")

        failed_step = "quality_scoring"
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
            add_video_record(video_id, topic, "long", "blocked", category=category)
            log_event("QUALITY", f"BLOCKED: {topic} (score: {quality['overall_score']})")
            update_pipeline_status(False)
            return False

        failed_step = "virality_analysis"
        try:
            raw = _execute_single_task(create_virality_analyst_crew, {"script": script_text, "title": topic, "category": category, "format_type": "long"}, script=script_text, title=topic, category=category, format_type="long")
            virality_result = _extract_json(raw)
            v_score = virality_result.get("overall_virality_score", 70)
            update_video_record(video_id, {"virality_prediction": virality_result})
            if v_score < get_virality_threshold():
                log_event("VIRALITY", f"Virality score {v_score}/100 below threshold — blocking")
                log_pipeline_error(video_id, f"Blocked by virality analyst: {v_score}/100", "virality")
                add_video_record(video_id, topic, "long", "blocked_virality", category=category)
                update_pipeline_status(False)
                return False
            log_event("VIRALITY", f"Virality score: {v_score}/100 — approved")
        except Exception as e:
            log_event("VIRALITY", f"Virality analysis CRASHED: {e}", "error")
            log_pipeline_error(video_id, f"Virality analysis failed: {e}", "virality")
        save_checkpoint(video_id, "quality_scoring", {"quality_score": quality["overall_score"]})

        failed_step = "director_script_review"
        script_review = run_director_review("script", topic, category, "long", script_text)
        if script_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (script): {script_review.get('feedback', '')[:200]}", "director_review")
            add_video_record(video_id, topic, "long", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at script review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "storyboarding"
        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "long"})

        failed_step = "director_storyboard_review"
        sb_review = run_director_review("storyboard", topic, category, "long", script_text, str(storyboard))
        if sb_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (storyboard)", "director_review")
            add_video_record(video_id, topic, "long", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at storyboard review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "video_pipeline"
        video_result = run_video_pipeline(script_text, str(storyboard), category, "long", video_id, LONG_MAX_DURATION)
        save_checkpoint(video_id, "video_pipeline", {"video_path": video_result.get("video_path", "")})

        failed_step = "review_gate"
        review_decision = apply_review_gate(video_id, topic, "long", script_text, quality, category)
        if review_decision == "block":
            update_pipeline_status(False)
            return False

        failed_step = "director_final_review"
        final_review = run_director_review("final", topic, category, "long", script_text, str(storyboard))
        if final_review.get("decision") == "block":
            log_pipeline_error(video_id, f"Blocked by Director (final)", "director_review")
            add_video_record(video_id, topic, "long", "blocked", category=category)
            log_event("DIRECTOR", f"BLOCKED at final review: {topic}")
            update_pipeline_status(False)
            return False

        failed_step = "thumbnail"
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

        failed_step = "description"
        desc_result = generate_description(
            title=topic,
            script=script_text,
            category=category,
            format_type="long",
            scenes=parse_scenes_from_storyboard(str(storyboard), "long"),
            channel_name="Vyom Ai Cloud",
        )
        affiliate_text = build_affiliate_section(script_text, category)
        full_desc = desc_result.get("full_description", "")
        if affiliate_text and affiliate_text not in full_desc:
            full_desc += affiliate_text
            desc_result["full_description"] = full_desc

        failed_step = "title_optimization"
        title_variants = []
        try:
            raw = _execute_single_task(create_title_optimizer_crew, {"script": script_text, "topic": topic, "category": category, "format_type": "long"}, script=script_text, topic=topic, category=category, format_type="long")
            title_result = _extract_json(raw)
            title_variants = title_result.get("variants", [])
            log_event("TITLE", f"Generated {len(title_variants)} title variants via CrewAI")
        except Exception as e:
            log_event("TITLE", f"CrewAI title optimization failed: {e}", "warn")
        if not title_variants:
            try:
                title_variants = [pick_best_title(topic, keywords=[category], count=5)]
                log_event("TITLE", f"Fallback title generated: '{title_variants[0]}'")
            except Exception as fallback_err:
                log_event("TITLE", f"Fallback title gen failed: {fallback_err}", "debug")

        failed_step = "publishing"
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
        save_checkpoint(video_id, "publishing", {"publish_count": publish_result.get("success_count", 0)})

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
            log_event("PIPELINE", "Generating multi-language versions for long video")
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

        failed_step = "title_tester"
        youtube_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        youtube_id = None
        if youtube_url and 'watch?v=' in youtube_url:
            youtube_id = youtube_url.split('watch?v=')[-1].split('&')[0]
        if youtube_id and title_variants:
            try:
                tester = TitleTester(youtube_api_update_func=None)
                full_title = topic
                tester.start_test(video_id, full_title, title_variants)
                log_event("TITLE", f"Title A/B test started for {video_id}")
            except Exception as e:
                log_event("TITLE", f"Title tester init skipped: {e}", "debug")

        failed_step = "series_registration"
        try:
            from utils.series_builder import pick_series_for_category
            series = pick_series_for_category(category)
            if series:
                series_id = series.get("series_id", "")
                part_num = series.get("current_part", 0) + 1
                register_video_in_series(series_id, youtube_id or video_id, topic, part_num)
                log_event("SERIES", f"Registered {topic} as {series.get('title')} Part {part_num}")
        except Exception as e:
            log_event("SERIES", f"Series registration skipped: {e}", "debug")

        failed_step = "finalizing"
        update_video_record(video_id, {
            "script": script_text,
            "subtitle_path": video_result.get("subtitle_path"),
            "chapters": video_result.get("chapters"),
            "is_above_8min": video_result.get("duration", 0) >= 480,
        })

        add_video_record(video_id, topic, "long", "uploaded", category=category)
        log_event("PIPELINE", f"LONG video generation SUCCESS: {topic}")
        update_pipeline_status(False)
        clear_checkpoint(video_id)
        try:
            from bot.notifications import send_upload_notification
            video_dur = video_result.get("duration", 0)
            send_upload_notification({
                "title": topic, "format": "long", "duration": video_dur,
                "platforms": publish_result.get("platforms", {}),
            })
        except Exception:
            log_event("NOTIFY", "Upload notification skipped", "debug")
        return True
    except Exception as e:
        error_msg = str(e)[:500]
        log_pipeline_error(video_id, f"[{failed_step}] {error_msg}", "long_video_pipeline")
        add_video_record(video_id, topic, "long", "failed", category=category)
        update_pipeline_status(False, paused_by_user=False)
        log_event("PIPELINE", f"LONG video FAILED at {failed_step}: {error_msg}", "error")
        clear_checkpoint(video_id)
        log_event("CLEANUP", "Intermediate files cleaned by scheduled daily_cleanup_job")
        try:
            from bot.notifications import send_error_notification
            send_error_notification(error_msg, f"long_video/{failed_step}: {topic}")
        except Exception:
            pass
        return False


def _next_schedule_time(hour: int) -> str:
    now = datetime.utcnow()
    scheduled = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if scheduled <= now:
        scheduled = scheduled.replace(day=scheduled.day + 1)
    return scheduled.strftime("%Y-%m-%dT%H:%M:%SZ")


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

    shorts_per_day = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", 2))
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 2))

    log_event("SCHEDULER", "Generating content plan via scheduler planner")
    try:
        opt_injection = get_optimization_prompt_injection()
        plan = generate_content_plan(extra_context=opt_injection)
        if opt_injection:
            log_event("SCHEDULER", f"Optimization context: {opt_injection[:100]}...")
    except Exception as e:
        log_event("SCHEDULER", f"Planner failed: {e}, falling back to trend-based", "error")
        plan = []

    if not plan and not trends:
        log_event("SCHEDULER", "No plan and no trends, skipping content generation")
        update_pipeline_status(False)
        return

    if not plan and trends:
        top_trends = sorted(trends, key=lambda t: t['score'], reverse=True)[:4]
        plan = []
        for i in range(shorts_per_day + long_per_day):
            trend = top_trends[i % len(top_trends)]
            fmt = "shorts" if i < shorts_per_day else "long"
            plan.append({
                "title": trend['title'],
                "category": trend['category'],
                "format": fmt,
                "priority": trend.get('score', 80),
            })

    shorts_plan = [v for v in plan if v.get('format') == 'shorts']
    longs_plan = [v for v in plan if v.get('format') == 'long']

    failed_topics = []
    successful_shorts = 0
    successful_longs = 0

    retry_queue = get_retry_queue()
    if retry_queue:
        log_event("SCHEDULER", f"Processing {len(retry_queue)} retries from queue")
        for retry_entry in retry_queue[:2]:
            process_retry(retry_entry['id'])
            log_event("SCHEDULER", f"Retrying: {retry_entry['topic']}")

    video_date = datetime.now().strftime('%Y%m%d')
    for i in range(shorts_per_day):
        if i < len(shorts_plan):
            item = shorts_plan[i]
        elif trends:
            fallback = sorted(trends, key=lambda t: t['score'], reverse=True)[i % max(len(trends), 1)]
            item = {"title": fallback['title'], "category": fallback['category'], "format": "shorts", "priority": fallback.get('score', 50)}
        else:
            break
        if item['title'] in failed_topics:
            continue
        if is_blacklisted(item['title']):
            log_event("SCHEDULER", f"Skipping blacklisted topic: {item['title']}")
            continue
        publish_time = _next_schedule_time(6 + i * 2)
        try:
            success = _run_with_timeout(
                generate_short_video,
                (item['title'], item['category'],
                 f"short-{video_date}-{i+1}", publish_time),
                PIPELINE_TIMEOUT_MINUTES,
            )
            if success:
                successful_shorts += 1
                track_video(f"short-{video_date}-{i+1}", item['title'], "shorts", "", 0)
                mark_topic_completed(f"short-{video_date}-{i+1}")
            else:
                failed_topics.append(item['title'])
                topic_id = schedule_topic(item['title'], "shorts", priority="high")
                mark_topic_failed(topic_id, "Generation failed")
        except Exception as e:
            failed_topics.append(item['title'])
            topic_id = schedule_topic(item['title'], "shorts", priority="high")
            mark_topic_failed(topic_id, str(e))
            log_event("SCHEDULER", f"Short video '{item['title']}' crashed: {e}", "error")

    for i in range(long_per_day):
        if i < len(longs_plan):
            item = longs_plan[i]
        elif trends:
            fallback = sorted(trends, key=lambda t: t['score'], reverse=True)[(shorts_per_day + i) % max(len(trends), 1)]
            item = {"title": fallback['title'], "category": fallback['category'], "format": "long", "priority": fallback.get('score', 50)}
        else:
            break
        if item['title'] in failed_topics:
            continue
        if is_blacklisted(item['title']):
            log_event("SCHEDULER", f"Skipping blacklisted topic: {item['title']}")
            continue
        publish_time = _next_schedule_time(10 + i * 4)
        try:
            success = _run_with_timeout(
                generate_long_video,
                (item['title'], item['category'],
                 f"long-{video_date}-{i+1}", publish_time),
                PIPELINE_TIMEOUT_MINUTES,
            )
            if success:
                successful_longs += 1
                track_video(f"long-{video_date}-{i+1}", item['title'], "long", "", 0)
                mark_topic_completed(f"long-{video_date}-{i+1}")
            else:
                failed_topics.append(item['title'])
                topic_id = schedule_topic(item['title'], "long", priority="high")
                mark_topic_failed(topic_id, "Generation failed")
        except Exception as e:
            failed_topics.append(item['title'])
            topic_id = schedule_topic(item['title'], "long", priority="high")
            mark_topic_failed(topic_id, str(e))
            log_event("SCHEDULER", f"Long video '{item['title']}' crashed: {e}", "error")

    update_pipeline_status(False)
    total = successful_shorts + successful_longs
    log_event("SCHEDULER", f"Daily content generation complete: {total} videos produced ({successful_shorts} shorts, {successful_longs} longs)")

    summary = get_performance_summary(days=7)
    log_event("ANALYTICS", f"7-day summary: {summary['total_videos']} videos, {summary['total_views']} views, avg score: {summary['avg_quality_score']}")

    cal_summary = get_calendar_summary(days=7)
    log_event("CALENDAR", f"7-day calendar: {cal_summary['completed']} completed, {cal_summary['failed']} failed, {cal_summary['retry_queue_size']} in retry queue")

    if failed_topics:
        log_event("SCHEDULER", f"Failed topics (will retry next run): {', '.join(failed_topics)}")

    return successful_shorts > 0 or successful_longs > 0


def daily_repurpose_job():
    log_event("REPURPOSE", "Starting content repurposing scan")
    update_agent_status("repurposer", "working", "Scanning for repurposing opportunities")
    result = batch_reprocess_all_videos()
    update_agent_status("repurposer", "completed", f"Processed {result['processed']} videos")
    log_event(
        "REPURPOSE", f"Repurposed {result['processed']} videos into {sum(v.get('clips', 0) for v in result.get('videos', []))} clips")  # noqa: E501


def daily_analytics_job():
    log_event("ANALYTICS", "Starting YouTube analytics pull for published videos")
    update_agent_status("analytics", "working", "Fetching video stats from YouTube")
    try:
        from utils.youtube_analytics import pull_all_video_analytics
        from utils.youtube_upload import get_channel_stats
        result = pull_all_video_analytics(max_videos=50)
        channel = get_channel_stats()
        if channel:
            update_channel_stats(channel)
        update_agent_status("analytics", "completed", f"Processed {result['processed']} videos")
        log_event("ANALYTICS", f"YouTube analytics pull: {result['processed']} updated, {result['failed']} failed")

        log_event("ANALYST", "Running performance analysis on recent data")
        update_agent_status("analytics", "working", "Analyzing performance trends")
        try:
            from crew.analyst import run_analyst
            analysis = run_analyst(days=7)
            if analysis and "error" not in analysis:
                log_event("ANALYST", f"Analysis complete: {len(analysis.get('recommendations', []))} recommendations")
                for rec in analysis.get("recommendations", [])[:3]:
                    log_event("ANALYST", f"  [{rec.get('priority','medium')}] {rec.get('suggestion','')[:120]}")
                update_video_record("analyst_latest", analysis)
            else:
                log_event("ANALYST", f"Analysis returned error: {analysis.get('error', 'unknown')}", "error")
        except Exception as e:
            log_event("ANALYST", f"Performance analysis failed: {e}", "error")
    except Exception as e:
        update_agent_status("analytics", "error", str(e))
        log_event("ANALYTICS", f"Analytics pull failed: {e}", "error")


def daily_revenue_job():
    log_event("REVENUE", "Starting daily revenue computation")
    update_agent_status("analytics", "working", "Computing revenue data")
    try:
        from utils.revenue_pipeline import daily_revenue_job as run_revenue, save_growth_snapshot
        run_revenue()
        save_growth_snapshot()
        update_agent_status("analytics", "completed", "Revenue data updated")
        log_event("REVENUE", "Revenue computation and growth snapshot complete")
    except Exception as e:
        log_event("REVENUE", f"Revenue job failed: {e}", "error")


def daily_cleanup_job():
    log_event("CLEANUP", "Starting auto-cleanup of uploaded videos")
    run_cleanup()
    log_event("CLEANUP", "Auto-cleanup complete")


def weekly_monetization_job():
    log_event("MONETIZATION", "Starting weekly monetization review")
    try:
        check_in = weekly_check_in()
        log_event("MONETIZATION", f"Weekly check-in recorded for {check_in['date'][:10]}")
        growth_summary = get_growth_summary()
        log_event("MONETIZATION", f"Growth summary: {growth_summary[:200]}")
        try:
            crew = create_monetization_review_crew()
            review = crew.kickoff(inputs={})
            log_event("MONETIZATION", "Monetization review complete")
        except Exception as e:
            log_event("MONETIZATION", f"Review crew failed: {e}", "warn")
    except Exception as e:
        log_event("MONETIZATION", f"Weekly monetization check failed: {e}", "error")


def daily_feedback_job():
    log_event("FEEDBACK", "Starting analytics feedback loop")
    try:
        from utils.youtube_analytics import pull_all_video_analytics
        analytics = pull_all_video_analytics(max_videos=100)
        videos = analytics.get("videos", [])
        if videos:
            insights = analyze_recent_performance(videos, days=30)
            best_cat = insights.get("best_category", "unknown")
            log_event("FEEDBACK", f"Best category: {best_cat}")
            for rec in insights.get("recommendations", [])[:3]:
                log_event("FEEDBACK", f"  Recommendation: {rec}")
        else:
            log_event("FEEDBACK", "No video analytics to analyze yet")
    except Exception as e:
        log_event("FEEDBACK", f"Analytics feedback loop failed: {e}", "warn")


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
        except Exception as e:
            log_event("SYSTEM", f"Failed to reset {agent_id}: {e}", "error")
    log_event("SYSTEM", "All agents reset to idle")


def _handle_pipeline_trigger(topic: str, category: str, format_type: str, trigger_id: str, publish_at: str = None):
    """Handle a pipeline run trigger from the dashboard."""
    scheduled_note = f" (scheduled: {publish_at})" if publish_at else ""
    log_event("TRIGGER", f"Dashboard trigger: {format_type} - {topic} (id: {trigger_id}){scheduled_note}")

    if is_blacklisted(topic):
        log_event("TRIGGER", f"Skipping blacklisted topic: {topic}")
        try:
            db = get_firestore_client()
            db.collection('pipeline_triggers').document(trigger_id).update({
                'status': 'skipped',
                'reason': 'blacklisted',
                'completed_at': time.time(),
            })
        except Exception as e:
            log_event("TRIGGER", f"Failed to mark trigger as skipped: {e}", "error")
        return

    try:
        video_id = f"trigger-{trigger_id}"
        if format_type == "long":
            success = _run_with_timeout(generate_long_video, (topic, category, video_id, publish_at), PIPELINE_TIMEOUT_MINUTES)
        else:
            success = _run_with_timeout(generate_short_video, (topic, category, video_id, publish_at), PIPELINE_TIMEOUT_MINUTES)

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
        except Exception as firebase_err:
            log_event("TRIGGER", f"Failed to update trigger status in Firestore: {firebase_err}", "error")


if __name__ == "__main__":
    log_event("SYSTEM", "Vyom Ai Cloud - Agent Orchestrator Starting")

    cleanup_stuck_state()

    from utils.firebase_status import reset_agent_statuses, delete_old_activity_entries, delete_old_videos, delete_old_pipeline_triggers
    try:
        reset_agent_statuses()
        delete_old_activity_entries()
        delete_old_videos()
        delete_old_pipeline_triggers()
    except Exception as startup_cleanup_err:
        log_event("CLEANUP", f"Startup cleanup failed: {startup_cleanup_err}", "warn")

    start_heartbeat_monitor(interval=600)
    start_health_server(port=8080)

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
    scheduler.add_job(daily_content_job, "cron", hour=6, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_analytics_job, "cron", hour=8, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_revenue_job, "cron", hour=8, minute=30, misfire_grace_time=86400)
    scheduler.add_job(daily_repurpose_job, "cron", hour=14, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_cleanup_job, "cron", hour=4, minute=0, misfire_grace_time=86400)
    scheduler.add_job(scheduled_publish_job, "interval", minutes=15)
    scheduler.add_job(weekly_monetization_job, "cron", day_of_week="mon", hour=12, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_feedback_job, "cron", hour=10, minute=0, misfire_grace_time=86400)
    log_event("SCHEDULER", "Daily content job scheduled at 06:00 UTC")
    log_event("SCHEDULER", "Daily analytics pull scheduled at 08:00 UTC")
    log_event("SCHEDULER", "Daily revenue computation scheduled at 08:30 UTC")
    log_event("SCHEDULER", "Daily repurpose job scheduled at 14:00 UTC")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")
    log_event("SCHEDULER", "Scheduled publish check every 15 minutes")
    log_event("SCHEDULER", "Weekly monetization review scheduled on Mondays at 12:00 UTC")
    log_event("SCHEDULER", "Daily analytics feedback loop scheduled at 10:00 UTC")

    try:
        daily_content_job()
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_event("SYSTEM", "Agent Orchestrator Shutting Down")
        control_listener.stop()
        update_pipeline_status(False)
