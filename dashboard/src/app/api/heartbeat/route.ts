import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const doc = await db.collection('system').doc('heartbeat').get();
    if (!doc.exists) {
      return NextResponse.json({ last_heartbeat: null, status: 'never' });
    }
    const data = doc.data()!;
    const raw = data.last_heartbeat || data.last_seen || 0;
    const lastSeen = typeof raw === 'string' ? new Date(raw) : raw?.toDate?.() || new Date(raw);
    const ageSeconds = Math.round((Date.now() - lastSeen.getTime()) / 1000);
    return NextResponse.json({
      last_heartbeat: data.last_heartbeat || null,
      pid: data.pid || null,
      uptime_minutes: data.uptime_minutes || null,
      ollama_available: data.ollama_available ?? null,
      cpu_percent: data.cpu_percent ?? null,
      memory_percent: data.memory_percent ?? null,
      disk_percent: data.disk_percent ?? null,
      age_seconds: ageSeconds,
      status: ageSeconds < 300 ? 'fresh' : ageSeconds < 3600 ? 'stale' : 'dead',
    });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}

export async function POST() {
  try {
    const db = getAdminFirestore();
    const now = new Date().toISOString();
    const stats = {
      last_heartbeat: now,
      source: 'dashboard-server',
      pid: process.pid,
      uptime_minutes: Math.round(process.uptime() / 60),
      node_version: process.version,
      timestamp: Date.now(),
    };
    await db.collection('system').doc('heartbeat').set(stats, { merge: true });
    return NextResponse.json({ written: true, timestamp: now });
  } catch (error: any) {
    return NextResponse.json({ written: false, error: error.message }, { status: 500 });
  }
}
