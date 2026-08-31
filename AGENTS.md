# AGENTS — Critical Context

## Latest Changes (committed)

### D27-2: Month-End Scheduler Crash Fix + Planner Sizing + YouTube-Only Publish + Manual Rerun Flag (deployed live)
- **Month-end crash fixed (`main.py:_next_schedule_time`)**: Scheduler daily job crashed daily at 15:05 on the last day of any month (`ValueError: day is out of range for month`) because `_next_schedule_time` used `scheduled.replace(day=scheduled.day + 1)`, which overflows on 28/29/30/31. The D24 overnight slots (news long at 01:00 = next day) made this a guaranteed monthly kill — it killed today's whole `daily_content_job` (Aug 31) before any pipeline built. Added `_add_days(dt, n)` helper using `timedelta(days=n)` (safe across all month lengths); `_next_schedule_time` now uses it. Verified: news-long slot on Aug 31 → `2026-09-01T01:00:00Z` (no crash). This bug would have recurred EVERY month-end.
- **Planner sizing tightened (`scheduler_planner.py:generate_content_plan`)**: When `SLOT=""` (the normal `daily_content_job` path), the planner sized output to a hard-coded `{shorts:1, longs:0}`, under-producing pillar content and relying on a trends fallback. It now sizes to the env-configured `SCHEDULE_SHORTS_PER_DAY` / `SCHEDULE_LONG_PER_DAY` so each night's plan guarantees a full slate (1 short + 2 longs). Verified: plan returns exactly `{shorts:1, longs:2}`.
- **YouTube-only publishing (`main.py:_platforms_to_publish`)**: New `PLATFORMS_TO_PUBLISH` env (comma list, default `youtube`) read by BOTH short+long publish paths (replaced hard-coded `['youtube','instagram','facebook']` / `['youtube','facebook']`). IG/FB/TikTok disabled pending a Meta re-plan (app deleted, code 190). Added to `.env`, `.env.example`, Firestore `env_vars`.
- **Manual rerun flag (`main.py:__main__`)**: `python main.py --run-once` executes `daily_content_job()` and exits — first-class manual reruns without touching the scheduler. (Today's crashed run was re-run via `main.daily_content_job()` in-container.)
- **Deploy**: `timi-pipeline:latest` rebuilt (`5b29e13d67b0`), container recreated, healthy. Verified: month-end slots rollover correctly, planner sizes 1S/2L.
- **Manual rerun today (YouTube-only)**: rebuilt plan = 5 pipelines (2 news shorts + 1 pillar short + 1 news long + 1 pillar long; GPU budget 2 enforced). 40 world + 92 nepal verified stories available.

### D27: YouTube OAuth Client Re-Auth + List-Category Crash Fix + News-Long ≥3min Gate (deployed live)
- **YouTube OAuth client restored**: old client `839918420419-88cjde4sjnt3s18stnaehoaggtdcp617.apps.googleusercontent.com` was deleted in Google Cloud Console → every YouTube upload/trend fetch failed with `deleted_client` (all 2026-08-30 shorts + news long dead). Re-authorized with new client `839918420419-ejklcj71ooogppkf3r701almgl4tlfgp.apps.googleusercontent.com` (Desktop app, same GCP project `839918420419`): ID/secret set in `.env` **and** Firestore `env_vars` (Firestore overrides `.env` at boot via `sync_env_from_firestore`), `youtube_token.json` regenerated via interactive OAuth (scopes `youtube.upload`, `youtube`, `youtube.force-ssl`, `yt-analytics.readonly`) — verified `channels().list(mine=True)` → **Legendary Laure** (12 subs / 388 videos). All 3 failed Aug-30 shorts re-uploaded to YouTube as public: Iceland EU talks → `shorts/2Lqr6IhrrQI`, Nepal tunnel → `shorts/vUR7LuMEUXs`, Python mistakes → `shorts/YjjLG3cnxRM`; Firestore `youtube_url`/`status` updated.
- **List-category crash fix (`scene_schema.py:normalize_category`)**: LLM planner (`_llm_plan`) sometimes emits `category` as a JSON list (e.g. `["AI News"]`); `normalize_category` passed it straight through and `music_gen.py:detect_mood`'s `category.lower()` crashed the long pipeline at 16:01 (Step 3, `'list' object has no attribute 'lower'`). `normalize_category` now coerces list→first element→string, so all shorts+longs+music paths survive.
- **News-long ≥3 min gate (`main.py:generate_long_video`)**: news longs were rendering ~15s because the LLM wrote a one-paragraph "explainer". Two-part fix: (1) news scriptwriter prompt now gets an explicit `LENGTH REQUIREMENT: ≥450 words / 12-18 scenes / 3+ minutes`; (2) post-simplification guard retries ONCE with a firmer "go deep, don't summarize" instruction when below `NEWS_LONG_MIN_NARRATION_WORDS=450` (news) / `LONG_MIN_NARRATION_WORDS=360` (other longs) — if a news long is still under 450 words it hard-fails + re-queues (never publishes a 15s "long"). New env vars added to `.env` + `.env.example`.
- **Deploy**: `timi-pipeline:latest` rebuilt (`277b795ba16a`), container recreated + renamed back to `timi-pipeline`, healthy. In-container verified: env + Firestore client ID = new client, scheduler armed (daily 15:05 UTC, publish check every 15 min), token mounted at `/app/youtube_token.json`.
- **Still broken (deferred)**: Instagram/Facebook publishing — Meta app was deleted (`Application has been deleted`, code 190). Requires recreating the Meta app + re-auth; until then videos publish YouTube-only.

### D24: Exactly-5 Videos/Day + AI/IT-Only Content + Overnight Idle-Window Rendering + No Auto-Repurposed Shorts
- **Volume fixed at 5 videos/day**: `SCHEDULE_SHORTS_PER_DAY=1` + `SCHEDULE_LONG_PER_DAY=2` + `GPU_VIDEO_BUDGET_PER_DAY=2` + `ENABLE_NEWS=true`. Every day = 2 news shorts (World + Nepal) + 1 pillar short + 1 news long + 1 pillar long = **5**. Pillar longs capped at 1 via GPU budget (news long charges slot #1; pillar loop breaks at `(count+_gpu_used)>=budget`). Updated `.env` + `.env.example` + **Firestore `env_vars.SCHEDULE_SHORTS_PER_DAY=1`** (Firestore overrides `.env` at boot — `sync_env_from_firestore` in `firebase_status.py:479` overwrites os.environ unconditionally, so the Firestore value MUST match `.env` or the old `4` would win).
- **Generation moved into laptop-idle window**: `daily_content_job` cron 06:00→**15:05 UTC (8:50 PM Nepal)** so heavy LTX renders+uploads never happen during the user's 10:30 AM–8:00 PM Nepal window. Render window 15:05 UTC→~4-5 AM = 8:50 PM→~10 AM Nepal, all idle.
- **Exact publish slots (UTC → Nepal, all inside idle window, all same Nepal day)**:
  - World news short `(19,0)` = 12:45 AM Nepal
  - Nepal news short `(21,0)` = 2:45 AM Nepal
  - Pillar short `(23,0)` = 4:45 AM Nepal
  - Pillar long `(21,15)` = 3:00 AM Nepal
  - News long `(1,0)` next-day = 6:45 AM Nepal
  - `_next_schedule_time()` refactored to accept `(hour, minute)` tuples (`main.py`) so the 15-min-offset pillar-long slot (3:00 AM Nepal) is expressible; slot constants in `daily_content_job` updated to tuples.
- **Auto-repurposed shorts REMOVED** (they had no off-switch): deleted the render+upload block in `generate_long_video` (was main.py `:2060-2094`) that made ~3 shorts/long to YT/IG/FB and inflated daily volume + render time. Deleted `daily_repurpose_job` + its 14:00 cron + the now-unused `batch_reprocess_all_videos` import in main. `repurposer.py`/`render_repurposed_shorts` remain for manual use (`scripts/repurpose.py`).
- **All non-news content restricted to AI/IT** (Business & Finance + Health & Medicine removed as canonical categories):
  - `scene_schema.py` = source of truth: `VALID_CATEGORIES`, `DEEP_LESSON_CATS` now `{AI News, Science & Technology, Programming & Software}` (news stay `NEWS_CATS`, ratio 0 in pillars). Business/Health aliases re-mapped (`Industry Analysis`→AI News, `Career & Learning`→Programming & Software).
  - `scheduler_planner.py` + `pillar_manager.py` `CONTENT_PILLARS` dropped Business/Health; rebalanced ratios AI News 0.40 / Science 0.30 / Programming 0.30.
  - `trend_engine.py` + `topic_scorer.py` `VALID_CATEGORIES`, `CATEGORY_KEYWORDS`, `CPM_MAP`, `CPM_RATES`, category-base scores purged.
  - `trend_discovery.py` focus_categories, YouTube category-id map (Business/Health ids→AI/IT), mock dataset, fallback analysis purged.
  - `scene_parser.py` `_get_suggested_assets` + `visual_profiles.py` category entry removed.
- **Sunday documentary moved into idle window**: `weekly_documentary_job` cron 08:00→**20:00 UTC Sunday (1:45 AM Nepal Monday)** — after Sunday's 15:05 UTC daily run, renders overnight Sunday→Monday, never in the use window.
- **Deploy (deployed live)**: `timi-pipeline:latest` rebuilt; container recreated, healthy. In-container verified: `SCHEDULE_SHORTS_PER_DAY=1` (Firestore+boot sync — 5 videos/day), scheduler crons (daily 15:05, documentary Sun 20:00, NO repurpose job), categories AI/IT-only.

### D23: Dual-Model LLM + Empty-Response Fallback + Hard Duration Guard + News Re-Queue (deployed live)
- **Dual-model routing** (`utils/llm_helper.py` + 9 crew files): new `OLLAMA_MODEL_ROUTES` env (JSON `{agent_id: model_tag}`) selects a per-agent Ollama model. Structured-JSON agents — `storyboard`, `virality_analyst`, `director`, `animator`, `metadata`, `composer` → **`gemma3:4b`** (3.3GB, survives memory pressure alongside LTX-video on the 16GB box); `scriptwriter` (short+long, `crew/scriptwriter.py:31,169`) stays on default **`OLLAMA_MODEL=qwen3.5:9b`**. Crew files now pass `agent_id=` into `get_llm()`. `verify_ollama_model()` accepts an optional `model` arg (cache shortcut only for the default-model check). Added `OLLAMA_MODEL_ROUTES` to `.env` + `.env.example`.
- **Empty-response fallback (decisive fix)** (`utils/llm_helper.py:empty_response_fallback()`, `main.py:run_agent_step`): previously on `"Invalid response from LLM call"` the pipeline called `reset_fallback()` which kept returning Ollama — but Ollama was memory-starved and returning EMPTY, so it retried the SAME failing provider and died (45 failures on the 2026-08-29 morning run killed all 6 news/pillar shorts + news long). Now empty responses call `empty_response_fallback()` which **rotates provider** (Ollama→Gemini→back) so the next retry actually uses Gemini's cloud capacity.
- **Hard min-duration guard (`main.py:_duration_ok`)**: FORCE_PUBLISH-proof sanity check blocking structurally-broken output — longs <30s, shorts <3s, or missing file → hard fail + re-queue, never published. Fixes the 15s-long that published 2026-08-29 and fed the 15s rerpurposed-short cascade.
- **News re-queue (`main.py:daily_content_job`)**: failed mandatory World/Nepal news jobs are re-run **serially with the specific verified `news_article` intact** (previously the article was dropped by `schedule_topic()`), so mandated slots land with accurate source explainers.
- **Publish observability**: `youtube_url` now logged in PUBLISH events (`log_event`) for both short+long paths — upload URLs were previously invisible in container logs.
- **Deploy**: `ollama pull gemma3:4b` on host; `timi-pipeline:latest` rebuilt; container recreated (healthy). In-container verified: both models reachable via `host.docker.internal:11434`, storyboard→gemma3:4b, scriptwriter→qwen3.5:9b, Gemini fallback armed, scheduler clean.

### D22: Verified-News Categories + 4/2 Daily Volume (pending image rebuild)
- **Two new canonical categories**: `World News (24hr)` + `Nepal News` added to `VALID_CATEGORIES`/`NEWS_CATS` (`scene_schema.py` = source of truth), aliases in `CATEGORY_ALIASES`, and synced into `pillar_manager`/`scheduler_planner` `CONTENT_PILLARS` (news ratio 0.0 — news are mandatory via schedule, not pillar ratios), `trend_engine.CPM_MAP`, `topic_scorer.CPM_RATES`. `description_gen.get_tech_metadata` picks YouTube `categoryId` "25" (News & Politics) for news, else "28".
- **`utils/news_scraper.py` (NEW)**: verified-publisher-only news gathering. `FEED_REGISTRY` (BBC World, Guardian World, Kathmandu Post, NepaliTimes, OnlineKhabar EN, Khabarhub, OnlineKhabar NP), lenient RSS/Atom parse (Kathmandu Post trailing-junk safe), `VERIFIED_HOSTS` allowlist gate (headline rejected unless host is a hard-coded verified publisher), `FRESHNESS_HOURS`/`NEWS_MAX_ITEMS_PER_FEED` env. Bilingual: OnlineKhabar-NP yields Devanagari content (`lang: ne`) alongside English. `__main__` self-test. Live-tested: 20 world + 50 nepal (EN+NE) verified items, 0 unverified drops. Dead sources excluded (ekantipur, Republica, Reuters/AP RSS, etc.).
- **Mandatory daily news slots** (`main.py:daily_content_job`): 1 World short (06 UTC) + 1 Nepal short (08 UTC) + 1 news long (14 UTC, picks a DIFFERENT verified article than the short, alternating World/Nepal). Gated by `ENABLE_NEWS=true`. Dedups against last-30d video titles via existing `_load_recent_topic_titles`. `news_article` param feeds a "VERIFIED NEWS ARTICLE to explain" context block into scriptwriter (replaces tech knowledge/series/trend context) so scripts are accurate, sourced explainers — never invented. News bypasses `_is_non_tech_topic` (source gate is authoritative).
- **Volume 4 shorts + 2 longs/day**: `SCHEDULE_SHORTS_PER_DAY=4`, `SCHEDULE_LONG_PER_DAY=2`; pillar shorts fill 10/12 UTC, pillar longs 10/14 UTC.
- **Single-GPU render budget guard**: `GPU_VIDEO_BUDGET_PER_DAY` (default = long_per_day) caps total long-form (GPU) videos per day so a heavy 4+2 day can't crash the 16GB box. News long is mandatory and charged first.
- **New env vars**: `ENABLE_NEWS`, `GPU_VIDEO_BUDGET_PER_DAY`, `NEWS_FRESHNESS_HOURS`, `NEWS_MAX_ITEMS_PER_FEED` (+ bumped scheduler counts). Added to `.env` + `.env.example`.
- **Firebase dashboard disconnect (investigated, confirmed OK)**: live dashboard at `timi.vyomai.cloud/api/health` returns `firestore: status ok`; `FIREBASE_SERVICE_ACCOUNT_KEY` (base64 SA) already exists in Vercel prod. Data endpoints return `Unauthorized` only because they require auth (expected). No code change needed.

### D21: Genuinely-Portrait Shorts + LIKE CTA + Font Fix (pending image rebuild)
- **Both LIKE CTAs confirmed emoji-free**: `👍`/`🔥` are NOT in the container's DejaVuSans charset → would render as tofu boxes. Removed emoji from `LIKE if this helped!` in both `shorts_renderer.py` and `video_compositor.py` (verified via `fc-query` glyph check).
- **Portrait Shorts root-cause fix** (`shorts_renderer.py:reformat_to_shorts()`): replaced the legacy blurred-pad center-crop (which letterboxed the landscape source tiny on a 9:16 canvas) with a genuine 9:16 crop that FILLS the portrait frame: `crop=min(iw,ih*9/16):ih:(iw-min(iw,ih*9/16))/2:0 → scale 1.06x → slow horizontal Ken Burns pan → scale 1080:1920`. No black bars. Gated by `ENABLE_PORTRAIT_SHORTS` (default true; false = legacy blurred-pad). Verified in-container: renders rc 0 at exactly **1080×1920**.
- **LIKE CTA near end** (both formats, gated by `ENABLE_LIKE_CTA`, default true): `shorts_renderer.py` draws a teal `LIKE if this helped!` pill at `y=h*0.72` in the final ~3s (subscribe CTA stays centered); `video_compositor.py` draws it at `y=h*0.70` fading in/out near the end for long + native shorts. Verified in-container both filter chains render rc 0.
- **Font fix**: `FONT_PATH` was empty and the fallback `/System/Library/Fonts/Helvetica.ttc` (macOS path) doesn't exist in the Linux container — pre-existing hook/CTA drawtext filters relied on fontconfig fallback. Set `FONT_PATH=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf` in `.env`+`.env.example` so ALL drawtext overlays (hook, subscribe, LIKE, composition) use a real font. Verified present in container image fonts.
- **End screens / info cards**: NOT scriptable via the public YouTube upload API (require Studio UI) — the burned LIKE+Subscribe end CTAs in both formats are the plan's "fallback burned CTA" (documented in monetization doc's end-card note).
- **New env vars**: `FONT_PATH` (drawtext font), `ENABLE_PORTRAIT_SHORTS` (true=genuine 9:16 crop), `ENABLE_LIKE_CTA` (true=end LIKE pill). Added to `.env` + `.env.example`.

### D20+: Subtitle Correctness, Non-Technical Scripts, Narration-Led Visuals, Real Dedup (committed `be704cc6`, deployed live)
- **Subtitle correctness (A1/A2/A3)**: `voice_gen.py` now returns `spoken_text` (the symbol-expanded narration the TTS actually reads); `main.py` builds the SRT from `spoken_text` instead of raw narration so captions match the voice exactly. New `SUBTITLE_MODE` env (`auto`=burn for shorts / soft-CC for longs, so ONE caption track, no burned+CC duplicates): `subtitle_gen.py` exposes `subtitle_mode_for()`, `should_burn_subtitles()`, `should_upload_cc()`; `video_compositor` burns via `_subs_enabled_for()`, `youtube_upload` gates `captions().insert`. Text-estimated SRT fallback gated behind `SUBTITLE_ALLOW_ESTIMATE` (default off).
- **Non-technical scripts (B1/B2)**: `AUDIENCE_LEVEL` env (`nontechnical`/`general`/`technical`) injected into both `create_scriptwriter_crew` and `create_deep_lesson_crew` prompts. New `utils/simplify_audit.py` — jargon/acronym detector + one-pass plain-language rewrite (non-blocking) called via `_simplify_script()` on both short+long paths. Deep-lesson temp `0.0→0.6` to stop near-identical daily scripts.
- **Narration-led visuals (C1)**: LTX prompts now led by `narration_text` with the visual as a `-- showing:` tail — in both `asset_router._render_scene_inner` (single-clip) and `ltx_model.generate_clips` (batch). Fallback to stock/static already in the dispatch chain.
- **Content freshness (D1)**: `scheduler_planner.py` real 30-day topic dedup (was no-op `deduped = selected[:]`), `_load_recent_topic_titles()` + disk fallback; `trend_discovery.py` stronger non-tech filter (gaming/kpop/trailers/celeb).
- **Monetization levers**: audience-retention insights (`retention_analyzer.get_insights`) fed back into scriptwriter `extra_context` (short+long); initial title picked by `score_title` over variants (not blind `variants[0]`); blur is now a blocking QA gate; `docs/monetization-strategy.md` data-backed plan (386 vids / 10 subs / 4192 views / 11.7 watch-hrs → 4,000-hr YPP needs ~340×).
- **Env**: `SUBTITLE_MODE=auto`, `SUBTITLE_ALLOW_ESTIMATE=false`, `AUDIENCE_LEVEL=nontechnical` added to `.env`+`.env.example`.
- **Deploy**: image `timi-pipeline:latest` rebuilt, container recreated, healthy. Smoke-tested in-container: jargon detection fires, shorts=burn/long=cc.

### Upload Reliability: Description Sanitization + DNS Retry + Accurate Status (committed `44de0537`, deployed live)
- **B1 — Description sanitization (fixes YouTube `invalidDescription` 400)**: `sanitize_description()` in `platform_captions.py` strips control chars/null bytes/unpaired surrogates and caps at 5000 chars; applied in `optimize_for_platform()`. Defense-in-depth: `_sanitize_metadata()` in `youtube_upload.py` sanitizes title (100) + description (5000) right before building the API body. Both short+long `full_description` ingest points in `main.py` also sanitize. Fixes intermittent LLM glitches that caused long/short uploads to be rejected and never go live.
- **B2 — Accurate upload status (main.py)**: Only mark video `status: uploaded`/`scheduled` when a real `youtube_url` exists; otherwise `upload_failed` (was falsely marking rendered-but-upload-failed videos as `uploaded` with blank `youtube_url`).
- **C1 — Firestore/DNS retry hardening (`firebase_status.py`)**: `get_firestore_client()` retries client creation 3× on transient DNS/conn errors (`gaierror`/`Name or service not known`/`ConnectionRefused`); helper `_is_transient_net_error()`. Fixes intermittent Sentry crashes (`oauth2.googleapis.com` NameResolutionError) when the Docker host sleeps/DNS hiccups.
- **L1 — Disable duplicate GH Actions schedule (`daily-content.yml`)**: Removed the `schedule:` cron triggers — the Docker container (`timi-pipeline`) is the canonical pipeline with its own APScheduler. Kept `workflow_dispatch` for manual runs. Eliminates redundant duplicate pipeline + daily failure emails from the self-hosted runner.
- **Redeployed today's failed long video**: "Back to Business: AI Productivity" → https://www.youtube.com/watch?v=OOdf2Xgrpr4 (was previously rejected on `invalidDescription` when first generated).
- **Image rebuilt** (`timi-pipeline:latest`) with all fixes baked in; container recreated. `llm_helper.verify_ollama_model()` retry (3×/2s) also included.

### Phase 0-5: Quality Visualization & Viral Optimization Pass (committed — pending)
- **Phase 0.1+0.4 — xfade transition system**: Replaced `_build_fade_transition()` (concat+fade-to-black) with `_build_xfade_transition()` using ffmpeg xfade filter supporting 17 types: dissolve, fade, fadeslow, wipeleft/right, slideleft/right, smoothleft/right, zoomin, circleopen/close, pixelize, radial, squeezeh, coverright, revealright (`video_compositor.py`)
- **Phase 0.2 — LTX denoising reduced**: `hqdn3d=3:2:6:3` → `hqdn3d=1:0.5:2:1.5` for less detail loss (`video_compositor.py:357`)
- **Phase 0.3 — LTX prompt quality upgrade**: Added "sharp focus, 8k texture detail, rich detail, clear edges, crisp" to `QUALITY_SUFFIX`; expanded `NEGATIVE_PROMPT` with "low resolution, smooth plastic texture, oversmoothed, flat, soft, jittery, noise"; both short and long prompt paths now include "sharp focus, rich detail" (`models/ltx_model.py`)
- **Phase 0.5 — Audio compressor threshold**: -18dB → **-24dB** for wider dynamic range in voice (`video_compositor.py`)
- **Phase 1 — Visual Annotation System**: New `utils/annotation_renderer.py` — renders animated callout boxes, step counters `[1/3]`, definition popups, arrow pointers, highlight regions, and counting numbers as ffmpeg drawtext/drawbox filters. Wired into `composite_video()` vf chain. Controlled by `ENABLE_ANNOTATIONS` env var.
- **Phase 2 — Diagram & Data Visualization Engine**: New `utils/diagram_renderer.py` — PIL-based renderer for flow charts, bar charts, comparison tables, timelines, architecture block diagrams → PNG frames looped into video clips. Wired into `asset_router.py:_render_scene_inner()` — scenes with `"diagram"` field auto-render. Controlled by `ENABLE_DIAGRAMS` env var.
- **Phase 3 — Audio SFX**: `_generate_emphasis_tone()` (880Hz ding at key terms) and `_generate_transition_whoosh()` (200→2000Hz sweep at scene boundaries) in `mix_audio()`. Wired into `sfx_scenes` parameter. Controlled by `ENABLE_SFX` env var.
- **Phase 4 — Viral Mid-roll CTA**: Subscribe prompt overlay at 60% mark, slides in/out over 4s. Controlled by `ENABLE_MIDROLL_CTA` env var.
- **Phase 5 — Auto-enrichment**: New `enrich_scenes_with_annotations()` in `scene_parser.py` — auto-generates annotation metadata from scene text/keywords. Called in `_parse_scenes_for_asset_router()` (main.py). Per-annotation-type flags: `ENABLE_ANNOTATIONS_CALLOUT/STEP/DEFINITION/ARROW/HIGHLIGHT/COUNTER`.

### C8-C11: Viral Optimization + Pipeline Stability + Publishing Debug (committed `557c46f2`-`8134f37`)
- **C1**: Shorts subtitle FontSize 12→28 in `composite_video()` (`video_compositor.py:888`)
- **C2**: Both short+long publish use `best_title = title_variants[0]` (`main.py:1283,1760` instead of raw topic)
- **C3**: `hqdn3d=3:2:6:3` denoise after each LTX clip in `_process_clip()` (`video_compositor.py:353-367`)
- **C4**: Section transition silence 1200→500ms (`voice_gen.py:511`)
- **H2**: Facebook upload sends `thumb` file param (`multi_platform_publisher.py:595-620`)
- **H3**: `weekly_monetization_job()` fetches real YouTube subs/views (`main.py:2258-2266`)
- **H4**: CRF 18→17 (`video_compositor.py:44`, `shorts_renderer.py:129`)
- **H5**: `alimiter=limit=-1.5dB` + `firequalizer` de-essing in audio chain (`video_compositor.py:913-916`)
- **L4**: `VOICE_ROTATION` cycles 4 voices per segment (Jenny/Aria/Chris/Eric) (`voice_gen.py`)
- **L5**: `ENERGY_KEYWORDS` + `score_scene_energy()` + per-scene mood arc (`music_gen.py`, `main.py:831-839`)
- **Pipeline fix**: `firequalizer` fscale=linear unsupported in ffmpeg 8.1 — removed from filter chain (`video_compositor.py:916`)
- **Pipeline fix**: Shorts subtitle FontSize 12→28 in `composite_video()` (`video_compositor.py:888`)
- **Pipeline fix**: `gemini_llm.py` — `http_options=HttpOptions(timeout=300000)` on Client (5min API timeout)
- **Pipeline fix**: `main.py:run_agent_step()` — calls `force_fallback()` on TimeoutError before retry (→ Ollama)
- **Pipeline fix**: `crew/scriptwriter.py:123` — `max_tokens` 16000→10000

## Latest Changes (pre-existing)

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

### Documentary Tier (committed `557c46f2`) — New `TIER=documentary` env var
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
| `ENABLE_ANNOTATIONS` | `true` | Enable visual annotation overlays (callouts, steps, etc.) |
| `ENABLE_ANNOTATIONS_CALLOUT` | `true` | Enable callout box annotations |
| `ENABLE_ANNOTATIONS_STEP` | `true` | Enable step counter annotations |
| `ENABLE_ANNOTATIONS_DEFINITION` | `true` | Enable definition popup annotations |
| `ENABLE_ANNOTATIONS_ARROW` | `false` | Enable arrow pointer annotations |
| `ENABLE_ANNOTATIONS_HIGHLIGHT` | `true` | Enable highlight region annotations |
| `ENABLE_ANNOTATIONS_COUNTER` | `false` | Enable counting number annotations |
| `ENABLE_MIDROLL_CTA` | `true` | Enable mid-roll subscribe CTA overlay |
| `ENABLE_SFX` | `true` | Enable audio sound effects (dings, whooshes) |
| `ENABLE_DIAGRAMS` | `true` | Enable 2D diagram rendering via PIL |
