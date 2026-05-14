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

    const db = getAdminFirestore();
    const snapshot = await db.collection('videos').orderBy('created_at', 'desc').limit(50).get();

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStr = today.toISOString();

    let shorts = 0;
    let longs = 0;
    const videos = snapshot.docs.map(doc => {
      const d = doc.data();
      const createdAt = d.created_at?.toDate?.()?.toISOString() || '';
      if (createdAt >= todayStr) {
        if (d.format === 'shorts') shorts++;
        else longs++;
      }
      return {
        id: doc.id,
        title: d.title || '',
        format: d.format || 'shorts',
        status: d.status || '',
        video_url: d.video_url || '',
        created_at: createdAt,
      };
    });

    return NextResponse.json({
      videos,
      total: videos.length,
      today: { shorts, long: longs },
    });
  } catch (error: any) {
    console.error('[VIDEOS API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }
    const body = await request.json();
    return NextResponse.json({ success: true, videoId: Date.now().toString(), ...body });
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid request' }, { status: 400 });
  }
}
