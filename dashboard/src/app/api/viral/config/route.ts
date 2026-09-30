import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function PUT(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const body = await request.json();
    const updates: Record<string, any> = {};
    if (typeof body.viral_threshold === 'number' && body.viral_threshold >= 0) {
      updates.viral_threshold = body.viral_threshold;
    }
    if (typeof body.hold_threshold === 'number' && body.hold_threshold >= 0) {
      updates.viral_hold_threshold = body.hold_threshold;
    }
    if (typeof body.max_per_day === 'number' && body.max_per_day >= 1) {
      updates.viral_max_per_day = body.max_per_day;
    }
    if (typeof body.cooldown_hours === 'number' && body.cooldown_hours >= 0) {
      updates.viral_cooldown_hours = body.cooldown_hours;
    }
    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ error: 'No valid fields to update' }, { status: 400 });
    }

    // Thresholds relative, so default hold = 75% of threshold when only
    // threshold is provided and hold stays below it.
    if ('viral_threshold' in updates && !('viral_hold_threshold' in updates)) {
      updates.viral_hold_threshold = Math.round(updates.viral_threshold * 0.75);
    }

    const db = getAdminFirestore();
    const doc = await db.collection('viral_news_config').doc('settings').get();
    const before: Record<string, any> = doc.exists ? doc.data() || {} : {};
    await db.collection('viral_news_config').doc('settings').set(
      { ...updates, updated_at: new Date().toISOString() },
      { merge: true },
    );

    return NextResponse.json({
      success: true,
      before,
      after: {
        viral_threshold: updates.viral_threshold ?? before.viral_threshold ?? 60,
        hold_threshold: updates.viral_hold_threshold ?? before.viral_hold_threshold ?? 45,
        max_per_day: updates.viral_max_per_day ?? before.viral_max_per_day ?? 2,
        cooldown_hours: updates.viral_cooldown_hours ?? before.viral_cooldown_hours ?? 6,
      },
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to update config' },
      { status: 500 },
    );
  }
}