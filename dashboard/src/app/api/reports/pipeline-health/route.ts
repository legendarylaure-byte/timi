import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { PIPELINE_STEPS } from '@/lib/constants';

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

    const [metricsSnap, logsSnap, pipelineSnap] = await Promise.all([
      db.collection('pipeline_metrics').orderBy('created_at', 'desc').limit(200).get(),
      db.collection('activity_logs')
        .where('level', 'in', ['error', 'PIPELINE ERROR'])
        .orderBy('level')
        .orderBy('timestamp', 'desc')
        .limit(50)
        .get(),
      db.collection('system').doc('pipeline').get(),
    ]);

    let totalRuns = 0;
    let successCount = 0;
    const stepDurations: Record<string, number[]> = {};
    const stepFailures: Record<string, number> = {};
    let totalDurationSec = 0;
    let lastUpdate: any = null;

    for (const doc of metricsSnap.docs) {
      const d = doc.data();
      totalRuns++;
      if (d.success) successCount++;
      totalDurationSec += d.duration_sec || 0;

      if (d.steps && Array.isArray(d.steps)) {
        for (const step of d.steps) {
          const name = step.name || step.step || 'unknown';
          if (!stepDurations[name]) stepDurations[name] = [];
          if (step.duration_sec) stepDurations[name].push(step.duration_sec);
          if (step.error || step.status === 'failed') {
            stepFailures[name] = (stepFailures[name] || 0) + 1;
          }
        }
      }

      const created = d.created_at || d.timestamp;
      if (created && (!lastUpdate || created.toDate?.() > lastUpdate.toDate?.())) {
        lastUpdate = created;
      }
    }

    const stepBreakdown = PIPELINE_STEPS.map(({ key, label, agentId }) => {
      const durations = stepDurations[key] || [];
      const failures = stepFailures[key] || 0;
      const stepTotalRuns = totalRuns;
      return {
        step: key,
        label,
        agentId,
        avgDurationSec: durations.length > 0
          ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
          : 0,
        failureCount: failures,
        successRate: stepTotalRuns > 0
          ? Math.round(((stepTotalRuns - failures) / stepTotalRuns) * 100)
          : 0,
        totalRuns: stepTotalRuns,
      };
    });

    const recentErrors: Array<{ time: string; step: string; error: string; agentId: string }> = [];
    for (const doc of logsSnap.docs) {
      const d = doc.data();
      const ts = d.timestamp?.toDate?.()?.toISOString() || '';
      recentErrors.push({
        time: ts,
        step: d.agent_id || 'unknown',
        error: (d.message || '').slice(0, 200),
        agentId: d.agent_id || 'unknown',
      });
    }

    const pipelineState = pipelineSnap.data() || {};
    const isRunning = pipelineState.running || false;

    const successRate = totalRuns > 0 ? Math.round((successCount / totalRuns) * 100) : 0;
    const avgDurationSec = totalRuns > 0 ? Math.round(totalDurationSec / totalRuns) : 0;

    const estimatedCostMTD = Math.round((totalDurationSec / 3600) * 0.5 * 100) / 100;

    const revenueSnap = await db.collection('monetization').doc('revenue').get();
    const revenueData = revenueSnap.data() || {};
    const revenueMTD = revenueData.currentMonth || 0;
    const roi = estimatedCostMTD > 0 ? Math.round((revenueMTD / estimatedCostMTD) * 100) / 100 : 0;

    // Publish-specific errors from activity_logs
    const allLogsSnap = await db.collection('activity_logs')
      .orderBy('timestamp', 'desc')
      .limit(200)
      .get();
    const publishErrors: Array<{ time: string; platform: string; error: string }> = [];
    const platformFailCount: Record<string, number> = { youtube: 0, tiktok: 0, instagram: 0, facebook: 0 };
    for (const doc of allLogsSnap.docs) {
      const d = doc.data();
      if (d.agent_id !== 'publisher') continue;
      const msg = d.message || '';
      if (d.level === 'error' || d.level === 'warn') {
        const platform = msg.toLowerCase().includes('tiktok') ? 'tiktok' : msg.toLowerCase().includes('instagram') ? 'instagram' : msg.toLowerCase().includes('facebook') ? 'facebook' : msg.toLowerCase().includes('youtube') ? 'youtube' : 'unknown';
        platformFailCount[platform] = (platformFailCount[platform] || 0) + 1;
        const ts = d.timestamp?.toDate?.()?.toISOString() || '';
        publishErrors.push({ time: ts, platform, error: msg.slice(0, 200) });
      }
    }

    return NextResponse.json({
      successRate,
      totalRuns,
      avgDurationSec,
      isRunning,
      stepBreakdown,
      recentErrors: recentErrors.slice(0, 20),
      estimatedCostMTD,
      revenueMTD,
      roi,
      publishErrors: publishErrors.slice(0, 20),
      platformFailCount,
      freshness: minutesAgo(lastUpdate),
    });
  } catch (error: any) {
    console.error('[PIPELINE HEALTH] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
