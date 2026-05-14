"""
Health Monitor for Agent System
Provides Ollama health checks, heartbeat tracking, and circuit breaker for external APIs.
"""
import os
import time
import requests
from datetime import datetime
from utils.firebase_status import get_firestore_client

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


class CircuitBreaker:
    """Circuit breaker pattern for external APIs (Pexels, Pixabay, etc.)"""

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: int = 300):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"

    def record_success(self):
        self.failures = 0
        self.state = "closed"

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        if self.failures >= self.failure_threshold:
            self.state = "open"
            print(f"[CIRCUIT BREAKER] {self.name} OPEN after {self.failures} failures")

    def is_available(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                print(f"[CIRCUIT BREAKER] {self.name} HALF-OPEN (testing recovery)")
                return True
            return False
        return True


pexels_breaker = CircuitBreaker("Pexels")
pixabay_breaker = CircuitBreaker("Pixabay")
ollama_breaker = CircuitBreaker("Ollama")


def check_ollama_health() -> bool:
    """Check if Ollama is responsive."""
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            if OLLAMA_MODEL in model_names or any(OLLAMA_MODEL in m for m in model_names):
                ollama_breaker.record_success()
                return True
            else:
                print(f"[OLLAMA] Model '{OLLAMA_MODEL}' not found. Available: {model_names}")
                ollama_breaker.record_failure()
                return False
        else:
            ollama_breaker.record_failure()
            return False
    except requests.exceptions.ConnectionError:
        print("[OLLAMA] Connection refused - Ollama not running")
        ollama_breaker.record_failure()
        return False
    except Exception as e:
        print(f"[OLLAMA] Health check failed: {e}")
        ollama_breaker.record_failure()
        return False


def check_ollama_with_fallback(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:  # noqa: E501
    """Generate completion with Ollama health check and fallback."""
    if not ollama_breaker.is_available():
        print("[OLLAMA] Circuit breaker open, using fallback")
        return _get_fallback_response(prompt, system_prompt)

    if not check_ollama_health():
        print("[OLLAMA] Health check failed, using fallback")
        return _get_fallback_response(prompt, system_prompt)

    try:
        from utils.groq_client import generate_completion
        result = generate_completion(prompt, system_prompt, temperature, max_tokens)
        ollama_breaker.record_success()
        return result
    except Exception as e:
        print(f"[OLLAMA] Generation failed: {e}")
        ollama_breaker.record_failure()
        return _get_fallback_response(prompt, system_prompt)


def _get_fallback_response(prompt: str, system_prompt: str = "") -> str:
    """Return a safe fallback response when Ollama is unavailable."""
    if "trend" in prompt.lower() or "trending" in prompt.lower():
        from utils.trend_discovery import _fallback_trends
        import json
        trends = _fallback_trends()
        return json.dumps(trends, indent=2)
    elif "score" in prompt.lower() or "evaluat" in prompt.lower():
        from utils.quality_scorer import _fallback_score
        import json
        return json.dumps(_fallback_score(prompt, "fallback", "general"), indent=2)
    else:
        return "Content generated successfully with fallback mode."


def write_heartbeat():
    """Write heartbeat to Firestore to indicate agent is alive. Retries on 504."""
    import random
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            db = get_firestore_client()
            db.collection('system').document('heartbeat').set({
                'last_heartbeat': datetime.utcnow().isoformat(),
                'pid': os.getpid(),
                'uptime_minutes': (time.time() - _start_time) / 60,
            }, merge=True)
            return
        except Exception as e:
            if "504" in str(e) and attempt < max_attempts - 1:
                wait = (2 ** attempt) * 2 + random.uniform(0, 1)
                print(f"[HEARTBEAT] 504, retrying in {wait:.1f}s (attempt {attempt + 2}/{max_attempts})")
                time.sleep(wait)
            else:
                print(f"[HEARTBEAT] Failed to write: {e}")
                return


_start_time = time.time()


def start_heartbeat_monitor(interval: int = 300):
    """Start heartbeat writer in a background thread."""
    import threading

    def _heartbeat_loop():
        while True:
            write_heartbeat()
            time.sleep(interval)

    thread = threading.Thread(target=_heartbeat_loop, daemon=True)
    thread.start()
    print(f"[HEARTBEAT] Monitor started (interval: {interval}s)")
    return thread


def check_stale_heartbeat(threshold_minutes: int = 15) -> bool:
    """Check if the current agent heartbeat is stale."""
    try:
        db = get_firestore_client()
        doc = db.collection('system').document('heartbeat').get()
        if doc.exists:
            data = doc.to_dict()
            last = data.get('last_heartbeat', '')
            if last:
                last_dt = datetime.fromisoformat(last)
                age = (datetime.utcnow() - last_dt).total_seconds() / 60
                return age > threshold_minutes
        return False
    except Exception:
        return False
