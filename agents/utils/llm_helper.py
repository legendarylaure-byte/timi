import os
import httpx
from crewai.llm import LLM


def _groq_has_quota() -> bool:
    """Check Groq rate limit state via process-global env var."""
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return False
    if os.environ.get('GROQ_RATE_LIMITED'):
        print("[LLM] Groq previously rate-limited, skipping to Gemini")
        return False
    return True


def get_llm(temperature: float = 0.7, max_tokens: int = 2000) -> LLM:
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    try:
        r = httpx.get(f"{ollama_base}/api/tags", timeout=3)
        if r.status_code == 200:
            print(f"[LLM] Using Ollama ({ollama_model})")
            return LLM(
                model=f"ollama/{ollama_model}",
                base_url=ollama_base,
                temperature=temperature,
                max_tokens=max_tokens,
            )
    except Exception:
        pass

    groq_key = os.getenv("GROQ_API_KEY", "")
    groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    if groq_key and _groq_has_quota():
        print(f"[LLM] Ollama unavailable, falling back to Groq ({groq_model})")
        return LLM(
            model=f"groq/{groq_model}",
            api_key=groq_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        print(f"[LLM] Falling back to Gemini ({gemini_model})")
        from utils.gemini_llm import GeminiLLM
        return GeminiLLM(
            model=gemini_model,
            api_key=gemini_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise RuntimeError("No LLM available: Ollama down, Groq unavailable, no GEMINI_API_KEY")
