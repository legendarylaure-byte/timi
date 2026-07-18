import os
import time
import json as _json
from pathlib import Path

import httpx
from crewai.llm import LLM
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

_force_next_provider = False
_gemini_cooldown_until = 0.0
_ollama_verified = False
_ollama_verified_at = 0.0
_OLLAMA_CACHE_TTL = 60
_consecutive_gemini_failures = 0
_MAX_GEMINI_FAILURES = 3
_GEMINI_COOLDOWN_SECONDS = 120

AGENT_LLM_ROUTES = {}


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


_parse_agent_routes()


def verify_ollama_model() -> bool:
    global _ollama_verified, _ollama_verified_at
    now = time.monotonic()
    if _ollama_verified and (now - _ollama_verified_at) < _OLLAMA_CACHE_TTL:
        return _ollama_verified
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        r = httpx.get(f"{base}/api/tags", timeout=5)
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
        print(f"[LLM] Ollama not reachable: {e}")
        _ollama_verified = False
        _ollama_verified_at = now
        return False


def force_fallback():
    global _force_next_provider, _gemini_cooldown_until
    _force_next_provider = True
    _gemini_cooldown_until = time.monotonic() + _GEMINI_COOLDOWN_SECONDS
    print(f"[LLM] Forcing fallback — Gemini cooldown for {_GEMINI_COOLDOWN_SECONDS}s, using Ollama")


def reset_fallback():
    global _force_next_provider, _gemini_cooldown_until
    _force_next_provider = False
    _gemini_cooldown_until = 0.0
    print("[LLM] Fallback reset — Gemini will be primary again")


def _get_ollama_llm(temperature: float, max_tokens: int) -> LLM:
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    print(f"[LLM] Using Ollama ({model})")
    return LLM(
        model=f"ollama/{model}",
        base_url=base,
        temperature=temperature,
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
        force_fallback()


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
    if _force_next_provider:
        return "ollama"
    if agent_id and agent_id in AGENT_LLM_ROUTES:
        return AGENT_LLM_ROUTES[agent_id]
    if AGENT_LLM_ROUTES.get("*"):
        return AGENT_LLM_ROUTES["*"]
    return None


def _gemini_on_cooldown() -> bool:
    return time.monotonic() < _gemini_cooldown_until


def get_llm(temperature: float = 0.7, max_tokens: int = 2000, agent_id: str = None) -> LLM:
    global _force_next_provider

    if _force_next_provider:
        print(f"[LLM] Fallback active — skipping Gemini")
        if verify_ollama_model():
            return _get_ollama_llm(temperature, max_tokens)
        raise RuntimeError("Gemini on cooldown and Ollama unavailable")

    routed_provider = _get_routed_provider(agent_id)
    if routed_provider:
        print(f"[LLM] Agent '{agent_id or '*'}' routed to '{routed_provider}'")
        if routed_provider == "gemini":
            if _gemini_on_cooldown():
                print(f"[LLM] Gemini on cooldown, falling back to Ollama")
                if verify_ollama_model():
                    return _get_ollama_llm(temperature, max_tokens)
                raise RuntimeError("Gemini on cooldown and Ollama unavailable")
            result = _try_gemini_or_none(temperature, max_tokens)
            if result:
                return result
            print("[LLM] Gemini routed attempt failed, retrying once")
            result = _try_gemini_or_none(temperature, max_tokens)
            if result:
                return result
            print("[LLM] Gemini routed but unavailable, trying Ollama")
        elif routed_provider == "ollama":
            if verify_ollama_model():
                return _get_ollama_llm(temperature, max_tokens)
            raise RuntimeError("Ollama routed but unavailable")

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not _force_next_provider and gemini_key and not _gemini_on_cooldown():
        result = _try_gemini_or_none(temperature, max_tokens)
        if result:
            return result
        print("[LLM] Gemini unavailable, trying Ollama")

    if verify_ollama_model():
        return _get_ollama_llm(temperature, max_tokens)

    if gemini_key and not _gemini_on_cooldown():
        result = _try_gemini_or_none(temperature, max_tokens)
        if result:
            return result

    raise RuntimeError("No LLM available: Ollama model not found, no GEMINI_API_KEY")
