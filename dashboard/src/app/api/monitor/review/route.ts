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

function num(v: any): number {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n) ? n : 0;
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const [videosSnap, channelSnap, revenueSnap, metricsSnap] = await Promise.all([
      db.collection('videos').orderBy('created_at', 'desc').limit(60).get(),
      db.collection('system').doc('channel_stats').get(),
      db.collection('monetization').doc('revenue').get(),
      db.collection('pipeline_metrics').orderBy('created_at', 'desc').limit(200).get(),
    ]);

    const channel = channelSnap.data() || {};
    const revenue = revenueSnap.data() || {};

    let totalRuns = 0;
    let successCount = 0;
    const failures: Array<{ created_at: string; format: string; topic: string; duration_sec: number }> = [];
    const durations: number[] = [];
    for (const doc of metricsSnap.docs) {
      const d = doc.data();
      totalRuns++;
      if (d.success) successCount++;
      if (d.duration_sec) durations.push(d.duration_sec);
      if (!d.success) {
        failures.push({
          created_at: d.created_at?.toDate?.().toISOString() || '',
          format: d.format || 'unknown',
          topic: d.topic || '',
          duration_sec: d.duration_sec || 0,
        });
      }
    }
    const avgDurationSec =
      durations.length > 0 ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length) : 0;

    const videos = videosSnap.docs.map((doc) => {
      const d = doc.data();
      return {
        id: doc.id,
        title: d.title || '',
        category: d.category || '',
        format: d.format || 'shorts',
        status: d.status || '',
        views: num(d.views),
        likes: num(d.likes),
        comments: num(d.comments),
        quality_score: num(d.quality_score),
        virality_score: num(d.virality_score),
        virality_prediction: d.virality_prediction || '',
        predicted_views_7d: num(d.predicted_views_7d),
        predicted_views_30d: num(d.predicted_views_30d),
        estimated_watch_hours: num(d.estimated_watch_hours),
        published_platforms: Array.isArray(d.published_platforms) ? d.published_platforms : [],
        created_at: d.created_at?.toDate?.().toISOString() || '',
      };
    });

    return NextResponse.json({
      channel: {
        name: channel.channel_name || '',
        subscribers: num(channel.subscribers),
        total_views: num(channel.total_views),
        video_count: num(channel.video_count),
        total_watch_hours: num(channel.total_watch_hours),
        updated_at: channel.last_updated?.toDate?.().toISOString() || null,
      },
      revenue: {
        current_month: num(revenue.currentMonth),
        estimated_yearly: num(revenue.estimatedYearly),
      },
      pipeline: {
        total_runs: totalRuns,
        success_rate: totalRuns > 0 ? Math.round((successCount / totalRuns) * 100) : 0,
        success_count: successCount,
        avg_duration_sec: avgDurationSec,
        last_failures: failures.slice(0, 20),
      },
      videos,
    });
  } catch (error: any) {
    console.error('[MONITOR REVIEW] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}