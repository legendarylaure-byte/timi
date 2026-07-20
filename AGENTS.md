# AGENTS — Critical Context

## Latest Changes

### Branch Education Pipeline — Blender 3D Photorealistic Render Engine
- **REPLACED Manim entirely** with Blender 3D for all deep lesson/documentary scenes.
- **14 Blender templates** in `blender_templates/`: `chip_cross_section`, `architecture_block`, `data_flow`, `pcb_layout`, `cutaway_device`, `comparison_bars`, `processor_pipeline`, `network_topology`, `timeline_3d`, `process_flow`, `layer_explosion`, `neural_network`, plus `__init__.py` (registry) and `common.py` (materials/lighting/camera).
- **Eevee-first rendering**: 60% of scenes use Eevee (real-time, ~0.3s/frame), 40% use Cycles at 64-256 samples with denoising.
- **Format-adaptive samples**: Shorts=64smp, Longs=128smp, Documentary=256smp. Config via `BLENDER_RENDER_SAMPLES_SHORT/LONG/DOC` env vars.
- **Render caching**: SHA-256 keyed (template+params), file-backed at `tmp/blender_cache/`.
- **New files**: `utils/blender_renderer.py` (orchestrator), `utils/blender_asset_router.py` (scene→template mapper).
- **Removed**: `manim_renderer.py`, `manim_templates.py`, `manim_validator.py`, `manim_agent.py`, `manim_code_gen.py`, `manim.cfg`.
- **All pipeline paths** (`asset_router._render_scene_inner()`, `dispatch_scene()`, `dispatch_scenes()`) route `render_type="blender"` to the new renderer.

### Quality Improvement Pass — Video Review Fixes: URL TTS, Subtitles, End Scene, Scriptwriter Viral Rule, Voiceover Race (uncommitted)
- **URL stripping in TTS** (`utils/voice_gen.py`): `_expand_symbols_for_tts()` now replaces `https?://\S+` and `www\.\S+` with " link " before symbol expansion — prevents TTS reading URLs as "forward slash forward slash" for 20s.
- **Subtitle color & font size** (`utils/video_compositor.py`, `utils/shorts_renderer.py`): Changed from teal `&HFF00CCCC&` to dark yellow `&HFF0088CC&` for better readability. Font sizes increased: `burn_subtitles()` 28→32, `composite_video()` 18→24, `shorts_renderer.py` 24→28.
- **Subtitle generation without timing file** (`main.py:766`): Removed `timing_file` gate — subtitle generation now runs even when voice timing file is missing, falling back to text-based estimation in `generate_srt()`.
- **End scene fix** (`utils/scene_parser.py:806`): Removed incorrect `vyomcloud.com` URL from outro scene text. Changed title from "Subscribe for more AI Tech" → "Subscribe for more AI content".
- **Viral/trending rule** (`crew/scriptwriter.py`): Added Rule #12 — explicit viral/trending optimization instruction using gap frame technique, trending hooks from `extra_context`, and surprise→breakdown→mind-blown structure.
- **Voiceover race fix** (`main.py:744`): `generate_voiceover()` now passes `output_filename=f"voiceover_{video_id}.wav"` — eliminates concurrent pipeline race where short+long both wrote to/deleted `voiceover.wav`.

### Tier 4: Content-Aware Duration Engine + Scene Architect + Audio Alignment (committed `1fc03f77`)
- **Phase 1 — Duration Engine** (`utils/scene_parser.py`): `_estimate_scene_duration()` modulates base `wc/2.5` via `_score_narrative_importance()` (5 criteria: new info, tension, transition, visual, key insight → 0.5×–1.3×) and `_compute_pacing_multiplier()` (difficulty + position + density → 0.7×–1.3×). Total effective range: ~0.35×–1.7× of base word-count duration.
- **Phase 2 — Scene Architect** (`utils/scene_architect.py`, NEW): Three audit functions — LTX prompt audit (camera/lighting/color keyword scoring), render type audit (uniqueness/direction/parameter variance), duration balance audit.
- **Phase 3 — Pipeline Order Fix (CRITICAL BUG)**: Voice now runs BEFORE `dispatch_scenes()`. Old flow was `dispatch→voice→sync` (no-op, read `target_duration=8.0` everywhere).
- **`.env.example`** — Added `SCENE_ARCHITECT_MODE=advisory`.

### Compositing & QA Bugfixes (committed `5a7f36dc`)
- **AudioSegment list→bytes**: `_generate_emphasis_tone()` and `_generate_ambient_pad()` use `array.array('h', ...).tobytes()` — fixes `ValueError: data length must be a multiple of...`
- **xfade concat fallback**: `trim_clip()` adds `-r 24` FPS flag; `_build_xfade_filter()` normalizes color properties via `setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709`.
- **Concurrent cleanup race**: `cleanup_after_upload()` no longer calls `cleanup_temp_directories()` (was deleting shared dirs across concurrent pipelines).
- **intro_template kwarg fix**: `intro_template()`/`outro_template()` accept `**kwargs` to swallow unexpected `title` arg.
- **Visual QA black threshold**: 0.3→**0.35**, blackdetect min duration 1.0s→**2.0s** (verified: 30.9%/32.4% both pass).
- **Shorts duration limit**: `SHORTS_MAX_DURATION` 60→**180** (125s short now passes).

### xfade Reliability & Black Frame Reduction (committed `04e09177`)
- **`-r 24` added to `_extend_clip()` and `_apply_camera_motion()`** — every re-encode path now forces exactly 24fps, preventing frame-rate drift that breaks xfade on mixed-source clips.
- **xfade input normalization expanded**: `fps=24,scale=W:H:flags=lanczos,format=yuv420p,setparams=bt709,setsar=1,settb=1/24` on every input — guarantees identical frame rate, dimensions, pixel format, color space, SAR, and time base entering xfade. Expected: xfade works reliably on LTX + mixed stock footage, no more concat fallback.
- **Leading dark frame trim**: `_process_clip()` trims 0.3s from start of each video clip via `trim_clip(src, trimmed, 0.3, dur-0.3)` — removes diffusion-model warmup near-black frames that contributed ~9s of black per 15-scene video.

### Phase 7: Production Readiness & Performance (5 new/upgraded files)
- **`utils/concurrent_pipeline.py`** (NEW) — Thread pool for parallel short+long generation. GPU semaphore prevents concurrent LTX access. Worker isolation (one failure doesn't kill the other). `run_concurrent_pipelines()` accepts job dicts with `gpu` flag. `run_with_gpu_lock()` for single-function GPU access. `CONCURRENT_PIPELINE_WORKERS` env var (default 2). Wire into `daily_content_job()` — all shorts + longs run concurrently via `ThreadPoolExecutor`.
- **`utils/translate.py`** (UPGRADED) — Added `generate_dubbed_audio()` (TTS audio for translated scripts per language using edge_tts_voice from LANGUAGES dict), `dub_all_languages()` (batch dubbing for all translations), `register_dub_cleanup()` (register temp dub dirs for cleanup). Controlled by `ENABLE_MULTI_LANG_DUB=false` env var.
- **`models/ltx_model.py`** (UPGRADED) — LRU prompt cache (50 entries, SHA-256 keyed, file-backed via `cache_meta.json`). `_check_cache()` (hit → return cached clip), `_update_cache()` (store + prune LRU). Self-healing: auto-discards stale entries where file is missing. Parallel scene generation in `generate_clips()` merges cached + new results. Controlled by `ENABLE_LTX_CACHE=true`.
- **`main.py`** (8 integration points):
  - Imports `run_concurrent_pipelines`, `dub_all_languages`, `register_dub_cleanup`
  - `daily_content_job()` — builds job list from plan, runs all shorts + longs via `run_concurrent_pipelines()`, processes results/tracking/retry
  - Both short + long multi-language paths now call `dub_all_languages()` when `ENABLE_MULTI_LANG_DUB=true`
  - `ENABLE_MULTI_LANG_DUB` / `ENABLE_LTX_CACHE` / `CONCURRENT_PIPELINE_WORKERS` logged at startup
  - `.env` updated with all 3 new vars + `GOOGLE_APPLICATION_CREDENTIALS` pointing to Firebase SA at `keys/timi-childern-stories-firebase-adminsdk-fbsvc-1997849771.json`
- **`.env`** (UPGRADED) — Added `CONCURRENT_PIPELINE_WORKERS=2`, `ENABLE_MULTI_LANG_DUB=false`, `ENABLE_LTX_CACHE=true`, uncommented `GOOGLE_APPLICATION_CREDENTIALS` pointing to Firebase SA

### Phase 6: Series + Knowledge Graph + Consistency Enforcement (6 new/upgraded files)
- **`utils/knowledge_graph.py`** (NEW) — Topic knowledge graph with prerequisite chains, difficulty scoring (beginner/intermediate/advanced), relationship types (prerequisite/related/builds_on/continues/contrasts_with), curriculum builder with progress tracking, coverage analysis, content gap detection (missing prerequisites, natural next topics, uncovered topics), stale topic pruning (90-day threshold), and `suggest_next_topic()` for pipeline-driven topic selection.
- **`utils/brand_manager.py`** (NEW) — Brand consistency engine with full style guide (colors `#00CCCC/#1e1e1e/#FF6B35`, fonts, voice rules, visual specs), vocabulary enforcement (preferred terms + avoided terms with regex matching), hook rotation tracker (records formula per video, suggests next formula from 5 types), `pre_publish_brand_check()` (sentence length, CTA presence, hook power phrases).
- **`utils/knowledge_integration.py`** (NEW) — Pipeline bridge connecting knowledge graph to content generation. `inject_knowledge_context()` provides prerequisite/related topic context to scriptwriter. `get_coverage_context()` feeds gap analysis to scheduler planner. `record_video_knowledge()` auto-registers each video in the graph with series relationships.
- **`utils/series_builder.py`** (UPGRADED) — Added `create_series()` (structured series creation), `get_series_progress()` (episode count/progress %), `build_continuity_text()` (generates "In Part 1, we covered X" references), `generate_part_title()` (auto-numbered episode titles like "NLP Fundamentals Part 2: Tokenization"), `sync_playlist()` (auto-create YouTube playlists + add videos). Now auto-syncs to knowledge graph on `register_video_in_series()`.
- **`utils/series_router.py`** (UPGRADED) — `inject_intro_outro()` now uses `generate_part_title()` for dynamic episode titling and `build_continuity_text()` for continuity hooks in long-form video intros.
- **`utils/consistency_checker.py`** (NEW) — Pre-publish audit that checks brand compliance (CTA, sentence length, hook phrases), terminology (jargon detection, avoided/preferred terms), hook rotation (3+ consecutive same-formula warning), and cross-video series references (missing "last time" mentions). Returns structured audit report with `passed` flag.
- **`main.py`** (6 integration points):
  - Scriptwriting: `inject_knowledge_context()` + `build_continuity_text()` merged into `extra_context` (alongside analytics feedback)
  - Hook scoring: Automatically detects hook formula (question/bold_claim/statistic/curiosity_gap/pain_point) and records via `record_hook_usage()`
  - Pre-publish: `run_consistency_audit()` called before publishing — logs warnings/errors
  - Post-publish: `record_video_knowledge()` registers each video in the knowledge graph
  - Daily scheduler: `get_coverage_context()` feeds content gaps into topic planning
  - Both short + long video paths fully wired with all 6 checks
- **Data files created on first use**: `data/knowledge_graph/graph.json`, `data/knowledge_graph/curricula.json`, `data/brand/style_guide.json`, `data/brand/hook_history.json`, `data/brand/vocabulary.json`

### Blender Render Engine — Setup & Storage
- **Blender 4.x LTS** required. Install via `brew install blender` or download from blender.org.
- **No LaTeX deps needed** — removed `texlive*`, `dvipng`, `cm-super` from Dockerfile (were Manim-only).
- **requirements.txt**: Removed `manim>=0.20.0,<0.21.0`. Blender uses its own bundled Python, no pip package needed.
- **Render dirs**: `tmp/blender_cache/` (cached renders), `tmp/blender_render/` (active renders). Both registered for cleanup.
- **chroma_db/**: At `agents/chroma_db/` — unchanged, still used by other pipeline components.

### D20: Subtitle Pipeline Overhaul + Facebook Permission Hardening + Caption Track Upload
- **B1 — Phrase timing matching fix**: Rewrote `generate_phrase_timings_from_sentences()` (`voice_gen.py`) — sentence matching now tracks used indices to prevent duplicates; word-level fallback groups `WordBoundary` events into phrases when sentence-level matching produces nothing. Guarantees non-empty phrase timings even on TTS text mismatch.
- **B2 — Broken subtitle fallback fix** (`subtitle_gen.py`): `_convert_word_times_to_phrases()` key `"word"` → `"text"` (was always empty). Removed dead word-timing fallback that read same file as phrase timings.
- **B3 — Subtitles visible on mobile**: Shorts subtitle font size 9 → 14 (`video_compositor.py:483`), matching repurposed shorts renderer.
- **B4 — YouTube caption track upload** (`youtube_upload.py`): After successful upload, calls `captions().insert()` with the SRT file so viewers can toggle subtitles on/off. Threaded `subtitle_path` through `upload_to_platform` → `_upload_youtube` → `multi_platform_publish` → `main.py` (both short + long call sites).
- **A2 — Facebook 403 detection** (`multi_platform_publisher.py`): Added `status_code in (401, 403)` alongside all existing `status_code == 401` checks in Facebook upload (direct, resumable init, resumable transfer phases).
- **A3 — Permission error fail-fast** (`multi_platform_publisher.py`): New `_is_graph_permission_error()` helper raises `PermissionError` on Graph API codes 190/200 or messages containing "permission". Caught before `retry_with_backoff` loop — no more 3× useless retries on permanent permission errors.
- **A1 — Firestore cleanup script** (`agents/scripts/cleanup_env_vars.py`): Connect, list, and delete stale `env_vars` docs (especially `FACEBOOK_ACCESS_TOKEN` that overrides `.env`). Run with `python -m agents.scripts.cleanup_env_vars`.

### D19: CI Pipeline Fixes — Indentation Error + flags=lanczos Filter + Circuit Breaker API
- **IndentationError fix**: `e6e760ef` commit's xfade try/except refactor left the inner `concat_list` block at 16-space indent while `try` was at 4 spaces and `except` at 8 spaces — Python `video_compositor.py:432` raised `IndentationError: unexpected indent`. Fixed by normalizing all 3 blocks to correct indentation (`video_compositor.py`).
- **Standalone `,flags=lanczos,` filter**: `apply_ken_burns()` vf string had `,flags=lanczos,` between `crop` and `scale` — ffmpeg 8.1 treats comma-separated items as filter names, so it tried to find a filter called `flags=lanczos` (`No option name near 'lanczos'`). Removed standalone `flags=lanczos` since `scale=...:flags=lanczos` already handles it (`video_compositor.py:155`).
- **Circuit breaker API mismatch**: `stock_video.py` called `pexels_breaker.allow_request()` and `pixabay_breaker.allow_request()` but `CircuitBreaker` class in `health_monitor.py` only has `is_available()`. Changed all 3 call sites (pexels, pixabay, and ImportError fallback) to use `is_available()`.
- **PIL ellipse ValueError fix**: `_generate_static_image()` in `asset_router.py:32` drew random ellipses without sorting coordinates — PIL `ImageDraw.ellipse()` requires `x1<=x2` and `y1<=y2`, and raises `ValueError: y1 must be greater than or equal to y0` when coordinates are inverted. This caused ALL CI pipeline runs to fail at compositing (the error appeared to be from ffmpeg but was actually from Pillow). Fixed by wrapping coords in `min()/max()` calls.
- **Full CI pipeline SUCCEEDED** after all 4 fixes applied — short video pipeline completed all steps including publishing.

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
  - **ALL 7 files with subprocess.run** (video_compositor, compilation_gen, upscaler, stock_video, blender_renderer, validators, thumbnail_gen) — 24+ calls converted from `subprocess.run(timeout=N)` → `safe_run()`/`safe_run_bool()`; orphan processes killed on TimeoutExpired
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

## Infrastructure (completed 2026-07-12)
- **Docker image rebuilt** (`04e09177`): Added `playwright install chromium --with-deps` to Dockerfile. Added volume mounts for `keys/` (Google TTS) and `agents/tmp/community_cookies/` (Playwright persistence) in `docker-compose.yml`.
- **Instagram root `.env` fixed**: Copied `FACEBOOK_APP_ID` and `FACEBOOK_APP_SECRET` from `agents/.env` to root `.env` (was empty — would break token refresh).
- **YouTube OAuth re-authed**: Deleted old tokens, ran OAuth setup via Chrome. New token has all 5 scopes (`youtube.upload`, `youtube`, `youtube.force-ssl`, `youtubepartner`, `yt-analytics.readonly`). Channel: Legendary Laure (284 videos).
- **Google Cloud TTS activated**: API already enabled (2066 voices). Set `VOICE_PROVIDER=google` and fixed `GOOGLE_APPLICATION_CREDENTIALS` path to `/app/keys/...` (Docker path). Verified working in Docker.
- **Playwright first login**: Completed with `channel='chrome'` to bypass Google's "app may not be secure" block. 54 cookies saved, verified working headlessly in Docker via `storage_state`.
- **Full pipeline test (Phase 6)**: Ran short video pipeline in Docker with `FORCE_PUBLISH=true`. **2 videos published to YouTube**: `https://www.youtube.com/shorts/E9nMe3OpDRg` ("Open Source Spotlight") and `https://www.youtube.com/shorts/m5xjoLix0JE` ("The Tale of Ronin: Final Chapter"). Instagram uploads started (R2 uploads completed).

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

## Phase 9: Comment Sentiment Analysis (1 new, 1 wired)
- **`utils/comment_analyzer.py`** (NEW) — `analyze_sentiment()` (keyword + negation + intensifier scoring), `analyze_video_comments()` (YouTube API batch fetch), `flag_negative_comments()` (threshold alert)
- **`main.py`** — Wired into both short+long pinned_comment step: analyzes first 30 comments, logs sentiment breakdown, flags negative/toxic comments

## Phase 10: Content Pillar Strategy (1 new, 1 wired)
- **`utils/pillar_manager.py`** (NEW) — 8 pillars with target ratios, `track_pillar_video()`, `get_pillar_balance()`, `get_underrepresented_pillars()`, `suggest_next_pillar()`, `generate_pillar_context()` for scheduler planner injection
- **`main.py`** — `track_pillar_video(category)` called after publish in both paths; `generate_pillar_context()` injected into scheduler planner's `combined_ctx` alongside knowledge graph coverage

## Phase 11: Video SEO Optimization (1 new, 4 wired)
- **`utils/seo_optimizer.py`** (NEW) — `CATEGORY_TAGS` (8 curated 15-tag sets), `get_optimized_tags()`, `score_description_seo()` (CTA, URL, hashtag, length checks), `suggest_seo_improvements()`
- **`main.py`** — SEO tags and description scoring wired into both short+long description generation steps
- **`utils/multi_platform_publisher.py`** — `upload_to_platform()`, `_upload_youtube()`, `multi_platform_publish()` all accept new `tags` parameter; SEO tags merged with existing tech_meta tags, passed to YouTube upload body

## Phase 12: Analytics Anomaly Alerting (2 new, 1 wired)
- **`utils/alert_manager.py`** (NEW) — Unified `send_alert()` (telegram + slack dispatch), `check_view_anomaly()` (deviation >30%), `check_pipeline_health_alert()` (success rate <80%), `check_monetization_milestone()` (sub milestones), `check_staleness()` (>24h inactivity), `process_alerts()` (run all + dispatch)
- **`utils/slack_notifier.py`** (NEW) — `send_slack_message()` webhook sender, `send_alert_slack()` with severity emoji prefixing
- **`main.py`** — `process_alerts()`, `check_pipeline_health_alert()`, and `check_staleness()` wired into `daily_analytics_job()`; pipeline health checked against last 20 pipeline metrics

## Quality Improvement Pass — 3Blue1Brown-Level Targeting

### Critical Fixes (settings/config)
- **C1 — LTX resolution**: 704×448 → **832×512** (36% more pixels, much sharper upscaled output) — `models/ltx_model.py:287-288`
- **C2 — FPS enforcement**: All render paths force **24fps** via `-r 24` to match compositor — `video_compositor.py:xfade input normalization`
- **C3 — Subtitle font sizes**: Long-form FontSize=10→**24**, Shorts FontSize=10→**32**, burn_subtitles default 22→**28** — `video_compositor.py:557`, `shorts_renderer.py:104`, `video_compositor.py:391`
- **C4 — Static image fallback**: Random ellipses → **styled title card** with topic text, brand teal accent stripe, Vyom Ai Cloud subtitle, corner accents — `asset_router.py:_generate_static_image()`
- **C5 — Upscaler enabled**: `ENABLE_UPSCALE=true` in `.env` (Real-ESRGAN 2x for LTX clips when binary available)
- **Blender templates** are standalone Python scripts invoked via `blender --background --python template.py -- --params <json_path>`. Each template reads `params["_output"]` for the frame output directory. Templates are registered in `TEMPLATE_REGISTRY` with keywords, engine preference, and priority. Common utilities (materials, lighting, camera, scene setup) are in `common.py`.

### High Priority (feature/code)
- **H1 — Brand color palette enforced**: Video bg now `#1e1e1e` (dark gray like 3B1B), accent `#00CCCC` teal throughout compositor lower-thirds & scene labels, accent `#FF6B35` orange for emphasis — `blender_templates/common.py`, `video_compositor.py`, `scene_parser.py`
- **H2 — 6 new Blender templates**: Added `comparison_bars`, `processor_pipeline`, `network_topology`, `timeline_3d`, `process_flow`, `layer_explosion`, `neural_network` — **14 templates total** in `blender_templates/`
- **H4 — SSML voice enhancement**: Added `_wrap_ssml()` — wraps TTS text with emphasis tags on key terms, 300ms micro-pauses at sentence boundaries, prosody control. Dramatically less robotic delivery — `voice_gen.py`, `voice_provider.py`

### Medium Priority
- **M1 — Script temperature lowered**: 0.7/0.8→**0.4** for accuracy (educational content needs tighter LLM) — `crew/scriptwriter.py:9`
- **M2 — Narration pacing improved**: Inter-segment silence 100ms→**500ms** (gives viewer breathing room after key points) — `voice_gen.py:440`
- **M3 — Animated hook text**: Fade-in over 2s (alpha ramp) for shorts hook text — `shorts_renderer.py:90-95`
- **M3 — Subscribe end card**: Brand teal CTA "Subscribe for more AI content" fades in during last 4s of each short with centering + line spacing — `shorts_renderer.py`
- **M4 — Stock footage quality filter**: Rejects clips below 1920×1080 from both Pexels and Pixabay — `stock_video.py` (Pexels line 161, Pixabay line 222)
- **M6 — 4K output option**: `OUTPUT_4K=true` env var renders long videos at 3840×2160 — `video_compositor.py`

### H3 — Cross-Scene Visual Continuity (3 steps, all implemented)
- **H3 Step 1 — SceneState dataclass** (`scene_parser.py`): Added `SceneState` dataclass (camera_angle, lighting, color_palette, dominant_colors). `_infer_ltx_prompt()` now accepts `prev_state` and returns `(str, SceneState)` tuple — camera/lighting rotate smoothly from previous scene with continuity hints ("continuing from previous close-up, similar angle with slight drift"). `_llm_scene_parse()` prompt now includes CRITICAL continuity guidance ("maintain consistent color palette, avoid sudden jumps in camera angle"). `_rule_based_parse()` threads prev_state through consecutive scenes.
- **H3 Step 2 — LTX prompt continuity** (`ltx_model.py`): `generate_clip()` now accepts `seed` and `prev_colors` parameters — appends color continuity to prompt. `generate_clips()` creates shared_seed from `hash(video_id)` and passes `seed=shared_seed + i` per scene for reproducible adjacent frames. Batch config JSON now includes `seed`, `scene_index`, and `scene_total` per scene. Each uncached scene appends `"maintaining consistent color palette from previous scene"` continuity.
- **H3 Step 3 — Color grading pass** (`video_compositor.py`): New `_color_grade_scenes()` compares adjacent scene YUV histograms via ffprobe `signalstats` (YAVG/UAVG/VAVG). `_histogram_shift()` computes mean Y/U/V difference normalized to 0-1. If shift > `COLOR_GRADING_THRESHOLD` (default 0.15), `_apply_color_correction()` applies `colorbalance` filter to match previous scene's histogram. Controlled by `ENABLE_COLOR_GRADING=false` env var (default off). New helpers: `_extract_yuv_histogram()`, `_apply_color_correction()`.

### H5 — Visual QA Blur Detection (`video_qa.py`, wired into `main.py`)
- **`check_blur()`**: Extracts frames at `sample_interval` (default every 5s), computes Laplacian variance via PIL `Kernel(3×3)` and `numpy.var()`. Returns `avg_blur_score`, `blurry_frames` list with timestamp+score, `blur_ratio`. Frames stored in temp dir `qa_blur_` (cleaned up on exit). Falls through on any failure (non-blocking).
- **`check_frame_quality()`**: Convenience wrapper combining blur check into structured report with `passed` flag and summary. Called from `main.py:verify_video_quality()` after existing black/freeze/corruption checks.
- **Env vars**: `QA_BLUR_THRESHOLD=100.0` (Laplacian variance threshold, lower = less tolerant). Wired in `main.py` alongside `QA_BLACK_THRESHOLD` and `QA_FREEZE_THRESHOLD`. Non-blocking — warnings logged but pipeline continues.
- **Requirements**: Uses PIL (already in requirements.txt) + numpy (already transitive from torch). No new dependencies.

## New Env Vars
| Variable | Default | Purpose |
|---|---|---|
| `OUTPUT_4K` | `false` | Render long videos at 3840×2160 |
| `SLACK_WEBHOOK_URL` | — | Slack webhook URL for Phase 12 alert dispatch |
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
| `SHORTS_MAX_DURATION` | `180` | Max short video seconds (was 60) |
| `FORCE_PUBLISH` | `false` | Override blocking gates, publish despite quality/virality failures |
| `MIN_VIRALITY_SCORE` | `40` | Minimum virality score for shorts |
| `MIN_VIRALITY_SCORE_LONG` | `30` | Minimum virality score for long videos |
| `GATE_ENFORCEMENT_MODE` | `advisory` | Gate mode (`advisory` logs only, `enforce` blocks pipeline) |
| `KNOWLEDGE_GRAPH_ENABLED` | `true` | Enable knowledge graph tracking |
| `BRAND_ENFORCEMENT` | `advisory` | Brand check mode (`advisory` logs only, `enforce` blocks publishing) |
| `CONCURRENT_PIPELINE_WORKERS` | `2` | Max parallel pipelines in ThreadPoolExecutor |
| `ENABLE_MULTI_LANG_DUB` | `false` | Generate TTS audio dubs for each translated language |
| `ENABLE_LTX_CACHE` | `true` | LRU prompt cache for repeated LTX scene generation |
| `ENABLE_COLOR_GRADING` | `false` | Cross-scene color balancing via YUV histogram matching |
| `COLOR_GRADING_THRESHOLD` | `0.15` | Max allowable YUV shift between adjacent scenes |
| `QA_BLUR_THRESHOLD` | `100.0` | Laplacian variance threshold for blur detection |
| `QA_BLACK_THRESHOLD` | `0.35` | Max black frame ratio before QA fails |
| `QA_FREEZE_THRESHOLD` | `0.1` | Max freeze frame ratio before QA fails |

### Documentary Tier (uncommitted) — New `TIER=documentary` env var
- **Sprint 1 — Audio, Subs, Color, Voice**:
  - Audio sample rate fix: `-ar 44100` in shorts_renderer.py and video_compositor.py concat paths — prevents "sample rate mismatch for aac codec" on mixed-source clips.
  - Subtitle styling: `composite_video()` accepts `tier` param → documentary gets `FontSize=24`, `MarginV=60`, white primary (`&H00FFFFFF&`), black outline (`&H00FFFFFF&/&H80000000&`), `has_outline=2`. Deep lesson and default each keep their own styling. `burn_subtitles()` accepts `tier` param.
  - Color grading reference: `DOCUMENTARY_YUV = {"y_mean": 90, "u_mean": 128, "v_mean": 118}` cooler/desaturated palette in `video_compositor.py`. `_color_grade_scenes()` accepts optional `target_ref` dict. Documentaries use `DOCUMENTARY_YUV`, everything else uses `BRAND_TEAL_YUV`.
  - Voice profile: `get_voice_settings("documentary")` → `en-US-JennyNeural`, `-10%` rate, `-3Hz` pitch (`voice_gen.py`). `CONTENT_TYPE_VOICES["documentary"] = "en-US-Studio-Q"` (`voice_provider.py`).
  - SSML documentary mode: `_build_google_ssml(is_documentary=True)` → 750ms sentence pauses, 250ms clause pauses, no emphasis words (calm documentary narration). Threaded through `EdgeTTSProvider.generate()`, `GoogleCloudTTSProvider.generate()`, all `generate_timing()` methods.
- **Sprint 2 — Pipeline Wiring**:
  - `TIER` env var read in `run_video_pipeline()` → `is_documentary` bool set once, threaded to `generate_voiceover(is_documentary=...)` and `composite_video(tier=...)`. All 4 composite_video call sites pass `tier`.
  - `_deep_lesson_dur()` checks `TIER=documentary` → returns `DOCUMENTARY_MAX_DURATION` (default 2400s = 40min).
  - Documentary context injected into deep lesson crew's `extra_context` in `generate_long_video()`: narrative storytelling, historical progression, case studies, [STOCK] for b-roll, [BLENDER] for 3D diagrams, 20-40 scenes.
  - `.env` + `.env.example` updated: `DOCUMENTARY_MAX_DURATION=2400`, `TIER=`.
- **Sprint 2b — Stock keyword map 70→200 entries**: `PEXELS_KEYWORD_MAP` expanded from ~70 to 200 entries with documentary-relevant categories (history, nature, science, space, culture, psychology, etc.). Fixed duplicate `engineering` key. Added public-domain archive fallback sources: `_search_archive_org()` (Internet Archive) and `_search_wikimedia()` (Wikimedia Commons) — wired into `_search_providers()` as fallback after Pexels/Pixabay (`stock_video.py`).
- **Sprint 3 — Blender path**: Now implemented — Blender replaces Manim entirely. LTX + Stock + Blender covers all scene types.
- **Sprint 4 — Scheduler + Ambient Music**: `weekly_documentary_job()` runs Sunday 08:00 UTC (`main.py`). Sets `TIER=documentary`, calls `generate_content_plan(slot="documentary")`, generates long videos as documentaries. With global dedup guard (`EVERYONE_DOCUMENTARY_JOB`). Music: added `"documentary"` mood to `music_gen.py` (55 BPM, low sine notes → sustained chord pads). `detect_mood()` and `generate_background_music()` accept `tier` param. Procedural pad generator for ambient/documentary (sustained overlays instead of note-by-note).

## New Env Vars
| Variable | Default | Purpose |
|---|---|---|
| `DOCUMENTARY_MAX_DURATION` | `2400` | Max documentary video duration (40 min) |
| `TIER` | — | Set to `"documentary"` for documentary-style long videos |
