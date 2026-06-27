export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud';
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || (() => {
  if (typeof window !== 'undefined') {
    console.warn('NEXT_PUBLIC_APP_URL not set — falling back to localhost. YouTube OAuth redirects will break in production.');
  }
  return 'http://localhost:3000';
})();

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
    color: '#00D2FF',
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
    description: 'Uploads your finished video to YouTube, TikTok, Instagram, and Facebook',
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
