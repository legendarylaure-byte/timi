# D18: Fix Remaining Issues — Publish + Stock Footage + Pipeline Hardening

## 1. Facebook Upload — API Error Handling

**File: `agents/utils/multi_platform_publisher.py`**

### Problem
Facebook returns API errors (413, 1363030 timeout) as HTTP **200 with an `error` object in JSON body**. The code checks `status_code == 200` and tries `json.get('id')` — when `id` is `None`, it says *"succeeded but no video ID returned"* instead of propagating the real Facebook error.

Also missing: 401 refresh check on resumable transfer phase, no `file_size` in error messages.

### Changes

**Replace** the entire `_do_upload()` inner function + supporting code (lines 512–622):

1. **Add `_raise_facebook_error(resp, phase)` helper** before `_do_upload`:
   ```python
   def _raise_facebook_error(resp, phase):
       body = resp.json()
       err = body.get('error')
       if err:
           msg = err.get('error_user_title', err.get('message', 'unknown'))
           code = err.get('code', '?')
           subcode = err.get('error_subcode', '')
           raise RuntimeError(f'Facebook {phase} failed: {msg} (code {code}, subcode {subcode})')
       raise RuntimeError(f'Facebook {phase} failed: HTTP {resp.status_code}')
   ```

2. **Direct upload path** (was lines 527–563):
   - After `_check_meta_rate_limit` and 401 refresh, parse `body = upload_resp.json()`
   - Check `if 'error' in body:` first — if true, raise with `err.get("error_user_title", err.get("message", "unknown"))` and `err.get("code")`, `err.get("error_subcode")`
   - Then check `body.get('id')` for success
   - Include `file_size` in the "no video ID" error: `f'(size={file_size})'`

3. **Resumable init path** (was lines 564–591):
   - Same pattern: parse `init_body = init_resp.json()`, check for `error` key first
   - Only then check `upload_session_id`

4. **Resumable transfer path** (was lines 593–622):
   - **Add** 401 refresh check (identical pattern to init path)
   - Check `chunk_body` for `error` key before checking `id`
   - Include `file_size` in error messages

## 2. Stock Footage — File Validation (asset_router.py)

**File: `agents/utils/asset_router.py`**

### Changes

1. **`_get_stock_clip()` cache retrieval** (line 22):
   - Change `if cached and os.path.exists(cached):` → `if cached and os.path.exists(cached) and os.path.getsize(cached) > 1000:`

2. **`_get_stock_clip()` download result** (lines 28–31):
   - Change `if result and os.path.exists(result):` → `if result and os.path.getsize(result) > 1000:`
   - Change `if result:` (line 32) → `if result and os.path.exists(result):`

## 3. Stock Footage — Circuit Breakers + Pexels URL + Cleanup

**File: `agents/utils/stock_video.py`**

### Changes

1. **Import circuit breakers** (near top):
   ```python
   from agents.utils.health_monitor import pexels_breaker, pixabay_breaker
   ```
   Or if import fails, define no-op fallbacks:
   ```python
   try:
       from agents.utils.health_monitor import pexels_breaker, pixabay_breaker
   except ImportError:
       from types import SimpleNamespace
       pexels_breaker = SimpleNamespace(allow_request=lambda: True, record_success=lambda: None, record_failure=lambda: None)
       pixabay_breaker = pexels_breaker
   ```

2. **Wrap Pexels API call** (`search_pexels_uncached`):
   - Before the `requests.get`, add: `if not pexels_breaker.allow_request(): return []`
   - After success: `pexels_breaker.record_success()`
   - On error: `pexels_breaker.record_failure()`

3. **Wrap Pixabay API call** (`search_pixabay_uncached`):
   - Same pattern: `if not pixabay_breaker.allow_request(): return []`
   - Record success/failure

4. **Pexels URL field fallback** (line 147):
   - Change `best.get("link", "")` → `best.get("link") or best.get("url", "")`

5. **Register CLIPS_DIR for cleanup** (after line 17):
   - Add: `register_temp_dir(str(CLIPS_DIR))`
   - Import: `from agents.utils.subprocess_helper import register_temp_dir`

## 4. Pipeline Hardening (main.py)

**File: `agents/main.py`**

### Changes

1. **Defensive `score_hook()` check** (after lines 797 and 1125):
   ```python
   if hook_score_result is None:
       hook_score_result = {"score": 0, "hook_score": 0, "approved": False,
                            "weaknesses": ["could not evaluate with llm"],
                            "suggested_alternatives": []}
   ```
   Add this after both `hook_score_result = score_hook(...)` calls.

2. **Publish failure logging** — in the retry_failure return paths, log `file_size` for debugging.
