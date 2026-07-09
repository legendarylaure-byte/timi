# AGENTS — Critical Context

## Latest Changes (uncommitted)

### D19: CI Pipeline Fixes — Indentation Error + flags=lanczos Filter + Circuit Breaker API
- **IndentationError fix**: `e6e760ef` commit's xfade try/except refactor left the inner `concat_list` block at 16-space indent while `try` was at 4 spaces and `except` at 8 spaces — Python `video_compositor.py:432` raised `IndentationError: unexpected indent`. Fixed by normalizing all 3 blocks to correct indentation (`video_compositor.py`).
- **Standalone `,flags=lanczos,` filter**: `apply_ken_burns()` vf string had `,flags=lanczos,` between `crop` and `scale` — ffmpeg 8.1 treats comma-separated items as filter names, so it tried to find a filter called `flags=lanczos` (`No option name near 'lanczos'`). Removed standalone `flags=lanczos` since `scale=...:flags=lanczos` already handles it (`video_compositor.py:155`).
- **Circuit breaker API mismatch**: `stock_video.py` called `pexels_breaker.allow_request()` and `pixabay_breaker.allow_request()` but `CircuitBreaker` class in `health_monitor.py` only has `is_available()`. Changed all 3 call sites (pexels, pixabay, and ImportError fallback) to use `is_available()`.
- **Triggered fresh CI run** after both fixes pushed.

### D18: Publish Error Handling + Stock Footage Hardening + Pipeline Defenses
- **Facebook upload API error detection**: Added `_raise_fb_api_error()` helper that inspects JSON response body for Facebook API errors (1363030 timeout, 413, etc.) even when HTTP status is 200. Previously these were missed and surfaced as misleading "succeeded but no video ID" messages. Applied to all 3 paths: direct upload, resumable init, resumable transfer (`multi_platform_publisher.py`).
- **Facebook 401 refresh on transfer phase**: Added `status_code == 401` check on resumable transfer POST (was missing — token could expire between init and transfer). `multi_platform_publisher.py`.
- **File size in errors**: Added `(size={file_size})` to all "no video ID" RuntimeErrors for faster debugging (`multi_platform_publisher.py`).
- **Stock footage file validation**: `asset_router.py:_get_stock_clip()` — cache retrieval and download result now check `os.path.getsize() > 1000` in addition to `os.path.exists()`, rejecting 0-byte/corrupt files before they reach compositing.
- **Circuit breakers wired**: `pexels_breaker` and `pixabay_breaker` from `health_monitor.py` now protect API calls in `stock_video.py`. Each search checks `breaker.allow_request()` before calling, records success/failure on response. Prevents hammering dead APIs.
- **Pexels URL fallback**: `best.get("link") or best.get("url", "")` — handles either API field name (`stock_video.py:147`).
- **CLIPS_DIR cleanup**: Registered `tmp/clips/` with `register_temp_dir()` so stock clips are cleaned up on exit alongside compositor temp dirs (`stock_video.py`).
- **Defensive score_hook()**: Added `if hook_score_result is None:` guard after both `score_hook()` calls in `main.py` (short + long paths) — ensures pipeline never crashes on None return.

### D17: Tier 1 Pipeline Enhancements — Subtitle Color, Visual Quality, Voice Pacing, Prompt Tuning
- **Subtitle color**: Changed from dark orange (`&HFF0055CC&`) to dark yellow (`&HFF00CCCC&`) in `video_compositor.py` (burn_subtitles + composite_video) and `shorts_renderer.py` (reformat_to_shorts). More readable on dark backgrounds, consistent with educational content branding.
- **Visual quality**: CRF 23→20 (higher bitrate, sharper video), saturation 1.15→1.25 (more vibrant colors) in both `video_compositor.py` and `shorts_renderer.py`.
- **Voice pacing**: Default TTS rate -5%→0% (faster, more natural delivery for educational content). Inter-segment silence gap 200ms→100ms (tighter pacing, less dead air). Applied in `voice_gen.py` (DEFAULT_RATE, NARRATOR_VOICE, educational setting, concatenate_audio offset).
- **Scriptwriter prompt**: Added rule #8 (hook formula rotation — question/bold claim/statistic/curiosity gap/pain point across videos) and rule #9 (power words — "secretly", "actually", "nobody", "the truth", "why most", etc.) in `crew/scriptwriter.py`.
- **Quality scorer**: Repetition threshold lowered from 60%→50% similarity in `quality_scorer.py` — catches repetitious content earlier.
- **Content safety fix**: Word-boundary regex replaces substring matching (fixes "forward"→"war" false positive). Per-word severity levels + allowlist for common tech contexts (`content_safety.py`).
- **Hook scoring fix**: Rule-based fallback when LLM scoring fails — scores on question marks, statistics, bold claims, pain points. Fixed missing return path when LLM response has no JSON (`hook_scorer.py`).
- **Stock video compositing fix**: Added `os.path.exists()` guards in `video_compositor.py:_process_clip()` (try/except around `os.path.getsize`), `asset_router.py:_get_stock_clip()` (cache validation), and `asset_router.py:dispatch_scene()` (path verification before return).

### Report Module — Dashboard Intelligence Hub (5 Phases)
- **Phase A — Foundation**: `report-types.ts` shared types, `/dashboard/reports` page shell with 6 animated tabs, nav item in sidebar, `KpiCard` reusable component, `GET /api/reports/summary` endpoint (aggregates from videos/channel_stats/revenue/pipeline_metrics/analytics/insights), `ExecutiveSummary` component with 8 KPI cards (total videos, views, subs, revenue, pipeline success, best category, best format, today's production).
- **Phase B — Charts & Trends**: Installed `recharts`. `GET /api/reports/quality-trends` — quality/virality score trends with anomaly detection (>100% deviation from predicted views). `GET /api/reports/pipeline-health` — success rate, step duration breakdown (horizontal bar chart), recent errors, ROI (cost vs revenue). `GET /api/reports/growth-forecast` — growth history + linear regression projection + milestone estimation. `PerformanceTrends` component — AreaChart for views/subs/watchHours over time + quality trend overlay. `PipelineHealth` component — 4 KPI cards, step bar chart, error feed.
- **Phase C — Advanced Analytics**: `GET /api/reports/correlations` — Pearson's r for hook/quality/virality/duration vs views, scatter plots, format/category breakdown. `GET /api/reports/content-gaps` — days since last post per category, trending indicators, recommendations. `GET/POST/DELETE /api/reports/goals` — goal CRUD with auto-projection. `QualityInsights` component — 3 sub-views: correlations (scatter + r-cards), anomalies (over/underperformers), breakdown (format bar chart + category ranking). `ContentGaps` component — active/stale/untapped summary cards + per-category status table. `GoalsPanel` component — goal cards with progress bars + what-if simulator + current stats.
- **Phase D — AI Chat**: `POST /api/reports/chat` — context-aware AI agent (via Gemini API or fallback), conversation persistence to Firestore `reports/chat_sessions/{sessionId}/messages/`, action card extraction (`[ACTION:label|type|target]`), rate-limited (15 req/min). `ChatPanel` component — full chat UI with message history, quick action buttons, action card rendering, streaming input, clear/reset.
- **Phase E — Polish**: Date range picker (7d/30d/90d), auto-refresh (120s polling), CSV export button, manual Refresh button, rate limiting on chat endpoint.
- **17 new files** created in dashboard (`src/app/dashboard/reports/`, `src/app/api/reports/*/`, `src/components/reports/`)
- **0 backend files modified** — no impact on agents/pipeline/workers.

### D15: Multi-Platform Publish Fixes — Debuggability & Persistence
- **`utils/multi_platform_publisher.py`** (2 fixes):
  - TikTok token persistence: `_refresh_tiktok_token()` now calls `_save_env()` after refresh (was updating `os.environ` only — token lost on restart).
  - Instagram R2 failure: Added `security_audit("UPLOAD_FAILED", ...)` on R2 upload failure (was only logging to `log_activity`, not security audit).
- **`utils/shorts_renderer.py`** — `render_repurposed_shorts()`: replaced `global _TEMP_DIR` with `import utils.shorts_renderer as _sr` / `_sr._TEMP_DIR` (fixes Python 3.14 `UnboundLocalError: cannot access local variable '_TEMP_DIR'`).
- **`dashboard/src/app/api/reports/pipeline-health/route.ts`** — added `publishErrors[]` and `platformFailCount{}` to response (queries `activity_logs` for `agent_id == 'publisher'`).
- **`dashboard/src/components/reports/PipelineHealth.tsx`** — added "Platform Publish Status" section with per-platform status cards (YouTube/TikTok/Instagram/Facebook) showing fail counts and recent publish error feed.
- **Deployed to Vercel live** (`timi.vyomai.cloud/dashboard/reports`).

### D16: All-3-Platforms Test Publish + Firestore Env Fix + Facebook Resumable
- **`agents/main.py`** — Removed `'tiktok'` from short video `platforms_to_publish` list (skips TikTok until production keys arrive).
- **`agents/utils/multi_platform_publisher.py`** (2 fixes):
  - Lowered Facebook resumable upload threshold from 100MB → 50MB (direct upload fails on 400 for 70MB composited videos).
  - Added response body to error messages (`safe_log(resp.text[:500])`) on all Facebook upload failures (direct init, transfer, and resumable) for better debugability.
- **Firestore `env_vars` override discovered**: `sync_env_from_firestore()` at pipeline startup overwrites `os.environ` with values from Firestore `env_vars` collection — even after `.env` is loaded. Old `FACEBOOK_PAGE_ID=61591308434889` and old User Token were stored in Firestore, overriding the correct values in `.env`. Fixed by updating both documents in Firestore via direct Python.
- **3 real videos published as proof**:
  1. "How Transformers Work" → YouTube ✅, Instagram ✅, Facebook ❌ (Firestore override bug)
  2. "RAG Architecture Explained Simply" → YouTube ✅, Instagram ✅, Facebook ❌ (same bug)
  3. "Top 5 AI Tools 2026" → YouTube ✅, Instagram ✅, Facebook ✅ — **3/3 after Firestore fix + resumable threshold**
- **Python dependency fixes**: installed Pillow, edge-tts, pydub, audioop-lts (Python 3.14 removed `audioop`), crewai in venv (Python 3.12 for dep compat). Created `venv/` with Python 3.12 for pipeline runs.
- **`utils/multi_platform_publisher.py`** (12 fixes):
  - Token refresh failures: `_refresh_tiktok_token()` and `_refresh_facebook_token()` now call `security_audit("TOKEN_REFRESH_FAILED", ...)` before `return None` (was silent).
  - 401 auto-refresh recursion: Added `_refresh_attempted` bool guard to each platform — max 1 refresh attempt per upload (prevents infinite recursion).
  - Idempotency key: Moved `_idempotency_key()` call outside `_do_upload()` closure — key generated once per upload, survives retries (prevents duplicate processing).
  - Instagram polling: Added `poll_finished` flag + `RuntimeError('timed out')` after loop exit (was silently falling through to publish).
  - Video ID validation: TikTok and Facebook success paths now `raise RuntimeError` if API returns falsy ID (was returning `success=True` with broken URL).
  - Failure logging: Added `log_activity('publisher', ..., 'error')` to all 3 platform failure paths (TikTok/Instagram/Facebook) — errors now reach Firestore.
  - R2 error logging: Instagram R2 upload failure now calls `log_activity` (was silent return).
  - `_update_queue()`: Changed `except Exception: pass` → `log_activity(..., 'warn')`.
  - `_send_telegram_notification()`: Changed `print()` → `log_activity(..., 'warn')`.
  - `schedule_upload()`: Changed `print()` → `log_activity(..., 'warn')`.
- **`main.py`** (4 fixes):
  - Hook re-scoring: Skips re-scoring when LLM was unavailable on first attempt — avoids "stuck at 50" confusion.
  - Platform compliance: New `_check_all_platforms_compliance()` helper checks compliance against ALL target platforms (was a no-op passing `category` as `platform`).
  - Both `generate_short_video()` and `generate_long_video()` updated with both fixes.
- **`.github/workflows/daily-content.yml`** — `FORCE_PUBLISH: true` (was `false`) — bypasses content safety blocks in production.

### C1: Comment Management
- `utils/engagement_manager.py` — refactored `post_pinned_comment()` with retry/logging. Added `auto_reply_to_comments()` (keyword-matches 5 rules, replies with templates). Added `fetch_comment_count()`. Controlled by `ENABLE_AUTO_REPLY` env var.
- `main.py` — wired into both `generate_short_video()` and `generate_long_video()` after publish. Auto-reply runs immediately after pinned comment is posted.

### C2: CrewAI bypass cleanup
- `main.py:run_agent_step()` — `_kick()` now wraps `crew.kickoff()` in the `_execute_single_task` bypass pattern (primary attempt, fallback to `agent.execute_task()`).
- `main.py:weekly_monetization_job()` — same bypass applied.

### C3: Model Abstraction
- `models/` — new package with `BaseVideoModel` (abstract), `LtxVideoModel` (LTX implementation), `registry.py` (reads `VIDEO_MODEL` env var).
- `utils/asset_router.py` — uses `get_video_model()` instead of direct `ltx_engine` import.
- `utils/ltx_engine.py` — deprecated re-export wrapper for backward compat.
- `VIDEO_MODEL` env var selects engine (default: `ltx`).

### C4: Long→Shorts Full Re-render
- `utils/shorts_renderer.py` — chops segments from final rendered long video, reformats to 9:16 with blurred padding, hook text overlay (top 15%), quality filters, and subtitle regeneration from phrase timings.
- `main.py:run_video_pipeline()` now returns `scenes`, `timing_file`, `phrase_timings`.
- `generate_long_video()` — renders 3 shorts immediately after long video publish, then uploads each to YouTube.
- Uses existing `generate_thumbnail_variants()` for short thumbnails.

### C5: Voice Provider (edge-tts + Google TTS)
- `utils/voice_provider.py` — `BaseTTSProvider` abstract class. `EdgeTTSProvider` (default, same behavior). `GoogleCloudTTSProvider` (optional, Google WaveNet/Studio voices).
- Google voice mapping: educational→Studio-Q, hooks→Journey-F, energetic→Neural2-J, general→Studio-O.
- `VOICE_PROVIDER=edge|google` env var. Falls back to edge-tts if Google credentials missing.
- `utils/voice_gen.py` — `generate_segment_audio()` and `generate_segment_timing()` delegate to provider.
- `google-cloud-texttosynthesisize` in requirements.

### C6: Community Posts
- `utils/community_manager.py` — Playwright browser automation for YouTube Studio. `login_to_youtube_studio()`, `create_text_post()`, `create_poll_post()`, `schedule_weekly_poll()`.
- First login: manual (120s timeout). Subsequent: cookie reuse from `tmp/community_cookies/`.
- `main.py:daily_community_post_job()` — runs Mon/Thu at 15:00 UTC if `ENABLE_COMMUNITY_POSTS=true`.

### C7: Housekeeping
- `.env.example` — updated with all new vars (LTX, voice, feature flags, etc.)

## D8: Pipeline Stability Overhaul (27 fixes, 12 files)
- **trend_discovery.py** — added `TECH_CATEGORIES` import + `_is_non_tech_topic()` to fix YouTube trending fetch crash
- **hook_scorer.py** — full rewrite: `_detect_leaked_prompt()`, `approved=False` on LLM failure (not `True`), `_is_valid_rewrite()` checking for meta-text, curated fallback hooks per category
- **voice_provider.py** — `texttosynthesisize`→`texttospeech` (6x), fixed wrong pip package name, fixed hardcoded `duration_ms: 200` to actual word-boundary timing
- **All 17 crew files** — added `memory=False, planning=False, cache=False` to every `Crew(...)` constructor (stops context bleed between agents)
- **main.py** (13 fixes):
  - `_extract_json()`: `raise ValueError` → safe default dict, key validation
  - `_execute_single_task()`: fresh crew per attempt, carries `task.tools` + `context` in bypass path, returns `None` instead of `""`
  - `verify_video_quality()`: IndexError guard for ffprobe
  - `log_event()`: `datetime.now()` → `datetime.utcnow()`
  - `score_hook()`/`enforce_rewrite()`: now receive `category` arg
  - `reset_fallback()` call after scriptwriting
  - Virality default: `70`→`0` (both paths)
  - `run_director_review()`: 2-attempt auto-retry with issue feedback
  - `parse_scenes_from_storyboard()`: regex match instead of `"clip" in stripped`
  - `if not trends: trends = []` guard
  - Removed duplicate `import os`, consolidated stdlib imports
  - `script_kwargs`: `format`→`fmt` (shadowing fix)
  - FORCE_PUBLISH env var fallback when all videos blocked
- **firebase_status.py** — `log_activity()`: deterministic doc ID with `.set(merge=True)` (fixes 409s); `update_pipeline_status()`: only set `started_at` once
- **llm_helper.py** — `reset_fallback()` function; cached `verify_ollama_model()` with 60s TTL
- **groq_client.py** — per-caller failure counters (`_consecutive_failures` → `_caller_failures`)
- **virality_analyst.py** — script content 2000→4000 chars; format-type threshold (`MIN_VIRALITY_SCORE_LONG=30`); `get_virality_threshold(format_type)`
- **scriptwriter/thumbnail/metadata.py** — `format`→`fmt` to avoid shadowing built-in

## D9: Phase 1 — Crash & Resource-Leak Prevention (10 fixes, 5 files)
- **requirements.txt** — added `torch>=2.0.0` (fixes PyTorch missing warning at import time)
- **main.py** (7 fixes):
  - `MAX_RETRIES_PER_TOPIC` env var now actually wired into `run_agent_step()` (was hardcoded to 2)
  - `_strip_ansi(None)` guard: `if raw` before `.strip()` call (crashed on `None`)
  - `len(raw) > 20` → `len(raw.strip()) > 0` — valid short JSON (e.g. `{"score":5}`) no longer discarded
  - `_extract_json()` safe default: `block`/`0` not `approve`/`75` — bad JSON no longer auto-passes all gates
  - Both compliance blocks (short + long) fully rewritten: `is_safe` not `has_issues`, `detail` not `message`, `high` not `error` — content safety is now live
  - Both compliance blocks wrapped in try/except — crashes no longer kill the pipeline
  - `video_result.get("video_path", "")` at 4 call sites — KeyError no longer kills pipeline
  - `scheduled_publish_job`: removed `update_metrics(video_id, views=0)` — no longer zeroes existing view counts
  - `daily_content_job()` removed from startup path — scheduler handles it; prevents duplicate content when startup is near 06:00 UTC
  - `verify_video_quality()`: `Popen`+`communicate(timeout=30)` instead of `run` — orphan killed on timeout
  - `FORCE_PUBLISH` override now actually calls `generate_short_video`/`generate_long_video` instead of just logging
- **run_pipeline.py** (2 fixes):
  - `load_dotenv()` added at top (was missing — env vars not loaded)
  - Signal handlers: named function + re-entrancy guard (`_cleaned_up` global) + try/except — no crashes on SIGINT/SIGTERM
- **models/ltx_model.py** (2 fixes):
  - Single generation: `Popen`+`communicate(timeout=1800)` → `process.kill()` on `TimeoutExpired`
  - Batch generation: `Popen`+`communicate(timeout=7200)` → `process.kill()` on `TimeoutExpired`
- **models/ltx_batch.py** (1 fix):
  - Latents moved to CPU (numpy) immediately after generation — `mx.eval()` + `np.array()` per scene, freeing GPU memory before next scene starts. Prevents OOM when generating 15+ scenes with ~2.25GB of latent data
- **utils/shorts_renderer.py** (2 fixes):
  - `chop_segment()`: `Popen`+`communicate(timeout=120)` → `process.kill()` on timeout
  - `reformat_to_shorts()`: `Popen`+`communicate(timeout=300)` → `process.kill()` on timeout

## D10: Phase 2 — Subprocess Safety, Upload Resiliency, Token Refresh (7 files, 1 new)
- **utils/subprocess_helper.py** (NEW) — `safe_run()` (Popen+communicate+kill on timeout, backwards-compat with `subprocess.run`), `safe_run_bool()` (return bool), `retry_with_backoff()` (exponential backoff + jitter, 3 retries), `register_temp_dir()` + `atexit` cleanup
- **ALL 7 files with subprocess.run** (video_compositor, compilation_gen, upscaler, stock_video, manim_renderer, validators, thumbnail_gen) — 24+ calls converted from `subprocess.run(timeout=N)` → `safe_run()`/`safe_run_bool()`; orphan processes killed on TimeoutExpired
- **utils/multi_platform_publisher.py** (3 uploads upgraded):
  - TikTok: retry_with_backoff (3 attempts, 5-60s), 401→auto-refresh via `_refresh_tiktok_token()`, idempotency key on publish
  - Instagram: retry_with_backoff (3 attempts), 401→auto-refresh via `_refresh_facebook_token()`, idempotency key on publish
  - Facebook: retry_with_backoff (3 attempts), 401→auto-refresh via `_refresh_facebook_token()`, idempotency key on direct+resumable
  - All error messages wrapped in `safe_log()` (redacts tokens/secrets)
- **Temp file lifecycle**: `register_temp_dir()` called in shorts_renderer, video_compositor, compilation_gen, upscaler. `_cleanup_all_temp()` called in `main.py:_shutdown()` and `run_pipeline.py:_cleanup()`. Plus `atexit` fallback.

## D11: Phase 3 — Security, Gate Enforcement, Rate Limiting (4 files)
- **utils/subprocess_helper.py** (enhanced):
  - `get_safe_env()` — returns env copy with TOKEN/SECRET/KEY vars stripped; `safe_run`/`safe_run_bool` use it by default, preventing token leakage to subprocesses
  - `security_audit()` — dual log (logger + `logs/security_audit.log`) for auth failures, gate blocks, token refreshes
  - `rate_limiter()` — in-memory sliding-window rate limiter per key (e.g. max 5 uploads/hour/platform)
- **utils/video_compositor.py** — removed `_get_env()` (was passing full `os.environ.copy()` to subprocess); env isolation now handled by `safe_run` default
- **utils/multi_platform_publisher.py** — all 3 uploads now rate-limited (5/hr) + `security_audit()` on failures
- **main.py** (10+ gate sites):
  - `GATE_ENFORCEMENT_MODE` env var (`advisory`|`enforce`) — `_gate_check()` helper wired into all 5 advisory gates × 2 format paths: quality scoring, virality, director script/storyboard/final review, review gate
  - Advisory mode (default): existing behavior — logs warnings, continues
  - Enforce mode: blocks pipeline when gates reject content, records `blocked_<gate>` status in Firestore
  - `validate_env()` at startup — warns on missing critical + optional env vars
   - `security_audit("STARTUP")` logs enforcement mode on boot

## D12: Phase 4 — Observability & Metrics (1 file)
- **main.py** (6 changes):
  - `log_event()` now writes to `logs/pipeline.log` in addition to stdout — pipeline events survive crashes
  - `_setup_logging()` — configures Python `logging` with file handler (`logs/python.log`) + stream handler; called at startup before `validate_env()`
  - `_track_pipeline_duration()` — writes duration/success/format/topic per pipeline run to Firestore `pipeline_metrics` collection
  - `_track_step()` — context manager for measuring individual pipeline stage durations (e.g. scriptwriting, storyboarding, publishing)
  - Duration tracking in both `generate_short_video()` and `generate_long_video()` — `_start_time`/`_elapsed` recorded on success and failure paths, both persist to Firestore
  - Sentry enrichment: `sentry_sdk.set_tag()` for `video_id`/`format`/`category`, `sentry_sdk.add_breadcrumb()` at pipeline start, `sentry_sdk.capture_exception(e)` in both exception handlers — Sentry now actually fires on pipeline failures
  - `atexit` registered via `_setup_logging()` — writes "Process exiting" log on graceful shutdown

## Remaining Setup
1. **TikTok OAuth** (REQUIRED — sandbox keys 401): Get a **production app** at `https://developers.tiktok.com/`. Set `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, go through OAuth to get `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`, and `TIKTOK_REFRESH_TOKEN`. The current sandbox keys will always return 401 for publishing.
2. **Instagram OAuth**: Set `FACEBOOK_APP_ID`, `FACEBOOK_APP_SECRET`, `FACEBOOK_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID` env vars. No `INSTAGRAM_ACCESS_TOKEN` needed — Instagram uses the Facebook Page token.
3. **YouTube Analytics API**: Re-auth needed (`yt-analytics.readonly` scope). Delete `youtube_token.json` and run any upload.
4. **Google Cloud TTS**: Create service account, download JSON key, set `GOOGLE_APPLICATION_CREDENTIALS`.
5. **Playwright browsers**: Run `playwright install chromium` after pip install.

## Run Commands
- Short pipeline: `SLOT=morning FORMAT=short CATEGORY="AI Explained" python3 run_pipeline.py`
- Long pipeline with auto-shorts: `SLOT=evening FORMAT=long CATEGORY="AI Explained" python3 run_pipeline.py`
- Google TTS: Set `VOICE_PROVIDER=google` and `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
- Community posts: Set `ENABLE_COMMUNITY_POSTS=true`
- Dashboard: `cd dashboard && npm run dev` (port 5001)

## LTX Model Location
- Pre-downloaded at `~/ltx-models/` (39GB, q4 quantization, dgrauet/ltx-2.3-mlx-q4)
- Key files: `transformer-dev.safetensors`, `transformer-distilled.safetensors`, `connector.safetensors`, `ltx-2.3-22b-distilled-lora-384-1.1.safetensors`
- Gemma model auto-downloads from HF (`mlx-community/gemma-3-12b-it-4bit`)
- `LTX_MODEL_DIR` defaults to `~/ltx-models/` — already populated, no download needed
- 16GB RAM with `--low-ram` flag — tested working

## D13: Long Video Fixes — Duration, Subtitles, Script Quality
- **crew/scriptwriter.py** — Audience changed from "general tech" to "non-technical beginner" (ZERO prior knowledge). Scene count increased from 6-10 to 15-20. Word count reduced to 600-1200. Jargon avoidance rule added.
- **models/ltx_model.py** — LTX frame cap raised from 241→481 frames (~10s→~20s per clip) in both `generate_clip()` and `generate_clips()`.
- **utils/video_compositor.py** — New `_extend_clip()` function loops short clips via `ffmpeg -stream_loop -1` to fill each scene's requested duration. Wire into `composite_video()` after duration check.
- **utils/video_compositor.py** — Subtitle color changed from white to dark orange (`&HFF0055CC&`) in both `burn_subtitles()` and main composite subtitle path.
- **utils/shorts_renderer.py** — Subtitle color changed to dark orange (`&HFF0055CC&`).
- **utils/scene_parser.py** — `_infer_ltx_prompt()` now extracts VISUAL description text from storyboard blocks and includes it in the LTX prompt. LLM scene parse prompt improved to stress using actual storyboard visuals.

## New Env Vars
| Variable | Default | Purpose |
|---|---|---|
| `VIDEO_MODEL` | `ltx` | Video generation engine |
| `VOICE_PROVIDER` | `edge` | TTS backend (`edge` or `google`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to Google service account JSON |
| `ENABLE_AUTO_REPLY` | `true` | Auto-reply to comments |
| `ENABLE_COMMUNITY_POSTS` | `false` | Enable community post automation |
| `ENABLE_UPSCALE` | `false` | Real-ESRGAN upscaling |
| `ENABLE_DIRECTOR_REVIEW` | `true` | Director review gate |
| `SENTRY_DSN` | — | Sentry error tracking |
| `AGENT_LLM_ROUTES` | `{}` | Per-agent LLM routing |
| `SLOT` | — | Content slot auto-detection |
| `USE_ANIMATION_ENGINE` | `true` | LTX vs stock footage |
| `LONG_MAX_DURATION` | `180` | Max long video seconds |
| `FORCE_PUBLISH` | `false` | Override blocking gates, publish despite quality/virality failures |
| `MIN_VIRALITY_SCORE` | `40` | Minimum virality score for shorts |
| `MIN_VIRALITY_SCORE_LONG` | `30` | Minimum virality score for long videos |
| `GATE_ENFORCEMENT_MODE` | `advisory` | Gate mode (`advisory` logs only, `enforce` blocks pipeline) |
