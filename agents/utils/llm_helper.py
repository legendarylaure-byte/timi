import os
import time
import json as _json
from pathlib import Path

import httpx
from crewai.llm import LLM
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

_forced_provider = None  # None = auto-route, "ollama" = force ollama, "gemini" = force gemini
_gemini_cooldown_until = 0.0
_ollama_verified = False
_ollama_verified_at = 0.0
_OLLAMA_CACHE_TTL = 60
_consecutive_gemini_failures = 0
_MAX_GEMINI_FAILURES = 3
_GEMINI_COOLDOWN_SECONDS = 120

AGENT_LLM_ROUTES = {}
OLLAMA_MODEL_ROUTES = {}


def _parse_agent_routes():
    raw = os.getenv("AGENT_LLM_ROUTES", "{}")
    if raw != "{}":
        try:
            import json
            routes = json.loads(raw)
            AGENT_LLM_ROUTES.update(routes)
            print(f"[LLM] Agent routes loaded: {routes}")
        except Exception as e:
            print(f"[LLM] Failed to parse AGENT_LLM_ROUTES: {e}")


def _parse_model_routes():
    raw = os.getenv("OLLAMA_MODEL_ROUTES", "{}")
    if raw != "{}":
        try:
            import json
            routes = json.loads(raw)
            OLLAMA_MODEL_ROUTES.update(routes)
            print(f"[LLM] Ollama model routes loaded: {routes}")
        except Exception as e:
            print(f"[LLM] Failed to parse OLLAMA_MODEL_ROUTES: {e}")


_parse_agent_routes()
_parse_model_routes()


def verify_ollama_model(model: str = None) -> bool:
    global _ollama_verified, _ollama_verified_at
    now = time.monotonic()
    # cache shortcut only applies to the default model check (model is None)
    if model is None and _ollama_verified and (now - _ollama_verified_at) < _OLLAMA_CACHE_TTL:
        return _ollama_verified
    model = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    total = int(os.getenv("OLLAMA_VERIFY_RETRIES", "8"))
    interval = float(os.getenv("OLLAMA_VERIFY_INTERVAL", "6"))
    for attempt in range(total):
        try:
            r = httpx.get(f"{base}/api/tags", timeout=8)
            if r.status_code == 200:
                names = [m.get("name", "") for m in r.json().get("models", [])]
                if model in names or any(model in n for n in names):
                    _ollama_verified = True
                    _ollama_verified_at = now
                    return True
                print(f"[LLM] Model '{model}' not found in Ollama. Available: {names[:5]}")
                _ollama_verified = False
                _ollama_verified_at = now
                return False
        except Exception as e:
            if attempt < total - 1:
                print(f"[LLM] Ollama attempt {attempt+1}/{total} failed: {e}, retrying in {int(interval)}s...")
                time.sleep(interval)
            else:
                print(f"[LLM] Ollama not reachable after {total} attempts: {e}")
    _ollama_verified = False
    _ollama_verified_at = now
    return False


def force_fallback(failed_provider: str = "ollama"):
    global _forced_provider, _gemini_cooldown_until
    if failed_provider == "ollama":
        _forced_provider = "gemini"
        print("[LLM] Ollama failed → forcing Gemini fallback")
    else:
        _forced_provider = "ollama"
        _gemini_cooldown_until = time.monotonic() + _GEMINI_COOLDOWN_SECONDS
        print("[LLM] Gemini failed → forcing Ollama fallback")


def reset_fallback():
    global _forced_provider, _gemini_cooldown_until, _ollama_verified, _ollama_verified_at
    _forced_provider = None
    _gemini_cooldown_until = 0.0
    _ollama_verified = False
    _ollama_verified_at = 0.0
    print("[LLM] Fallback reset — auto-routing restored")


def empty_response_fallback():
    # ponytail: Ollama returns EMPTY (not an exception) when it's memory-starved on the
    # shared 16GB M5 box during LTX rendering. 'reset_fallback' alone never leaves Ollama
    # because it isn't DOWN — so rotate to Gemini for the next attempt, and back to Ollama
    # once it recovers. This is the decisive fix for the 45 empty-response failures.
    global _forced_provider
    if _forced_provider == "gemini":
        _forced_provider = "ollama"
        print("[LLM] Empty response while on Gemini — rotating back to Ollama")
    else:
        _forced_provider = "gemini"
        print("[LLM] Ollama returned empty response → forcing Gemini fallback")


def _ollama_model_for(agent_id: str | None = None) -> str:
    if agent_id and agent_id in OLLAMA_MODEL_ROUTES:
        return OLLAMA_MODEL_ROUTES[agent_id]
    return os.getenv("OLLAMA_MODEL", "qwen2.5:7b")


def _get_ollama_llm(temperature: float, max_tokens: int, agent_id: str | None = None) -> LLM:
    model = _ollama_model_for(agent_id)
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    print(f"[LLM] Using Ollama ({model})")
    return LLM(
        model=f"ollama/{model}",
        base_url=base,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _get_gemini_llm(temperature: float, max_tokens: int) -> LLM:
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    print(f"[LLM] Using Gemini ({gemini_model})")
    from utils.gemini_llm import GeminiLLM
    return GeminiLLM(
        model=gemini_model,
        api_key=gemini_key,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _record_gemini_failure():
    global _consecutive_gemini_failures
    _consecutive_gemini_failures += 1
    if _consecutive_gemini_failures >= _MAX_GEMINI_FAILURES:
        print(f"[LLM] {_consecutive_gemini_failures} consecutive Gemini failures — forcing fallback to Ollama")
        force_fallback(failed_provider="gemini")


def _reset_gemini_failures():
    global _consecutive_gemini_failures
    _consecutive_gemini_failures = 0


def _try_gemini_or_none(temperature: float, max_tokens: int) -> LLM | None:
    try:
        llm = _get_gemini_llm(temperature, max_tokens)
        _reset_gemini_failures()
        return llm
    except Exception as e:
        print(f"[LLM] Gemini unavailable: {e}")
        _record_gemini_failure()
        return None


def _get_routed_provider(agent_id: str | None) -> str | None:
    if _forced_provider:
        return _forced_provider
    if agent_id and agent_id in AGENT_LLM_ROUTES:
        return AGENT_LLM_ROUTES[agent_id]
    if AGENT_LLM_ROUTES.get("*"):
        return AGENT_LLM_ROUTES["*"]
    return None


def _gemini_on_cooldown() -> bool:
    return time.monotonic() < _gemini_cooldown_until


def get_llm(temperature: float = 0.7, max_tokens: int = 2000, agent_id: str = None) -> LLM:
    routed_provider = _get_routed_provider(agent_id)
    if routed_provider:
        print(f"[LLM] Agent '{agent_id or '*'}' routed to '{routed_provider}'")
        if routed_provider == "ollama":
            if verify_ollama_model(_ollama_model_for(agent_id)):
                return _get_ollama_llm(temperature, max_tokens, agent_id)
            print("[LLM] Ollama unavailable, trying Gemini fallback")
            result = _try_gemini_or_none(temperature, max_tokens)
            if result:
                return result
            raise RuntimeError("No LLM available: Ollama down, Gemini also failed")
        elif routed_provider == "gemini":
            if _gemini_on_cooldown():
                print("[LLM] Gemini on cooldown, trying Ollama")
                if verify_ollama_model(_ollama_model_for(agent_id)):
                    return _get_ollama_llm(temperature, max_tokens, agent_id)
                raise RuntimeError("No LLM available: Gemini cooldown, Ollama also down")
            result = _try_gemini_or_none(temperature, max_tokens)
            if result:
                return result
            print("[LLM] Gemini unavailable, trying Ollama fallback")
            if verify_ollama_model(_ollama_model_for(agent_id)):
                return _get_ollama_llm(temperature, max_tokens, agent_id)
            raise RuntimeError("No LLM available: Gemini down, Ollama also down")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key and not _gemini_on_cooldown():
        result = _try_gemini_or_none(temperature, max_tokens)
        if result:
            return result
        print("[LLM] Gemini unavailable, trying Ollama")

    if verify_ollama_model(_ollama_model_for(agent_id)):
        return _get_ollama_llm(temperature, max_tokens, agent_id)

    if gemini_key and not _gemini_on_cooldown():
        result = _try_gemini_or_none(temperature, max_tokens)
        if result:
            return result

    raise RuntimeError("No LLM available: Ollama model not found, no GEMINI_API_KEY")
