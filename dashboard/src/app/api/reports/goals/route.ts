import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';

const METRIC_LABELS: Record<string, string> = {
  subscribers: 'Subscribers',
  monthly_views: 'Monthly Views',
  revenue: 'Revenue ($)',
  videos_published: 'Videos Published',
  watch_hours: 'Watch Hours',
};

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const db = getAdminFirestore();
    const snap = await db.collection('reports').doc('goals').collection('items').orderBy('created_at', 'desc').get();

    const channelSnap = await db.collection('system').doc('channel_stats').get();
    const channelData = channelSnap.data() || {};
    const currentSubs = parseInt(channelData.subscribers || '0', 10);

    const revenueSnap = await db.collection('monetization').doc('revenue').get();
    const revenueData = revenueSnap.data() || {};

    const videosSnap = await db.collection('videos').count().get();
    const totalVideos = videosSnap.data()?.count || 0;

    const currentMetrics: Record<string, number> = {
      subscribers: currentSubs,
      monthly_views: parseInt(channelData.total_views || '0', 10),
      revenue: revenueData.currentMonth || 0,
      videos_published: totalVideos,
      watch_hours: Math.round(parseFloat(channelData.total_watch_hours || '0')),
    };

    const goals = snap.docs.map(doc => {
      const d = doc.data();
      const metric = d.metric as string;
      const target = d.target as number || 1;
      const current = currentMetrics[metric] || 0;
      const createdAt = d.created_at?.toDate?.()?.toISOString() || d.created_at || '';
      const deadline = d.deadline || '';

      let projectedDate: string | null = null;
      if (createdAt && current > 0) {
        const daysSinceCreation = Math.round((Date.now() - new Date(createdAt).getTime()) / 86400000);
        const growthRate = daysSinceCreation > 0 ? current / daysSinceCreation : 0;
        if (growthRate > 0) {
          const remaining = target - current;
          const daysToTarget = Math.round(remaining / growthRate);
          const projected = new Date();
          projected.setDate(projected.getDate() + daysToTarget);
          projectedDate = projected.toISOString().slice(0, 10);
        }
      }

      return {
        id: doc.id,
        metric,
        metricLabel: METRIC_LABELS[metric] || metric,
        target,
        current,
        deadline,
        createdAt,
        projectedDate,
        progress: target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0,
      };
    });

    return NextResponse.json({ goals, currentMetrics });
  } catch (error: any) {
    console.error('[GOALS] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const body = await request.json();
    const { metric, target, deadline } = body;

    if (!metric || !target || !deadline) {
      return NextResponse.json({ success: false, error: 'Missing required fields: metric, target, deadline' }, { status: 400 });
    }

    const validMetrics = ['subscribers', 'monthly_views', 'revenue', 'videos_published', 'watch_hours'];
    if (!validMetrics.includes(metric)) {
      return NextResponse.json({ success: false, error: `Invalid metric. Must be one of: ${validMetrics.join(', ')}` }, { status: 400 });
    }

    const db = getAdminFirestore();
    const ref = db.collection('reports').doc('goals').collection('items').doc();
    await ref.set({
      metric,
      target: Number(target),
      deadline,
      created_at: new Date(),
    });

    return NextResponse.json({ success: true, id: ref.id });
  } catch (error: any) {
    console.error('[GOALS CREATE] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    if (!id) {
      return NextResponse.json({ success: false, error: 'Missing id parameter' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('reports').doc('goals').collection('items').doc(id).delete();

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[GOALS DELETE] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
