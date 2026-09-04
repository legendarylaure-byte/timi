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

function ageSeconds(timestamp: any): number | null {
  if (!timestamp) return null;
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const age = (Date.now() - date.getTime()) / 1000;
  return Math.max(0, Math.round(age));
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const [pipelineSnap, heartbeatSnap, agentSnap] = await Promise.all([
      db.collection('system').doc('pipeline').get(),
      db.collection('system').doc('heartbeat').get(),
      db.collection('agent_status').get(),
    ]);

    const pipelineState = pipelineSnap.data() || {};
    const heartbeat = heartbeatSnap.data() || {};

    const lastHb = heartbeat.last_heartbeat || heartbeat.last_seen || 0;
    const hbAge = ageSeconds(lastHb);

    const agents = agentSnap.docs.map((doc) => {
      const d = doc.data();
      const stale =
        d.status === 'working' &&
        d.last_updated &&
        (ageSeconds(d.last_updated) ?? 999) > 300;
      return {
        id: d.agent_id || doc.id,
        name: d.name || doc.id,
        enabled: d.enabled !== false,
        status: stale ? 'stale' : d.status || 'idle',
        current_action: d.current_action || '',
        updated_too: ageSeconds(d.last_updated),
      };
    });

    return NextResponse.json({
      running: pipelineState.running || false,
      paused_by_user: pipelineState.paused_by_user || false,
      current_video: pipelineState.current_video || '',
      status: pipelineState.status || 'idle',
      started_at: pipelineState.started_at?.toDate?.().toISOString() || null,
      last_updated: pipelineState.last_updated?.toDate?.().toISOString() || null,
      agents,
      heartbeat: {
        age_seconds: hbAge,
        status: hbAge === null ? 'never' : hbAge < 300 ? 'fresh' : hbAge < 3600 ? 'stale' : 'dead',
        cpu_percent: heartbeat.cpu_percent ?? null,
        memory_percent: heartbeat.memory_percent ?? null,
        disk_percent: heartbeat.disk_percent ?? null,
        uptime_minutes: heartbeat.uptime_minutes ?? null,
        ollama_available: heartbeat.ollama_available ?? null,
      },
    });
  } catch (error: any) {
    console.error('[MONITOR LIVE] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}