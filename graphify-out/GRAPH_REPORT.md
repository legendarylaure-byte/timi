# Graph Report - /Users/Ai Mark/timi  (2026-06-29)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1379 nodes · 2334 edges · 129 communities (107 shown, 22 thin omitted)
- Extraction: 87% EXTRACTED · 13% INFERRED · 0% AMBIGUOUS · INFERRED: 312 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ceb034d3`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Affiliate Performance Analytics|Affiliate Performance Analytics]]
- [[_COMMUNITY_Web Application Dependencies|Web Application Dependencies]]
- [[_COMMUNITY_Content Quality Scoring|Content Quality Scoring]]
- [[_COMMUNITY_Content Hook & Repurposing|Content Hook & Repurposing]]
- [[_COMMUNITY_Multi-Platform Content Publishing|Multi-Platform Content Publishing]]
- [[_COMMUNITY_Video Description Generation|Video Description Generation]]
- [[_COMMUNITY_Voiceover & Music Generation|Voiceover & Music Generation]]
- [[_COMMUNITY_YouTube ID Extraction|YouTube ID Extraction]]
- [[_COMMUNITY_Firestore Activity Logging|Firestore Activity Logging]]
- [[_COMMUNITY_Agent System Documentation|Agent System Documentation]]
- [[_COMMUNITY_Sound Effects Generation|Sound Effects Generation]]
- [[_COMMUNITY_Live Activity Feed|Live Activity Feed]]
- [[_COMMUNITY_Content Calendar Management|Content Calendar Management]]
- [[_COMMUNITY_Admin API Routes|Admin API Routes]]
- [[_COMMUNITY_Content Series & Trends|Content Series & Trends]]
- [[_COMMUNITY_Pipeline Trigger & Cleanup|Pipeline Trigger & Cleanup]]
- [[_COMMUNITY_Manim Scene Rendering|Manim Scene Rendering]]
- [[_COMMUNITY_Animation Engine & Publishing|Animation Engine & Publishing]]
- [[_COMMUNITY_Video Pipeline Orchestration|Video Pipeline Orchestration]]
- [[_COMMUNITY_Agent Health Monitoring|Agent Health Monitoring]]
- [[_COMMUNITY_UI Component Library|UI Component Library]]
- [[_COMMUNITY_Agent Activity Timeline|Agent Activity Timeline]]
- [[_COMMUNITY_Telegram Bot Handler|Telegram Bot Handler]]
- [[_COMMUNITY_TypeScript Compiler Configuration|TypeScript Compiler Configuration]]
- [[_COMMUNITY_Content Series Planning|Content Series Planning]]
- [[_COMMUNITY_Dashboard UI Layout|Dashboard UI Layout]]
- [[_COMMUNITY_Design System Guidelines|Design System Guidelines]]
- [[_COMMUNITY_Firestore Index Deployment|Firestore Index Deployment]]
- [[_COMMUNITY_Multi-Voice Voiceover Generation|Multi-Voice Voiceover Generation]]
- [[_COMMUNITY_Scene Content Parsing|Scene Content Parsing]]
- [[_COMMUNITY_Prediction API & Rate Limiting|Prediction API & Rate Limiting]]
- [[_COMMUNITY_Stock Video Download|Stock Video Download]]
- [[_COMMUNITY_Admin Authentication Routes|Admin Authentication Routes]]
- [[_COMMUNITY_Monetization Analytics Dashboard|Monetization Analytics Dashboard]]
- [[_COMMUNITY_Theme Toggle Component|Theme Toggle Component]]
- [[_COMMUNITY_Background Image Generation|Background Image Generation]]
- [[_COMMUNITY_Agent Control Listener|Agent Control Listener]]
- [[_COMMUNITY_Thumbnail Image Generation|Thumbnail Image Generation]]
- [[_COMMUNITY_Daily Cleanup Service|Daily Cleanup Service]]
- [[_COMMUNITY_Title AB Testing|Title A/B Testing]]
- [[_COMMUNITY_Monetization Tracker & Thresholds|Monetization Tracker & Thresholds]]
- [[_COMMUNITY_Video Compositing Fixes|Video Compositing Fixes]]
- [[_COMMUNITY_Animation Math Tests|Animation Math Tests]]
- [[_COMMUNITY_Dashboard Layout & Status|Dashboard Layout & Status]]
- [[_COMMUNITY_Agent Skill Guidelines|Agent Skill Guidelines]]
- [[_COMMUNITY_Vercel Environment Setup|Vercel Environment Setup]]
- [[_COMMUNITY_Scene Schema Validation|Scene Schema Validation]]
- [[_COMMUNITY_Text Spotlight Animation|Text Spotlight Animation]]
- [[_COMMUNITY_Channel Analytics Dashboard|Channel Analytics Dashboard]]
- [[_COMMUNITY_Analytics Feedback & Recommendations|Analytics Feedback & Recommendations]]
- [[_COMMUNITY_Video Performance Tracking|Video Performance Tracking]]
- [[_COMMUNITY_Video Compilation Generation|Video Compilation Generation]]
- [[_COMMUNITY_Subtitle File Generation|Subtitle File Generation]]
- [[_COMMUNITY_React Error Boundary|React Error Boundary]]
- [[_COMMUNITY_Vercel Deployment Configuration|Vercel Deployment Configuration]]
- [[_COMMUNITY_Thumbnail Image Generation|Thumbnail Image Generation]]
- [[_COMMUNITY_NPM Project Scripts|NPM Project Scripts]]
- [[_COMMUNITY_Content Safety & Compliance|Content Safety & Compliance]]
- [[_COMMUNITY_Title Optimization & Scoring|Title Optimization & Scoring]]
- [[_COMMUNITY_Next Upload Timer|Next Upload Timer]]
- [[_COMMUNITY_Firestore Data Seeding|Firestore Data Seeding]]
- [[_COMMUNITY_Schedule Time Calculation|Schedule Time Calculation]]
- [[_COMMUNITY_Authenticated API Routes|Authenticated API Routes]]
- [[_COMMUNITY_Authenticated API Routes|Authenticated API Routes]]
- [[_COMMUNITY_Model Installation Script|Model Installation Script]]
- [[_COMMUNITY_Video Cleanup Script|Video Cleanup Script]]
- [[_COMMUNITY_Engagement Comment Management|Engagement Comment Management]]
- [[_COMMUNITY_Playwright Test Dependencies|Playwright Test Dependencies]]
- [[_COMMUNITY_Pipeline Service Setup|Pipeline Service Setup]]
- [[_COMMUNITY_Character Sprite Generation|Character Sprite Generation]]
- [[_COMMUNITY_MLX Engine Integration|MLX Engine Integration]]
- [[_COMMUNITY_ESLint Configuration|ESLint Configuration]]
- [[_COMMUNITY_Authenticated API Routes|Authenticated API Routes]]
- [[_COMMUNITY_Happy Scene Component|Happy Scene Component]]
- [[_COMMUNITY_Loading Skeleton Components|Loading Skeleton Components]]
- [[_COMMUNITY_Pipeline Run Script|Pipeline Run Script]]
- [[_COMMUNITY_Character Sprite Generation|Character Sprite Generation]]
- [[_COMMUNITY_Jest Test Configuration|Jest Test Configuration]]
- [[_COMMUNITY_Next.js Sentry Configuration|Next.js Sentry Configuration]]
- [[_COMMUNITY_Idle Behavior API|Idle Behavior API]]
- [[_COMMUNITY_Container Info API|Container Info API]]
- [[_COMMUNITY_Heartbeat Write API|Heartbeat Write API]]
- [[_COMMUNITY_Authenticated API Route|Authenticated API Route]]
- [[_COMMUNITY_R2 Client API|R2 Client API]]
- [[_COMMUNITY_Button Component|Button Component]]
- [[_COMMUNITY_Card Component|Card Component]]
- [[_COMMUNITY_Character Sprite Generation|Character Sprite Generation]]
- [[_COMMUNITY_Sentry Setup Script|Sentry Setup Script]]
- [[_COMMUNITY_Scheduler Run Script|Scheduler Run Script]]
- [[_COMMUNITY_Community 110|Community 110]]
- [[_COMMUNITY_Community 112|Community 112]]
- [[_COMMUNITY_Community 113|Community 113]]
- [[_COMMUNITY_Community 116|Community 116]]

## God Nodes (most connected - your core abstractions)
1. `getAdminFirestore()` - 50 edges
2. `get_firestore_client()` - 46 edges
3. `generate_long_video()` - 39 edges
4. `generate_short_video()` - 38 edges
5. `get_llm()` - 22 edges
6. `getAdminAuth()` - 22 edges
7. `log_event()` - 21 edges
8. `daily_content_job()` - 19 edges
9. `log_activity()` - 19 edges
10. `db` - 19 edges

## Surprising Connections (you probably didn't know these)
- `cleanup()` --calls--> `run_cleanup()`  [INFERRED]
  bot/handlers.py → agents/utils/cleanup_service.py
- `youtube_stats()` --calls--> `get_channel_stats()`  [INFERRED]
  bot/handlers.py → agents/utils/youtube_upload.py
- `create_series_planner_crew()` --calls--> `get_llm()`  [INFERRED]
  agents/crew/series_planner.py → agents/utils/llm_helper.py
- `create_thumbnail_crew()` --calls--> `get_llm()`  [INFERRED]
  agents/crew/thumbnail.py → agents/utils/llm_helper.py
- `run_cleanup()` --calls--> `send_telegram_message()`  [EXTRACTED]
  agents/utils/cleanup_service.py → bot/notifications.py

## Import Cycles
- None detected.

## Communities (129 total, 22 thin omitted)

### Community 0 - "Affiliate Performance Analytics"
Cohesion: 0.05
Nodes (36): build_affiliate_section(), create_affiliate_manager_crew(), find_relevant_affiliates(), _load_affiliates(), create_analyst_crew(), load_recent_performance(), Run the Analyst agent and return analysis results., Load recent analytics data and format as a report summary. (+28 more)

### Community 1 - "Web Application Dependencies"
Cohesion: 0.04
Nodes (47): dependencies, @aws-sdk/client-s3, firebase, firebase-admin, framer-motion, lucide-react, next, react (+39 more)

### Community 2 - "Content Quality Scoring"
Cohesion: 0.07
Nodes (34): main(), Standalone Quality Scorer Agent Run: python -m agents.scripts.quality_scorer --t, Tests for quality_scorer.py, When LLM returns unparseable JSON, fallback should still return valid dict., test_check_repetition_returns_dict(), test_evaluate_publish_decision_auto_approve(), test_evaluate_publish_decision_block_high_similarity(), test_evaluate_publish_decision_block_low_score() (+26 more)

### Community 3 - "Content Hook & Repurposing"
Cohesion: 0.08
Nodes (36): check_and_improve_hook(), enforce_rewrite(), extract_hook(), has_prohibited_content(), score_hook(), main(), Standalone Repurposing Script Run: python -m agents.scripts.repurpose --title "., main() (+28 more)

### Community 4 - "Multi-Platform Content Publishing"
Cohesion: 0.08
Nodes (34): get_ai_disclosure(), main(), Standalone Multi-Platform Publisher Script Run: python -m agents.scripts.publish, multi_platform_publish(), Multi-Platform Publisher Agent Handles uploads to YouTube, TikTok, Instagram, an, Upload to TikTok via Content Posting API v2., Upload to Instagram via Graph API., Upload to Facebook via Graph API. (+26 more)

### Community 5 - "Video Description Generation"
Cohesion: 0.09
Nodes (26): get_disclosure_text(), Tests for description_gen.py, When LLM returns unparseable, fallback should still work., test_generate_description_channel_name(), test_generate_description_fallback(), test_generate_description_returns_keys(), test_generate_description_short_script(), test_generate_description_with_affiliate() (+18 more)

### Community 6 - "Voiceover & Music Generation"
Cohesion: 0.14
Nodes (29): generate_voiceover(), get_timings(), main(), End-to-end test: render "How Transformers Work" Generates voiceover (Edge TTS),, _build_musicgen_prompt(), detect_mood(), generate_background_music(), generate_melody() (+21 more)

### Community 7 - "YouTube ID Extraction"
Cohesion: 0.12
Nodes (28): test_extract_youtube_id_from_publish_urls(), test_extract_youtube_id_from_shorts_url(), test_extract_youtube_id_from_video_url(), test_extract_youtube_id_from_youtube_id_field(), test_extract_youtube_id_from_youtube_url_in_video_url(), test_extract_youtube_id_from_yt_video_id_field(), test_extract_youtube_id_prefers_youtube_id_over_url(), test_extract_youtube_id_returns_none_for_invalid_length() (+20 more)

### Community 8 - "Firestore Activity Logging"
Cohesion: 0.12
Nodes (24): daily_analytics_job(), Check for videos scheduled to publish now and process them., scheduled_publish_job(), delete_old_videos(), _firestore_op(), get_firestore_client(), is_agent_enabled(), log_activity() (+16 more)

### Community 9 - "Agent System Documentation"
Cohesion: 0.07
Nodes (27): Agent Roles, Agents Setup, AI Agents, Architecture, Compliance, Content Categories, Cost Breakdown (Monthly), CPM Ranges (Tech/AI Education) (+19 more)

### Community 10 - "Sound Effects Generation"
Cohesion: 0.15
Nodes (22): test_all_generators_return_audiosegment(), test_generate_all_sfx_creates_all(), test_generate_sfx_creates_file(), test_generate_sfx_unknown_name(), test_get_sfx_path_generates_if_missing(), test_load_sfx_scene_assignments(), test_map_effect_to_sfx(), _bounce() (+14 more)

### Community 11 - "Live Activity Feed"
Cohesion: 0.08
Nodes (17): PipelineTrigger, ActivityLog, LiveActivityFeed(), ActivePipeline(), Checkpoint, PIPELINE_STEPS, PipelineStatus, PipelineDoc (+9 more)

### Community 12 - "Content Calendar Management"
Cohesion: 0.18
Nodes (23): daily_content_job(), _next_schedule_time(), add_to_blacklist(), get_calendar_summary(), get_retry_queue(), get_todays_topics(), is_blacklisted(), load_calendar() (+15 more)

### Community 13 - "Admin API Routes"
Cohesion: 0.14
Nodes (14): register(), PATCH(), GET(), GET(), GET(), POST(), POST(), LEGACY_PATTERNS (+6 more)

### Community 14 - "Content Series & Trends"
Cohesion: 0.11
Nodes (17): gradients, Series, SeriesPart, SeriesPlan, TrendItem, glowShadows, GradientCard(), GradientCardProps (+9 more)

### Community 15 - "Pipeline Trigger & Cleanup"
Cohesion: 0.16
Nodes (23): _clean_scene_keyword(), cleanup_stuck_state(), daily_repurpose_job(), daily_revenue_job(), _handle_pipeline_trigger(), _limit_scenes(), log_event(), parse_scenes_from_storyboard() (+15 more)

### Community 16 - "Manim Scene Rendering"
Cohesion: 0.14
Nodes (14): dispatch_scene(), dispatch_scenes(), _get_stock_clip(), _cached_path(), compose_manim_block(), Render multiple consecutive Manim scenes as a single video block., render_manim_scene(), _scene_hash() (+6 more)

### Community 17 - "Animation Engine & Publishing"
Cohesion: 0.09
Nodes (10): Animation engine — simplified for tech/AI content. Generates single-frame previe, render_single_frame(), main(), VideoDoc, PlatformConfig, UploadQueueItem, RepurposeClip, RepurposeJob (+2 more)

### Community 18 - "Video Pipeline Orchestration"
Cohesion: 0.17
Nodes (19): get_virality_threshold(), apply_review_gate(), _execute_single_task(), _extract_json(), generate_long_video(), generate_short_video(), run_director_review(), main() (+11 more)

### Community 19 - "Agent Health Monitoring"
Cohesion: 0.13
Nodes (17): check_ollama_health(), check_ollama_with_fallback(), check_stale_heartbeat(), CircuitBreaker, _get_fallback_response(), Health Monitor for Agent System Provides Ollama health checks, heartbeat trackin, Return a safe fallback response when Ollama is unavailable., Write heartbeat to Firestore to indicate agent is alive. Retries on 504. (+9 more)

### Community 20 - "UI Component Library"
Cohesion: 0.08
Nodes (18): FEATURES, TAGLINES, PERKS, TAGLINES, BACKGROUNDS, EFFECTS, FORMATS, MOODS (+10 more)

### Community 21 - "Agent Activity Timeline"
Cohesion: 0.11
Nodes (15): ActivityEntry, AgentCard(), AgentCardProps, AgentStatus, AgentTimeline(), formatRelativeTime(), ActivityEntry, AgentGrid() (+7 more)

### Community 22 - "Telegram Bot Handler"
Cohesion: 0.27
Nodes (17): error_handler(), handle_message(), DEFAULT_TYPE, Update, analytics(), cleanup(), _get_firestore(), pause_pipeline() (+9 more)

### Community 23 - "TypeScript Compiler Configuration"
Cohesion: 0.10
Nodes (19): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+11 more)

### Community 24 - "Content Series Planning"
Cohesion: 0.20
Nodes (14): create_series_planner_crew(), save_series_plan(), _sync_plan_to_firestore(), test_inject_intro_outro_no_series(), test_load_series_returns_dict(), test_pick_series_for_category_known(), test_pick_series_for_category_unknown(), add_video_to_playlist() (+6 more)

### Community 25 - "Dashboard UI Layout"
Cohesion: 0.12
Nodes (12): DashboardPage(), SettingsPage(), WorkspaceAgent, WorkspacePage(), metadata, Toast, ToastContext, ToastContextType (+4 more)

### Community 26 - "Design System Guidelines"
Cohesion: 0.11
Nodes (18): Animation Tokens, Button, Card, Colors, Components, Dark Theme, Do's, Don'ts (+10 more)

### Community 27 - "Firestore Index Deployment"
Cohesion: 0.17
Nodes (18): _array_config_name(), build_index_proto(), get_client(), get_existing_indexes(), get_field_overrides(), index_matches(), main(), _order_name() (+10 more)

### Community 28 - "Multi-Voice Voiceover Generation"
Cohesion: 0.22
Nodes (17): concatenate_audio(), extract_narration_text(), _extract_narration_via_dialogue_tags(), _extract_narration_via_markers(), _generate_multi_voice(), generate_phrase_timings_from_sentences(), generate_segment_audio(), generate_segment_timing() (+9 more)

### Community 30 - "Scene Content Parsing"
Cohesion: 0.23
Nodes (16): _adjust_scenes_for_format(), _default_scene(), _estimate_scene_duration(), _extract_json_array(), _get_suggested_assets(), _infer_asset_type(), _infer_background(), _infer_effects() (+8 more)

### Community 31 - "Prediction API & Rate Limiting"
Cohesion: 0.18
Nodes (14): AGENT_LABELS, GET(), POST(), verifyAuth(), CATEGORY_MULTIPLIERS, DEFAULT_SUGGESTIONS, generatePrediction(), hashStr() (+6 more)

### Community 32 - "Stock Video Download"
Cohesion: 0.23
Nodes (15): download_clip(), _ffprobe_cmd(), get_video_duration(), _handle_rate_limit(), _keyword_expand(), Path, _rate_limit_delay(), Handle 429 rate limit. Sets circuit breaker for Pixabay, logs for Pexels. (+7 more)

### Community 33 - "Admin Authentication Routes"
Cohesion: 0.20
Nodes (11): POST(), POST(), verifyAuth(), GET(), verifyAuth(), GET(), verifyAuth(), GET() (+3 more)

### Community 34 - "Monetization Analytics Dashboard"
Cohesion: 0.15
Nodes (10): CategoryRevenue, DailyEntry, Milestone, PlatformRevenue, PlatformStats, RevenueData, VideoStats, DEFAULT_THRESHOLDS (+2 more)

### Community 35 - "Theme Toggle Component"
Cohesion: 0.53
Nodes (4): initTheme(), themeConfig, ThemeMode, toggleTheme()

### Community 36 - "Background Image Generation"
Cohesion: 0.24
Nodes (13): generate_color_solid(), generate_gradient_bedroom(), generate_gradient_classroom(), generate_gradient_forest(), generate_gradient_garden(), generate_gradient_night(), generate_gradient_ocean(), generate_gradient_sky() (+5 more)

### Community 37 - "Agent Control Listener"
Cohesion: 0.15
Nodes (7): AgentControlListener, Check if an agent is currently paused., Set callback for pipeline triggers from dashboard., Start background polling thread., Stop background polling thread., Check for pipeline run requests from the dashboard., Polls Firestore for agent control signals (pause/resume) and pipeline triggers.

### Community 38 - "Thumbnail Image Generation"
Cohesion: 0.27
Nodes (12): create_thumbnail_crew(), render_thumbnails(), _apply_glow(), _draw_circle_decoration(), _draw_gradient_bar(), _draw_grid(), _find_font(), generate_thumbnail() (+4 more)

### Community 39 - "Daily Cleanup Service"
Cohesion: 0.15
Nodes (14): daily_cleanup_job(), cleanup_after_upload(), cleanup_local_files(), cleanup_old_checkpoints(), Immediately clean up source/intermediate files after a successful upload.      K, Clean up local temp and old output files after successful uploads.      Args:, Delete old pipeline checkpoint files from the project root.      Args:         m, run_cleanup() (+6 more)

### Community 40 - "Title A/B Testing"
Cohesion: 0.27
Nodes (7): advance_title_test(), get_test_status(), _pick_winner(), record_title_ctr(), start_title_test(), _test_path(), TitleTester

### Community 41 - "Monetization Tracker & Thresholds"
Cohesion: 0.33
Nodes (10): get_platform_thresholds(), get_thresholds(), create_monetization_review_crew(), get_growth_summary(), load_tracker(), save_tracker(), _sync_to_firestore(), update_platform_metrics() (+2 more)

### Community 42 - "Video Compositing Fixes"
Cohesion: 0.17
Nodes (11): 1. Add diagnostic logging before every `return None`, 2. Scale FFmpeg timeout by format, 3. Clean old frames dir before rendering, 4. Guard `characters.json` load against I/O errors, 5. Fix `_render_effects` double-processing bug, Changes Required, File: `agents/utils/animation_engine.py`, Fix: Video Compositing Pipeline Failure (+3 more)

### Community 44 - "Dashboard Layout & Status"
Cohesion: 0.22
Nodes (5): navItems, GlobalStatusBar(), StatusPill, Notification, NotificationCenter()

### Community 45 - "Agent Skill Guidelines"
Cohesion: 0.18
Nodes (10): How to Use, Must Use, Recommended, Rule Categories by Priority, Skip, Step 1: Analyze User Requirements, Step 2: Use Quick Reference, Step 3: Apply Pre-Delivery Checklist (+2 more)

### Community 46 - "Vercel Environment Setup"
Cohesion: 0.36
Nodes (9): add_vercel_env(), github_api(), header(), info(), ok(), prompt_yn(), setup.sh script, vercel_api() (+1 more)

### Community 47 - "Scene Schema Validation"
Cohesion: 0.36
Nodes (7): test_validate_scenes_empty(), test_validate_scenes_invalid_missing_fields(), test_validate_scenes_valid(), test_validation_error_exception(), validate_scene(), validate_scenes(), ValidationError

### Community 48 - "Text Spotlight Animation"
Cohesion: 0.29
Nodes (9): assign_spotlights_to_scenes(), extract_spotlight_events(), _find_spotlight_font(), load_phrase_timing(), process_spotlights(), FreeTypeFont, ImageDraw, render_spotlight() (+1 more)

### Community 49 - "Channel Analytics Dashboard"
Cohesion: 0.24
Nodes (9): AnalyticsPage(), AnalyticsSummary, categories, ChannelStats, formatNumber(), generateLocalPrediction(), hashStr(), PredictionResult (+1 more)

### Community 50 - "Analytics Feedback & Recommendations"
Cohesion: 0.39
Nodes (8): daily_feedback_job(), analyze_recent_performance(), _generate_recommendations(), get_active_insights(), get_optimization_prompt_injection(), _load_feedback(), _save_feedback(), _sync_insights_to_firestore()

### Community 51 - "Video Performance Tracking"
Cohesion: 0.47
Nodes (7): calculate_engagement_rate(), get_performance_summary(), get_top_performing_videos(), load_analytics(), save_analytics(), track_video(), update_metrics()

### Community 53 - "Video Compilation Generation"
Cohesion: 0.33
Nodes (8): create_compilation(), create_compilation_from_shorts(), _ensure_format(), _find_executable(), _generate_transition(), _get_duration(), Path, Locate ffmpeg/ffprobe, checking env var override first, then common paths.

### Community 54 - "Subtitle File Generation"
Cohesion: 0.50
Nodes (8): _convert_word_times_to_phrases(), generate_srt(), generate_subtitles_for_video(), generate_vtt(), load_phrase_timing(), load_word_timing(), _ms_to_srt_time(), _ms_to_vtt_time()

### Community 55 - "React Error Boundary"
Cohesion: 0.25
Nodes (3): ErrorBoundary, Props, State

### Community 56 - "Vercel Deployment Configuration"
Cohesion: 0.22
Nodes (8): buildCommand, devCommand, env, NEXT_PUBLIC_APP_NAME, NEXT_PUBLIC_APP_URL, framework, installCommand, outputDirectory

### Community 57 - "Thumbnail Image Generation"
Cohesion: 0.43
Nodes (6): _draw_text_shadow(), _ensure_thumbnail_dir(), extract_text_overlay(), _find_font(), generate_thumbnail_image(), _wrap_text()

### Community 58 - "NPM Project Scripts"
Cohesion: 0.25
Nodes (7): name, private, scripts, build, dev, lint, start

### Community 59 - "Content Safety & Compliance"
Cohesion: 0.43
Nodes (3): check_content_safety(), check_platform_compliance(), get_monetization_thresholds()

### Community 60 - "Title Optimization & Scoring"
Cohesion: 0.38
Nodes (6): generate_title_variations(), pick_best_title(), Generate variations, score them, and return the best one., Generate A/B test title variations from a base title., Score a title for SEO and engagement potential., score_title()

### Community 61 - "Next Upload Timer"
Cohesion: 0.60
Nodes (4): calcTimeRemaining(), formatNPT(), NextUploadTimer(), TimeRemaining

### Community 62 - "Firestore Data Seeding"
Cohesion: 0.33
Nodes (4): Seed Firestore with initial pipeline data for dashboard monitoring., # NOTE: 'timi-childern-stories' is legacy — update when new Firebase project is, POST(), verifySignature()

### Community 63 - "Schedule Time Calculation"
Cohesion: 0.60
Nodes (5): _next_schedule_time(), test_returns_utc_iso_format(), test_slot_already_past_returns_tomorrow(), test_slot_format(), test_two_slots_different()

### Community 64 - "Authenticated API Routes"
Cohesion: 0.60
Nodes (5): DELETE(), GET(), POST(), PUT(), verifyAuth()

### Community 65 - "Authenticated API Routes"
Cohesion: 0.60
Nodes (5): DELETE(), GET(), POST(), PUT(), verifyAuth()

### Community 66 - "Model Installation Script"
Cohesion: 0.67
Nodes (5): download_model(), err(), log(), install.sh script, warn()

### Community 67 - "Video Cleanup Script"
Cohesion: 0.40
Nodes (5): cleanup(), __dirname, initApp(), OLD_TITLE_PATTERNS, projectRoot

### Community 69 - "Engagement Comment Management"
Cohesion: 0.60
Nodes (3): append_comment_prompt_to_script(), build_pinned_comment(), pick_comment_prompt()

### Community 70 - "Playwright Test Dependencies"
Cohesion: 0.40
Nodes (4): dependencies, @opencode-ai/plugin, @playwright/mcp, @playwright/test

### Community 71 - "Pipeline Service Setup"
Cohesion: 0.60
Nodes (3): install_linux(), install_macos(), setup-pipeline-service.sh script

### Community 73 - "MLX Engine Integration"
Cohesion: 0.83
Nodes (3): generate_clip(), is_available(), _run_mlx_pipeline()

### Community 74 - "ESLint Configuration"
Cohesion: 0.50
Nodes (3): extends, rules, @next/next/no-img-element

### Community 75 - "Authenticated API Routes"
Cohesion: 0.83
Nodes (3): GET(), POST(), verifyAuth()

## Knowledge Gaps
- **232 isolated node(s):** `@opencode-ai/plugin`, `@playwright/mcp`, `@playwright/test`, `run_scheduler.sh script`, `extends` (+227 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run_video_pipeline()` connect `Pipeline Trigger & Cleanup` to `Voiceover & Music Generation`, `Sound Effects Generation`, `Text Spotlight Animation`, `Video Pipeline Orchestration`, `Subtitle File Generation`, `Multi-Voice Voiceover Generation`?**
  _High betweenness centrality (0.058) - this node is a cross-community bridge._
- **Why does `get_firestore_client()` connect `Firestore Activity Logging` to `Content Quality Scoring`, `Content Hook & Repurposing`, `Multi-Platform Content Publishing`, `Agent Control Listener`, `Daily Cleanup Service`, `YouTube ID Extraction`, `Monetization Tracker & Thresholds`, `Content Calendar Management`, `Pipeline Trigger & Cleanup`, `Analytics Feedback & Recommendations`, `Video Pipeline Orchestration`, `Agent Health Monitoring`, `Telegram Bot Handler`, `Content Series Planning`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Are the 26 inferred relationships involving `get_firestore_client()` (e.g. with `get_thresholds()` and `_sync_to_firestore()`) actually correct?**
  _`get_firestore_client()` has 26 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `generate_long_video()` (e.g. with `check_content_safety()` and `enforce_rewrite()`) actually correct?**
  _`generate_long_video()` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 28 inferred relationships involving `generate_short_video()` (e.g. with `check_content_safety()` and `enforce_rewrite()`) actually correct?**
  _`generate_short_video()` has 28 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `get_llm()` (e.g. with `create_affiliate_manager_crew()` and `create_analyst_crew()`) actually correct?**
  _`get_llm()` has 17 INFERRED edges - model-reasoned connections that need verification._
- **What connects `@opencode-ai/plugin`, `@playwright/mcp`, `@playwright/test` to the rest of the system?**
  _341 weakly-connected nodes found - possible documentation gaps or missing edges._