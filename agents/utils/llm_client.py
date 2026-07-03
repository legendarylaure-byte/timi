import time


_caller_failures: dict[str, int] = {}
_last_failure_time: dict[str, float] = {}


def generate_completion(prompt: str, system_prompt: str = "", temperature: float = 0.7, max_tokens: int = 2000, caller_id: str = "default") -> str:
    failures = _caller_failures.get(caller_id, 0)
    last_fail = _last_failure_time.get(caller_id, 0.0)

    if failures >= 3:
        time_since_failure = time.time() - last_fail
        if time_since_failure < 60:
            remaining = 60 - time_since_failure
            print(
                f"[LLM] Consecutive failures ({failures}) for '{caller_id}',"
                f" waiting {remaining:.0f}s before retry")
            time.sleep(60 - time_since_failure)

    try:
        from utils.llm_helper import get_llm
        llm = get_llm(temperature=temperature, max_tokens=max_tokens)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        result = llm.call(messages)
        _caller_failures[caller_id] = 0
        return result
    except Exception as e:
        print(f"[LLM] Failed: {e}")
        _caller_failures[caller_id] = failures + 1
        _last_failure_time[caller_id] = time.time()
        raise
