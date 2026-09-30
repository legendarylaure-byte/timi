import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const { active } = await request.json();
    if (typeof active !== 'boolean') {
      return NextResponse.json({ error: 'active must be a boolean' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('viral_news_config').doc('settings').set(
      { active, last_toggled: new Date().toISOString(), toggled_by: 'dashboard' },
      { merge: true },
    );

    return NextResponse.json({ success: true, active });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to toggle viral agent' },
      { status: 500 },
    );
  }
}