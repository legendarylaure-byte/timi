import { NextResponse } from 'next/server';

const IDLE_BEHAVIORS = [
  {
    id: 'scriptwriter',
    name: 'Scriptwriter',
    idle_action: 'Monitoring content plan queue for new topics',
    next_trigger: 'Daily 06:00 UTC or manual pipeline trigger',
    idle_detail: 'Scans the content_plan and pipeline_triggers Firestore collections every 60s for pending topics. When idle, it has no queued scripts to write.',
  },
  {
    id: 'storyboard',
    name: 'Storyboard Artist',
    idle_action: 'Waiting for a completed script to visualize',
    next_trigger: 'Immediately after Scriptwriter finishes',
    idle_detail: 'Depends on the Scriptwriter. Once a script is written, the director reviews it, then the storyboard agent receives the script and begins planning scenes.',
  },
  {
    id: 'voice',
    name: 'Voice Actor',
    idle_action: 'Waiting for storyboard + script to generate narration',
    next_trigger: 'After storyboarding completes',
    idle_detail: 'Uses Edge TTS for voice synthesis. Idle while waiting for the storyboard agent to finish scene planning, which provides the narration cues.',
  },
  {
    id: 'composer',
    name: 'Composer',
    idle_action: 'Waiting for scene mood/vibe information',
    next_trigger: 'After storyboarding completes',
    idle_detail: 'Generates background music with MusicGen. Idle when no scene mood data is available from the storyboard step.',
  },
  {
    id: 'animator',
    name: 'Animator',
    idle_action: 'Waiting for scene descriptions to route to assets',
    next_trigger: 'After storyboarding completes',
    idle_detail: 'Routes scenes to the right asset engine: Manim for diagrams, PIL for mockups, Pexels for stock footage. Idle when no scenes are queued.',
  },
  {
    id: 'editor',
    name: 'Video Editor',
    idle_action: 'Waiting for all assets, voice, and music to be ready',
    next_trigger: 'After all assets + audio are generated',
    idle_detail: 'Composites everything with FFmpeg xfade transitions. This is the most resource-intensive step. Idle while upstream agents are still producing assets.',
  },
  {
    id: 'thumbnail',
    name: 'Thumbnail Creator',
    idle_action: 'Waiting for the final video render',
    next_trigger: 'After video editing completes',
    idle_detail: 'Uses PIL to render a high-CTR thumbnail with title text overlay. Idle until the editor finishes compositing.',
  },
  {
    id: 'metadata',
    name: 'Metadata Writer',
    idle_action: 'Waiting for video to be ready for SEO',
    next_trigger: 'After thumbnail creation',
    idle_detail: 'Generates SEO-optimized titles, descriptions, and tags based on the script content. Idle when no completed video is awaiting metadata.',
  },
  {
    id: 'publisher',
    name: 'Publisher',
    idle_action: 'Checking scheduled publish times and pending uploads',
    next_trigger: 'Every 15 min (scheduled_publish_job) or when a video is ready',
    idle_detail: 'Uploads to YouTube, TikTok, Instagram, and Facebook with AI disclosure flags. Idle most of the day — only active when a video is fully ready or a scheduled publish time is reached.',
  },
  {
    id: 'quality_scorer',
    name: 'Quality Scorer',
    idle_action: 'Waiting for new scripts to evaluate',
    next_trigger: 'After Scriptwriter creates a script',
    idle_detail: 'Scores the hook strength (1-100), rewrites if below 60. Also checks for problematic content. Idle between script evaluations.',
  },
  {
    id: 'trend_discovery',
    name: 'Trend Scout',
    idle_action: 'Scanning YouTube and web for trending tech topics',
    next_trigger: 'Daily analytics cycle (08:00 UTC)',
    idle_detail: 'Analyzes YouTube trending data and web search patterns to recommend high-potential topics. Runs on a daily cycle, not per-video.',
  },
  {
    id: 'repurposer',
    name: 'Content Repurposer',
    idle_action: 'Checking for long-form videos to split into shorts',
    next_trigger: 'Daily at 14:00 UTC',
    idle_detail: 'Splits long videos into short clips for cross-platform distribution. Runs on schedule, not per-video-trigger.',
  },
  {
    id: 'scheduler',
    name: 'Scheduler AI',
    idle_action: 'Planning optimal publish times for queued videos',
    next_trigger: 'Every 15 min (scheduled_publish_job)',
    idle_detail: 'Calculates best posting times based on audience analytics. Part of the APScheduler system, runs periodically to check and adjust the content calendar.',
  },
];

export async function GET() {
  return NextResponse.json({
    agents: IDLE_BEHAVIORS,
    summary: {
      total_agents: IDLE_BEHAVIORS.length,
      idle_behaviors: {
        waiting_for_upstream: IDLE_BEHAVIORS.filter(a =>
          a.idle_action.toLowerCase().includes('waiting')
        ).length,
        on_schedule: IDLE_BEHAVIORS.filter(a =>
          a.next_trigger.toLowerCase().includes('daily') ||
          a.next_trigger.toLowerCase().includes('min')
        ).length,
        on_trigger: IDLE_BEHAVIORS.filter(a =>
          a.next_trigger.toLowerCase().includes('after') ||
          a.next_trigger.toLowerCase().includes('immediately')
        ).length,
      },
    },
  });
}
