"""Safe subprocess runner — Popen+communicate+kill on timeout, mirrors subprocess.run API."""
import atexit
import logging
import os
import random
import shutil
import subprocess
import time

logger = logging.getLogger(__name__)

# Temp directory registry — all registered dirs are cleaned on exit
_TEMP_DIRS = set()

# Keys to strip from subprocess environment to prevent token leakage
_SENSITIVE_ENV_PATTERNS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "BEARER")


def get_safe_env():
    """Return a sanitized environment copy with sensitive keys removed."""
    env = os.environ.copy()
    keys_to_drop = [k for k in env if any(p in k.upper() for p in _SENSITIVE_ENV_PATTERNS)]
    for k in keys_to_drop:
        del env[k]
    return env


def register_temp_dir(path: str):
    """Register a temp directory for cleanup on exit."""
    _TEMP_DIRS.add(path)


def _cleanup_all_temp():
    for d in list(_TEMP_DIRS):
        try:
            if os.path.exists(d):
                shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


atexit.register(_cleanup_all_temp)


def safe_run(cmd, timeout=30, capture_output=True, text=True, env=None, **kwargs):
    """Run a command with Popen, kill child on TimeoutExpired. Returns CompletedProcess.

    When env=None (default), uses a sanitized env with sensitive keys stripped
    to prevent token leakage to subprocesses.
    """
    if env is None:
        env = get_safe_env()
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text,
        env=env,
        **kwargs,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return subprocess.CompletedProcess(
            args=cmd, returncode=process.returncode,
            stdout=stdout or "", stderr=stderr or "",
        )
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise


def safe_run_bool(cmd, timeout=120, env=None):
    """Run and return True if returncode == 0, False otherwise. Kills on timeout.

    When env=None (default), uses a sanitized env with sensitive keys stripped.
    """
    if env is None:
        env = get_safe_env()
    try:
        r = safe_run(cmd, timeout=timeout, capture_output=True, text=True, env=env)
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False


def retry_with_backoff(func, max_retries=3, base_delay=2, max_delay=60):
    """Retry a callable with exponential backoff + jitter. Returns (success_bool, result_or_last_error)."""
    last_error = None
    for attempt in range(max_retries):
        try:
            result = func()
            return True, result
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
                time.sleep(delay)
    return False, last_error


def security_audit(event: str, detail: str = "", level: str = "info"):
    """Log a security-relevant event to both the regular logger and a dedicated audit trail."""
    msg = f"[SECURITY] {event}"
    if detail:
        msg += f" — {detail}"
    getattr(logger, level, logger.info)(msg)
    try:
        audit_log = os.path.join(os.path.dirname(__file__), "..", "logs", "security_audit.log")
        os.makedirs(os.path.dirname(audit_log), exist_ok=True)
        with open(audit_log, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} [{level.upper()}] {event}: {detail}\n")
    except Exception:
        pass


# In-memory rate limiter: {key: [timestamp, ...]}
_RATE_LIMIT_BUCKETS: dict = {}


def rate_limiter(key: str, max_per_hour: int = 10) -> bool:
    """Check if an action is within rate limits. Returns True if allowed."""
    now = time.time()
    window = 3600
    if key not in _RATE_LIMIT_BUCKETS:
        _RATE_LIMIT_BUCKETS[key] = []
    bucket = _RATE_LIMIT_BUCKETS[key]
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= max_per_hour:
        return False
    bucket.append(now)
    return True
