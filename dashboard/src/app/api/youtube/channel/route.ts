import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const db = getAdminFirestore();
    const doc = await db.collection('system').doc('channel_stats').get();

    if (!doc.exists) {
      return NextResponse.json({ success: true, channel: null });
    }

    const data = doc.data()!;
    return NextResponse.json({
      success: true,
      channel: {
        channel_name: data.channel_name || '',
        subscribers: data.subscribers || '0',
        total_views: data.total_views || '0',
        video_count: data.video_count || '0',
        thumbnail: data.thumbnail || '',
        last_updated: data.last_updated?.toDate?.()?.toISOString() || null,
      },
    });
  } catch (error: any) {
    console.error('[CHANNEL API] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
