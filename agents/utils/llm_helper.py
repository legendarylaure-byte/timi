import os
import httpx
from crewai.llm import LLM


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
    if groq_key:
        print(f"[LLM] Ollama unavailable, falling back to Groq ({groq_model})")
        return LLM(
            model=f"groq/{groq_model}",
            api_key=groq_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise RuntimeError("No LLM available: Ollama is down and no GROQ_API_KEY is set")
