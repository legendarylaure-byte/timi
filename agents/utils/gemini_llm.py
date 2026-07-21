import os
import time
import threading
from google import genai
from google.genai import types as genai_types
from crewai.llm import LLM
from utils.cost_tracker import log_llm_cost


GEMINI_CONTEXT_WINDOW = 1_048_576

_GEMINI_SEMAPHORE = threading.Semaphore(1)
_GEMINI_RATE_LOG: list[float] = []
_GEMINI_RATE_LOCK = threading.Lock()
_GEMINI_MAX_RPM = 10
_GEMINI_RETRYABLE_KEYWORDS = (
    "429", "503", "rate_limit", "quota", "timeout",
    "unavailable", "service_busy", "broken pipe",
    "connection reset", "connection refused",
    "connection error", "errno 32", "errno 54",
    "errno 104", "reset by peer", "eof",
)


def _wait_rate_limit():
    with _GEMINI_RATE_LOCK:
        now = time.monotonic()
        cutoff = now - 60
        _GEMINI_RATE_LOG[:] = [t for t in _GEMINI_RATE_LOG if t > cutoff]
        if len(_GEMINI_RATE_LOG) >= _GEMINI_MAX_RPM:
            wait = _GEMINI_RATE_LOG[0] + 60 - now + 1
            print(f"[GEMINI] Rate limit reached ({len(_GEMINI_RATE_LOG)} req/min), waiting {wait:.0f}s")
            return wait
        return 0


class GeminiLLM(LLM):
    def __init__(self, model=None, api_key=None, temperature=0.7, max_tokens=2000, **kwargs):
        model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self._model_name = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = genai.Client(api_key=api_key, http_options=genai_types.HttpOptions(timeout=300000))
        super().__init__(model=model, api_key=api_key, temperature=temperature, max_tokens=max_tokens, **kwargs)

    def call(self, messages, callbacks=None):
        system_instruction = None
        user_contents = []
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content", "")
            else:
                user_contents.append(msg.get("content", ""))

        prompt = "\n".join(user_contents)
        last_error = None

        wait = _wait_rate_limit()
        if wait > 0:
            time.sleep(wait)

        for attempt in range(3):
            acquired = _GEMINI_SEMAPHORE.acquire(timeout=30)
            if not acquired:
                print("[GEMINI] Could not acquire semaphore within 30s, proceeding anyway")
            try:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        system_instruction=system_instruction or None,
                        temperature=self._temperature,
                        max_output_tokens=self._max_tokens,
                    ),
                )
                with _GEMINI_RATE_LOCK:
                    _GEMINI_RATE_LOG.append(time.monotonic())
                try:
                    um = getattr(response, "usage_metadata", None)
                    if um:
                        pt = getattr(um, "prompt_token_count", 0) or 0
                        ct = getattr(um, "candidates_token_count", 0) or 0
                        log_llm_cost("gemini_call", pt, ct, self._model_name)
                except Exception:
                    pass
                return response.text if response.text else ""
            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_retryable = any(k in err_str for k in _GEMINI_RETRYABLE_KEYWORDS)
                if is_retryable:
                    delay = 2 ** (attempt + 1) if attempt > 0 else 2
                    if "broken pipe" in err_str or "connection" in err_str or "errno" in err_str:
                        delay = max(delay, 5)
                    print(f"[GEMINI] Retryable error (attempt {attempt+1}/3): {e} — waiting {delay}s")
                    time.sleep(delay)
                    continue
                print(f"[GEMINI] API call failed: {e}")
                if "api_key" in err_str or "not found" in err_str or "permission" in err_str:
                    pass
                raise
            finally:
                _GEMINI_SEMAPHORE.release()

        print(f"[GEMINI] All 3 retries exhausted: {last_error}")
        raise last_error or RuntimeError("Gemini call failed after 3 retries")

    def get_context_window_size(self) -> int:
        return GEMINI_CONTEXT_WINDOW
