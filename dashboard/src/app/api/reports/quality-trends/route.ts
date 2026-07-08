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

function minutesAgo(timestamp: any): string {
  if (!timestamp) return 'never';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const diff = Math.floor((Date.now() - date.getTime()) / 60000);
  if (diff < 1) return 'just now';
  if (diff < 60) return `${diff}m ago`;
  const hours = Math.floor(diff / 60);
  return `${hours}h ago`;
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const now = new Date();
    const ninetyDaysAgo = new Date(now.getTime() - 90 * 86400000);

    const videosSnap = await db.collection('videos')
      .where('created_at', '>=', ninetyDaysAgo)
      .orderBy('created_at', 'desc')
      .limit(100)
      .get();

    const dailyBuckets: Record<string, { scores: number[]; virality: number[]; views: number[] }> = {};
    let lastUpdate: any = null;

    const anomalies: Array<{
      videoId: string; title: string; format: string;
      predictedViews: number; actualViews: number;
      deviation: number; type: 'overperformer' | 'underperformer';
    }> = [];

    const viewAverages: number[] = [];

    for (const doc of videosSnap.docs) {
      const d = doc.data();
      const createdAt = d.created_at?.toDate?.();
      if (!createdAt) continue;

      const dateKey = createdAt.toISOString().slice(0, 10);
      if (!dailyBuckets[dateKey]) {
        dailyBuckets[dateKey] = { scores: [], virality: [], views: [] };
      }

      const score = d.quality_score || d.brand_review_score || 0;
      if (score > 0) dailyBuckets[dateKey].scores.push(score);

      const vScore = d.virality_prediction?.overall_virality_score || 0;
      if (vScore > 0) dailyBuckets[dateKey].virality.push(vScore);

      const views = d.views || 0;
      if (views > 0) {
        dailyBuckets[dateKey].views.push(views);
        viewAverages.push(views);
      }

      const updated = d.analytics_updated_at || d.updated_at;
      if (updated && (!lastUpdate || updated.toDate?.() > lastUpdate.toDate?.())) {
        lastUpdate = updated;
      }

      const predictedViews = d.predicted_views_7d || 0;
      if (predictedViews > 0 && views > 0) {
        const deviation = ((views - predictedViews) / predictedViews) * 100;
        if (Math.abs(deviation) > 100) {
          anomalies.push({
            videoId: doc.id,
            title: d.title || 'Untitled',
            format: d.format || 'shorts',
            predictedViews,
            actualViews: views,
            deviation: Math.round(deviation * 10) / 10,
            type: deviation > 0 ? 'overperformer' : 'underperformer',
          });
        }
      }
    }

    const trends = Object.entries(dailyBuckets)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, bucket]) => ({
        date,
        avgQualityScore: bucket.scores.length > 0
          ? Math.round((bucket.scores.reduce((a, b) => a + b, 0) / bucket.scores.length) * 10) / 10
          : 0,
        avgViralityScore: bucket.virality.length > 0
          ? Math.round((bucket.virality.reduce((a, b) => a + b, 0) / bucket.virality.length) * 10) / 10
          : 0,
        avgViews: bucket.views.length > 0
          ? Math.round(bucket.views.reduce((a, b) => a + b, 0) / bucket.views.length)
          : 0,
        videoCount: Math.max(bucket.scores.length, bucket.virality.length, bucket.views.length),
      }));

    const avgAllViews = viewAverages.length > 0
      ? viewAverages.reduce((a, b) => a + b, 0) / viewAverages.length
      : 0;

    const correlationSummary = trends.length > 1
      ? `Across ${trends.length} days of data, average quality score is ${trends[trends.length - 1]?.avgQualityScore || 0} (latest) with ${anomalies.length} anomalous videos detected.`
      : 'Insufficient data for correlation analysis. Keep producing content to unlock insights.';

    return NextResponse.json({
      trends,
      anomalies: anomalies.slice(0, 10),
      correlationSummary,
      freshness: minutesAgo(lastUpdate),
      averageViewsOverall: Math.round(avgAllViews),
    });
  } catch (error: any) {
    console.error('[QUALITY TRENDS] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
