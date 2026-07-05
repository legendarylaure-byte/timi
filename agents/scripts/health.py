"""
Pipeline Health Check
Run: python3 scripts/health.py   (from agents/ directory)
Or:  python -m agents.scripts.health   (from timi/ directory)
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from utils.health_monitor import check_stale_heartbeat
from utils.firebase_status import get_firestore_client
from utils.voice_provider import GoogleCloudTTSProvider
from models.registry import get_video_model

OK = "OK"
WARN = "WARN"
FAIL = "FAIL"


def _check_env(name: str, critical: bool = True) -> tuple:
    val = os.getenv(name, "")
    if val:
        masked = val[:8] + "..." if len(val) > 12 else "set"
        return (OK, masked)
    return (FAIL if critical else WARN, "not set")


def _check_tool(name: str) -> tuple:
    path = shutil.which(name)
    if path:
        return (OK, path)
    return (FAIL, "not found")


def _check_ffmpeg_codecs() -> tuple:
    try:
        r = subprocess.run(["ffmpeg", "-encoders", "-hide_banner"],
                           capture_output=True, text=True, timeout=10)
        has_h264 = "libx264" in r.stdout
        has_aac = "aac" in r.stdout
        if has_h264 and has_aac:
            return (OK, "h264+aac")
        return (WARN, f"h264={'Y' if has_h264 else 'N'}, aac={'Y' if has_aac else 'N'}")
    except Exception:
        return (FAIL, "ffmpeg not available")


def _check_log_activity(name: str) -> dict:
    path = Path("logs") / name
    if not path.exists():
        return {"status": WARN, "detail": "not found"}
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    age_h = (datetime.now() - mtime).total_seconds() / 3600
    size_mb = path.stat().st_size / (1024 * 1024)
    if age_h < 24:
        return {"status": OK, "detail": f"{size_mb:.1f}MB, {age_h:.1f}h ago"}
    return {"status": WARN, "detail": f"{size_mb:.1f}MB, {age_h:.1f}h old"}


def _check_youtube_token() -> tuple:
    path = Path("youtube_token.json")
    if not path.exists():
        return (WARN, "not found")
    try:
        data = json.loads(path.read_text())
        expiry = data.get("expiry", data.get("token_expiry", ""))
        if expiry:
            exp_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
            remaining = (exp_dt - datetime.now().astimezone()).total_seconds() / 3600
            if remaining > 24:
                return (OK, f"expires in {remaining:.0f}h")
            elif remaining > 0:
                return (WARN, f"expires in {remaining:.0f}h")
            return (FAIL, "expired")
        return (WARN, "no expiry field")
    except Exception:
        return (FAIL, "parse error")


def _check_disk() -> tuple:
    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        pct = usage.used / usage.total * 100
        if pct < 80:
            return (OK, f"{free_gb:.0f}GB free ({pct:.0f}% used)")
        return (WARN, f"{free_gb:.0f}GB free ({pct:.0f}% used)")
    except Exception:
        return (FAIL, "check failed")


def _check_ollama() -> tuple:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    try:
        import requests
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            if model in models:
                return (OK, f"{model} loaded")
            return (WARN, f"'{model}' not found; available: {models[:3]}")
        return (FAIL, f"Ollama returned {r.status_code}")
    except Exception as e:
        return (FAIL, str(e)[:60])


def _check_firestore() -> tuple:
    db = get_firestore_client()
    if db is None:
        return (FAIL, "no credentials")
    try:
        doc = db.collection("system").document("heartbeat").get()
        if doc.exists:
            data = doc.to_dict()
            last = data.get("last_heartbeat", "unknown")
            return (OK, f"heartbeat: {last[:19]}")
        return (WARN, "no heartbeat document")
    except Exception as e:
        return (FAIL, str(e)[:60])


def _check_ltx() -> tuple:
    model_dir = os.getenv("LTX_MODEL_DIR", os.path.expanduser("~/ltx-models"))
    if not os.path.isdir(model_dir):
        return (WARN, f"model dir not found at {model_dir}")
    try:
        model = get_video_model()
        if model and model.is_available():
            return (OK, model.name())
        return (WARN, "dir ok but no model loaded (missing ltx_pipelines_mlx?)")
    except Exception as e:
        return (WARN, str(e)[:80])


def _check_tts() -> tuple:
    provider = os.getenv("VOICE_PROVIDER", "edge")
    if provider == "google":
        try:
            g = GoogleCloudTTSProvider()
            if g.is_available():
                return (OK, "Google TTS ready")
            return (FAIL, "Google TTS creds missing")
        except Exception as e:
            return (FAIL, str(e)[:60])
    return (OK, "edge-tts (default)")


def _check_python_version() -> tuple:
    v = sys.version_info
    if v.major >= 3 and v.minor >= 10:
        return (OK, f"{v.major}.{v.minor}.{v.micro}")
    return (WARN, f"{v.major}.{v.minor}.{v.micro} (min 3.10)")


def _check_scheduler_pid() -> tuple:
    pid_paths = ["scheduler.pid", "/tmp/timi_pipeline.pid"]
    for p in pid_paths:
        path = Path(p)
        if path.exists():
            try:
                pid = int(path.read_text().strip())
                try:
                    os.kill(pid, 0)
                    return (OK, f"PID {pid} running ({p})")
                except ProcessLookupError:
                    return (WARN, f"PID {pid} stale ({p})")
                except PermissionError:
                    return (OK, f"PID {pid} exists (no perm) ({p})")
            except Exception:
                return (WARN, f"bad PID file ({p})")
    return (WARN, "no scheduler PID file found")


def _check_agent_statuses(db) -> list:
    results = []
    try:
        docs = db.collection("agent_status").stream()
        for d in docs:
            data = d.to_dict()
            status = data.get("status", "unknown")
            error = data.get("error_message", "")
            updated = data.get("last_updated", None)
            age_h = "?"
            if updated:
                if hasattr(updated, "tzinfo") and updated.tzinfo is not None:
                    age = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
                else:
                    age = (datetime.now() - updated).total_seconds() / 3600
                age_h = f"{age:.0f}h"
            label = f"  {d.id:<25}"
            if error:
                label += f" \033[33m{status:<6}\033[0m {error[:60]} (updated {age_h})"
                results.append((WARN, label))
            else:
                label += f" \033[32m{status:<6}\033[0m updated {age_h}"
                results.append((OK, label))
    except Exception as e:
        results.append((FAIL, f"  agent_status  \033[31mFAIL  \033[0m {str(e)[:60]}"))
    return results


def _check_recent_pipeline_metrics(db) -> tuple:
    try:
        docs = db.collection("pipeline_metrics").order_by("timestamp", direction="DESCENDING").limit(3).stream()
        lines = []
        for d in docs:
            data = d.to_dict()
            ts = data.get("timestamp", "")
            dur = data.get("duration_s", 0)
            fmt = data.get("format", "?")
            topic = data.get("topic", "?")[:30]
            status = data.get("status", data.get("success", "?"))
            label = f"  {str(status):<12} {fmt:<6} {dur:>6.0f}s  {topic}"
            lines.append(label)
        if lines:
            return (OK, "\n" + "\n".join(lines))
        return (WARN, "no pipeline metrics")
    except Exception as e:
        return (FAIL, str(e)[:60])


def print_section(title: str):
    print(f"\n  \033[1;36m{title}\033[0m")
    print(f"  {'─' * 50}")


def print_row(name: str, status: str, detail: str):
    color_map = {OK: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m"}
    color = color_map.get(status, "\033[0m")
    print(f"  {name:<30} {color}{status:<6}\033[0m {detail}")


def main():
    print()
    print(f"  \033[1;37m═══ Pipeline Health Report ═══\033[0m")
    print(f"  Timestamp: {datetime.now().isoformat()[:19]}")
    print(f"  CWD: {os.getcwd()}")
    print()

    env_critical = [
        "GEMINI_API_KEY", "FIREBASE_PROJECT_ID",
        "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET",
    ]
    env_optional = [
        "OLLAMA_BASE_URL", "OLLAMA_MODEL",
        "PEXELS_API_KEY", "PIXABAY_API_KEY",
        "TIKTOK_ACCESS_TOKEN", "TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET",
        "FACEBOOK_ACCESS_TOKEN", "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET",
        "INSTAGRAM_ACCOUNT_ID",
        "LTX_MODEL_DIR", "SENTRY_DSN", "VIDEO_MODEL", "VOICE_PROVIDER",
        "GATE_ENFORCEMENT_MODE", "FORCE_PUBLISH",
        "ENABLE_UPSCALE", "ENABLE_AUTO_REPLY", "ENABLE_COMMUNITY_POSTS",
    ]

    failed = False

    print_section("Environment Variables (Critical)")
    for var in env_critical:
        s, d = _check_env(var, critical=True)
        print_row(var, s, d)
        if s == FAIL:
            failed = True

    print_section("Environment Variables (Optional)")
    for var in env_optional:
        s, d = _check_env(var, critical=False)
        print_row(var, s, d)

    print_section("System Tools")
    for tool in ["ffmpeg", "ffprobe", "python3", "git", "playwright"]:
        s, d = _check_tool(tool)
        print_row(tool, s, d)
        if s == FAIL and tool in ("ffmpeg", "ffprobe"):
            failed = True

    s, d = _check_ffmpeg_codecs()
    print_row("ffmpeg codecs", s, d)

    print_section("Model Backends")
    s, d = _check_ollama()
    print_row("Ollama", s, d)
    s, d = _check_ltx()
    print_row("LTX Video", s, d)
    s, d = _check_tts()
    print_row("TTS", s, d)

    print_section("Firestore & Auth")
    db = get_firestore_client()
    if db:
        s, d = _check_firestore()
        print_row("Firestore", s, d)
        try:
            stale = check_stale_heartbeat(threshold_minutes=30)
            print_row("Heartbeat", OK if not stale else WARN,
                      "recent" if not stale else "stale (>30 min)")
        except Exception:
            print_row("Heartbeat", WARN, "check failed")
    else:
        print_row("Firestore", FAIL, "no credentials")
        print_row("Heartbeat", WARN, "no firestore")

    s, d = _check_youtube_token()
    print_row("YouTube Token", s, d)
    if s == FAIL:
        # YouTube token can be auto-refreshed during upload — warn instead of fail
        pass

    print_section("Pipeline Status")
    s, d = _check_scheduler_pid()
    print_row("Scheduler", s, d)
    if db:
        statuses = _check_agent_statuses(db)
        for s2, label in statuses:
            if s2 == FAIL:
                failed = True
            print(label)
        print()
        s3, d3 = _check_recent_pipeline_metrics(db)
        if d3:
            print(f"  Recent runs:")
            print(d3)

    print_section("System Resources")
    s, d = _check_disk()
    print_row("Disk", s, d)
    s, d = _check_python_version()
    print_row("Python", s, d)

    print_section("Log Activity (last 24h)")
    for logfile in ["pipeline.log", "python.log", "security_audit.log"]:
        info = _check_log_activity(logfile)
        print_row(logfile, info["status"], info["detail"])

    print()
    if failed:
        print(f"  \033[1;31mFAIL: Critical checks failed — pipeline may not function.\033[0m")
        sys.exit(1)
    else:
        print(f"  \033[1;32mAll critical checks passed.\033[0m")
    print()


if __name__ == "__main__":
    main()
