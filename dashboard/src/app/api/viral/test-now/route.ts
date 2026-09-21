import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function POST() {
  try {
    const db = getAdminFirestore();
    const trigger = await db.collection('viral_news_triggers').add({
      status: 'queued',
      requested_at: new Date().toISOString(),
      source: 'dashboard',
    });

    return NextResponse.json({
      success: true,
      trigger_id: trigger.id,
      message: 'Viral scan triggered. The backend consumer (runs every 5 min) will process it and results appear in the activity feed.',
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to trigger viral scan' },
      { status: 500 },
    );
  }
}