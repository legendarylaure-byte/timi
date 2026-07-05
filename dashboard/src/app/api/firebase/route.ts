import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();

    const start = Date.now();
    const heartbeatDoc = await db.collection('system').doc('heartbeat').get();
    const latency = Date.now() - start;

    let heartbeat: Record<string, any> = { age_seconds: null, status: 'unknown' };
    if (heartbeatDoc.exists) {
      const hb = heartbeatDoc.data();
      const raw = hb?.last_heartbeat || hb?.last_seen || 0;
      const lastSeen = typeof raw === 'string' ? new Date(raw) : raw?.toDate?.() || new Date(raw);
      const ageSeconds = Math.round((Date.now() - lastSeen.getTime()) / 1000);
      heartbeat = {
        age_seconds: ageSeconds,
        status: ageSeconds < 300 ? 'fresh' : ageSeconds < 3600 ? 'stale' : 'dead',
        source: hb?.source || 'python-agent',
        last_heartbeat: hb?.last_heartbeat || null,
      };
    }

    const pipelineDoc = await db.collection('system').doc('pipeline').get();
    const pipeline = pipelineDoc.exists
      ? { running: pipelineDoc.data()?.running || false, current_video: pipelineDoc.data()?.current_video || null }
      : null;

    return NextResponse.json({
      connected: true,
      project_id: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'unknown',
      latency_ms: latency,
      heartbeat,
      pipeline,
    });
  } catch (error: any) {
    return NextResponse.json({
      connected: false,
      error: error.message,
    });
  }
}
