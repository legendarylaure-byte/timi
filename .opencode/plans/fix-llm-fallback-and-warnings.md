# Fix: LLM Fallback + pydub Warning Suppression

## Bug 2: Ollama Fallback Missing in `get_llm()`

**File:** `utils/llm_helper.py`

**Problem:** `get_llm()` calls `_get_gemini_llm()` at lines 106, 113, 119 without catching `ImportError`. When `google-genai` package is missing, the `from google import genai` in `gemini_llm.py:2` raises `ImportError`, which propagates up uncaught — Ollama fallback is never reached.

**Fix:** Add a helper `_try_gemini_or_none()` and wrap all three `_get_gemini_llm()` calls:

```python
def _try_gemini_or_none(temperature: float, max_tokens: int) -> LLM | None:
    try:
        return _get_gemini_llm(temperature, max_tokens)
    except ImportError:
        print("[LLM] Gemini unavailable (google-genai not installed), falling back")
        return None
```

Then replace each `return _get_gemini_llm(...)` with:

```python
llm = _try_gemini_or_none(temperature, max_tokens)
if llm:
    return llm
# else fall through to Ollama
```

This ensures that if `google-genai` isn't installed, the pipeline auto-falls back to Ollama instead of crashing.

## Bug 3: pydub SyntaxWarnings

**File:** `main.py`

**Problem:** pydub emits 4 `SyntaxWarning: invalid escape sequence '\('` at import time. This is a known pydub issue with Python 3.13+.

**Fix:** Add suppression before pydub is imported (e.g., next to the existing PyTorch warning filter at line 9):

```python
warnings.filterwarnings("ignore", message="invalid escape sequence")
```

## Verification

1. Run `python3 -c "from utils.llm_helper import get_llm; llm = get_llm(); print(type(llm).__name__)"` without `google-genai` installed — should return Ollama LLM without crash.
2. Run `python3 main.py` (or pipeline) — pydub warnings should no longer appear.
3. Run `python3 scripts/health.py` — YouTube token expiry and LTX model status should show as warnings.
