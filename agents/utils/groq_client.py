import os
import time
from dotenv import load_dotenv
from ollama import chat

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_consecutive_failures = 0
_last_failure_time = 0


def generate_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000) -> str:
    global _consecutive_failures

    if _consecutive_failures >= 3:
        time_since_failure = time.time() - _last_failure_time
        if time_since_failure < 60:
            print(
                f"[OLLAMA] Consecutive failures ({_consecutive_failures}), waiting {60 - time_since_failure:.0f}s before retry")  # noqa: E501
            time.sleep(60 - time_since_failure)

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

    _consecutive_failures = 0
    return response["message"]["content"]
