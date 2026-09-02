import os
import sys
import json
import re
import asyncio
import signal
import time
import warnings
warnings.filterwarnings("ignore", message="PyTorch was not found")
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub")
import logging
import atexit
from contextlib import contextmanager
from pathlib import Path
try:
    import sentry_sdk
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN", ""),
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
    )
    sentry_sdk.set_tag("service", "pipeline")
except ImportError:
    sentry_sdk = None

from utils.content_calendar import (
    schedule_topic, mark_topic_completed, mark_topic_failed, get_retry_queue,
    process_retry, get_calendar_summary, is_blacklisted
)
from utils.analytics_tracker import track_video, update_metrics, get_performance_summary
from utils.scheduler_planner import generate_content_plan
from utils.thumbnail_gen import generate_thumbnail_image, generate_thumbnail_variants, pick_best_thumbnail
from utils.health_monitor import start_heartbeat_monitor, start_health_server, check_ollama_health
from utils.description_gen import generate_description
from utils.subtitle_gen import generate_subtitles_for_video
from utils.translate import translate_script, dub_all_languages, register_dub_cleanup as register_dub_cleanup_func
from utils.comment_analyzer import analyze_sentiment, flag_negative_comments
from utils.pillar_manager import track_pillar_video, suggest_next_pillar, validate_plan_balance
from utils.seo_optimizer import get_optimized_tags, score_description_seo
from utils.alert_manager import process_alerts, send_alert

from utils.music_gen import generate_background_music
from utils.voice_gen import generate_voiceover
from utils.stock_video import search_videos_for_scenes
from utils.multi_platform_publisher import multi_platform_publish
from utils.trend_discovery import discover_trends
from utils.quality_scorer import score_content, predict_performance, check_repetition, evaluate_publish_decision
from utils.cleanup_service import run_cleanup
from utils.concurrent_pipeline import run_concurrent_pipelines
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
    sync_env_from_firestore,
)
from crew.thumbnail import create_thumbnail_crew
from crew.storyboard import create_storyboard_crew
from crew.scriptwriter import create_scriptwriter_crew, create_deep_lesson_crew
from crew.title_optimizer import create_title_optimizer_crew
from crew.virality_analyst import create_virality_analyst_crew, get_virality_threshold
from crew.monetization_tracker import create_monetization_review_crew, weekly_check_in, get_growth_summary
from utils.engagement_manager import append_comment_prompt_to_script
from compliance.hook_scorer import score_hook, enforce_rewrite
from compliance.content_safety import check_content_safety
from compliance.platform_policy import check_platform_compliance
from utils.title_tester import TitleTester
from utils.analytics_feedback import analyze_recent_performance, get_optimization_prompt_injection, get_pipeline_tuning
from utils.llm_helper import force_fallback, reset_fallback, empty_response_fallback
from utils.series_builder import register_video_in_series, build_continuity_text, generate_part_title, pick_series_for_category
from utils.checkpoint import save_checkpoint, load_checkpoint, clear_checkpoint
from utils.title_optimizer import pick_best_title
from crew.affiliate_manager import build_affiliate_section
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from utils.scene_parser import normalize_scene_durations
from utils.scene_architect import audit_scenes, SceneArchitectError

os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GLOG_minloglevel"] = "2"

SHORTS_MAX_DURATION = int(os.getenv("SHORTS_MAX_DURATION", "180"))
MIN_VIDEO_SIZE = 500 * 1024

ENABLE_VISUAL_QA = os.getenv("ENABLE_VISUAL_QA", "true").lower() == "true"
QA_BLACK_THRESHOLD = float(os.getenv("QA_BLACK_THRESHOLD", "0.35"))
QA_FREEZE_THRESHOLD = float(os.getenv("QA_FREEZE_THRESHOLD", "0.1"))
QA_BLUR_THRESHOLD = float(os.getenv("QA_BLUR_THRESHOLD", "100.0"))
QA_MAX_RETRIES = int(os.getenv("QA_MAX_RETRIES", "2"))


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
    for extra_braces in range(1, 20):
        try:
            parsed = json.loads(text + '}' * extra_braces)
            if isinstance(parsed, dict) and any(k in parsed for k in ["decision", "score", "overall_virality_score"]):
                return parsed
        except json.JSONDecodeError:
            continue
    from utils.json_utils import extract_json as _fallback_extract
    result = _fallback_extract(text)
    if result is not None:
        return result
    print(f"[EXTRACT] Failed to parse crew output (len={len(text)}), returning safe default")
    return {"decision": "block", "score": 0, "issues": [{"severity": "high", "detail": "Crew output parse failed"}], "feedback": "Auto-blocked (parse failure)", "breakdown": {"script_quality": 0, "visual_effectiveness": 0, "engagement": 0, "technical": 0}}


def _execute_single_task(crew_factory, inputs=None, **factory_kwargs):
    from crewai import Task as CrewAITask
    for attempt in range(3):
        crew = crew_factory(**factory_kwargs)
        try:
            result = crew.kickoff(inputs=inputs or {})
            raw = getattr(result, 'raw', str(result))
            if raw and len(raw.strip()) > 0:
                return raw
        except Exception as e:
            err_lower = str(e).lower()
            is_conn_err = any(k in err_lower for k in (
                "broken pipe", "connection reset", "connection refused",
                "errno 32", "errno 54", "errno 104",
                "reset by peer", "eof",
            ))
            if ('rate_limit' in err_lower or is_conn_err) and attempt < 2:
                delay = 5 if 'rate_limit' in err_lower else 2 ** (attempt + 2)
                print(f"[EXECUTE] Retryable error (attempt {attempt+1}/3), sleeping {delay}s: {str(e)[:80]}")
                time.sleep(delay)
                continue
            break
    try:
        agent = crew.agents[0]
        task = crew.tasks[0]
        desc = task.description
        for key, val in (inputs or {}).items():
            desc = desc.replace('{' + key + '}', str(val))
        existing_tools = getattr(task, 'tools', None)
        new_task = CrewAITask(
            description=desc,
            expected_output=task.expected_output,
            agent=agent,
        )
        if existing_tools:
            new_task.tools = existing_tools
        result = agent.execute_task(task=new_task, context=inputs, tools=existing_tools)
        raw = str(result or "")
        if raw and len(raw) > 20:
            return raw
    except Exception as e:
        print(f"[EXECUTE] Bypass also failed: {e}")
    return None


def verify_video_quality(video_path: str, format_type: str = "shorts") -> tuple[bool, str]:
    """Verify video file exists, has valid size, duration, and frame-level quality."""
    if not video_path or not os.path.exists(video_path):
        return False, "Video file not found"
    file_size = os.path.getsize(video_path)
    if file_size < MIN_VIDEO_SIZE:
        return False, f"Video too small ({file_size} bytes)"
    try:
        from utils.subprocess_helper import safe_run
        result = safe_run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
             "-of", "csv=p=0", video_path],
            timeout=30, capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) >= 1 and parts[0].strip():
                duration = float(parts[0])
                if format_type == "shorts" and duration > SHORTS_MAX_DURATION + 15:
                    return False, f"Duration {duration:.0f}s exceeds shorts limit"
                if format_type == "long" and duration < 30:
                    return False, f"Duration {duration:.0f}s too short for long-form"
    except Exception as e:
        print(f"[QUALITY] ffprobe check failed: {e}")

    if ENABLE_VISUAL_QA:
        try:
            from utils.video_qa import verify_frame_quality, check_frame_quality
            qa_pass, qa_report = verify_frame_quality(
                video_path, format_type,
                black_threshold=QA_BLACK_THRESHOLD,
                freeze_threshold=QA_FREEZE_THRESHOLD,
            )
            if not qa_pass:
                msg = f"Visual QA: {qa_report['summary']}"
                print(f"[QUALITY] {msg}")
                return False, msg
            print(f"[QUALITY] Visual QA passed: {qa_report['summary']}")

            blur_report = check_frame_quality(video_path, format_type, blur_threshold=QA_BLUR_THRESHOLD)
            if not blur_report.get("passed", True):
                msg = f"Visual QA blur: {blur_report['summary']}"
                print(f"[QUALITY] {msg}")
                return False, msg
            print(f"[QUALITY] Blur check passed: {blur_report['summary']}")
        except Exception as e:
            print(f"[QUALITY] Visual QA check failed (non-blocking): {e}")

    return True, ""


def _duration_ok(video_path: str, format_type: str) -> tuple[bool, str]:
    """Hard duration sanity check that FORCE_PUBLISH can NOT bypass.

    ponytail: FORCE_PUBLISH is meant to override *content/QA* subjective gates,
    NOT structural corruption. A 15s 'long' (or a 0s/absent file) is broken output,
    not a style choice — publishing it poisons the channel AND feeds the repurpose
    job (today's 15s long -> 15s repurposed short cascade). Return False = re-queue.
    """
    if not video_path or not os.path.exists(video_path):
        return False, "No video file produced"
    try:
        from utils.subprocess_helper import safe_run
        result = safe_run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size",
             "-of", "csv=p=0", video_path],
            timeout=30, capture_output=True, text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if parts and parts[0].strip():
                duration = float(parts[0])
                if format_type == "long" and duration < 30:
                    return False, f"Duration {duration:.0f}s too short for long-form (hard block)"
                if format_type == "shorts" and duration < 3:
                    return False, f"Duration {duration:.0f}s too short for a short (hard block)"
    except Exception as e:
        print(f"[QUALITY] duration check failed: {e}")
    return True, ""


def _run_async(coro, timeout=300):
    """Run an async coroutine safely, even from a threaded context with a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=timeout)


logging.getLogger("grpc").setLevel(logging.ERROR)
logging.getLogger("google.cloud.firestore").setLevel(logging.WARNING)

warnings.filterwarnings("ignore", message=".*fork_posix.*")
warnings.filterwarnings("ignore", message=".*ev_poll_posix.*")
warnings.filterwarnings("ignore", message=".*Detected filter using positional arguments.*")


load_dotenv()

# Reload env vars after load_dotenv() (module-level reads happen before dotenv)
for _key in ("SHORTS_MAX_DURATION", "MIN_VIRALITY_SCORE", "MIN_VIRALITY_SCORE_LONG", "HOOK_FORMULA"):
    _val = os.getenv(_key)
    if _val:
        os.environ[_key] = _val
SHORTS_MAX_DURATION = int(os.getenv("SHORTS_MAX_DURATION", "180"))
LONG_MAX_DURATION = int(os.getenv("LONG_MAX_DURATION", "600"))

# Override env vars from Firestore env_vars collection (dashboard-managed)
sync_env_from_firestore()

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
ENABLE_COMPANION_PAGES = os.getenv("ENABLE_COMPANION_PAGES", "true").lower() == "true"
ENABLE_DIRECTOR_REVIEW = os.getenv("ENABLE_DIRECTOR_REVIEW", "true").lower() == "true"
MULTI_LANG_CODES = os.getenv("MULTI_LANG_CODES", "es,de,fr").split(",")
ENABLE_MULTI_LANG_DUB = os.getenv("ENABLE_MULTI_LANG_DUB", "false").lower() == "true"
ENABLE_LTX_CACHE = os.getenv("ENABLE_LTX_CACHE", "true").lower() == "true"
PIPELINE_TIMEOUT_MINUTES = int(os.getenv("PIPELINE_TIMEOUT_MINUTES", 120))
MAX_RETRIES_PER_TOPIC = int(os.getenv("MAX_RETRIES_PER_TOPIC", 2))
FORCE_PUBLISH = os.getenv("FORCE_PUBLISH", "true").lower() == "true"
USE_ANIMATION_ENGINE = os.getenv("USE_ANIMATION_ENGINE", "true").lower() == "true"
LONG_MAX_DURATION = int(os.getenv("LONG_MAX_DURATION", 600))
DEEP_LESSON_MAX_DURATION = int(os.getenv("DEEP_LESSON_MAX_DURATION", 600))
DOCUMENTARY_MAX_DURATION = int(os.getenv("DOCUMENTARY_MAX_DURATION", 2400))
LONG_MIN_NARRATION_WORDS = int(os.getenv("LONG_MIN_NARRATION_WORDS", "360"))
NEWS_LONG_MIN_NARRATION_WORDS = int(os.getenv("NEWS_LONG_MIN_NARRATION_WORDS", "450"))

from utils.scene_schema import DEEP_LESSON_CATS as DEEP_LESSON_CATEGORIES


def _deep_lesson_dur(category: str) -> int:
    """Return max_duration appropriate for this category (deep lesson vs regular long)."""
    if os.environ.get("TIER", "") == "documentary":
        return DOCUMENTARY_MAX_DURATION
    return DEEP_LESSON_MAX_DURATION if category in DEEP_LESSON_CATEGORIES else LONG_MAX_DURATION
ENABLE_COMMUNITY_POSTS = os.getenv("ENABLE_COMMUNITY_POSTS", "false").lower() == "true"
GATE_ENFORCEMENT_MODE = os.getenv("GATE_ENFORCEMENT_MODE", "advisory").lower()
SCENE_ARCHITECT_MODE = os.getenv("SCENE_ARCHITECT_MODE", "advisory").lower()

# ── Logging setup ────────────────────────────────────────────────
_LOG_FILE = None


def _get_log_file():
    global _LOG_FILE
    if _LOG_FILE is None:
        log_dir = Path(__file__).parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        _LOG_FILE = str(log_dir / "pipeline.log")
    try:
        # lightweight size-based rotation (10MB cap, keep 1 backup)
        if os.path.getsize(_LOG_FILE) > 10 * 1024 * 1024:
            os.replace(_LOG_FILE, _LOG_FILE + ".1")
    except OSError:
        pass
    return _LOG_FILE


def _setup_logging():
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_dir / "python.log")),
            logging.StreamHandler(),
        ],
    )
    atexit.register(lambda: logging.info("Process exiting"))


def log_event(agent: str, message: str, level: str = "info"):
    """Log a structured event to stdout JSON, pipeline.log, and Python logging."""
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level.upper(),
        "agent": agent,
        "message": message,
    }
    line = json.dumps(record)
    print(line)
    try:
        with open(_get_log_file(), "a") as f:
            f.write(line + "\n")
    except Exception:
        pass
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.getLogger(agent).log(log_level, "%s", message)


# ── Pipeline timing / metrics ────────────────────────────────────


def _track_pipeline_duration(video_id: str, format_type: str, topic: str,
                              duration_sec: float, success: bool):
    """Record pipeline execution metrics to Firestore."""
    try:
        from utils.firebase_status import get_firestore_client
        db = get_firestore_client()
        if not db:
            return
        doc_id = f"{video_id}_{int(time.time())}"
        from google.cloud.firestore import SERVER_TIMESTAMP
        db.collection("pipeline_metrics").document(doc_id).set({
            "video_id": video_id,
            "format": format_type,
            "topic": topic,
            "duration_sec": round(duration_sec, 1),
            "success": success,
            "created_at": SERVER_TIMESTAMP,
        })
    except Exception:
        pass


@contextmanager
def _track_step(video_id, step_name):
    """Context manager to measure and log a pipeline step duration."""
    start = time.perf_counter()
    try:
        yield
        elapsed = time.perf_counter() - start
        log_event("TIMING", f"{step_name}: {elapsed:.1f}s", "info")
    except Exception as e:
        elapsed = time.perf_counter() - start
        log_event("TIMING", f"{step_name}: FAILED at {elapsed:.1f}s — {e}", "error")
        raise


def validate_env():
    """Validate required env vars at startup. Log warnings for missing critical vars."""
    critical = {
        "GEMINI_API_KEY": "LLM provider (primary)",
        "FIREBASE_PROJECT_ID": "Firebase/Firestore",
    }
    conditional = {
        "TIKTOK_ACCESS_TOKEN": "TikTok publishing",
        "TIKTOK_CLIENT_KEY": "TikTok OAuth refresh",
        "TIKTOK_CLIENT_SECRET": "TikTok OAuth refresh",
        "FACEBOOK_ACCESS_TOKEN": "Facebook/Instagram publishing",
        "FACEBOOK_APP_ID": "Facebook token refresh",
        "FACEBOOK_APP_SECRET": "Facebook token refresh",
        "PEXELS_API_KEY": "Stock video search",
        "SENTRY_DSN": "Error tracking",
    }
    for var, purpose in critical.items():
        if not os.getenv(var):
            log_event("ENV", f"MISSING required env var: {var} ({purpose})", "error")
    for var, purpose in conditional.items():
        if not os.getenv(var):
            log_event("ENV", f"MISSING optional env var: {var} ({purpose}) — feature disabled", "warn")
    log_event("ENV", f"Gate enforcement mode: {GATE_ENFORCEMENT_MODE}")
    from utils.subprocess_helper import security_audit
    security_audit("STARTUP", f"Gate enforcement mode: {GATE_ENFORCEMENT_MODE}")


def _run_with_timeout(func, args, timeout_minutes: int):
    """Run a synchronous function with a timeout. Raises TimeoutError if exceeded."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func, *args)
        return future.result(timeout=timeout_minutes * 60)


def _check_all_platforms_compliance(video_data: dict, platforms: list) -> list:
    """Check platform compliance against each target platform. Aggregates warnings."""
    if not isinstance(video_data, dict):
        video_data = {}
    from compliance.platform_policy import check_platform_compliance
    all_warnings = []
    for p in platforms:
        try:
            warnings = check_platform_compliance(video_data, p)
            all_warnings.extend(warnings)
        except Exception:
            pass
    return all_warnings


def _gate_check(name, is_flagged, topic, video_id, format_type, category):
    """If GATE_ENFORCEMENT_MODE=enforce and gate is flagged, block the pipeline."""
    if not is_flagged:
        return True
    log_event("GATE", f"{name} flagged '{topic}' — {'blocking' if GATE_ENFORCEMENT_MODE == 'enforce' else 'proceeding anyway'}",
              "warn")
    from utils.subprocess_helper import security_audit
    security_audit("GATE_BLOCK", f"{name} — {topic} (mode={GATE_ENFORCEMENT_MODE})", "warning")
    if GATE_ENFORCEMENT_MODE == "enforce":
        log_event("GATE", f"{name} BLOCKED '{topic}'", "error")
        add_video_record(video_id, topic, format_type, f"blocked_{name.lower().replace(' ', '_')}", category=category)
        update_pipeline_status(False)
        return False
    return True


def _strip_ansi(text: str) -> str:
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


def _count_script_words(script_text) -> int:
    return len(str(script_text or "").split())


def _simplify_script(script_text: str, category: str, fmt: str) -> str:
    """One-pass plain-language rewrite of NARRATION lines. Never blocks the pipeline."""
    try:
        from utils.simplify_audit import audit_simplify, simplify_rewrite
        if not isinstance(script_text, str) or not script_text.strip():
            return script_text
        audit = audit_simplify(script_text)
        if audit["passed"]:
            return script_text
        log_event("SIMPLIFY", f"Script too technical ({len(audit['terms'])} flagged terms) — one-pass rewrite", "warn")
        res = simplify_rewrite(script_text, format_type=fmt, category=category)
        if res.get("changed") and res["rewritten"]:
            log_event("SIMPLIFY", f"Simplified narration for a non-technical audience")
            return res["rewritten"]
        log_event("SIMPLIFY", f"Simplify rewrite skipped: {res.get('error', 'no change')}", "warn")
        return script_text
    except Exception as e:
        log_event("SIMPLIFY", f"Simplify step skipped: {e}", "warn")
        return script_text


def _rewrite_on_director_fix(review: dict, topic: str, category: str, fmt: str, script_text: str,
                             extra_ctx: str = "") -> str:
    """If director grades the script as needing fixes (not a hard block), do ONE
    scriptwriter re-author pass injecting the issues, then simplify. Safe: any
    failure falls back to the original script."""
    if not review or review.get("decision") not in ("fix", "needs_edit", "review"):
        return script_text
    issues = review.get("issues") or []
    if not issues:
        return script_text
    try:
        issues_txt = "; ".join([f"[{i.get('severity','info')}] {i.get('description','')}" for i in issues[:3]])
        ctx = (extra_ctx + "\n\n" if extra_ctx else "") + \
              f"DIRECTOR FEEDBACK to fix in the rewrite:\n{issues_txt}\nAddress each concretely."
        kw = {"topic": topic, "category": category, "fmt": fmt,
              "max_duration": SHORTS_MAX_DURATION if fmt == "shorts" else _deep_lesson_dur(category),
              "extra_context": ctx}
        crew_fn = create_scriptwriter_crew if fmt == "shorts" else create_deep_lesson_crew
        rewritten = run_agent_step("scriptwriter", "Scriptwriter (director-fix)",
                                   f"Rewriting per director feedback for: {topic}", crew_fn, kw,
                                   timeout_minutes=20)
        if rewritten and isinstance(rewritten, str) and rewritten.strip():
            log_event("DIRECTOR", f"Re-authored script per director feedback (decision={review.get('decision')})")
            return _simplify_script(rewritten, category, "shorts" if fmt == "shorts" else "long")
        log_event("DIRECTOR", "Director-fix rewrite returned empty; keeping original", "warn")
        return script_text
    except Exception as e:
        log_event("DIRECTOR", f"Director-fix rewrite skipped: {e}", "warn")
        return script_text


def _pick_best_title(variants, topic: str, category: str = "") -> str:
    """Pick the highest-scoring title from CrewAI variants instead of blindly [0].
    Falls back to the topic when nothing usable exists."""
    from utils.title_optimizer import score_title
    if isinstance(topic, dict):
        topic = topic.get("title", "")
    vals = []
    for v in (variants or []):
        if isinstance(v, dict):
            v = v.get("title", "")
        v = (v or "").strip()
        if v:
            vals.append(v)
    if not vals:
        return topic or "Untitled"
    scored = [(score_title(t, [category]), t) for t in vals]
    scored.sort(key=lambda x: x[0]["score"], reverse=True)
    best = scored[0][1]
    # YouTube API hard-caps titles at 100 chars; LLMs can't count, so enforce at the choke point.
    if len(best) > 100:
        cut = best[:100].rsplit(" ", 1)[0].rstrip()
        best = (cut or best[:100]).rstrip()
    return best




def run_agent_step(agent_id: str, agent_name: str, action: str, crew_factory, inputs: dict, max_retries: int = None, timeout_minutes: int = 15):
    if max_retries is None:
        max_retries = MAX_RETRIES_PER_TOPIC
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
                try:
                    result = crew.kickoff(inputs=inputs)
                    raw = getattr(result, 'raw', str(result))
                    raw = _strip_ansi(raw) if raw else ""
                    if raw and len(raw.strip()) > 0:
                        return raw
                except Exception:
                    from crewai import Task as CrewAITask
                    agent = crew.agents[0]
                    task = crew.tasks[0]
                    desc = task.description.format(**inputs) if inputs else task.description
                    new_task = CrewAITask(description=desc, expected_output=task.expected_output, agent=agent)
                    bypass = agent.execute_task(task=new_task, context=None, tools=None)
                    bypass = _strip_ansi(bypass or "")
                    return bypass or ""
                return ""
            result = _run_with_timeout(_kick, (), timeout_minutes)
            update_agent_status(agent_id, "completed", f"Completed: {action}")
            log_activity(agent_id, f"Completed: {action}", "success")
            log_event(agent_name, f"Completed: {action}")
            return result
        except Exception as e:
            err_str = str(e)
            err_lower = err_str.lower()
            is_connection_error = any(k in err_lower for k in (
                "broken pipe", "connection reset", "connection refused",
                "errno 32", "errno 54", "errno 104",
                "reset by peer", "eof", "connection error",
            ))
            if "rate_limit" in err_lower:
                log_event(agent_name, "Rate-limited, flagging for fallback", "warn")
            if "Invalid response from LLM call" in err_str:
                log_event(agent_name, "LLM returned empty response — rotating provider routing", "warn")
                empty_response_fallback()
            if "TimeoutError" in type(e).__name__ or "timed out" in err_lower:
                log_event(agent_name, f"Timed out after {timeout_minutes}min — resetting provider routing", "error")
                reset_fallback()
            if is_connection_error:
                if "connection refused" in err_lower:
                    log_event(agent_name, "Ollama connection refused → forcing Gemini fallback", "error")
                    force_fallback(failed_provider="ollama")
                else:
                    log_event(agent_name, f"Connection error — resetting provider routing: {err_str[:80]}", "error")
                    reset_fallback()
            if attempt < max_retries - 1:
                delay = 2 ** (attempt + 2) if is_connection_error else 2 ** (attempt + 1)
                log_event(agent_name, f"Failed (attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {err_str[:120]}")
                time.sleep(delay)
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
            if re.match(r'--(SCENE|SHOT|CLIP)\b', stripped, re.IGNORECASE) and len(stripped) < 100:
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
        min_scenes = max(12, max_duration // 30)
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


def _parse_scenes_for_asset_router(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int = None) -> list[dict]:  # noqa: E501
    from utils.scene_parser import (parse_script_to_scenes, normalize_scene_durations,
                                     enrich_scenes_with_annotations)
    from utils.series_router import inject_intro_outro
    scenes = parse_script_to_scenes(script_text, title=video_id, category=category, format_type=format_type, storyboard_text=str(storyboard_text), max_duration=max_duration)
    scenes = inject_intro_outro(scenes, category, format_type)
    normalize_scene_durations(scenes)
    if os.getenv("ENABLE_ANNOTATIONS", "true").lower() == "true":
        scenes = enrich_scenes_with_annotations(scenes)
    log_event("PIPELINE", f"Asset Router: {len(scenes)} scenes")
    if SCENE_ARCHITECT_MODE != "off":
        try:
            audit_scenes(scenes)
        except SceneArchitectError as e:
            log_event("ARCHITECT", f"Scene Architect blocked: {e}", "warn")
    return scenes


STOPWORDS_FOR_ALIGN = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "and", "or", "but", "if", "while", "about", "up", "down", "like",
    "just", "because", "also", "very", "too", "not", "no", "only", "so",
    "then", "once", "here", "there", "when", "where", "why", "how",
}


_SUFFIX_RULES = [
    (r'ing$', ''), (r'ed$', ''), (r'ies$', 'y'), (r'ies$', 'ie'),
    (r'es$', ''), (r's$', ''), (r'ly$', ''), (r'tion$', 't'),
    (r'sion$', 's'), (r'ment$', ''), (r'ness$', ''), (r'able$', ''),
    (r'ful$', ''), (r'er$', ''), (r'est$', ''), (r'al$', ''),
    (r'ive$', ''), (r'ize$', ''), (r'ise$', ''),
]


def _stem(word: str) -> str:
    for pattern, replacement in _SUFFIX_RULES:
        if re.search(pattern, word):
            return re.sub(pattern, replacement, word)
    return word


def _word_overlap_ratio(phrase_words: set, scene_words: set, scene_idx: int = 0) -> float:
    if not phrase_words or not scene_words:
        return 0.0
    intersection = phrase_words & scene_words
    if not intersection:
        return 0.0
    short_len = min(len(phrase_words), len(scene_words))
    overlap = len(intersection) / max(short_len, 1)
    return overlap - (scene_idx * 1e-9)


def _tokenize(text: str) -> set:
    return {_stem(w) for w in re.findall(r'\b[a-z]{2,}\b', text.lower()) if w not in STOPWORDS_FOR_ALIGN}


def _align_scenes_to_audio(scenes: list[dict], phrase_timings: list[dict], audio_duration: float) -> list[dict]:
    if not phrase_timings or not scenes or audio_duration <= 0:
        return scenes

    if len(phrase_timings) < 3:
        log_event("VOICE", "Audio align: too few phrase timings, using proportional scaling", "debug")
        return _proportional_scale(scenes, audio_duration)

    scene_audio_durs = [0.0 for _ in scenes]
    unmatched_phrases = []
    mapped_count = 0
    total_phrases = len(phrase_timings)

    scene_words = [_tokenize(s.get("narration_text", "")) for s in scenes]

    for pt in phrase_timings:
        phrase_text = pt.get("text", "")
        if not phrase_text:
            continue
        phrase_dur = max(pt.get("end_ms", 0) - pt.get("start_ms", 0), 100)
        phrase_w = _tokenize(phrase_text)
        if not phrase_w:
            continue

        best_idx = -1
        best_ratio = 0.0
        for si, sw in enumerate(scene_words):
            ratio = _word_overlap_ratio(phrase_w, sw, scene_idx=si)
            if ratio > best_ratio and ratio >= 0.3:
                best_ratio = ratio
                best_idx = si

        if best_idx >= 0:
            scene_audio_durs[best_idx] += phrase_dur / 1000.0
            mapped_count += 1
        else:
            unmatched_phrases.append(pt)

    if mapped_count < 3 or mapped_count / max(total_phrases, 1) < 0.3:
        log_event("VOICE", f"Audio align: only {mapped_count}/{total_phrases} phrases mapped to scenes, falling back to proportional", "debug")
        return _proportional_scale(scenes, audio_duration)

    collided_idx = max(range(len(scene_audio_durs)), key=lambda i: scene_audio_durs[i])
    collided_ratio = scene_audio_durs[collided_idx] / max(sum(scene_audio_durs), 0.01)
    if collided_ratio > 0.80:
        log_event("VOICE", f"Audio align: {collided_ratio:.0%} of audio maps to scene {collided_idx}, falling back to proportional", "debug")
        return _proportional_scale(scenes, audio_duration)

    total_mapped = sum(scene_audio_durs)
    for i, s_dur in enumerate(scene_audio_durs):
        gap = 0.3
        if s_dur > 0:
            scenes[i]["target_duration"] = round(max(2.0, min(30.0, s_dur + gap)), 1)
        else:
            planner = scenes[i].get("duration", scenes[i].get("target_duration", 8.0))
            scenes[i]["target_duration"] = round(max(2.0, min(30.0, planner)), 1)

    new_total = sum(s.get("target_duration", 8.0) for s in scenes)
    if new_total > audio_duration * 1.1:
        ratio = audio_duration / max(new_total, 1)
        for s in scenes:
            s["target_duration"] = round(max(2.0, min(30.0, s.get("target_duration", 8.0) * ratio)), 1)
        log_event("VOICE", f"Audio align: compressed {new_total:.1f}s → {audio_duration:.1f}s ({ratio:.2f}x)", "debug")
    else:
        log_event("VOICE", f"Audio align: mapped {mapped_count}/{total_phrases} phrases, total {sum(scene_audio_durs):.1f}s", "debug")

    return scenes


def _proportional_scale(scenes: list[dict], audio_duration: float) -> list[dict]:
    scene_total = sum(s.get("target_duration", s.get("duration", 8.0)) for s in scenes)
    if scene_total <= 0:
        return scenes
    ratio = audio_duration / scene_total
    for s in scenes:
        td = s.get("target_duration", s.get("duration", 8.0))
        s["target_duration"] = max(2.0, min(30.0, round(td * ratio, 1)))
    return scenes


def run_video_pipeline(script_text: str, storyboard_text: str, category: str, format_type: str, video_id: str, max_duration: int, generate_subs: bool = True, subtitle_lang: str = "en", tier: str = "") -> dict:  # noqa: E501
    log_event("PIPELINE", "Step 1: Parsing storyboard into scenes")
    is_documentary = bool(tier) if tier else (os.environ.get("TIER", "") == "documentary")
    _tier_param = tier or ("documentary" if is_documentary else "")
    use_asset_router = USE_ANIMATION_ENGINE

    scenes = None
    clips = None
    total_video_duration = 0.0

    if use_asset_router:
        scenes = _parse_scenes_for_asset_router(script_text, storyboard_text, category, format_type, video_id, max_duration)
    else:
        scenes, clips, total_video_duration = _run_stock_footage_pipeline(script_text, storyboard_text, category, format_type, video_id, max_duration)

    log_event("PIPELINE", "Step 2: Generating voice-over with Edge TTS")
    update_agent_status("voice", "working", "Generating narration audio")
    is_long = format_type == "long"
    is_deep_lesson = True if format_type == "long" else (category in DEEP_LESSON_CATEGORIES)
    from utils.voice_gen import extract_narration_text
    narration_text = extract_narration_text(script_text, is_long_form=is_long)
    # ponytail: hard cap narration for shorts — 150 words ≈ 60s at TTS pace
    if format_type == "shorts":
        _max_w = int(os.getenv("SHORTS_MAX_WORDS", "150"))
        _words = narration_text.split()
        if len(_words) > _max_w:
            narration_text = " ".join(_words[:_max_w])
            log_event("VOICE", f"Truncated narration from {len(_words)} to {_max_w} words for shorts")
    voice_result = _run_async(generate_voiceover(script_text, output_filename=f"voiceover_{video_id}.wav", content_type="educational", is_long_form=is_long, is_deep_lesson=is_deep_lesson, is_documentary=is_documentary))
    if not voice_result.get("success"):
        log_pipeline_error(video_id, "Voice-over generation failed", "voice_generation")
        raise Exception("Voice-over generation failed.")
    log_event(
        "VOICE", f"Voice-over: {voice_result['duration']:.1f}s, {voice_result['segments']} segments -> {voice_result['path']}")  # noqa: E501
    update_agent_status("voice", "completed", f"Voice-over {voice_result['duration']:.1f}s")

    audio_dur = voice_result.get("duration", 0)
    if use_asset_router and audio_dur > 0 and voice_result.get("phrase_timings"):
        scenes = _align_scenes_to_audio(scenes, voice_result["phrase_timings"], audio_dur)
        from utils.asset_router import dispatch_scenes
        update_agent_status("animator", "working", f"Generating {len(scenes)} scenes via AI video engine")
        log_activity("pipeline", f"Asset Router: generating {len(scenes)} scenes (LTX AI + stock fallback)", "info")
        clips = dispatch_scenes(scenes, video_id, format_type, category=category)
        update_agent_status("animator", "completed", f"Generated {len(clips)}/{len(scenes)} video assets")
        total_video_duration = sum(c.get("duration", 8.0) for c in clips)
    elif audio_dur > 0 and scenes:
        scenes = _proportional_scale(scenes, audio_dur)
        total_video_duration = audio_dur

    subtitle_path = None
    if generate_subs and ENABLE_SUBTITLES:
        timing_file = voice_result.get("timing_file", "")
        # ponytail: subtitles must reflect EXACTLY what the voice said. The voice
        # speaks the symbol-expanded narration (voice_gen._expand_symbols_for_tts),
        # so feed that spoken_text (not the raw narration) to the SRT builder.
        caption_src = voice_result.get("spoken_text") or narration_text
        log_event("PIPELINE", f"Step 2.5: Generating subtitles (timing_file={'yes' if timing_file else 'no — using text fallback'})")
        update_agent_status("voice", "working", "Generating subtitles from voice timing")
        sub_result = generate_subtitles_for_video(
            timing_file=timing_file,
            full_text=caption_src,
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

    update_agent_status("voice", "completed", "Voice processing complete")

    log_event("PIPELINE", "Step 3: Generating background music")
    update_agent_status("composer", "working", "Creating background music")
    from utils.music_gen import score_scene_energy, ENERGY_TO_MOOD
    scene_moods = []
    for s in (scenes if isinstance(scenes, list) else []):
        if isinstance(s, dict):
            mm = s.get("music_mood")
            if mm and mm != "focused":
                scene_moods.append(mm)
            else:
                text = s.get("narration_text") or s.get("text") or s.get("keyword", "")
                energy = score_scene_energy(text)
                scene_moods.append(ENERGY_TO_MOOD.get(energy, "focused"))
    music_result = generate_background_music(category, duration=total_video_duration, scene_moods=scene_moods if scene_moods else None, tier=_tier_param)
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

        def _chapter_title(scene: dict, idx: int) -> str:
            kw = scene.get("keyword") or ""
            if kw:
                return kw[:50]
            keywords = scene.get("asset_keywords", [])
            if keywords and isinstance(keywords, list) and keywords[0]:
                return keywords[0][:50]
            ltx = scene.get("ltx_prompt", "")
            if ltx:
                words = ltx.split()[:6]
                return " ".join(words)[:50]
            title = scene.get("scene_title", "")
            if title:
                return title[:50]
            return f"Chapter {idx + 1}"

        if use_asset_router and scenes:
            for i, s in enumerate(scenes):
                dur = s.get("duration", s.get("target_duration", 8.0))
                chapters.append({"start_time": current_time, "end_time": current_time + dur, "title": _chapter_title(s, i)})
                current_time += dur
        elif clips and scenes:
            clip_count = len(clips)
            for i, scene in enumerate(scenes[:clip_count]):
                clip_dur = clips[i]["duration"] if i < len(clips) else 5.0
                chapters.append({"start_time": current_time, "end_time": current_time + clip_dur, "title": _chapter_title(scene, i)})
                current_time += clip_dur
        log_event("PIPELINE", f"Generated {len(chapters)} chapter markers")

    log_event("PIPELINE", "Step 4: Compositing final video")
    anim_label = " with Asset Router" if use_asset_router else " with FFmpeg"
    update_agent_status("editor", "working", f"Compositing video{anim_label}")

    from utils.video_compositor import composite_video
    if use_asset_router:
        final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes, tier=_tier_param)
    else:
        final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes, tier=_tier_param)

    if not final_path:
        log_event("EDITOR", "Composite failed, retrying with concat-only fallback")
        if use_asset_router:
            final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes, force_concat=True, tier=_tier_param)
        else:
            final_path = composite_video(clips=clips, voice_path=voice_result["path"], music_path=music_path, format_type=format_type, video_id=video_id, subtitle_path=subtitle_path, chapters=chapters, category=category, scenes=scenes, force_concat=True, tier=_tier_param)

    if not final_path:
        log_pipeline_error(video_id, "Video compositing failed after retry", "video_compositing")
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
        "timing_file": voice_result.get("timing_file"),
        "phrase_timings": voice_result.get("phrase_timings", []),
        "scenes": scenes,
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
    from crew.director import create_director_crew
    last_review = None
    for attempt in range(2):
        try:
            extra_context = ""
            if attempt == 1 and last_review and last_review.get("issues"):
                issues_text = "; ".join([f"[{i['severity']}] {i['description']}" for i in last_review["issues"][:3]])
                extra_context = f"\n\nPrevious review flagged these issues — address them specifically:\n{issues_text}"
            raw = _execute_single_task(create_director_crew, {
                "script": script + extra_context,
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
            if attempt == 0 and review.get("decision") == "fix":
                last_review = review
                log_event("DIRECTOR", f"[{stage}] Fix needed ({review.get('score', 0)}/100), retrying with feedback")
                continue
            return review
        except Exception as e:
            log_event("DIRECTOR", f"[{stage}] Review attempt {attempt+1} failed: {e}", "error")
    return {"decision": "block", "score": 0, "issues": [{"severity": "error", "description": "Review unavailable"}], "feedback": "Auto-blocked (review unavailable)"}


_pipeline_tuning_cache: dict = {}


def _apply_pipeline_tuning() -> dict:
    global _pipeline_tuning_cache
    tuning = get_pipeline_tuning()
    _pipeline_tuning_cache = tuning
    if not tuning.get("preferred_category") and not tuning.get("preferred_format"):
        return tuning
    log_event("ANALYTICS", f"Pipeline tuning active: category={tuning['preferred_category']}, format={tuning['preferred_format']}, virality_boost={tuning['virality_boost']}")
    if tuning["preferred_format"]:
        os.environ["PREFERRED_FORMAT"] = tuning["preferred_format"]
    if tuning["preferred_category"]:
        os.environ["PREFERRED_CATEGORY"] = tuning["preferred_category"]
    return tuning


def generate_short_video(topic: str, category: str, video_id: str, publish_at: str = None, news_article: dict = None):
    from utils.scene_schema import normalize_category
    category = normalize_category(category)
    _start_time = time.perf_counter()
    _apply_pipeline_tuning()
    update_pipeline_status(True, topic)
    add_video_record(video_id, topic, "shorts", "generating", category=category)
    log_event("PIPELINE", f"Starting SHORT video generation: {topic}")

    if sentry_sdk:
        sentry_sdk.set_tag("video_id", video_id)
        sentry_sdk.set_tag("format", "shorts")
        sentry_sdk.set_tag("category", category)
        sentry_sdk.add_breadcrumb(category="pipeline", message=f"Starting shorts: {topic}", level="info")

    cp = load_checkpoint(video_id)
    if cp:
        log_event("CHECKPOINT", f"Resuming from step: {cp.get('step', 'unknown')}")

    failed_step = "setup"
    try:
        failed_step = "scriptwriting"
        with _track_step(video_id, "scriptwriting"):
            opt_injection = get_optimization_prompt_injection()

            from utils.knowledge_integration import inject_knowledge_context
            knowledge_ctx = inject_knowledge_context(topic, category)
            series_ctx = ""
            try:
                _series = pick_series_for_category(category)
                if _series:
                    next_part = _series.get("current_part", 0) + 1
                    continuity = build_continuity_text(_series, next_part)
                    if continuity:
                        series_ctx = f"Series context: {continuity}"
            except Exception:
                pass

            trend_ctx = ""
            try:
                from utils.trend_discovery import discover_trends as _dt
                _tr = _dt()
                if _tr:
                    _hooks = [t.get("title", "") for t in _tr[:5] if t.get("title")]
                    trend_ctx = "Current trending hooks for viral optimization:\n" + "\n".join(f"- {h}" for h in _hooks)
            except Exception:
                trend_ctx = ""

            from utils.analytics_feedback import get_top_performing_topics
            _topics_ctx = ""
            try:
                _best_topics = get_top_performing_topics(3)
                if _best_topics:
                    _topics_ctx = "Topics that performed well recently:\n" + "\n".join(
                        f"- {t['topic']}: {t['avg_views']} avg views" for t in _best_topics
                    )
            except Exception:
                pass

            _retention_ctx = ""
            try:
                from utils.retention_analyzer import get_insights
                ri = get_insights(category)
                if ri and ri.get("sample_size", 0) > 0:
                    drops = ", ".join(f"{t} ({mag})" for t, mag in ri.get("common_drop_points", [])) or "none"
                    _retention_ctx = (
                        f"Audience retention feedback for this category (sample {ri.get('sample_size')}): "
                        f"hook retention avg {ri.get('avg_hook_retention', 0)}, overall avg "
                        f"{ri.get('avg_overall_retention', 0)}. Viewers drop off around: {drops}. "
                        "Tighten the hook if low, and avoid padding or re-explaining right before "
                        "the drop points to hold viewers to the end."
                    )
            except Exception:
                _retention_ctx = ""

            extra_parts = [p for p in [knowledge_ctx, series_ctx, trend_ctx, opt_injection, _topics_ctx, _retention_ctx] if p]
            # News videos: replace tech knowledge/series/trend context with the actual verified
            # news article so the script is an accurate, sourced explainer (never invented).
            if news_article:
                _na = news_article
                news_ctx = (
                    f"VERIFIED NEWS ARTICLE to explain:\n"
                    f"- Headline: {_na.get('title','')}\n"
                    f"- Source: {_na.get('source','')} (verified publisher)\n"
                    f"- Article link: {_na.get('link','')}\n"
                    f"- Language: {_na.get('lang','en')}\n"
                    f"- Summary: {_na.get('description','')}\n"
                    f"Write an educational explainer that reports the news accurately from the "
                    f"source above, gives context, and explains why it matters. Do NOT invent "
                    f"facts not in the article. Cite the source in the description at the end."
                )
                extra_parts = [news_ctx]
            try:
                from utils.hook_tester import suggest_hook_formula, get_hook_stats
                best_hook = suggest_hook_formula(category)
                hook_stats = get_hook_stats(category)
                best_stat = hook_stats.get(best_hook, {})
                if best_stat.get("count", 0) > 0:
                    extra_parts.append(f"Hook recommendation: Use '{best_hook}' hook for {category} — avg {best_stat['avg_views']} views, {best_stat['avg_retention']:.0%} retention across {best_stat['count']} videos. Other formulas: " + ", ".join(f"{f}({s['avg_views']}v)" for f, s in hook_stats.items() if s.get("count", 0) > 0 and f != best_hook))
            except Exception:
                pass
            # Pre-writing virality guidance
            try:
                from crew.virality_analyst import get_prewriting_guidance
                extra_parts.append(get_prewriting_guidance(topic, category, "shorts"))
            except Exception:
                pass
            extra_context = "\n".join(extra_parts) if extra_parts else ""

            script_kwargs = {"topic": topic, "category": category, "fmt": "shorts", "max_duration": SHORTS_MAX_DURATION}
            if extra_context:
                script_kwargs["extra_context"] = extra_context
            script = run_agent_step("scriptwriter", "Scriptwriter", f"Writing script for: {topic}", create_scriptwriter_crew, script_kwargs, timeout_minutes=20)  # noqa: E501
            script_text = str(script)
            save_checkpoint(video_id, "scriptwriting", {"script_preview": script_text[:200]})

            from utils.llm_helper import reset_fallback
            reset_fallback()

        failed_step = "hook_scoring"
        hook_score_result = score_hook(script_text, category=category)
        if hook_score_result is None:
            hook_score_result = {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["could not evaluate with llm"], "suggested_alternatives": []}
        _hook_llm_failed = "could not evaluate with llm" in str(hook_score_result.get("weaknesses", [])).lower()
        if hook_score_result["score"] < 60:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — enforcing rewrite")
            new_script = enforce_rewrite(script_text, category=category)
            if new_script != script_text:
                script_text = new_script
                if not _hook_llm_failed:
                    recheck = score_hook(script_text, category=category)
                    if recheck is not None:
                        log_event("HOOK", f"Hook re-scored: {recheck['score']}/100 after rewrite")
                    else:
                        log_event("HOOK", f"Hook re-scoring returned None — skipped", "warn")
                else:
                    log_event("HOOK", f"LLM scoring unavailable — using rewrite without re-scoring", "warn")
            else:
                log_event("HOOK", f"Rewrite skipped (invalid output)", "warn")
        else:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — passed")

        script_text = _simplify_script(script_text, category, "shorts")

        try:
            from utils.brand_manager import record_hook_usage, HOOK_FORMULAS
            _sl = (script_text or "")[:200].lower()
            _dh = "question"
            if any(_sl.startswith(p) for p in ["imagine", "what if"]):
                _dh = "question"
            elif any(w in _sl for w in ["secretly", "nobody", "the truth", "why most"]):
                _dh = "bold_claim"
            elif any(c.isdigit() for c in _sl[:100]):
                _dh = "statistic"
            elif any(p in _sl for p in ["here's why", "the reason", "but here's"]):
                _dh = "curiosity_gap"
            elif any(p in _sl for p in ["stop", "frustrated", "annoyed", "tired of"]):
                _dh = "pain_point"
            record_hook_usage(video_id, topic, _dh, "shorts")
        except Exception:
            pass

        failed_step = "compliance_check"
        try:
            if not isinstance(script_text, str):
                script_text = str(script_text)
            safety = check_content_safety(script_text)
            if not isinstance(safety, dict):
                safety = {"is_safe": True, "issues": []}
            is_safe = safety.get("is_safe", True)
            issues = safety.get("issues", [])
            if not is_safe:
                log_event("COMPLIANCE", f"Content safety issues found: {len(issues)}", "warn")
                for issue in issues[:3]:
                    if isinstance(issue, dict):
                        log_event("COMPLIANCE", f"  [{issue.get('severity', '?')}] {issue.get('detail', '')[:100]}")
                if any(isinstance(i, dict) and i.get("severity") == "high" for i in issues):
                    if FORCE_PUBLISH:
                        log_event("COMPLIANCE", f"FORCE_PUBLISH overrides content safety block: {topic}", "warn")
                    else:
                        log_pipeline_error(video_id, "Blocked by content safety check", "compliance")
                        add_video_record(video_id, topic, "shorts", "blocked_compliance", category=category)
                        log_event("COMPLIANCE", f"BLOCKED: {topic} (content safety)")
                        update_pipeline_status(False)
                        return False
            platform_compliance = _check_all_platforms_compliance({"title": topic, "script": script_text}, ['youtube', 'tiktok', 'instagram', 'facebook'])
            if platform_compliance:
                for w in platform_compliance:
                    log_event("COMPLIANCE", f"Platform warning: {w[:100]}", "warn")
        except Exception as e:
            log_event("COMPLIANCE", f"Content safety check crashed: {e}", "error")

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

        if not _gate_check("Quality gate", quality["recommendation"] == "block", topic, video_id, "shorts", category):
            return False

        failed_step = "virality_analysis"
        try:
            raw = _execute_single_task(create_virality_analyst_crew, {"script": script_text, "title": topic, "category": category, "format_type": "shorts"}, script=script_text, title=topic, category=category, format_type="shorts")
            virality_result = _extract_json(raw)
            v_score = virality_result.get("overall_virality_score", 0)
            update_video_record(video_id, {"virality_prediction": virality_result})
            boost = _pipeline_tuning_cache.get("virality_boost", 0)
            threshold = get_virality_threshold("shorts") - boost
            if not _gate_check("Virality gate", v_score < threshold, topic, video_id, "shorts", category):
                return False
            else:
                log_event("VIRALITY", f"Virality score: {v_score}/100 (threshold: {threshold}) — approved")
        except Exception as e:
            log_event("VIRALITY", f"Virality analysis CRASHED: {e}", "error")
            log_pipeline_error(video_id, f"Virality analysis failed: {e}", "virality")
        save_checkpoint(video_id, "quality_scoring", {"quality_score": quality["overall_score"]})

        failed_step = "director_script_review"
        script_review = run_director_review("script", topic, category, "shorts", script_text)
        if not _gate_check("Director script review", script_review.get("decision") == "block", topic, video_id, "shorts", category):
            return False
        script_text = _rewrite_on_director_fix(script_review, topic, category, "shorts", script_text)

        failed_step = "storyboarding"
        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "shorts"})

        failed_step = "director_storyboard_review"
        sb_review = run_director_review("storyboard", topic, category, "shorts", script_text, str(storyboard))
        if not _gate_check("Director storyboard review", sb_review.get("decision") == "block", topic, video_id, "shorts", category):
            return False

        failed_step = "video_pipeline"
        with _track_step(video_id, "video_pipeline"):
            video_result = run_video_pipeline(script_text, str(storyboard), category, "shorts", video_id, SHORTS_MAX_DURATION)

        failed_step = "duration_check"
        dur_ok, dur_msg = _duration_ok(video_result.get("video_path", ""), "shorts")
        if not dur_ok:
            log_pipeline_error(video_id, f"Hard duration block: {dur_msg}", "duration_check")
            add_video_record(video_id, topic, "shorts", "failed", category=category)
            log_event("QUALITY", f"FAILED (hard duration block): {dur_msg}")
            update_pipeline_status(False)
            return False

        failed_step = "quality_check"
        qc_pass, qc_msg = verify_video_quality(video_result.get("video_path", ""), "shorts")
        if not qc_pass:
            if FORCE_PUBLISH:
                log_event("QUALITY", f"FORCE_PUBLISH overrides quality check: {qc_msg}", "warn")
            else:
                log_pipeline_error(video_id, f"Quality check failed: {qc_msg}", "quality_check")
                add_video_record(video_id, topic, "shorts", "failed", category=category)
                log_event("QUALITY", f"FAILED: {qc_msg}")
                update_pipeline_status(False)
                return False
        save_checkpoint(video_id, "video_pipeline", {"video_path": video_result.get("video_path", "")})

        failed_step = "review_gate"
        review_decision = apply_review_gate(video_id, topic, "shorts", script_text, quality, category)
        if not _gate_check("Review gate", review_decision == "block", topic, video_id, "shorts", category):
            return False

        failed_step = "director_final_review"
        final_review = run_director_review("final", topic, category, "shorts", script_text, str(storyboard))
        if not _gate_check("Director final review", final_review.get("decision") == "block", topic, video_id, "shorts", category):
            return False

        failed_step = "thumbnail"
        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail",
                                   create_thumbnail_crew, {"topic": topic, "fmt": "shorts"})
        thumbnail_text = str(thumbnail)
        thumb_result = generate_thumbnail_variants(
            topic, thumbnail_text, format_type="shorts")
        thumbnail_path = thumb_result.get("best") or thumb_result.get("variants", [None])[0]
        if not thumbnail_path:
            thumbnail_path = str(thumbnail)
            log_event("THUMBNAIL", "Using text-based thumbnail (image generation fallback)")
        else:
            log_event("THUMBNAIL", f"Generated {thumb_result['count']} thumbnail variants, selected: {thumbnail_path}")

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
        from utils.platform_captions import sanitize_description
        full_desc = sanitize_description(full_desc)
        desc_result["full_description"] = full_desc
        try:
            seo_tags = get_optimized_tags(category, "shorts", topic)
            seo_score = score_description_seo(full_desc)
            if seo_score["missing"]:
                log_event("SEO", f"Description missing: {', '.join(seo_score['missing'])}")
            desc_result["tags"] = seo_tags
        except Exception:
            pass

        failed_step = "title_optimization"
        title_variants = []
        try:
            raw = _execute_single_task(create_title_optimizer_crew, {"topic": topic, "category": category, "format_type": "shorts"}, topic=topic, category=category, format_type="shorts")
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

        failed_step = "thumbnail_video_frame"
        if video_result.get("video_path") and thumbnail_path:
            video_thumb = pick_best_thumbnail(thumbnail_path, video_result.get("video_path", ""), topic, format_type="shorts")
            if video_thumb:
                thumbnail_path = video_thumb

        failed_step = "consistency_audit"
        try:
            from utils.consistency_checker import run_consistency_audit, get_audit_summary
            audit = run_consistency_audit(topic, script_text, "shorts", category, video_id)
            log_event("CONSISTENCY", f"Pre-publish audit: {get_audit_summary(audit)}")
            if audit.get("warnings", 0) > 0:
                for issue in audit.get("issues", [])[:3]:
                    if issue.get("severity") == "warning":
                        log_event("CONSISTENCY", f"  ⚠ {issue.get('detail', '')[:120]}")
        except Exception as e:
            log_event("CONSISTENCY", f"Audit skipped: {e}", "debug")

        failed_step = "publishing"
        with _track_step(video_id, "publishing"):
            platforms_to_publish = _platforms_to_publish()
            best_title = _pick_best_title(title_variants, topic, category)
            publish_result = multi_platform_publish(
                video_id=video_id,
                title=best_title,
                description=desc_result.get("full_description", ""),
                video_path=video_result.get("video_path", ""),
                thumbnail_path=thumbnail_path,
                format_type="shorts",
                platforms=platforms_to_publish,
                publish_at=publish_at,
                category=category,
                subtitle_path=video_result.get("subtitle_path"),
                tags=desc_result.get("tags"),
            )
        publish_status = "scheduled" if publish_at else "Published"
        _yt = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        log_event(
            "PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms" + (f" | YouTube: {_yt}" if _yt else ""))  # noqa: E501
        save_checkpoint(video_id, "publishing", {"publish_count": publish_result.get("success_count", 0)})

        if publish_result.get("success_count", 0) > 0 and ENABLE_COMPANION_PAGES:
            try:
                from utils.companion_page import generate_companion_page, upload_companion_page
                from utils.r2_storage import upload_thumbnail as r2_upload_thumb
                thumb_r2_url = r2_upload_thumb(thumbnail_path, video_id) if thumbnail_path else ""
                yt_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
                chaps = video_result.get("chapters", [])
                tags = [category] + [w for w in topic.split() if len(w) > 3][:8]
                page_path = generate_companion_page(
                    video_id=video_id, title=topic,
                    description=desc_result.get("full_description", ""),
                    category=category, tags=tags, thumbnail_url=thumb_r2_url,
                    video_url=yt_url, format_type="shorts", chapters=chaps,
                )
                if page_path:
                    companion_url = upload_companion_page(page_path, video_id)
                    log_event("COMPANION", f"Companion page: {companion_url}")
            except Exception as e:
                log_event("COMPANION", f"Companion page skipped: {e}", "debug")

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result.get("video_path", ""),
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
                if ENABLE_MULTI_LANG_DUB:
                    log_event("PIPELINE", "Generating dubbed audio for multi-language")
                    try:
                        dubs = _run_async(dub_all_languages(translations, video_id))
                        if dubs:
                            update_video_record(video_id, {"dubs": {k: {"duration": v["duration"]} for k, v in dubs.items() if v["success"]}})
                            register_dub_cleanup_func(video_id)
                            output_video_path = (video_result or {}).get("video_path", "")
                            for lang_code, dub_result in dubs.items():
                                if dub_result["success"] and output_video_path and os.path.exists(output_video_path):
                                    dub_video_path = os.path.join(os.path.dirname(output_video_path), f"{video_id}_{lang_code}.mp4")
                                    from utils.translate import mux_dubbed_video
                                    if mux_dubbed_video(output_video_path, dub_result["audio_path"], dub_video_path):
                                        log_event("DUB", f"Muxed {lang_code} version -> {dub_video_path}")
                                        try:
                                            from utils.multi_platform_publisher import upload_to_platform
                                            upload_to_platform(dub_video_path, {
                                                "title": translations[lang_code].get("title", f"{topic} [{lang_code.upper()}]"),
                                                "description": translations[lang_code].get("description_snippet", ""),
                                                "language": lang_code,
                                                "format": "short",
                                            })
                                            log_event("DUB", f"Published {lang_code} version")
                                        except Exception as ue:
                                            log_event("DUB", f"Upload {lang_code} failed: {ue}")
                    except Exception as e:
                        log_event("DUB", f"Failed to generate dubs: {e}")

        failed_step = "title_tester"
        youtube_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        youtube_id = None
        if youtube_url and 'watch?v=' in youtube_url:
            youtube_id = youtube_url.split('watch?v=')[-1].split('&')[0]
        if youtube_id and title_variants:
            try:
                from utils.youtube_upload import update_youtube_video_title
                tester = TitleTester(youtube_api_update_func=update_youtube_video_title)
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

        try:
            from utils.knowledge_integration import record_video_knowledge
            record_video_knowledge(video_id, topic, category, difficulty="intermediate")
            log_event("KNOWLEDGE", f"Registered {topic} in knowledge graph")
        except Exception as e:
            log_event("KNOWLEDGE", f"Knowledge registration skipped: {e}", "debug")

        failed_step = "pinned_comment"
        if youtube_id:
            try:
                from utils.youtube_upload import get_youtube_service as _get_yt_service
                from utils.engagement_manager import post_pinned_comment, auto_reply_to_comments, build_pinned_comment
                yt_svc = _get_yt_service()
                if yt_svc:
                    comment_text = build_pinned_comment(topic, format_type="shorts")
                    post_pinned_comment(youtube_id, comment_text, yt_svc)
                    auto_reply_to_comments(youtube_id, yt_svc)
                    log_event("COMMENT", f"Pinned comment + auto-reply set up for {youtube_id}")
                    try:
                        from utils.comment_analyzer import analyze_video_comments, flag_negative_comments
                        sentiment = analyze_video_comments(youtube_id, yt_svc, max_comments=30)
                        if sentiment["total"] > 0:
                            log_event("SENTIMENT", f"Comments: {sentiment['total']} total, {sentiment['sentiments']['negative'] + sentiment['sentiments']['toxic']} negative")
                        flagged = flag_negative_comments(youtube_id, yt_svc)
                        if flagged:
                            log_event("SENTIMENT", f"Negative comment alert: {flagged['message']}", "warn")
                    except Exception as se:
                        log_event("SENTIMENT", f"Sentiment analysis skipped: {se}", "debug")
            except Exception as e:
                log_event("COMMENT", f"Pinned comment skipped: {e}", "debug")
        try:
            track_pillar_video(category)
        except Exception:
            pass
        try:
            from utils.hook_engine import detect_hook_formula
            from utils.hook_tester import record_hook_result
            hook_formula = detect_hook_formula(script_text)
            record_hook_result(video_id, category, hook_formula)
            log_event("HOOK", f"Recorded hook formula: {hook_formula} for {category}")
        except Exception as e:
            log_event("HOOK", f"Hook recording skipped: {e}", "debug")

        failed_step = "finalizing"
        short_status = "scheduled" if publish_at else ("uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed")
        _news_updates = {"news_source": news_article.get("source")} if news_article and news_article.get("source") else {}
        update_video_record(video_id, {
            "status": short_status,
            "publish_success_count": publish_result.get("success_count", 0),
            "youtube_url": youtube_url,
            "publish_at": publish_at,
            **_news_updates,
        })
        if short_status == "upload_failed":
            log_event("PUBLISH", f"Short video rendered but ALL platform uploads failed", "error")
        log_event("PIPELINE", f"SHORT video generation SUCCESS: {topic} ({short_status})")
        update_pipeline_status(False)
        clear_checkpoint(video_id)
        _elapsed = time.perf_counter() - _start_time
        _track_pipeline_duration(video_id, "shorts", topic, _elapsed, success=True)
        log_event("TIMING", f"Pipeline total: {_elapsed:.1f}s")
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
        if sentry_sdk:
            sentry_sdk.capture_exception(e)
        clear_checkpoint(video_id)
        _elapsed = time.perf_counter() - _start_time
        _track_pipeline_duration(video_id, "shorts", topic, _elapsed, success=False)
        log_event("TIMING", f"Pipeline total: {_elapsed:.1f}s (FAILED)")
        log_event("CLEANUP", "Intermediate files cleaned by scheduled daily_cleanup_job")
        try:
            from bot.notifications import send_error_notification
            send_error_notification(error_msg, f"short_video/{failed_step}: {topic}")
        except Exception:
            pass
        return False


def generate_long_video(topic: str, category: str, video_id: str, publish_at: str = None, news_article: dict = None):
    from utils.scene_schema import normalize_category
    category = normalize_category(category)
    _start_time = time.perf_counter()
    _apply_pipeline_tuning()
    if sentry_sdk:
        sentry_sdk.set_tag("video_id", video_id)
        sentry_sdk.set_tag("format", "long")
        sentry_sdk.set_tag("category", category)
    update_pipeline_status(True, topic)
    add_video_record(video_id, topic, "long", "generating", category=category)
    log_event("PIPELINE", f"Starting LONG video generation: {topic}")
    if sentry_sdk:
        sentry_sdk.add_breadcrumb(category="pipeline", message=f"Starting long: {topic}", level="info")

    cp = load_checkpoint(video_id)
    if cp:
        log_event("CHECKPOINT", f"Resuming from step: {cp.get('step', 'unknown')}")

    failed_step = "setup"
    try:
        failed_step = "scriptwriting"
        with _track_step(video_id, "scriptwriting"):
            opt_injection = get_optimization_prompt_injection()

            from utils.knowledge_integration import inject_knowledge_context
            knowledge_ctx = inject_knowledge_context(topic, category)
            series_ctx = ""
            try:
                _series = pick_series_for_category(category)
                if _series:
                    next_part = _series.get("current_part", 0) + 1
                    continuity = build_continuity_text(_series, next_part)
                    if continuity:
                        series_ctx = f"Series context: {continuity}"
            except Exception:
                pass

            trend_ctx = ""
            try:
                from utils.trend_discovery import discover_trends as _dt
                _tr = _dt()
                if _tr:
                    _hooks = [t.get("title", "") for t in _tr[:5] if t.get("title")]
                    trend_ctx = "Current trending hooks for viral optimization:\n" + "\n".join(f"- {h}" for h in _hooks)
            except Exception:
                trend_ctx = ""

            from utils.analytics_feedback import get_top_performing_topics
            _topics_ctx = ""
            try:
                _best_topics = get_top_performing_topics(3)
                if _best_topics:
                    _topics_ctx = "Topics that performed well recently:\n" + "\n".join(
                        f"- {t['topic']}: {t['avg_views']} avg views" for t in _best_topics
                    )
            except Exception:
                pass

            _retention_ctx = ""
            try:
                from utils.retention_analyzer import get_insights
                ri = get_insights(category)
                if ri and ri.get("sample_size", 0) > 0:
                    drops = ", ".join(f"{t} ({mag})" for t, mag in ri.get("common_drop_points", [])) or "none"
                    _retention_ctx = (
                        f"Audience retention feedback for this category (sample {ri.get('sample_size')}): "
                        f"hook retention avg {ri.get('avg_hook_retention', 0)}, overall avg "
                        f"{ri.get('avg_overall_retention', 0)}. Viewers drop off around: {drops}. "
                        "Tighten the hook if low, and avoid padding or re-explaining right before "
                        "the drop points to hold viewers to the end."
                    )
            except Exception:
                _retention_ctx = ""

            extra_parts = [p for p in [knowledge_ctx, series_ctx, trend_ctx, opt_injection, _topics_ctx, _retention_ctx] if p]
            # News videos: replace tech knowledge/series/trend context with the actual verified
            # news article so the script is an accurate, sourced explainer (never invented).
            if news_article:
                _na = news_article
                news_ctx = (
                    f"VERIFIED NEWS ARTICLE to explain:\n"
                    f"- Headline: {_na.get('title','')}\n"
                    f"- Source: {_na.get('source','')} (verified publisher)\n"
                    f"- Article link: {_na.get('link','')}\n"
                    f"- Language: {_na.get('lang','en')}\n"
                    f"- Summary: {_na.get('description','')}\n"
                    f"Write an educational explainer that reports the news accurately from the "
                    f"source above, gives context, and explains why it matters. Do NOT invent "
                    f"facts not in the article. Cite the source in the description at the end."
                )
                extra_parts = [news_ctx]
            try:
                from utils.hook_tester import suggest_hook_formula, get_hook_stats
                best_hook = suggest_hook_formula(category)
                hook_stats = get_hook_stats(category)
                best_stat = hook_stats.get(best_hook, {})
                if best_stat.get("count", 0) > 0:
                    extra_parts.append(f"Hook recommendation: Use '{best_hook}' hook for {category} — avg {best_stat['avg_views']} views, {best_stat['avg_retention']:.0%} retention across {best_stat['count']} videos. Other formulas: " + ", ".join(f"{f}({s['avg_views']}v)" for f, s in hook_stats.items() if s.get("count", 0) > 0 and f != best_hook))
            except Exception:
                pass
            # Pre-writing virality guidance
            try:
                from crew.virality_analyst import get_prewriting_guidance
                extra_parts.append(get_prewriting_guidance(topic, category, "long"))
            except Exception:
                pass
            extra_context = "\n".join(extra_parts) if extra_parts else ""

            _tier_long = os.environ.get("TIER", "")
            if _tier_long == "documentary":
                _doc_ctx = (
                    "DOCUMENTARY TIER — This is a documentary-style video, NOT a tutorial or lesson.\n"
                    "Write for a general audience. Use narrative storytelling, historical progression, "
                    "real-world case studies, expert quotes, and cinematic pacing.\n"
                    "Scenes: 20-40. Duration: 20-40 minutes. Use [STOCK] for archival/b-roll, "
                    "[BLENDER] for 3D photorealistic visualizations and renders. "
                    "Include scene-setting descriptions and atmospheric context.\n"
                    "Structure: Hook → Historical/Rationale Context → Deep Dive → Case Studies → Future Outlook → Credits."
                )
                extra_context = (extra_context + "\n\n" + _doc_ctx) if extra_context else _doc_ctx

            script_kwargs = {"topic": topic, "category": category, "fmt": "long", "max_duration": _deep_lesson_dur(category)}
            if news_article:
                # ponytail: news longs came out ~15s because the LLM wrote a short
                # explainer. Make the 3+ min floor explicit in the prompt too.
                script_kwargs["extra_context"] = (
                    (extra_context + "\n\n") if extra_context else ""
                ) + "LENGTH REQUIREMENT: LONG-FORM news explainer. Write AT LEAST 450 words of narration (~3+ minutes) across 12-18 scenes. Expand with background, key players, implications."
            elif extra_context:
                script_kwargs["extra_context"] = extra_context
            is_deep = True  # ponytail: all long-form gets deep lesson treatment for Sample 6 quality
            crew_fn = create_deep_lesson_crew
            label = "Deep Lesson Scriptwriter"
            dl_kwargs = {k: v for k, v in script_kwargs.items() if k != "fmt"}
            script = run_agent_step("scriptwriter", label, f"Writing script for: {topic}", crew_fn, dl_kwargs, timeout_minutes=45 if is_deep else 30)
            script_text = str(script)
            save_checkpoint(video_id, "scriptwriting", {"script_preview": script_text[:200]})

            from utils.llm_helper import reset_fallback
            reset_fallback()

        failed_step = "hook_scoring"
        hook_score_result = score_hook(script_text, category=category)
        if hook_score_result is None:
            hook_score_result = {"score": 0, "hook_score": 0, "approved": False, "weaknesses": ["could not evaluate with llm"], "suggested_alternatives": []}
        _hook_llm_failed = "could not evaluate with llm" in str(hook_score_result.get("weaknesses", [])).lower()
        if hook_score_result["score"] < 60:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — enforcing rewrite")
            new_script = enforce_rewrite(script_text, category=category)
            if new_script != script_text:
                script_text = new_script
                if not _hook_llm_failed:
                    recheck = score_hook(script_text, category=category)
                    if recheck is not None:
                        log_event("HOOK", f"Hook re-scored: {recheck['score']}/100 after rewrite")
                    else:
                        log_event("HOOK", f"Hook re-scoring returned None — skipped", "warn")
                else:
                    log_event("HOOK", f"LLM scoring unavailable — using rewrite without re-scoring", "warn")
            else:
                log_event("HOOK", f"Rewrite skipped (invalid output)", "warn")
        else:
            log_event("HOOK", f"Hook score: {hook_score_result['score']}/100 — passed")

        script_text = _simplify_script(script_text, category, "long")

        _min_words = NEWS_LONG_MIN_NARRATION_WORDS if news_article else LONG_MIN_NARRATION_WORDS
        if _count_script_words(script_text) < _min_words:
            # ponytail: LLM sometimes returns a one-paragraph "explainer" and the
            # whole pipeline happily renders 15s of it. Retry ONCE with a firmer
            # floor before trusting it; news longs must be >= NEWS_LONG_MIN_WORDS.
            log_event("SCRIPT", f"Only {_count_script_words(script_text)} words (need {_min_words}) — rewriting longer")
            dl_kwargs["extra_context"] = (
                (dl_kwargs.get("extra_context", "") + "\n\n") if dl_kwargs.get("extra_context") else ""
            ) + f"The previous draft was too short. Write AT LEAST {_min_words} words of narration with 12-18 scenes. Do not summarize — go deep."
            _retry = run_agent_step("scriptwriter", "Deep Lesson Scriptwriter (longer)", f"Rewriting longer script for: {topic}", create_deep_lesson_crew, dl_kwargs, timeout_minutes=45)
            if _retry and _count_script_words(str(_retry)) > _count_script_words(script_text):
                script_text = _simplify_script(str(_retry), category, "long")
            if news_article and _count_script_words(script_text) < _min_words:
                raise RuntimeError(f"news long script too short ({_count_script_words(script_text)} < {_min_words} words) — re-queue")

        try:
            from utils.brand_manager import record_hook_usage
            _sl = (script_text or "")[:200].lower()
            _dh = "question"
            if any(_sl.startswith(p) for p in ["imagine", "what if"]):
                _dh = "question"
            elif any(w in _sl for w in ["secretly", "nobody", "the truth", "why most"]):
                _dh = "bold_claim"
            elif any(c.isdigit() for c in _sl[:100]):
                _dh = "statistic"
            elif any(p in _sl for p in ["here's why", "the reason", "but here's"]):
                _dh = "curiosity_gap"
            elif any(p in _sl for p in ["stop", "frustrated", "annoyed", "tired of"]):
                _dh = "pain_point"
            record_hook_usage(video_id, topic, _dh, "long")
        except Exception:
            pass

        failed_step = "compliance_check"
        try:
            if not isinstance(script_text, str):
                script_text = str(script_text)
            safety = check_content_safety(script_text)
            if not isinstance(safety, dict):
                safety = {"is_safe": True, "issues": []}
            is_safe = safety.get("is_safe", True)
            issues = safety.get("issues", [])
            if not is_safe:
                log_event("COMPLIANCE", f"Content safety issues found: {len(issues)}", "warn")
                for issue in issues[:3]:
                    if isinstance(issue, dict):
                        log_event("COMPLIANCE", f"  [{issue.get('severity', '?')}] {issue.get('detail', '')[:100]}")
                if any(isinstance(i, dict) and i.get("severity") == "high" for i in issues):
                    if FORCE_PUBLISH:
                        log_event("COMPLIANCE", f"FORCE_PUBLISH overrides content safety block: {topic}", "warn")
                    else:
                        log_pipeline_error(video_id, "Blocked by content safety check", "compliance")
                        add_video_record(video_id, topic, "long", "blocked_compliance", category=category)
                        log_event("COMPLIANCE", f"BLOCKED: {topic} (content safety)")
                        update_pipeline_status(False)
                        return False
            platform_compliance = _check_all_platforms_compliance({"title": topic, "script": script_text}, ['youtube', 'facebook'])
            if platform_compliance:
                for w in platform_compliance:
                    log_event("COMPLIANCE", f"Platform warning: {w[:100]}", "warn")
        except Exception as e:
            log_event("COMPLIANCE", f"Content safety check crashed: {e}", "error")

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

        if not _gate_check("Quality gate", quality["recommendation"] == "block", topic, video_id, "long", category):
            return False

        failed_step = "virality_analysis"
        try:
            raw = _execute_single_task(create_virality_analyst_crew, {"script": script_text, "title": topic, "category": category, "format_type": "long"}, script=script_text, title=topic, category=category, format_type="long")
            virality_result = _extract_json(raw)
            v_score = virality_result.get("overall_virality_score", 0)
            update_video_record(video_id, {"virality_prediction": virality_result})
            boost = _pipeline_tuning_cache.get("virality_boost", 0)
            threshold = get_virality_threshold("long") - boost
            if not _gate_check("Virality gate", v_score < threshold, topic, video_id, "long", category):
                return False
            else:
                log_event("VIRALITY", f"Virality score: {v_score}/100 (threshold: {threshold}) — approved")
        except Exception as e:
            log_event("VIRALITY", f"Virality analysis CRASHED: {e}", "error")
            log_pipeline_error(video_id, f"Virality analysis failed: {e}", "virality")
        save_checkpoint(video_id, "quality_scoring", {"quality_score": quality["overall_score"]})

        failed_step = "director_script_review"
        script_review = run_director_review("script", topic, category, "long", script_text)
        if not _gate_check("Director script review", script_review.get("decision") == "block", topic, video_id, "long", category):
            return False
        script_text = _rewrite_on_director_fix(script_review, topic, category, "long", script_text)

        failed_step = "storyboarding"
        storyboard = run_agent_step("storyboard", "Storyboard", "Generating storyboard",
                                    create_storyboard_crew, {"script": script_text, "format_type": "long", "is_deep": True})

        failed_step = "director_storyboard_review"
        sb_review = run_director_review("storyboard", topic, category, "long", script_text, str(storyboard))
        if not _gate_check("Director storyboard review", sb_review.get("decision") == "block", topic, video_id, "long", category):
            return False

        failed_step = "video_pipeline"
        with _track_step(video_id, "video_pipeline"):
            video_result = run_video_pipeline(script_text, str(storyboard), category, "long", video_id, _deep_lesson_dur(category))

        failed_step = "duration_check"
        dur_ok, dur_msg = _duration_ok(video_result.get("video_path", ""), "long")
        if not dur_ok:
            log_pipeline_error(video_id, f"Hard duration block: {dur_msg}", "duration_check")
            add_video_record(video_id, topic, "long", "failed", category=category)
            log_event("QUALITY", f"FAILED (hard duration block): {dur_msg}")
            update_pipeline_status(False)
            return False

        failed_step = "quality_check"
        qc_pass, qc_msg = verify_video_quality(video_result.get("video_path", ""), "long")
        if not qc_pass:
            if FORCE_PUBLISH:
                log_event("QUALITY", f"FORCE_PUBLISH overrides quality check: {qc_msg}", "warn")
            else:
                log_pipeline_error(video_id, f"Quality check failed: {qc_msg}", "quality_check")
                add_video_record(video_id, topic, "long", "failed", category=category)
                log_event("QUALITY", f"FAILED: {qc_msg}")
                update_pipeline_status(False)
                return False
        save_checkpoint(video_id, "video_pipeline", {"video_path": video_result.get("video_path", "")})

        failed_step = "review_gate"
        review_decision = apply_review_gate(video_id, topic, "long", script_text, quality, category)
        if not _gate_check("Review gate", review_decision == "block", topic, video_id, "long", category):
            return False

        failed_step = "director_final_review"
        final_review = run_director_review("final", topic, category, "long", script_text, str(storyboard))
        if not _gate_check("Director final review", final_review.get("decision") == "block", topic, video_id, "long", category):
            return False

        failed_step = "thumbnail"
        thumbnail = run_agent_step("thumbnail", "Thumbnail Creator", "Creating thumbnail",
                                   create_thumbnail_crew, {"topic": topic, "fmt": "long"})
        thumbnail_text = str(thumbnail)
        thumb_result = generate_thumbnail_variants(
            topic, thumbnail_text, format_type="long")
        thumbnail_path = thumb_result.get("best") or thumb_result.get("variants", [None])[0]
        if not thumbnail_path:
            thumbnail_path = str(thumbnail)
            log_event("THUMBNAIL", "Using text-based thumbnail (image generation fallback)")
        else:
            log_event("THUMBNAIL", f"Generated {thumb_result['count']} thumbnail variants, selected: {thumbnail_path}")

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
        from utils.platform_captions import sanitize_description
        full_desc = sanitize_description(full_desc)
        desc_result["full_description"] = full_desc
        try:
            seo_tags = get_optimized_tags(category, "long", topic)
            seo_score = score_description_seo(full_desc)
            if seo_score["missing"]:
                log_event("SEO", f"Description missing: {', '.join(seo_score['missing'])}")
            desc_result["tags"] = seo_tags
        except Exception:
            pass

        failed_step = "title_optimization"
        title_variants = []
        try:
            raw = _execute_single_task(create_title_optimizer_crew, {"topic": topic, "category": category, "format_type": "long"}, topic=topic, category=category, format_type="long")
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

        failed_step = "thumbnail_video_frame"
        if video_result.get("video_path") and thumbnail_path:
            video_thumb = pick_best_thumbnail(thumbnail_path, video_result.get("video_path", ""), topic, format_type="long")
            if video_thumb:
                thumbnail_path = video_thumb

        failed_step = "consistency_audit"
        try:
            from utils.consistency_checker import run_consistency_audit, get_audit_summary
            audit = run_consistency_audit(topic, script_text, "long", category, video_id)
            log_event("CONSISTENCY", f"Pre-publish audit: {get_audit_summary(audit)}")
            if audit.get("warnings", 0) > 0:
                for issue in audit.get("issues", [])[:3]:
                    if issue.get("severity") == "warning":
                        log_event("CONSISTENCY", f"  ⚠ {issue.get('detail', '')[:120]}")
        except Exception as e:
            log_event("CONSISTENCY", f"Audit skipped: {e}", "debug")

        failed_step = "publishing"
        with _track_step(video_id, "publishing"):
            platforms_to_publish = _platforms_to_publish()
            best_title = _pick_best_title(title_variants, topic, category)
            publish_result = multi_platform_publish(
                video_id=video_id,
                title=best_title,
                description=desc_result.get("full_description", ""),
                video_path=video_result.get("video_path", ""),
                thumbnail_path=thumbnail_path,
                format_type="long",
                platforms=platforms_to_publish,
                publish_at=publish_at,
                category=category,
                cleanup=False,
                subtitle_path=video_result.get("subtitle_path"),
                tags=desc_result.get("tags"),
            )
        publish_status = "scheduled" if publish_at else "Published"
        _yt = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        log_event(
            "PUBLISH", f"{publish_status} to {publish_result['success_count']}/{publish_result['total_count']} platforms" + (f" | YouTube: {_yt}" if _yt else ""))  # noqa: E501
        save_checkpoint(video_id, "publishing", {"publish_count": publish_result.get("success_count", 0)})

        if publish_result.get("success_count", 0) > 0 and ENABLE_COMPANION_PAGES:
            try:
                from utils.companion_page import generate_companion_page, upload_companion_page
                from utils.r2_storage import upload_thumbnail as r2_upload_thumb
                thumb_r2_url = r2_upload_thumb(thumbnail_path, video_id) if thumbnail_path else ""
                yt_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
                chaps = video_result.get("chapters", [])
                tags = [category] + [w for w in topic.split() if len(w) > 3][:8]
                page_path = generate_companion_page(
                    video_id=video_id, title=topic,
                    description=desc_result.get("full_description", ""),
                    category=category, tags=tags, thumbnail_url=thumb_r2_url,
                    video_url=yt_url, format_type="long", chapters=chaps,
                )
                if page_path:
                    companion_url = upload_companion_page(page_path, video_id)
                    log_event("COMPANION", f"Companion page: {companion_url}")
            except Exception as e:
                log_event("COMPANION", f"Companion page skipped: {e}", "debug")

        if publish_result.get("success_count", 0) > 0:
            log_event("CLEANUP", "Cleaning up intermediate files after successful upload")
            from utils.cleanup_service import cleanup_after_upload
            cleanup_after_upload(
                video_path=video_result.get("video_path", ""),
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
                if ENABLE_MULTI_LANG_DUB:
                    log_event("PIPELINE", "Generating dubbed audio for multi-language")
                    try:
                        dubs = _run_async(dub_all_languages(translations, video_id))
                        if dubs:
                            update_video_record(video_id, {"dubs": {k: {"duration": v["duration"]} for k, v in dubs.items() if v["success"]}})
                            register_dub_cleanup_func(video_id)
                            output_video_path = (video_result or {}).get("video_path", "")
                            for lang_code, dub_result in dubs.items():
                                if dub_result["success"] and output_video_path and os.path.exists(output_video_path):
                                    dub_video_path = os.path.join(os.path.dirname(output_video_path), f"{video_id}_{lang_code}.mp4")
                                    from utils.translate import mux_dubbed_video
                                    if mux_dubbed_video(output_video_path, dub_result["audio_path"], dub_video_path):
                                        log_event("DUB", f"Muxed {lang_code} version -> {dub_video_path}")
                                        try:
                                            from utils.multi_platform_publisher import upload_to_platform
                                            upload_to_platform(dub_video_path, {
                                                "title": translations[lang_code].get("title", f"{topic} [{lang_code.upper()}]"),
                                                "description": translations[lang_code].get("description_snippet", ""),
                                                "language": lang_code,
                                                "format": "long",
                                            })
                                            log_event("DUB", f"Published {lang_code} version")
                                        except Exception as ue:
                                            log_event("DUB", f"Upload {lang_code} failed: {ue}")
                    except Exception as e:
                        log_event("DUB", f"Failed to generate dubs: {e}")

        failed_step = "title_tester"
        youtube_url = publish_result.get('platforms', {}).get('youtube', {}).get('video_url', '')
        youtube_id = None
        if youtube_url and 'watch?v=' in youtube_url:
            youtube_id = youtube_url.split('watch?v=')[-1].split('&')[0]
        if youtube_id and title_variants:
            try:
                from utils.youtube_upload import update_youtube_video_title
                tester = TitleTester(youtube_api_update_func=update_youtube_video_title)
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

        try:
            from utils.knowledge_integration import record_video_knowledge
            record_video_knowledge(video_id, topic, category, difficulty="intermediate")
            log_event("KNOWLEDGE", f"Registered {topic} in knowledge graph")
        except Exception as e:
            log_event("KNOWLEDGE", f"Knowledge registration skipped: {e}", "debug")

        failed_step = "pinned_comment"
        if youtube_id:
            try:
                from utils.youtube_upload import get_youtube_service as _get_yt_service
                from utils.engagement_manager import post_pinned_comment, auto_reply_to_comments, build_pinned_comment
                yt_svc = _get_yt_service()
                if yt_svc:
                    comment_text = build_pinned_comment(topic, format_type="long")
                    post_pinned_comment(youtube_id, comment_text, yt_svc)
                    auto_reply_to_comments(youtube_id, yt_svc)
                    log_event("COMMENT", f"Pinned comment + auto-reply set up for {youtube_id}")
                    try:
                        from utils.comment_analyzer import analyze_video_comments, flag_negative_comments
                        sentiment = analyze_video_comments(youtube_id, yt_svc, max_comments=30)
                        if sentiment["total"] > 0:
                            log_event("SENTIMENT", f"Comments: {sentiment['total']} total, {sentiment['sentiments']['negative'] + sentiment['sentiments']['toxic']} negative")
                        flagged = flag_negative_comments(youtube_id, yt_svc)
                        if flagged:
                            log_event("SENTIMENT", f"Negative comment alert: {flagged['message']}", "warn")
                    except Exception as se:
                        log_event("SENTIMENT", f"Sentiment analysis skipped: {se}", "debug")
            except Exception as e:
                log_event("COMMENT", f"Pinned comment skipped: {e}", "debug")
        try:
            track_pillar_video(category)
        except Exception:
            pass
        try:
            from utils.hook_engine import detect_hook_formula
            from utils.hook_tester import record_hook_result
            hook_formula = detect_hook_formula(script_text)
            record_hook_result(video_id, category, hook_formula)
            log_event("HOOK", f"Recorded hook formula: {hook_formula} for {category}")
        except Exception as e:
            log_event("HOOK", f"Hook recording skipped: {e}", "debug")

        failed_step = "finalizing"
        final_status = "uploaded" if (youtube_url or publish_result.get("success_count", 0) > 0) else "upload_failed"
        _news_updates = {"news_source": news_article.get("source")} if news_article and news_article.get("source") else {}
        update_video_record(video_id, {
            "script": script_text,
            "subtitle_path": video_result.get("subtitle_path"),
            "chapters": video_result.get("chapters"),
            "is_above_8min": video_result.get("duration", 0) >= 480,
            "status": final_status,
            "publish_success_count": publish_result.get("success_count", 0),
            "youtube_url": youtube_url,
            "publish_at": publish_at,
            **_news_updates,
        })

        if final_status == "uploaded":
            add_video_record(video_id, topic, "long", "uploaded", category=category)
        else:
            add_video_record(video_id, topic, "long", "upload_failed", category=category)
            log_event("PUBLISH", f"Long video rendered but ALL platform uploads failed — status={final_status}", "error")
        log_event("PIPELINE", f"LONG video generation SUCCESS: {topic} ({final_status})")
        update_pipeline_status(False)
        clear_checkpoint(video_id)
        _elapsed = time.perf_counter() - _start_time
        _track_pipeline_duration(video_id, "long", topic, _elapsed, success=True)
        log_event("TIMING", f"Pipeline total: {_elapsed:.1f}s")
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
        if sentry_sdk:
            sentry_sdk.capture_exception(e)
        clear_checkpoint(video_id)
        _elapsed = time.perf_counter() - _start_time
        _track_pipeline_duration(video_id, "long", topic, _elapsed, success=False)
        log_event("TIMING", f"Pipeline total: {_elapsed:.1f}s (FAILED)")
        log_event("CLEANUP", "Intermediate files cleaned by scheduled daily_cleanup_job")
        try:
            from bot.notifications import send_error_notification
            send_error_notification(error_msg, f"long_video/{failed_step}: {topic}")
        except Exception:
            pass
        return False


def _add_days(dt, n: int):
    """Return dt advanced by n days, safe across month/month-end boundaries
    (ponytail: replace(day=+1) overflows on 28/29/30/31 -> ValueError)."""
    return dt + timedelta(days=n)


def _platforms_to_publish() -> list:
    """Target platforms for video publishing.

    ponytail: IG/FB/TikTok are disabled pending a re-plan (Meta app deleted).
    Read a comma list from PLATFORMS_TO_PUBLISH (default 'youtube')."""
    raw = os.getenv("PLATFORMS_TO_PUBLISH", "youtube")
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _next_schedule_time(slot) -> str:
    """Next occurrence of a (hour, minute) UTC slot (int hour allowed for compat)."""
    hour, minute = (slot, 0) if isinstance(slot, int) else (slot[0], slot[1])
    now = datetime.utcnow()
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled <= now:
        scheduled = _add_days(scheduled, 1)
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
    long_per_day = int(os.getenv("SCHEDULE_LONG_PER_DAY", 1))

    log_event("SCHEDULER", "Generating content plan via scheduler planner")
    try:
        opt_injection = get_optimization_prompt_injection()
        from utils.analytics_feedback import get_pipeline_tuning, get_top_performing_topics
        pipeline_tuning = get_pipeline_tuning()
        if pipeline_tuning and pipeline_tuning.get("preferred_category"):
            tuning_ctx = (
                f"Pipeline tuning: preferred category '{pipeline_tuning['preferred_category']}', "
                f"virality boost {pipeline_tuning['virality_boost']}%, "
                f"voice rate {pipeline_tuning['voice_rate_adjust']}"
            )
            top_topics = get_top_performing_topics(3)
            if top_topics:
                tuning_ctx += "\nTop performing topics:\n" + "\n".join(
                    f"- {t['topic']}: {t['avg_views']} avg views" for t in top_topics
                )
            opt_injection = (opt_injection + "\n" + tuning_ctx) if opt_injection else tuning_ctx
        from utils.knowledge_integration import get_coverage_context
        coverage_ctx = get_coverage_context()
        pillar_ctx = ""
        try:
            from utils.pillar_manager import generate_pillar_context
            pillar_ctx = generate_pillar_context()
        except Exception:
            pass
        next_pillar = suggest_next_pillar()
        if next_pillar:
            pillar_ctx += f"\nSuggested next pillar to focus on: {next_pillar['name']}"
        combined_ctx = "\n".join(p for p in [opt_injection, coverage_ctx, pillar_ctx] if p)
        # Inject trending topics from trend engine
        try:
            from utils.trend_engine import get_daily_digest
            digest = get_daily_digest()
            if digest:
                combined_ctx += "\n\nTrending topics right now:\n" + "\n".join(f"- {d['title']} ({d['category']}, {d['source']})" for d in digest[:5])
        except Exception:
            pass
        # Inject topic scorer recommendation
        try:
            from utils.topic_scorer import get_smart_category_slot
            best_cat = get_smart_category_slot()
            combined_ctx += f"\n\nBest category to produce next: {best_cat} (based on CPM, freshness, balance)"
        except Exception:
            pass
        plan = generate_content_plan(extra_context=combined_ctx, slot=os.getenv("SLOT", ""))
        plan = validate_plan_balance(plan)
        if combined_ctx:
            log_event("SCHEDULER", f"Content planner context: {combined_ctx[:200]}...")
    except Exception as e:
        log_event("SCHEDULER", f"Planner failed: {e}, falling back to trend-based", "error")
        plan = []

    if not plan and not trends:
        log_event("SCHEDULER", "No plan and no trends, skipping content generation")
        update_pipeline_status(False)
        return

    if not trends:
        trends = []

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

    video_date = datetime.utcnow().strftime('%Y%m%d')
    pipeline_jobs = []
    short_video_ids = {}
    long_video_ids = {}

    # ── Verified news (mandatory daily slots) ──────────────────────────────
    news_enabled = os.getenv("ENABLE_NEWS", "true").lower() != "false"
    news_articles = {"world": None, "nepal": None}
    if news_enabled:
        try:
            from utils.news_scraper import WORLD_CATEGORY, NEPAL_CATEGORY, fetch_news
            from utils.scheduler_planner import _load_recent_topic_titles
            _all_news = fetch_news(category=None)
            _w = [a for a in _all_news if a["category"] == WORLD_CATEGORY]
            _n = [a for a in _all_news if a["category"] == NEPAL_CATEGORY]
            # pick top stories, avoiding ones already used recently (30d dedup by title)
            _recent = set(_load_recent_topic_titles(days=30))
            for pool, key in ((_w, "world"), (_n, "nepal")):
                for a in pool:
                    if a["title"].lower().strip() not in _recent:
                        news_articles[key] = a
                        break
            log_event("SCHEDULER", f"News: {len(_w)} world + {len(_n)} nepal verified stories available")
        except Exception as e:
            log_event("SCHEDULER", f"News scraper failed: {e}", "warn")
            news_articles = {"world": None, "nepal": None}

    # GPU render budget guard (single 16GB box): cap total GPU (long) videos per day
    # so a heavy day can't crash the container. News long is mandatory and goes first.
    gpu_budget = int(os.getenv("GPU_VIDEO_BUDGET_PER_DAY", str(long_per_day)))

    def _news_job(category: str, fmt: str, article: dict, slot: tuple, idx: int):
        vid = f"{'short' if fmt=='shorts' else 'long'}-{video_date}-n{idx}"
        func = generate_short_video if fmt == "shorts" else generate_long_video
        kwargs = {"news_article": article} if article else {}
        (short_video_ids if fmt == "shorts" else long_video_ids)[vid] = {"title": article["title"] if article else category, "category": category, "format": fmt, "priority": 100}
        return {"func": func, "args": (article["title"] if article else f"{category} update", category, vid, _next_schedule_time(slot)), "kwargs": kwargs, "name": f"{'short' if fmt=='shorts' else 'long'}-news-{idx}", "gpu": fmt == "long"}

    _news_job_idx = [0]
    # D24 slot times (UTC): World 19:00 (12:45 AM Nepal), Nepal 21:00 (2:45 AM Nepal),
    # News long 01:00 next day (6:45 AM Nepal) — all inside the user's idle window.
    if news_enabled and news_articles.get("world"):
        pipeline_jobs.append(_news_job("World News (24hr)", "shorts", news_articles["world"], (19, 0), _news_job_idx[0] + 1))
        _news_job_idx[0] += 1
    if news_enabled and news_articles.get("nepal"):
        pipeline_jobs.append(_news_job("Nepal News", "shorts", news_articles["nepal"], (21, 0), _news_job_idx[0] + 1))
        _news_job_idx[0] += 1
    # one news long per day, alternating which regime gets the long (gpu budget permitting)
    if news_enabled and gpu_budget >= 1 and (news_articles.get("world") or news_articles.get("nepal")):
        # prefer a DIFFERENT verified article than the short already used, for variety
        _uses_world = bool(news_articles.get("world"))
        _cat_key = "world" if _uses_world else "nepal"
        _cat = WORLD_CATEGORY if _uses_world else NEPAL_CATEGORY
        _article = news_articles[_cat_key]
        _short_title = _article["title"].lower().strip()
        _pool = (_w if _uses_world else _n)
        for _a in _pool:
            if _a["title"].lower().strip() != _short_title and _a["title"].lower().strip() not in _recent:
                _article = _a
                break
        pipeline_jobs.append(_news_job(_cat, "long", _article, (1, 0), _news_job_idx[0] + 1))
        _news_job_idx[0] += 1

    # ── Fill remaining pillar slots (regular categories) ──────────────────
    # D24: single AI/IT pillar short publishes at (23,0) UTC = 4:45 AM Nepal.
    _short_count = [0]
    _short_base = (23, 0)
    _short_n = 0
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
        _short_count[0] += 1
        _short_n = _short_count[0] - 1
        vid = f"short-{video_date}-{_short_count[0]}"
        short_video_ids[vid] = item
        slot = (_short_base[0] + _short_n * 2, _short_base[1])
        pipeline_jobs.append({
            "func": generate_short_video,
            "args": (item['title'], item['category'], vid, _next_schedule_time(slot)),
            "kwargs": {},
            "name": f"short-{_short_count[0]}",
            "gpu": False,
        })

    # longs: news long already consumed 1 GPU slot from the budget; pillars fill the rest.
    # D24: single pillar long publishes at (21,15) UTC = 3:00 AM Nepal.
    _long_count = [0]
    _long_slot = (21, 15)
    _gpu_used = sum(1 for j in pipeline_jobs if j['gpu'])
    for i in range(long_per_day):
        if gpu_budget and (_long_count[0] + _gpu_used) >= gpu_budget:
            log_event("SCHEDULER", f"GPU budget {gpu_budget} reached — skipping remaining long slots")
            break
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
        _long_count[0] += 1
        _long_n = _long_count[0] - 1
        vid = f"long-{video_date}-{_long_count[0]}"
        long_video_ids[vid] = item
        slot = (_long_slot[0] + _long_n * 4, _long_slot[1])
        pipeline_jobs.append({
            "func": generate_long_video,
            "args": (item['title'], item['category'], vid, _next_schedule_time(slot)),
            "kwargs": {},
            "name": f"long-{_long_count[0]}",
            "gpu": True,
        })

    log_event("SCHEDULER", f"Planned {len(pipeline_jobs)} pipelines ({sum(1 for j in pipeline_jobs if not j['gpu'])} shorts, {sum(1 for j in pipeline_jobs if j['gpu'])} longs)")

    # ponytail: news jobs are mandatory daily slots AND carry a specific verified article
    # (which plain schedule_topic() drops). Re-run a failed news job serially with the
    # article intact so the mandated World/Nepal slot still lands, instead of losing it.
    failed_news_jobs = []

    if pipeline_jobs:
        log_event("SCHEDULER", f"Running {len(pipeline_jobs)} pipelines concurrently")
        job_results = run_concurrent_pipelines(pipeline_jobs)

        for idx, (job, result) in enumerate(zip(pipeline_jobs, job_results)):
            item = job["args"][0]
            vid = job["args"][2]
            is_short = "short" in vid
            if result.get("success"):
                if is_short:
                    successful_shorts += 1
                    track_video(vid, item, "shorts", "", 0)
                    mark_topic_completed(vid)
                else:
                    successful_longs += 1
                    track_video(vid, item, "long", "", 0)
                    mark_topic_completed(vid)
            else:
                failed_topics.append(item)
                fmt = "shorts" if is_short else "long"
                if job.get("name", "").startswith(("short-news", "long-news")) or job.get("kwargs", {}).get("news_article"):
                    failed_news_jobs.append({"job": job, "vid": vid, "fmt": fmt})
                topic_id = schedule_topic(item, fmt, priority="high")
                mark_topic_failed(topic_id, result.get("error", "Generation failed"))
                log_event("SCHEDULER", f"{fmt} video '{item}' {'crashed' if result.get('error') else 'failed'}: {result.get('error', 'unknown')}", "error")
    else:
        log_event("SCHEDULER", "No pipeline jobs to run")

    # Serial news retry — retain the specific verified article the concurrent run lost.
    for njob in failed_news_jobs:
        job, vid, fmt = njob["job"], njob["vid"], njob["fmt"]
        item = job["args"][0]
        log_event("SCHEDULER", f"Retrying failed news {fmt} '{item}' serially with article intact")
        try:
            func = job["func"] if "func" in job else (generate_short_video if fmt == "shorts" else generate_long_video)
            ok = func(*job["args"], **job["kwargs"])
            if ok:
                if fmt == "shorts":
                    successful_shorts += 1
                    track_video(vid, item, "shorts", "", 0)
                else:
                    successful_longs += 1
                    track_video(vid, item, "long", "", 0)
                mark_topic_completed(vid)
                if item in failed_topics:
                    failed_topics.remove(item)
                log_event("SCHEDULER", f"News {fmt} '{item}' recovered on serial retry")
        except Exception as e:
            log_event("SCHEDULER", f"News {fmt} '{item}' retry failed: {e}", "error")

    update_pipeline_status(False)
    total = successful_shorts + successful_longs
    log_event("SCHEDULER", f"Daily content generation complete: {total} videos produced ({successful_shorts} shorts, {successful_longs} longs)")

    if total == 0 and FORCE_PUBLISH and failed_topics:
        log_event("SCHEDULER", f"FORCE_PUBLISH=true — re-attempting: {failed_topics[0]}", "warn")
        for ft in failed_topics[:1]:
            log_event("SCHEDULER", f"Force-publishing: {ft}", "info")
            try:
                force_vid = f"force-{video_date}-{int(time.time())}"
                generate_short_video(ft, "AI Explained", force_vid)
            except Exception as e:
                log_event("SCHEDULER", f"Force-publish failed: {e}", "error")

    summary = get_performance_summary(days=7)
    log_event("ANALYTICS", f"7-day summary: {summary['total_videos']} videos, {summary['total_views']} views, avg score: {summary['avg_quality_score']}")

    cal_summary = get_calendar_summary(days=7)
    log_event("CALENDAR", f"7-day calendar: {cal_summary['completed']} completed, {cal_summary['failed']} failed, {cal_summary['retry_queue_size']} in retry queue")

    if failed_topics:
        log_event("SCHEDULER", f"Failed topics (will retry next run): {', '.join(failed_topics)}")

    return successful_shorts > 0 or successful_longs > 0


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

        # Sync hook stats with real YouTube data
        try:
            from utils.hook_tester import sync_hook_stats_from_youtube
            updated = sync_hook_stats_from_youtube(max_videos=50)
            if updated:
                log_event("HOOK_SYNC", f"Updated {updated} hook entries with real YouTube stats")
        except Exception as e:
            log_event("HOOK_SYNC", f"Hook sync failed: {e}", "debug")

        # Sync title CTR with real YouTube data
        try:
            from utils.title_tester import sync_title_ctr_from_youtube
            updated_titles = sync_title_ctr_from_youtube()
            if updated_titles:
                log_event("TITLE_SYNC", f"Updated {updated_titles} title tests with real CTR")
        except Exception as e:
            log_event("TITLE_SYNC", f"Title CTR sync failed: {e}", "debug")

        # Pull retention curves for recent videos
        try:
            from utils.retention_analyzer import pull_retention_from_youtube
            from utils.firebase_status import get_firestore_client
            db = get_firestore_client()
            if db:
                from datetime import datetime
                recent = db.collection("videos").order_by("created_at", direction="DESCENDING").limit(5).stream()
                for doc in recent:
                    v = doc.to_dict()
                    vid = v.get("youtube_id", v.get("video_id", ""))
                    cat = v.get("category", "AI News")
                    dur = v.get("duration_seconds", 60)
                    if vid:
                        pull_retention_from_youtube(vid, cat, dur)
        except Exception as e:
            log_event("RETENTION", f"Retention pull failed: {e}", "debug")

        try:
            from utils.alert_manager import process_alerts, check_pipeline_health_alert, check_staleness
            from utils.firebase_status import get_pipeline_metrics, get_firestore_client

            # Pipeline health alert
            pm = get_pipeline_metrics(limit=20)
            if pm and len(pm) >= 5:
                successes = sum(1 for m in pm if m.get("success"))
                success_rate = successes / len(pm)
                pipeline_alert = check_pipeline_health_alert(success_rate)
                if pipeline_alert:
                    send_alert(pipeline_alert["message"], pipeline_alert["severity"])
                    log_event("ALERT", pipeline_alert["message"], "warn")

            # Staleness check — get last activity from Firestore
            last_activity = None
            try:
                db = get_firestore_client()
                if db:
                    docs = db.collection("activity_logs").order_by("timestamp", direction="DESCENDING").limit(1).stream()
                    for doc in docs:
                        data = doc.to_dict()
                        ts = data.get("timestamp")
                        if ts:
                            if hasattr(ts, 'timestamp'):  # google.cloud.Timestamp
                                last_activity = datetime.utcfromtimestamp(ts.timestamp())
                            elif isinstance(ts, str):
                                last_activity = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                            else:
                                last_activity = ts  # already a datetime
            except Exception:
                pass
            staleness_alert = check_staleness(last_activity)
            if staleness_alert:
                send_alert(staleness_alert["message"], staleness_alert["severity"])
                log_event("ALERT", staleness_alert["message"], "warn")

            # System-health drift (disk/memory) from heartbeat record — alert before it kills a pipeline
            try:
                hb = db.collection("system").document("heartbeat").get() if db else None
                if hb and hb.exists:
                    hdata = hb.to_dict() or {}
                    disk_pct = hdata.get("disk_percent") or 0
                    mem_pct = hdata.get("memory_percent") or 0
                    overrides = []
                    if float(disk_pct) >= 85:
                        overrides.append(f"disk {disk_pct:.0f}%")
                    if float(mem_pct) >= 90:
                        overrides.append(f"memory {mem_pct:.0f}%")
                    if overrides:
                        msg = f"System resource warning: {' / '.join(overrides)}"
                        send_alert(msg, "warning")
                        log_event("ALERT", msg, "warn")
            except Exception:
                pass

            # Missed-slot / daily-volume guard — verifies the scheduled 5/day landed
            try:
                target_short = int(os.getenv("SCHEDULE_SHORTS_PER_DAY", "1"))
                target_long = int(os.getenv("SCHEDULE_LONG_PER_DAY", "2"))
                target_total = target_short + target_long
                if db:
                    cutoff = datetime.utcnow() - timedelta(hours=26)
                    published = 0
                    short_count, long_count = 0, 0
                    _snap = db.collection("videos").where(
                        "created_at", ">=", cutoff
                    ).stream()
                    for _doc in _snap:
                        _v = _doc.to_dict() or {}
                        if _v.get("status") in ("uploaded", "scheduled", "published", "completed"):
                            published += 1
                            if _v.get("format") == "short":
                                short_count += 1
                            elif _v.get("format") == "long":
                                long_count += 1
                    if published < target_total:
                        msg = (f"Missed-slot warning: only {published} video(s) in last 26h "
                               f"(target {target_total}; shorts {short_count}/{target_short}, "
                               f"longs {long_count}/{target_long})")
                        send_alert(msg, "warning")
                        log_event("ALERT", msg, "warn")
            except Exception:
                pass
        except Exception as alert_err:
            log_event("ALERT", f"Alert checks failed: {alert_err}", "debug")
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
        from utils.youtube_upload import get_channel_stats
        try:
            stats = get_channel_stats()
            if stats:
                hours = int(stats.get("total_views", 0)) / 60  # rough: total_views/60 ~ watch hours
                update_platform_metrics("youtube", {
                    "subs": int(stats.get("subscribers", 0)),
                    "watch_hours": max(1, int(hours)),
                    "total_views": int(stats.get("total_views", 0)),
                })
                log_event("MONETIZATION", f"Real stats: {stats.get('subscribers')} subs, {stats.get('total_views')} views")
        except Exception as e:
            log_event("MONETIZATION", f"Could not fetch real YouTube stats: {e}", "warn")
        check_in = weekly_check_in()
        log_event("MONETIZATION", f"Weekly check-in recorded for {check_in['date'][:10]}")
        growth_summary = get_growth_summary()
        log_event("MONETIZATION", f"Growth summary: {growth_summary[:200]}")
        try:
            crew = create_monetization_review_crew()
            try:
                result = crew.kickoff(inputs={})
                review = getattr(result, 'raw', str(result))
            except Exception:
                from crewai import Task as CrewAITask
                agent = crew.agents[0]
                task = crew.tasks[0]
                new_task = CrewAITask(description=task.description, expected_output=task.expected_output, agent=agent)
                review = agent.execute_task(task=new_task, context=None, tools=None) or ""
            log_event("MONETIZATION", "Monetization review complete")
            try:
                from utils.firebase_status import get_firestore_client
                from google.cloud.firestore import SERVER_TIMESTAMP as _ts
                _db = get_firestore_client()
                if _db is not None:
                    _db.collection('monetization').document('revenue').set(
                        {'last_reviewed_at': _ts}, merge=True)
            except Exception as _e:
                log_event("MONETIZATION", f"Could not stamp review time: {_e}", "debug")
        except Exception as e:
            log_event("MONETIZATION", f"Review crew failed: {e}", "warn")
    except Exception as e:
        log_event("MONETIZATION", f"Weekly monetization check failed: {e}", "error")


EVERYONE_DOCUMENTARY_JOB = False

def weekly_documentary_job():
    global EVERYONE_DOCUMENTARY_JOB
    if EVERYONE_DOCUMENTARY_JOB:
        log_event("SCHEDULER", "Skipping weekly documentary job — documentarians are resting")
        return
    log_event("SCHEDULER", "Starting weekly documentary generation")
    try:
        from utils.scheduler_planner import generate_content_plan
        from utils.knowledge_integration import get_coverage_context
        from utils.pillar_manager import generate_pillar_context
        combined_ctx = ""
        try:
            kc = get_coverage_context()
            if kc:
                combined_ctx += kc
        except Exception:
            pass
        try:
            pc = generate_pillar_context()
            if pc:
                combined_ctx += "\n" + pc
        except Exception:
            pass
        plan = generate_content_plan(extra_context=combined_ctx, slot="documentary")
        log_event("SCHEDULER", f"Content plan: {len(plan.get('shorts', []))} shorts, {len(plan.get('longs', []))} longs")
        videos = plan.get("longs", [])
        if not videos:
            log_event("SCHEDULER", "No long videos in plan — skipping")
            return
        original_format = os.environ.get("FORMAT", "")
        os.environ["TIER"] = "documentary"
        for video in videos:
            topic = video.get("topic", "")
            cat = video.get("category", "AI Explained")
            video_id = generate_video_id()
            try:
                log_event("SCHEDULER", f"Generating documentary: {topic}")
                update_agent_status("scheduler", "working", f"Documentary: {topic[:40]}")
                generate_long_video(topic=topic, category=cat, video_id=video_id)
                log_event("SCHEDULER", f"Documentary generated: {topic}")
            except Exception as e:
                log_event("SCHEDULER", f"Documentary failed: {topic}: {e}", "error")
                continue
        os.environ["TIER"] = ""
        if original_format:
            os.environ["FORMAT"] = original_format
        EVERYONE_DOCUMENTARY_JOB = True
    except Exception as e:
        log_event("SCHEDULER", f"Weekly documentary job failed: {e}", "error")


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


def daily_title_test_job():
    log_event("TITLE_TEST", "Checking active title A/B tests")
    try:
        import json, glob
        from utils.title_tester import advance_title_test
        from utils.youtube_upload import update_youtube_video_title
        test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "title_tests")
        if not os.path.exists(test_dir):
            return
        for f in glob.glob(os.path.join(test_dir, "*.json")):
            try:
                with open(f) as fh:
                    test = json.load(fh)
                if test.get("status") != "testing":
                    continue
                video_id = test.get("video_id", "")
                result = advance_title_test(video_id, update_youtube_video_title)
                status = result.get("status", "")
                if status == "waiting":
                    log_event("TITLE_TEST", f"Test for {video_id}: {result.get('hours_remaining', 0)}h remaining")
                elif status == "testing":
                    log_event("TITLE_TEST", f"Test advanced for {video_id}")
                elif status == "completed":
                    log_event("TITLE_TEST", f"Test completed for {video_id}, winner: {result.get('winner', {})}")
            except Exception as e:
                log_event("TITLE_TEST", f"Test advancement error: {e}", "warn")
    except Exception as e:
        log_event("TITLE_TEST", f"Title test job failed: {e}", "warn")


def daily_community_post_job():
    if not ENABLE_COMMUNITY_POSTS:
        return
    log_event("COMMUNITY", "Starting community post job")
    try:
        from utils.community_manager import schedule_weekly_poll
        ok = _run_async(schedule_weekly_poll())
        if ok:
            log_event("COMMUNITY", "Weekly poll post created")
        else:
            log_event("COMMUNITY", "Weekly poll post failed (no success from studio)", "warn")
    except Exception as e:
        log_event("COMMUNITY", f"Community post failed: {e}", "warn")
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
                # Analytics already initialized by track_video() during pipeline run — skip views reset
                log_event("SCHEDULE", f"Video {doc.id} status updated to uploaded")
        if published > 0:
            log_event("SCHEDULE", f"Published {published} scheduled videos")
    except Exception as e:
        if "429" not in str(e):
            log_event("SCHEDULE", f"Scheduled publish check failed: {e}", "error")


def cleanup_stuck_state():
    """Reset stale pipeline state on startup. Recovers from crashes."""
    log_event("SYSTEM", "Resetting agent status...")
    try:
        from utils.firebase_status import reset_agent_statuses
        n = reset_agent_statuses()
        log_event("SYSTEM", f"Reset {n} stale agent statuses (crash recovery)")
    except Exception as e:
        log_event("SYSTEM", f"Agent status reset failed: {e}", "error")
        for agent_id in AGENT_MAP.values():
            try:
                update_agent_status(agent_id, "idle", "Ready")
            except Exception as e2:
                log_event("SYSTEM", f"Failed to reset {agent_id}: {e2}", "error")

    # Reset stale pipeline.running flag (left true by a crash)
    try:
        from utils.firebase_status import get_firestore_client
        db = get_firestore_client()
        if db:
            doc = db.collection('system').document('pipeline').get()
            if doc.exists and doc.to_dict().get('running'):
                db.collection('system').document('pipeline').set({
                    'running': False,
                    'current_video': '',
                }, merge=True)
                log_event("SYSTEM", "Reset stale pipeline.running flag (crash recovery)")
    except Exception as e:
        log_event("SYSTEM", f"Pipeline crash recovery failed: {e}", "error")


def _handle_pipeline_trigger(topic: str, category: str, format_type: str, trigger_id: str, publish_at: str = None):
    """Handle a pipeline run trigger from the dashboard."""
    from utils.scene_schema import normalize_category
    category = normalize_category(category)
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


def tiktok_composer_job():
    """Publish queued dashboard TikTok composer intents (audit-compliant: explicit privacy, no default)."""
    try:
        from utils.firebase_status import get_firestore_client
        db = get_firestore_client()
        if not db:
            return
        docs = list(db.collection('tiktok_composer').where('status', '==', 'queued').stream(timeout=30))
        if not docs:
            return

        docs.sort(key=lambda d: d.to_dict().get('created_at', None) or 0)
        intent = docs[0]
        data = intent.to_dict()
        intent_id = intent.id

        title = data.get('title', '')
        video_id = data.get('video_id', '')
        privacy = data.get('privacy_level', '')
        comment_disabled = bool(data.get('comment_disabled', False))
        duet_disabled = bool(data.get('duet_disabled', True))
        stitch_disabled = bool(data.get('stitch_disabled', True))

        if not video_id:
            _fail_intent(db, intent_id, 'Missing video_id')
            return
        if not privacy:
            _fail_intent(db, intent_id, 'Missing privacy_level (no default)')
            return

        intent_ref = db.collection('tiktok_composer').document(intent_id)
        intent_ref.update({'status': 'processing', 'started_at': time.time()})

        video_path = ''
        cp = load_checkpoint(video_id)
        if cp:
            video_path = (cp.get('state') or {}).get('video_path', '') or ''
        if not video_path or not os.path.exists(video_path):
            video_path = _resolve_video_for_publish(db, video_id, video_path)

        if not video_path:
            _fail_intent(db, intent_id, f'Video file unavailable for video_id={video_id}')
            return

        def _do():
            result = multi_platform_publish(
                video_id=video_id,
                title=title,
                description=data.get('description', '') or title,
                video_path=video_path,
                thumbnail_path='',
                format_type=data.get('format', 'shorts'),
                platforms=['tiktok'],
                category=data.get('category', ''),
                cleanup=False,
                tiktok_privacy_level=privacy,
                tiktok_comment_disabled=comment_disabled,
                tiktok_duet_disabled=duet_disabled,
                tiktok_stitch_disabled=stitch_disabled,
            )
            t = result.get('platforms', {}).get('tiktok', {})
            if t.get('success'):
                db.collection('tiktok_composer').document(intent_id).update({
                    'status': 'published',
                    'publish_id': t.get('video_id'),
                    'url': t.get('url', ''),
                    'completed_at': time.time(),
                })
                log_event("TIKTOK_COMPOSER", f"Published: {title} -> {t.get('url', '')}")
            else:
                raise RuntimeError(t.get('error', 'TikTok publish failed'))

        from utils.subprocess_helper import retry_with_backoff
        ok, result = retry_with_backoff(_do, max_retries=2, base_delay=5, max_delay=30)
        if not ok:
            _fail_intent(db, intent_id, result if isinstance(result, str) else str(result))
    except Exception as e:
        log_event("TIKTOK_COMPOSER", f"Composer job failed: {e}", "error")


def _fail_intent(db, intent_id: str, reason: str):
    try:
        db.collection('tiktok_composer').document(intent_id).update({
            'status': 'failed',
            'error': str(reason)[:500],
            'completed_at': time.time(),
        })
    except Exception as e:
        log_event("TIKTOK_COMPOSER", f"Failed to mark intent failed: {e}", "error")


def _resolve_video_for_publish(db, video_id: str, local_path: str = '') -> str:
    """Resolve a publishable video file: local path, else download from R2 by key."""
    if local_path and os.path.exists(local_path):
        return local_path
    try:
        doc = db.collection('videos').document(video_id).get()
        if not doc.exists:
            return ''
        vdata = doc.to_dict()
        r2_key = vdata.get('r2_key') or ''
        if not r2_key:
            r2_key = f"videos/{video_id}_{vdata.get('format', 'long')}.mp4"
        from utils.r2_storage import generate_presigned_url
        import urllib.request
        tmp = f"tmp/composer_{video_id}.mp4"
        os.makedirs("tmp", exist_ok=True)
        url = generate_presigned_url(r2_key, expires_in=300)
        urllib.request.urlretrieve(url, tmp)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
            return tmp
    except Exception as e:
        log_event("TIKTOK_COMPOSER", f"R2 resolve failed for {video_id}: {e}", "warn")
    return ''


if __name__ == "__main__":
    log_event("SYSTEM", "Vyom Ai Cloud - Agent Orchestrator Starting")

    _run_once = "--run-once" in sys.argv
    if _run_once:
        log_event("SYSTEM", "RUN-ONCE mode: executing daily_content_job() then exiting")
        cleanup_stuck_state()
        daily_content_job()
        update_pipeline_status(False)
        sys.exit(0)

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
    log_event("SYSTEM", f"Multi-language dubbing: {ENABLE_MULTI_LANG_DUB}")
    log_event("SYSTEM", f"Subtitles: {ENABLE_SUBTITLES}")
    log_event("SYSTEM", f"Review gate: {ENABLE_REVIEW_GATE} (threshold: {AUTO_APPROVE_THRESHOLD})")
    log_event("SYSTEM", f"Pipeline timeout: {PIPELINE_TIMEOUT_MINUTES}min per video")
    log_event("SYSTEM", f"Concurrent pipeline workers: {os.getenv('CONCURRENT_PIPELINE_WORKERS', '2')}")
    log_event("SYSTEM", f"LTX prompt cache: {os.getenv('ENABLE_LTX_CACHE', 'true')}")
    log_event("SYSTEM", f"Max retries per topic: {MAX_RETRIES_PER_TOPIC}")
    log_event("SYSTEM", f"Gate enforcement: {GATE_ENFORCEMENT_MODE}")

    _setup_logging()
    validate_env()

    from utils.llm_helper import verify_ollama_model
    ollama_ok = verify_ollama_model()
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_ok = bool(gemini_key)
    ollama_status = "✅" if ollama_ok else "❌"
    gemini_status = "✅" if gemini_ok else "❌"
    log_event("LLM", f"Startup: Ollama={ollama_status} Gemini={gemini_status} (Ollama primary, Gemini fallback)")

    scheduler = BlockingScheduler()
    # D24: run content generation overnight (15:05 UTC = 8:50 PM Nepal) so the
    # heavy LTX renders never happen during the user's 10:30 AM-8:00 PM Nepal laptop window.
    scheduler.add_job(daily_content_job, "cron", hour=15, minute=5, misfire_grace_time=86400)
    scheduler.add_job(daily_analytics_job, "cron", hour=8, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_revenue_job, "cron", hour=8, minute=30, misfire_grace_time=86400)
    scheduler.add_job(daily_cleanup_job, "cron", hour=4, minute=0, misfire_grace_time=86400)
    scheduler.add_job(scheduled_publish_job, "interval", minutes=15)
    scheduler.add_job(tiktok_composer_job, "interval", minutes=5)
    scheduler.add_job(weekly_monetization_job, "cron", day_of_week="mon", hour=12, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_feedback_job, "cron", hour=10, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_title_test_job, "cron", hour=12, minute=0, misfire_grace_time=86400)
    scheduler.add_job(daily_community_post_job, "cron", day_of_week="mon,thu", hour=15, minute=0, misfire_grace_time=86400)
    # D24: weekly documentary long render moved into the idle window (20:00 UTC = 1:45 AM Mon Nepal)
    # so it never renders during laptop use, and runs after the Sunday 15:05 UTC daily content job.
    scheduler.add_job(weekly_documentary_job, "cron", day_of_week="sun", hour=20, minute=0, misfire_grace_time=86400)
    log_event("SCHEDULER", "Daily content job scheduled at 15:05 UTC (overnight)")
    log_event("SCHEDULER", "Daily analytics pull scheduled at 08:00 UTC")
    log_event("SCHEDULER", "Daily revenue computation scheduled at 08:30 UTC")
    log_event("SCHEDULER", "Daily cleanup job scheduled at 04:00 UTC")
    log_event("SCHEDULER", "Scheduled publish check every 15 minutes")
    log_event("SCHEDULER", "TikTok composer check every 5 minutes")
    log_event("SCHEDULER", "Weekly monetization review scheduled on Mondays at 12:00 UTC")
    log_event("SCHEDULER", "Weekly documentary generation scheduled on Sundays at 20:00 UTC")
    log_event("SCHEDULER", "Daily analytics feedback loop scheduled at 10:00 UTC")

    def _shutdown():
        if getattr(_shutdown, "_called", False):
            return
        _shutdown._called = True
        from utils.firebase_status import reset_agent_statuses
        from utils.subprocess_helper import _cleanup_all_temp
        reset_agent_statuses()
        update_pipeline_status(False)
        _cleanup_all_temp()
        log_event("SYSTEM", "Pipeline stopped — agent statuses reset, temp cleaned")
        control_listener.stop()

    signal.signal(signal.SIGTERM, lambda *_: (_shutdown(), sys.exit(0)))
    signal.signal(signal.SIGINT, lambda *_: (_shutdown(), sys.exit(0)))

    try:
        # Skip immediate run — scheduler handles it (prevents duplicate content on startup near 06:00 UTC)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log_event("SYSTEM", "Agent Orchestrator Shutting Down")
    except Exception as e:
        log_event("SYSTEM", f"Pipeline crashed: {e}", "error")
    finally:
        _shutdown()
