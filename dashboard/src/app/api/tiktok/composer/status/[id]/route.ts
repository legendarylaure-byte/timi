import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const { id } = await params;
    const db = getAdminFirestore();
    const snap = await db.collection('tiktok_composer').doc(id).get();
    if (!snap.exists) {
      return NextResponse.json({ success: false, error: 'Intent not found' }, { status: 404 });
    }
    const d = snap.data() || {};
    return NextResponse.json({
      success: true,
      id,
      status: d.status || 'unknown',
      privacy_level: d.privacy_level || '',
      title: d.title || '',
      publish_id: d.publish_id || '',
      url: d.url || '',
      error: d.error || '',
      created_at: d.created_at?.toMillis?.() ?? null,
      started_at: d.started_at ?? null,
      completed_at: d.completed_at ?? null,
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}