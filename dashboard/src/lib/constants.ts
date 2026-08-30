export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud';
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://timi.vyomai.cloud';

export interface AgentRole {
  id: string;
  name: string;
  emoji: string;
  color: string;
  description: string;
}

export const AGENT_ROLES: AgentRole[] = [
  {
    id: 'scriptwriter',
    name: 'Scriptwriter',
    emoji: '📝',
    color: '#FF6B6B',
    description: 'Writes a complete script for your video — like a TV show writer planning every scene and what the narrator will say',
  },
  {
    id: 'storyboard',
    name: 'Storyboard Artist',
    emoji: '🎨',
    color: '#4ECDC4',
    description: 'Draws a picture-by-picture plan of what viewers will see on screen for every scene',
  },
  {
    id: 'voice',
    name: 'Voice Actor',
    emoji: '🎙️',
    color: '#FFD93D',
    description: 'Records the narration using AI voices so your video has professional-sounding audio',
  },
  {
    id: 'composer',
    name: 'Composer',
    emoji: '🎵',
    color: '#A29BFE',
    description: 'Creates custom background music that matches the mood of each scene',
  },
  {
    id: 'animator',
    name: 'Animator',
    emoji: '🎬',
    color: '#8a50e8',
    description: 'Gathers all the visuals — stock footage, screen recordings, diagrams, and code snippets',
  },
  {
    id: 'editor',
    name: 'Video Editor',
    emoji: '✂️',
    color: '#F39C12',
    description: 'Stitches voice, music, and visuals together into the final video you can watch',
  },
  {
    id: 'thumbnail',
    name: 'Thumbnail Creator',
    emoji: '🖼️',
    color: '#E056FD',
    description: 'Designs the clickable cover image that makes people want to watch your video',
  },
  {
    id: 'metadata',
    name: 'Metadata Writer',
    emoji: '🏷️',
    color: '#22A6B3',
    description: 'Writes the title, description, and tags so YouTube and search engines can find your video',
  },
  {
    id: 'publisher',
    name: 'Publisher',
    emoji: '🚀',
    color: '#7ED6DF',
    description: 'Uploads your finished video to YouTube, Instagram, and Facebook (TikTok ready, enabled soon)',
  },
  {
    id: 'quality_scorer',
    name: 'Quality Scorer',
    emoji: '⭐',
    color: '#10B981',
    description: 'Reads the script and predicts how much viewers will love it before we invest time making it',
  },
  {
    id: 'trend_discovery',
    name: 'Trend Scout',
    emoji: '🔍',
    color: '#F97316',
    description: 'Scans YouTube and the internet to find what topics are hot right now',
  },
  {
    id: 'repurposer',
    name: 'Content Repurposer',
    emoji: '🔄',
    color: '#06B6D4',
    description: 'Splits long videos into short clips so you get more content from less work',
  },
  {
    id: 'scheduler',
    name: 'Scheduler AI',
    emoji: '📅',
    color: '#06D6A0',
    description: 'Plans the best times to publish each video so the most people see it',
  },
];

export const AGENT_STATUS = {
  IDLE: 'idle',
  WORKING: 'working',
  COMPLETED: 'completed',
  ERROR: 'error',
};

export const VIDEO_FORMATS = {
  SHORTS: { ratio: '9:16', maxDuration: 120, label: 'Shorts' },
  LONG: { ratio: '16:9', maxDuration: 300, label: 'Long Form' },
};

export interface ContentCategory {
  name: string;
  description: string;
  group: 'pillar' | 'news';
  isNews?: boolean;
  emoji?: string;
}

// Mirrors backend agents/utils/scene_schema.py VALID_CATEGORIES.
export const CONTENT_CATEGORIES: ContentCategory[] = [
  { name: 'AI News', description: 'Latest AI developments, model releases, industry moves', group: 'pillar', isNews: false, emoji: '🤖' },
  { name: 'Science & Technology', description: 'Science discoveries, tech innovations, research breakthroughs', group: 'pillar', isNews: false, emoji: '🔬' },
  { name: 'Programming & Software', description: 'Code tutorials, software engineering, development tools, AI tooling', group: 'pillar', isNews: false, emoji: '💻' },
  { name: 'World News (24hr)', description: 'Verified global stories from curated reputable publishers', group: 'news', isNews: true, emoji: '🌍' },
  { name: 'Nepal News', description: 'Verified news from reputable Nepali outlets (English + Nepali)', group: 'news', isNews: true, emoji: '🇳🇵' },
];

export const PILLAR_CATEGORIES = CONTENT_CATEGORIES.filter((c) => c.group === 'pillar');
export const NEWS_CATEGORIES = CONTENT_CATEGORIES.filter((c) => c.group === 'news');

// The pipeline is fixed at exactly 5 videos/day: 2 news shorts + 1 pillar short
// + 1 news long + 1 pillar long. News slots are mandatory; longs are capped by
// the single-GPU render budget. Mirrors env SHORTS_PER_DAY=1, LONG_PER_DAY=2,
// GPU_VIDEO_BUDGET_PER_DAY=2, ENABLE_NEWS=true.
export const DAILY_SCHEDULE = {
  newsShorts: 2,
  pillarShorts: 1,
  newsLong: 1,
  pillarLong: 1,
  shorts: 3,
  long: 2,
  total: 5,
  gpuBudget: 2,
  label: '5 videos/day',
};

// All publish slots fall inside the overnight idle window (8:50 PM Nepal start),
// on the same Nepal day. Times shown in Nepal local.
export const PUBLISH_SLOTS = [
  { id: 'world-short', label: 'World News short', category: 'World News (24hr)', format: 'shorts', npt: '12:45 AM', utc: '19:00 UTC' },
  { id: 'nepal-short', label: 'Nepal News short', category: 'Nepal News', format: 'shorts', npt: '2:45 AM', utc: '21:00 UTC' },
  { id: 'pillar-long', label: 'Pillar long', category: 'AI-IT pillar', format: 'long', npt: '3:00 AM', utc: '21:15 UTC' },
  { id: 'pillar-short', label: 'Pillar short', category: 'AI-IT pillar', format: 'shorts', npt: '4:45 AM', utc: '23:00 UTC' },
  { id: 'news-long', label: 'News long', category: 'World / Nepal News', format: 'long', npt: '6:45 AM', utc: '01:00 UTC' },
];

export const PLATFORMS = {
  YOUTUBE: { name: 'YouTube', color: '#FF0000' },
  TIKTOK: { name: 'TikTok', color: '#000000' },
  INSTAGRAM: { name: 'Instagram', color: '#E4405F' },
  FACEBOOK: { name: 'Facebook', color: '#1877F2' },
};

export const PIPELINE_STEPS = [
  { key: 'script', label: 'Script Generation', agentId: 'scriptwriter' },
  { key: 'storyboard', label: 'Storyboarding', agentId: 'storyboard' },
  { key: 'voice_generation', label: 'Voice Generation', agentId: 'voice' },
  { key: 'composition', label: 'Music Composition', agentId: 'composer' },
  { key: 'animation', label: 'Animation', agentId: 'animator' },
  { key: 'video_pipeline', label: 'Video Assembly', agentId: 'editor' },
  { key: 'editing', label: 'Editing', agentId: 'editor' },
  { key: 'thumbnail', label: 'Thumbnail Design', agentId: 'thumbnail' },
  { key: 'metadata', label: 'Metadata Optimization', agentId: 'metadata' },
  { key: 'publishing', label: 'Publishing', agentId: 'publisher' },
];

export const AGENT_COLORS: Record<string, string> = {
  scriptwriter: '#FF6B6B',
  storyboard: '#4ECDC4',
  voice: '#FFD93D',
  composer: '#A29BFE',
  animator: '#8a50e8',
  editor: '#F39C12',
  thumbnail: '#E056FD',
  metadata: '#22A6B3',
  publisher: '#7ED6DF',
};

export const RENDERING_STEPS = [
  'script', 'storyboard', 'voice_generation', 'composition', 'animation',
  'video_pipeline', 'editing', 'thumbnail', 'metadata', 'publishing',
];

export const SCHEDULE_HOUR_UTC = 15; // daily content generation fires at 15:05 UTC = 8:50 PM Nepal
export const SCHEDULE_MINUTE_UTC = 5;
export const KATHMANDU_TZ = 'Asia/Kathmandu';

export interface TimeRemaining {
  hours: number;
  minutes: number;
  seconds: number;
  totalMinutes: number;
  totalSeconds: number;
}

export function calcTimeRemaining(): TimeRemaining {
  const now = new Date();
  const scheduleTotalSec = SCHEDULE_HOUR_UTC * 3600 + SCHEDULE_MINUTE_UTC * 60;
  const utcNowTotalSec = now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();
  let diffSec = utcNowTotalSec < scheduleTotalSec
    ? scheduleTotalSec - utcNowTotalSec
    : (24 * 3600) - utcNowTotalSec + scheduleTotalSec;
  diffSec = Math.max(0, diffSec);
  return {
    hours: Math.floor(diffSec / 3600),
    minutes: Math.floor((diffSec % 3600) / 60),
    seconds: diffSec % 60,
    totalMinutes: Math.floor(diffSec / 60),
    totalSeconds: diffSec,
  };
}

export function formatNPT(date: Date): string {
  return date.toLocaleTimeString('en-US', {
    timeZone: KATHMANDU_TZ,
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
}

export function getNextUploadDisplay() {
  const rem = calcTimeRemaining();
  const nextDate = new Date(Date.now() + rem.totalSeconds * 1000);
  return {
    ...rem,
    nptTime: formatNPT(nextDate),
  };
}

export const HUMAN_READABLE_ACTIONS: Record<string, string> = {
  scriptwriting: 'writing the script',
  storyboarding: 'planning visuals',
  voice_generating: 'recording narration',
  composing: 'creating background music',
  animating: 'assembling visual assets',
  editing: 'compositing the video',
  thumbnail_creating: 'designing a thumbnail',
  metadata_writing: 'writing video metadata',
  uploading: 'publishing to platforms',
  scoring: 'evaluating content quality',
  discovering_trends: 'finding trending topics',
  repurposing: 'splitting videos into shorts',
  planning: 'planning content schedule',
};
