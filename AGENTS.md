# AGENTS — Critical Context

## Latest Changes (Eras 1-4, committed 07780ae4)
- **Duration fix**: `_llm_scene_parse()` now injects `max_duration` into LLM prompt. `_adjust_scenes_for_format()` scales both up AND down.
- **Video quality**: Lanczos scaling, sharpening, color grading, 24fps uniform, CRF18/medium, universal negative prompt, audio mastering (compression + loudnorm I=-16).
- **Real-ESRGAN**: Binary at `agents/bin/realesrgan-ncnn-vulkan`. Wrapper at `agents/utils/upscaler.py`. Enable via `ENABLE_UPSCALE=true`.
- **Title A/B testing**: `update_youtube_video_title()` in `youtube_upload.py`. `daily_title_test_job` runs at 12:00 UTC.
- **Analytics**: Per-video CTR and avg view duration pulled via YouTube Analytics API v2.
- **End screen**: 5s Subscribe CTA appended to every video via `add_end_scene()`.
- **Content pillars**: 6 defined in `scheduler_planner.py` with ratios and series.
- **Dashboard**: Fixed 404 by cleaning `.next` cache. Port 5001.

## Remaining Setup (Era 5050+)
1. **TikTok OAuth**: Set `TIKTOK_ACCESS_TOKEN`, `TIKTOK_OPEN_ID`, `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET` env vars.
2. **Instagram OAuth**: Set `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID` env vars.
3. **YouTube Analytics API**: Re-auth needed to activate `yt-analytics.readonly` scope for CTR data.
4. **ElevenLabs voice**: Optional upgrade from edge-tts. Set `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`.
5. **CrewAI bug**: `_create_crew_output` bug at `crew.py:1646` — use `_execute_single_task()` + `agent.execute_task()` bypass. Not yet fixed in version pin.

## Run Commands
- Manual trigger: `SLOT=morning FORMAT=long CATEGORY="AI Explained" python3 run_pipeline.py` (from `agents/`)
- Dashboard: `cd dashboard && npm run dev` (port 5001)
- All files parse clean with Python 3.x.
