import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';

async function verifyAuth(request: Request): Promise<{ uid: string } | null> {
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  try {
    const token = authHeader.slice(7);
    const decoded = await getAdminAuth().verifyIdToken(token);
    return { uid: decoded.uid };
  } catch {
    return null;
  }
}

function pearsonR(xs: number[], ys: number[]): number {
  const n = xs.length;
  if (n < 3) return 0;
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = ys.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((a, _, i) => a + xs[i] * ys[i], 0);
  const sumX2 = xs.reduce((a, b) => a + b * b, 0);
  const sumY2 = ys.reduce((a, b) => a + b * b, 0);
  const num = n * sumXY - sumX * sumY;
  const den = Math.sqrt((n * sumX2 - sumX * sumX) * (n * sumY2 - sumY * sumY));
  return den === 0 ? 0 : Math.round((num / den) * 1000) / 1000;
}

function interpretR(r: number): string {
  const abs = Math.abs(r);
  if (abs >= 0.7) return 'strong';
  if (abs >= 0.4) return 'moderate';
  if (abs >= 0.2) return 'weak';
  return 'very weak';
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const videosSnap = await db.collection('videos')
      .orderBy('created_at', 'desc')
      .limit(100)
      .get();

    const hookScores: number[] = [];
    const qualityScores: number[] = [];
    const viralityScores: number[] = [];
    const views: number[] = [];
    const durations: number[] = [];
    const labels: string[] = [];
    const formats: string[] = [];
    const categories: string[] = [];
    const titles: string[] = [];

    for (const doc of videosSnap.docs) {
      const d = doc.data();
      const v = d.views || 0;
      if (v <= 0) continue;

      views.push(v);
      labels.push(doc.id.slice(0, 8));
      titles.push((d.title || 'Untitled').slice(0, 30));
      formats.push(d.format || 'shorts');
      categories.push(d.category || 'Unknown');

      const h = d.virality_prediction?.hook_strength || 0;
      hookScores.push(h);

      const q = d.quality_score || 0;
      qualityScores.push(q);

      const vs = d.virality_prediction?.overall_virality_score || 0;
      viralityScores.push(vs);

      const dur = d.duration_seconds || 0;
      durations.push(dur);
    }

    const correlations = [
      {
        factor: 'Hook Strength',
        metric: 'Views',
        pearsonR: pearsonR(hookScores, views),
        sampleSize: views.length,
        interpretation: `${interpretR(pearsonR(hookScores, views))} correlation`,
        scatterData: hookScores.slice(0, 50).map((x, i) => ({
          x, y: views[i] || 0,
          label: titles[i] || labels[i],
        })),
      },
      {
        factor: 'Quality Score',
        metric: 'Views',
        pearsonR: pearsonR(qualityScores, views),
        sampleSize: views.length,
        interpretation: `${interpretR(pearsonR(qualityScores, views))} correlation`,
        scatterData: qualityScores.slice(0, 50).map((x, i) => ({
          x, y: views[i] || 0,
          label: titles[i] || labels[i],
        })),
      },
      {
        factor: 'Virality Score',
        metric: 'Views',
        pearsonR: pearsonR(viralityScores, views),
        sampleSize: views.length,
        interpretation: `${interpretR(pearsonR(viralityScores, views))} correlation`,
        scatterData: viralityScores.slice(0, 50).map((x, i) => ({
          x, y: views[i] || 0,
          label: titles[i] || labels[i],
        })),
      },
      {
        factor: 'Duration (seconds)',
        metric: 'Views',
        pearsonR: pearsonR(durations, views),
        sampleSize: views.length,
        interpretation: `${interpretR(pearsonR(durations, views))} correlation`,
        scatterData: durations.slice(0, 50).map((x, i) => ({
          x, y: views[i] || 0,
          label: titles[i] || labels[i],
        })),
      },
    ];

    const formatAvg: Record<string, { total: number; count: number }> = {};
    const categoryAvg: Record<string, { total: number; count: number }> = {};
    for (let i = 0; i < views.length; i++) {
      const f = formats[i] || 'unknown';
      if (!formatAvg[f]) formatAvg[f] = { total: 0, count: 0 };
      formatAvg[f].total += views[i];
      formatAvg[f].count++;

      const c = categories[i] || 'Unknown';
      if (!categoryAvg[c]) categoryAvg[c] = { total: 0, count: 0 };
      categoryAvg[c].total += views[i];
      categoryAvg[c].count++;
    }

    const formatBreakdown = Object.entries(formatAvg).map(([name, s]) => ({
      name,
      avgViews: s.count > 0 ? Math.round(s.total / s.count) : 0,
      count: s.count,
    }));

    const categoryBreakdown = Object.entries(categoryAvg)
      .map(([name, s]) => ({
        name,
        avgViews: s.count > 0 ? Math.round(s.total / s.count) : 0,
        count: s.count,
      }))
      .sort((a, b) => b.avgViews - a.avgViews);

    return NextResponse.json({
      correlations,
      formatBreakdown,
      categoryBreakdown,
      totalVideosAnalyzed: views.length,
      insight: views.length >= 5
        ? `Analyzed ${views.length} videos. ${
            correlations.filter(c => Math.abs(c.pearsonR) >= 0.3).length
          } factors show meaningful correlation with views.`
        : 'Not enough data for meaningful correlation analysis. Need at least 5 videos with views.',
    });
  } catch (error: any) {
    console.error('[CORRELATIONS] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
