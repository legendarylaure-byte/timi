import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { Timestamp } from 'firebase-admin/firestore';

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

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }
    const body = await request.json();
    const { topic, category, format, publish_at } = body;

    if (!topic || !category || !format) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields: topic, category, format' },
        { status: 400 },
      );
    }

    const db = getAdminFirestore();
    const doc = await db.collection('pipeline_triggers').add({
      topic,
      category,
      format,
      status: 'pending',
      publish_at: publish_at || null,
      created_at: Timestamp.now(),
    });

    await db.collection('system').doc('pipeline').set({
      running: true,
      current_video: `Triggered: "${topic.slice(0, 50)}${topic.length > 50 ? '...' : ''}"`,
      last_updated: Timestamp.now(),
    }, { merge: true });

    return NextResponse.json({
      success: true,
      id: doc.id,
      message: `Triggered ${format}: "${topic}"`,
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
