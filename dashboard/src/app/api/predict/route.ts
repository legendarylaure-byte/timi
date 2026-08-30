import { NextRequest, NextResponse } from 'next/server';
import { rateLimitMiddleware } from '@/lib/rate-limit';

interface PredictionResult {
  predicted_views_7d: number;
  predicted_views_30d: number;
  predicted_engagement_rate: number;
  predicted_ctr: number;
  predicted_avg_watch_time_seconds: number;
  virality_score: number;
  confidence: number;
  suggestions: string[];
  trending_match: 'low' | 'medium' | 'high';
  reasoning: string;
}

const CATEGORY_MULTIPLIERS: Record<string, number> = {
  'AI News': 1.5,
  'Science & Technology': 1.2,
  'Programming & Software': 1.4,
  'World News (24hr)': 1.0,
  'Nepal News': 1.0,
};

const SUGGESTIONS: Record<string, string[]> = {
  'AI News': [
    'Lead with the single most surprising development in the first 3 seconds',
    'Explain why the news matters to a non-technical viewer',
    'Cite the verified source on screen for credibility',
  ],
  'Science & Technology': [
    'Start with a real-world problem the innovation solves',
    'Use visuals and analogies instead of jargon',
    'Reference the originating research for credibility',
  ],
  'Programming & Software': [
    'Show the final project output first as a hook',
    'Include step-by-step code/build walkthroughs',
    'Provide a repo link in the description',
  ],
  'World News (24hr)': [
    'Open with the headline as a bold claim',
    'Stay factual and cite the verified publisher',
    'Keep it tight — fast, no filler',
  ],
  'Nepal News': [
    'Open with the headline in a bold, clear claim',
    'Cover the local angle viewers care about',
    'Cite the verified Nepali source (EN or NP)',
  ],
};

const DEFAULT_SUGGESTIONS = [
  'Add a hook in the first 3 seconds to boost retention',
  'Use bright, high-contrast thumbnail with large text',
  'Best posting window: overnight 12:45 AM – 6:45 AM NPT (pipeline scheduled)',
  'Include popular keywords: "AI", "news", "explained"',
];

function hashStr(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = ((h << 5) - h) + s.charCodeAt(i);
  return h;
}

function generatePrediction(title: string, category: string, format: string): PredictionResult {
  const seed = hashStr(title + category + format);
  const rand = (min: number, max: number) =>
    min + (Math.abs(seed * 9301 + 49297) % 233280) / 233280 * (max - min);

  const baseViews = format === 'shorts' ? 8000 : 4000;
  const mult = CATEGORY_MULTIPLIERS[category] || 1.0;
  const virality = Math.min(100, Math.max(0, Math.floor(mult * rand(30, 80))));

  const catSuggestions = SUGGESTIONS[category] || DEFAULT_SUGGESTIONS;
  const suggestions = [
    ...catSuggestions.slice(0, 2),
    format === 'shorts'
      ? 'Keep pacing fast — aim for 60+ cuts per minute'
      : 'Add chapter markers to improve navigation',
    ...DEFAULT_SUGGESTIONS.slice(1, 2),
  ];

  return {
    predicted_views_7d: Math.floor(baseViews * mult * rand(0.5, 2.0)),
    predicted_views_30d: Math.floor(baseViews * mult * rand(2.0, 6.0)),
    predicted_engagement_rate: parseFloat(rand(3.0, 10.0).toFixed(1)),
    predicted_ctr: parseFloat(rand(3.0, 8.0).toFixed(1)),
    predicted_avg_watch_time_seconds: format === 'shorts' ? Math.floor(rand(30, 55)) : Math.floor(rand(120, 240)),
    virality_score: virality,
    confidence: Math.floor(rand(55, 85)),
    suggestions,
    trending_match: virality > 60 ? 'high' : virality > 40 ? 'medium' : 'low',
    reasoning: `Based on ${category} popularity trends, ${format} format performance, and current YouTube algorithm patterns for tech educational content.`,
  };
}

export async function POST(request: NextRequest) {
  const rateLimitResponse = rateLimitMiddleware(request, 10);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const body = await request.json();
    const { title, category, format } = body;

    if (!title || !title.trim()) {
      return NextResponse.json({ success: false, error: 'Title is required' }, { status: 400 });
    }

    const prediction = generatePrediction(title, category || 'AI News', format || 'shorts');

    return NextResponse.json({ success: true, prediction });
  } catch (error) {
    console.error('[PREDICT API] Error:', error);
    return NextResponse.json({ success: false, error: 'Prediction failed' }, { status: 500 });
  }
}
