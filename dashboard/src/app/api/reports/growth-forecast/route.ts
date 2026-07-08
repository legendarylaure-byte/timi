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

function linearProjection(
  history: Array<{ date: Date; value: number }>,
  daysToProject: number,
): number[] {
  if (history.length < 2) return [];
  const n = history.length;
  const avgX = (n - 1) / 2;
  const avgY = history.reduce((s, h) => s + h.value, 0) / n;
  let num = 0, den = 0;
  for (let i = 0; i < n; i++) {
    const dx = i - avgX;
    const dy = history[i].value - avgY;
    num += dx * dy;
    den += dx * dx;
  }
  const slope = den !== 0 ? num / den : 0;
  const intercept = avgY - slope * avgX;
  return Array.from({ length: daysToProject }, (_, i) => {
    const projected = intercept + slope * (n + i);
    return Math.max(0, Math.round(projected));
  });
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 500 });
    }

    const db = getAdminFirestore();
    const historySnap = await db.collection('system').doc('channel_stats')
      .collection('growth_history')
      .orderBy('recorded_at', 'asc')
      .limit(365)
      .get();

    let lastUpdate: any = null;

    const growthHistory: Array<{ date: string; subs: number; views: number; watchHours: number }> = [];
    for (const doc of historySnap.docs) {
      const d = doc.data();
      const ts = d.recorded_at;
      if (!ts) continue;
      const date = ts.toDate ? ts.toDate().toISOString().slice(0, 10) : String(ts).slice(0, 10);
      growthHistory.push({
        date,
        subs: d.subscribers || 0,
        views: d.total_views || 0,
        watchHours: Math.round(d.total_watch_hours || 0),
      });
      if (!lastUpdate) lastUpdate = ts;
    }

    const channelSnap = await db.collection('system').doc('channel_stats').get();
    const channelData = channelSnap.data() || {};
    const currentSubs = parseInt(channelData.subscribers || '0', 10);
    const currentViews = parseInt(channelData.total_views || '0', 10);
    const currentWatchHours = parseFloat(channelData.total_watch_hours || '0');
    const currentVideoCount = parseInt(channelData.video_count || '0', 10);

    const today = new Date().toISOString().slice(0, 10);
    const hasTodayEntry = growthHistory.length > 0 && growthHistory[growthHistory.length - 1].date === today;
    if (!hasTodayEntry && (currentSubs > 0 || currentViews > 0)) {
      growthHistory.push({
        date: today,
        subs: currentSubs,
        views: currentViews,
        watchHours: Math.round(currentWatchHours),
      });
    }

    const subsHistory = growthHistory.map(h => ({ date: new Date(h.date), value: h.subs }));
    const viewsHistory = growthHistory.map(h => ({ date: new Date(h.date), value: h.views }));

    const projectionDays = 90;
    const subsProjection = linearProjection(subsHistory, projectionDays);
    const viewsProjection = linearProjection(viewsHistory, projectionDays);

    const projection: Array<{ date: string; subs: number; views: number }> = [];
    const lastDate = growthHistory.length > 0 ? new Date(growthHistory[growthHistory.length - 1].date) : new Date();
    for (let i = 0; i < projectionDays; i++) {
      const d = new Date(lastDate);
      d.setDate(d.getDate() + i + 1);
      projection.push({
        date: d.toISOString().slice(0, 10),
        subs: subsProjection[i] ?? currentSubs,
        views: viewsProjection[i] ?? currentViews,
      });
    }

    const milestones: Array<{
      target: number; metric: string;
      estimatedDate: string; confidence: 'high' | 'medium' | 'low';
    }> = [];

    const subTargets = [500, 1000, 5000, 10000, 50000, 100000];
    for (const target of subTargets) {
      if (currentSubs >= target) continue;
      const projected = projection.find(p => p.subs >= target);
      if (projected) {
        milestones.push({
          target,
          metric: 'subscribers',
          estimatedDate: projected.date,
          confidence: projection.length > 30 ? 'medium' : 'low',
        });
        break;
      }
    }

    if (milestones.length === 0 && currentSubs < 100000) {
      const nextTarget = subTargets.find(t => t > currentSubs);
      if (nextTarget) {
        const growthRate = subsHistory.length > 1
          ? (subsHistory[subsHistory.length - 1].value - subsHistory[0].value) / subsHistory.length
          : 0;
        if (growthRate > 0) {
          const daysToTarget = Math.round((nextTarget - currentSubs) / growthRate);
          const estDate = new Date();
          estDate.setDate(estDate.getDate() + daysToTarget);
          milestones.push({
            target: nextTarget,
            metric: 'subscribers',
            estimatedDate: estDate.toISOString().slice(0, 10),
            confidence: 'low',
          });
        }
      }
    }

    return NextResponse.json({
      history: growthHistory,
      projection,
      milestones,
      freshness: minutesAgo(lastUpdate),
      currentStats: {
        subscribers: currentSubs,
        totalViews: currentViews,
        watchHours: Math.round(currentWatchHours),
        videoCount: currentVideoCount,
      },
    });
  } catch (error: any) {
    console.error('[GROWTH FORECAST] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
