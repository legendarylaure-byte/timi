export interface ReportSummary {
  totalVideos: number;
  publishedVideos: number;
  totalViews: number;
  totalSubs: number;
  monthlyRevenue: number;
  estimatedYearly: number;
  pipelineSuccessRate: number;
  bestCategory: { name: string; avgViews: number } | null;
  bestFormat: 'shorts' | 'long' | null;
  periodComparison: {
    viewsChange: number;
    subsChange: number;
    revenueChange: number;
  };
  freshness: {
    views: string;
    subs: string;
    revenue: string;
    pipeline: string;
  };
  todayCount: { shorts: number; long: number };
  formatBreakdown: { shorts: number; long: number };
}

export interface QualityTrend {
  date: string;
  avgQualityScore: number;
  avgViralityScore: number;
  avgViews: number;
  videoCount: number;
}

export interface QualityTrendsResponse {
  trends: QualityTrend[];
  anomalies: AnomalyItem[];
  correlationSummary: string;
  freshness: string;
}

export interface AnomalyItem {
  videoId: string;
  title: string;
  format: string;
  predictedViews: number;
  actualViews: number;
  deviation: number;
  type: 'overperformer' | 'underperformer';
}

export interface PipelineHealth {
  successRate: number;
  totalRuns: number;
  avgDurationSec: number;
  stepBreakdown: PipelineStepHealth[];
  recentErrors: PipelineError[];
  estimatedCostMTD: number;
  revenueMTD: number;
  roi: number;
  freshness: string;
}

export interface PipelineStepHealth {
  step: string;
  label: string;
  avgDurationSec: number;
  failureCount: number;
  successRate: number;
  totalRuns: number;
}

export interface PipelineError {
  time: string;
  step: string;
  error: string;
  agentId: string;
}

export interface CorrelationResult {
  factor: string;
  metric: string;
  pearsonR: number;
  interpretation: string;
  sampleSize: number;
  scatterData: Array<{ x: number; y: number; label: string }>;
}

export interface GrowthForecast {
  history: Array<{ date: string; subs: number; views: number; watchHours: number }>;
  projection: Array<{ date: string; subs: number; views: number }>;
  milestones: Array<{ target: number; metric: string; estimatedDate: string; confidence: 'high' | 'medium' | 'low' }>;
  freshness: string;
}

export interface ContentGap {
  category: string;
  daysSinceLastPost: number;
  isTrending: boolean;
  avgViews: number;
  avgScore: number;
  recommendation: string;
  totalVideos: number;
}

export interface Goal {
  id: string;
  metric: 'subscribers' | 'monthly_views' | 'revenue' | 'videos_published' | 'watch_hours';
  target: number;
  current: number;
  deadline: string;
  createdAt: string;
  projectedDate: string | null;
  progress: number;
}

export interface GoalInput {
  metric: Goal['metric'];
  target: number;
  deadline: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: Array<{ label: string; type: 'link' | 'trigger'; target: string }>;
  timestamp: string;
}

export interface ChatRequest {
  message: string;
  sessionId?: string;
}

export interface ChatResponse {
  sessionId: string;
  message: string;
  actions?: ChatMessage['actions'];
}
