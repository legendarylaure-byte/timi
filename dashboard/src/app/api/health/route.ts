import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

const HEARTBEAT_TTL_MS = 60000;

async function ensureHeartbeat(db: FirebaseFirestore.Firestore) {
  try {
    const doc = await db.collection('system').doc('heartbeat').get();
    if (doc.exists) {
      const data = doc.data();
      const raw = data?.last_heartbeat || data?.last_seen || 0;
      const lastSeen = typeof raw === 'string' ? new Date(raw) : raw?.toDate?.() || new Date(raw);
      const age = Date.now() - lastSeen.getTime();
      if (age < HEARTBEAT_TTL_MS) return;
    }
    await db.collection('system').doc('heartbeat').set({
      last_heartbeat: new Date().toISOString(),
      source: 'dashboard-server',
      pid: process.pid,
      uptime_minutes: Math.round(process.uptime() / 60),
      node_version: process.version,
    }, { merge: true });
  } catch {
    // heartbeat write is best-effort
  }
}

export async function GET() {
  const checks: Record<string, { status: string; detail?: string }> = {};
  let healthy = true;

  try {
    const db = getAdminFirestore();
    await ensureHeartbeat(db);
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
      const raw = hb?.last_heartbeat || hb?.last_seen || 0;
      const lastSeen = typeof raw === 'string' ? new Date(raw) : raw?.toDate?.() || new Date(raw);
      const ageSeconds = (Date.now() - lastSeen.getTime()) / 1000;
      checks.agent_heartbeat = {
        status: ageSeconds < 300 ? 'ok' : 'stale',
        detail: `${Math.round(ageSeconds)}s ago (${hb?.source || 'python agent'})`,
      };
    } else {
      checks.agent_heartbeat = { status: 'unknown' };
    }
  } catch {
    checks.agent_heartbeat = { status: 'unknown' };
  }

  return NextResponse.json({
    status: healthy ? 'healthy' : 'degraded',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    checks,
  }, { status: 200 });
}
