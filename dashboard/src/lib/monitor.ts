export interface LiveAgent {
  id: string;
  name: string;
  enabled: boolean;
  status: string;
  current_action: string;
}

export interface LivePayload {
  running: boolean;
  paused_by_user: boolean;
  current_video: string;
  status: string;
  started_at: string | null;
  last_updated: string | null;
  agents: LiveAgent[];
  heartbeat: {
    age_seconds: number | null;
    status: 'never' | 'fresh' | 'stale' | 'dead';
    cpu_percent: number | null;
    memory_percent: number | null;
    disk_percent: number | null;
    uptime_minutes: number | null;
    ollama_available: boolean | null;
  };
}

export interface ReviewVideo {
  id: string;
  title: string;
  category: string;
  format: string;
  status: string;
  views: number;
  likes: number;
  comments: number;
  quality_score: number;
  virality_score: number;
  virality_prediction: string;
  predicted_views_7d: number;
  predicted_views_30d: number;
  estimated_watch_hours: number;
  published_platforms: string[];
  created_at: string;
}

export interface ReviewPayload {
  channel: {
    name: string;
    subscribers: number;
    total_views: number;
    video_count: number;
    total_watch_hours: number;
    updated_at: string | null;
  };
  revenue: {
    current_month: number;
    estimated_yearly: number;
  };
  pipeline: {
    total_runs: number;
    success_rate: number;
    success_count: number;
    avg_duration_sec: number;
    last_failures: Array<{
      created_at: string;
      format: string;
      topic: string;
      duration_sec: number;
    }>;
  };
  videos: ReviewVideo[];
}

export function healthColor(score: number): string {
  if (score >= 75) return '#10B981';
  if (score >= 50) return '#F59E0B';
  return '#EF4444';
}

export function healthLabel(score: number): string {
  if (score >= 75) return 'Healthy';
  if (score >= 50) return 'Needs attention';
  return 'At risk';
}