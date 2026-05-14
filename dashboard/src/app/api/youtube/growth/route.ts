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

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const limitParam = parseInt(searchParams.get('limit') || '90');

    const db = getAdminFirestore();
    const snapshot = await db
      .collection('system')
      .doc('channel_stats')
      .collection('growth_history')
      .orderBy('recorded_at', 'desc')
      .limit(limitParam)
      .get();

    const history = snapshot.docs.map(doc => {
      const d = doc.data();
      return {
        id: doc.id,
        subscribers: d.subscribers || 0,
        total_views: d.total_views || 0,
        total_watch_hours: d.total_watch_hours || 0,
        video_count: d.video_count || 0,
        recorded_at: d.recorded_at || null,
      };
    });

    history.reverse();

    return NextResponse.json({ success: true, history });
  } catch (error: any) {
    console.error('[GROWTH API] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
