import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  const checks: Record<string, { status: string; detail?: string }> = {};
  let healthy = true;

  try {
    const db = getAdminFirestore();
    await db.collection('system').doc('health_check').set({
      last_check: new Date().toISOString(),
    }, { merge: true });
    checks.firestore = { status: 'ok' };
  } catch (e: any) {
    checks.firestore = { status: 'error', detail: e.message };
    healthy = false;
  }

  try {
    const pipelineDoc = await getAdminFirestore().collection('system').doc('pipeline').get();
    const pipeline = pipelineDoc.exists ? pipelineDoc.data() : null;
    checks.pipeline = { status: 'ok', detail: pipeline?.running ? 'running' : 'idle' };
  } catch {
    checks.pipeline = { status: 'unknown' };
  }

  try {
    const heartbeatDoc = await getAdminFirestore().collection('system').doc('heartbeat').get();
    if (heartbeatDoc.exists) {
      const hb = heartbeatDoc.data();
      const lastSeen = hb?.last_seen?.toDate?.() || new Date(hb?.last_seen || 0);
      const ageSeconds = (Date.now() - lastSeen.getTime()) / 1000;
      checks.agent_heartbeat = {
        status: ageSeconds < 120 ? 'ok' : 'stale',
        detail: `${Math.round(ageSeconds)}s ago`,
      };
      if (ageSeconds >= 120) healthy = false;
    } else {
      checks.agent_heartbeat = { status: 'unknown' };
    }
  } catch {
    checks.agent_heartbeat = { status: 'unknown' };
  }

  const statusCode = healthy ? 200 : 503;
  return NextResponse.json({
    status: healthy ? 'healthy' : 'degraded',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks,
  }, { status: statusCode });
}
