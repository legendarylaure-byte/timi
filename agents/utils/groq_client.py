import os
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

_consecutive_failures = 0
_last_failure_time = 0


def generate_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    global _consecutive_failures, _last_failure_time

    if _consecutive_failures >= 3:
        time_since_failure = time.time() - _last_failure_time
        if time_since_failure < 60:
            print(
                f"[LLM] Consecutive failures ({_consecutive_failures}), waiting {60 - time_since_failure:.0f}s before retry")
            time.sleep(60 - time_since_failure)

    try:
        result = _ollama_completion(prompt, system_prompt, temperature, max_tokens)
        _consecutive_failures = 0
        return result
    except Exception as e:
        print(f"[OLLAMA] Failed: {e}")
        if GROQ_API_KEY:
            print(f"[LLM] Falling back to Groq ({GROQ_MODEL})")
            try:
                result = _groq_completion(prompt, system_prompt, temperature, max_tokens)
                _consecutive_failures = 0
                return result
            except Exception as groq_e:
                print(f"[GROQ] Failed: {groq_e}")
                _consecutive_failures += 1
                _last_failure_time = time.time()
                raise
        _consecutive_failures += 1
        _last_failure_time = time.time()
        raise


def _ollama_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    from ollama import chat

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = chat(
        model=OLLAMA_MODEL,
        messages=messages,
        options={
            "temperature": temperature,
            "num_predict": max_tokens,
            "keep_alive": "5m",
        },
    )
    return response["message"]["content"]


def _groq_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    return content if content is not None else ""
