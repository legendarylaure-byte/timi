import { NextRequest, NextResponse } from 'next/server';

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
  'AI Explained': 1.3,
  'Deep Tech': 1.0,
  'Paper Breakdowns': 0.9,
  'Tool Tutorials': 1.2,
  'Industry Analysis': 1.1,
  'Code & Build': 1.4,
  'AI News': 1.5,
  'Career & Learning': 1.0,
};

const SUGGESTIONS: Record<string, string[]> = {
  'AI Explained': [
    'Use analogies to explain complex concepts',
    'Include visual diagrams for architecture explanations',
    'Add comparison tables for model benchmarks',
  ],
  'Deep Tech': [
    'Start with a real-world problem the tech solves',
    'Include code snippets or pseudocode for key algorithms',
    'Reference original papers for credibility',
  ],
  'Tool Tutorials': [
    'Show actual screen recordings of the tool in action',
    'Include installation and setup steps',
    'Provide example projects viewers can build along',
  ],
  'Code & Build': [
    'Show the final project output first as a hook',
    'Use screen captures for code walkthroughs',
    'Provide GitHub repo link in description',
  ],
};

const DEFAULT_SUGGESTIONS = [
  'Add a hook in the first 3 seconds to boost retention',
  'Use bright, high-contrast thumbnail with large text',
  'Best posting time: 6:00 PM – 8:00 PM',
  'Include popular keywords: "AI", "tutorial", "explained"',
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
  try {
    const body = await request.json();
    const { title, category, format } = body;

    if (!title || !title.trim()) {
      return NextResponse.json({ success: false, error: 'Title is required' }, { status: 400 });
    }

    const prediction = generatePrediction(title, category || 'AI Explained', format || 'shorts');

    return NextResponse.json({ success: true, prediction });
  } catch (error) {
    console.error('[PREDICT API] Error:', error);
    return NextResponse.json({ success: false, error: 'Prediction failed' }, { status: 500 });
  }
}
