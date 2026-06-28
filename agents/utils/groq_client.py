import os
import time
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_consecutive_failures = 0
_last_failure_time = 0


def generate_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    global _consecutive_failures, _last_failure_time

    if _consecutive_failures >= 3:
        time_since_failure = time.time() - _last_failure_time
        if time_since_failure < 60:
            remaining = 60 - time_since_failure
            print(
                f"[LLM] Consecutive failures ({_consecutive_failures}),"
                f" waiting {remaining:.0f}s before retry")
            time.sleep(60 - time_since_failure)

    try:
        result = _ollama_completion(prompt, system_prompt, temperature, max_tokens)
        _consecutive_failures = 0
        return result
    except Exception as e:
        print(f"[OLLAMA] Failed: {e}")
        if GEMINI_API_KEY:
            print(f"[LLM] Falling back to Gemini ({GEMINI_MODEL})")
            try:
                result = _gemini_completion(prompt, system_prompt, temperature, max_tokens)
                _consecutive_failures = 0
                return result
            except Exception as gemini_e:
                print(f"[GEMINI] Failed: {gemini_e}")
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


def _gemini_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=system_prompt if system_prompt else None,
    )
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text if response.text else ""
