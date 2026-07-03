import os
import time
from pathlib import Path

import httpx
from crewai.llm import LLM
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / '.env')

_force_next_provider = False
_ollama_verified = False
_ollama_verified_at = 0.0
_OLLAMA_CACHE_TTL = 60

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
    """Check that the configured Ollama model is actually loaded (cached for 60s)."""
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
    """Force the next get_llm() call to skip primary (Gemini) and use fallback (Ollama)."""
    global _force_next_provider
    _force_next_provider = True
    print("[LLM] Forcing fallback — next LLM will skip Gemini and use Ollama")


def reset_fallback():
    """Reset the forced fallback flag. Call after each agent step completes."""
    global _force_next_provider
    _force_next_provider = False
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


def get_llm(temperature: float = 0.7, max_tokens: int = 2000, agent_id: str = None) -> LLM:
    global _force_next_provider

    routed_provider = AGENT_LLM_ROUTES.get(agent_id) if agent_id else None
    if routed_provider:
        print(f"[LLM] Agent '{agent_id}' routed to provider '{routed_provider}'")
        if routed_provider == "gemini":
            return _get_gemini_llm(temperature, max_tokens)
        elif routed_provider == "ollama":
            return _get_ollama_llm(temperature, max_tokens)

    # Gemini is much faster than local Ollama on CPU — try it first unless forced to skip
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not _force_next_provider and gemini_key:
        return _get_gemini_llm(temperature, max_tokens)

    if verify_ollama_model():
        return _get_ollama_llm(temperature, max_tokens)

    if gemini_key:
        return _get_gemini_llm(temperature, max_tokens)

    raise RuntimeError("No LLM available: Ollama model not found, no GEMINI_API_KEY")
