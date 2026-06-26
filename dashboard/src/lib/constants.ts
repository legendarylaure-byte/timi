export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud';
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || (() => {
  if (typeof window !== 'undefined') {
    console.warn('NEXT_PUBLIC_APP_URL not set — falling back to localhost. YouTube OAuth redirects will break in production.');
  }
  return 'http://localhost:3000';
})();

export const AGENT_ROLES = [
  { id: 'scriptwriter', name: 'Scriptwriter', emoji: 'writer', color: '#FF6B6B' },
  { id: 'storyboard', name: 'Storyboard Artist', emoji: 'artist', color: '#4ECDC4' },
  { id: 'voice', name: 'Voice Actor', emoji: 'voice', color: '#FFD93D' },
  { id: 'composer', name: 'Composer', emoji: 'composer', color: '#A29BFE' },
  { id: 'animator', name: 'Animator', emoji: 'animator', color: '#00D2FF' },
  { id: 'editor', name: 'Video Editor', emoji: 'editor', color: '#F39C12' },
  { id: 'thumbnail', name: 'Thumbnail Creator', emoji: 'designer', color: '#E056FD' },
  { id: 'metadata', name: 'Metadata Writer', emoji: 'writer', color: '#22A6B3' },
  { id: 'publisher', name: 'Publisher', emoji: 'publisher', color: '#7ED6DF' },
  { id: 'quality_scorer', name: 'Quality Scorer', emoji: 'quality', color: '#10B981' },
  { id: 'trend_discovery', name: 'Trend Scout', emoji: 'trends', color: '#F97316' },
  { id: 'repurposer', name: 'Content Repurposer', emoji: 'repurpose', color: '#06B6D4' },
  { id: 'scheduler', name: 'Scheduler AI', emoji: 'scheduler', color: '#06D6A0' },
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

export const CONTENT_CATEGORIES = [
  { name: 'AI Explained', description: 'How AI and ML technologies work, explained simply' },
  { name: 'Deep Tech', description: 'In-depth technical deep dives and architecture breakdowns' },
  { name: 'Paper Breakdowns', description: 'Latest research papers summarized and analyzed' },
  { name: 'Tool Tutorials', description: 'Hands-on tutorials for AI tools and frameworks' },
  { name: 'Industry Analysis', description: 'Tech industry trends, predictions, and news analysis' },
  { name: 'Code & Build', description: 'Learn to build with code — projects and examples' },
  { name: 'AI News', description: 'Weekly AI and technology news roundup' },
  { name: 'Career & Learning', description: 'Tech career advice, learning paths, and resources' },
];

export const DAILY_QUOTA = {
  shorts: 2,
  long: 2,
};

export const PLATFORMS = {
  YOUTUBE: { name: 'YouTube', color: '#FF0000' },
  TIKTOK: { name: 'TikTok', color: '#000000' },
  INSTAGRAM: { name: 'Instagram', color: '#E4405F' },
  FACEBOOK: { name: 'Facebook', color: '#1877F2' },
};

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
