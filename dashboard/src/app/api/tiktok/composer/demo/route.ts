import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const body = await request.json().catch(() => ({}));
    const topic = String(body.topic || '').trim();
    if (!topic) {
      return NextResponse.json(
        { success: false, error: 'Topic is required' },
        { status: 400 }
      );
    }
    if (topic.length > 120) {
      return NextResponse.json(
        { success: false, error: 'Topic too long (max 120 chars)' },
        { status: 400 }
      );
    }

    const db = getAdminFirestore();
    const ref = db.collection('demo_video_requests').doc();
    await ref.set({
      topic,
      status: 'queued',
      created_at: new Date(),
    });
    return NextResponse.json({ success: true, id: ref.id, topic });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}