export const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME || 'Vyom Ai Cloud';
export const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000';

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
  { name: 'Self-Learning', description: 'Educational content for kids' },
  { name: 'Bedtime Stories', description: 'Calming stories for sleep' },
  { name: 'Mythology Stories', description: 'Ancient myths for children' },
  { name: 'Animated Fables', description: 'Classic fables with morals' },
  { name: 'Science for Kids', description: 'Fun science experiments' },
  { name: 'Rhymes & Songs', description: 'Nursery rhymes and music' },
  { name: 'Colors & Shapes', description: 'Visual learning basics' },
  { name: 'Tech & AI', description: 'Technology and AI trends' },
  { name: 'Gaming', description: 'Gaming content and reviews' },
  { name: 'Cooking & Food', description: 'Recipes and food content' },
  { name: 'DIY & Crafts', description: 'DIY projects and crafts' },
  { name: 'Health & Wellness', description: 'Health and fitness content' },
  { name: 'Travel & Adventure', description: 'Travel guides and adventures' },
  { name: 'Finance & Business', description: 'Finance and business tips' },
  { name: 'Comedy & Entertainment', description: 'Funny and entertaining content' },
  { name: 'Music & Dance', description: 'Music and dance content' },
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
  scriptwriting: 'crafting a story',
  storyboarding: 'drawing scenes',
  voice_generating: 'recording voices',
  composing: 'creating background music',
  animating: 'bringing characters to life',
  editing: 'putting the video together',
  thumbnail_creating: 'designing a thumbnail',
  metadata_writing: 'writing the video details',
  uploading: 'sharing the video',
  scoring: 'evaluating content quality',
  discovering_trends: 'finding trending topics',
  repurposing: 'splitting videos into shorts',
};
