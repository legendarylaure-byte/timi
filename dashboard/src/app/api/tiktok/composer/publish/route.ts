import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { Timestamp } from 'firebase-admin/firestore';

// Audit-compliance: reject when no privacy level is selected (no implicit default),
// matching the backend hard-fail. Comment/duet/stitch default to off.
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { video_id, title, description, format, category, privacy_level, comment_disabled, duet_disabled, stitch_disabled } = body;

    if (!video_id || !title) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields: video_id, title' },
        { status: 400 },
      );
    }
    if (!privacy_level || !privacy_level.trim()) {
      return NextResponse.json(
        { success: false, error: 'privacy_level is required (no default is preselected)' },
        { status: 400 },
      );
    }

    const db = getAdminFirestore();
    const doc = await db.collection('tiktok_composer').add({
      video_id,
      title,
      description: description || '',
      format: format || 'shorts',
      category: category || '',
      privacy_level,
      comment_disabled: !!comment_disabled,
      duet_disabled: duet_disabled === undefined ? true : !!duet_disabled,
      stitch_disabled: stitch_disabled === undefined ? true : !!stitch_disabled,
      status: 'queued',
      created_at: Timestamp.now(),
    });

    return NextResponse.json({ success: true, intent_id: doc.id });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
