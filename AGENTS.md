# AGENTS — Critical Context

## Latest Changes (Group B + C, uncommitted)

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

## Remaining Setup
1. **TikTok OAuth**: Set `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` env vars.
2. **Instagram OAuth**: Set `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID` env vars.
3. **YouTube Analytics API**: Re-auth needed (`yt-analytics.readonly` scope). Delete `youtube_token.json` and run any upload.
4. **Google Cloud TTS**: Create service account, download JSON key, set `GOOGLE_APPLICATION_CREDENTIALS`.
5. **Playwright browsers**: Run `playwright install chromium` after pip install.

## Run Commands
- Short pipeline: `SLOT=morning FORMAT=short CATEGORY="AI Explained" python3 run_pipeline.py`
- Long pipeline with auto-shorts: `SLOT=evening FORMAT=long CATEGORY="AI Explained" python3 run_pipeline.py`
- Google TTS: Set `VOICE_PROVIDER=google` and `GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json`
- Community posts: Set `ENABLE_COMMUNITY_POSTS=true`
- Dashboard: `cd dashboard && npm run dev` (port 5001)

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
