import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';
import { rateLimitMiddleware } from '@/lib/rate-limit';

export async function POST(request: Request) {
  const rateLimitResponse = rateLimitMiddleware(request, 30);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const db = getAdminFirestore();

    const agentSnap = await db.collection('agent_status').get();
    let resetCount = 0;
    const batch = db.batch();
    agentSnap.docs.forEach((doc) => {
      const data = doc.data();
      if (data.status !== 'idle') {
        batch.set(doc.ref, {
          status: 'idle',
          current_action: 'Ready',
          last_updated: FieldValue.serverTimestamp(),
        }, { merge: true });
        resetCount++;
      }
    });

    batch.set(db.collection('system').doc('pipeline'), {
      running: false,
      current_video: '',
      status: 'cleared',
      last_updated: FieldValue.serverTimestamp(),
    }, { merge: true });

    await batch.commit();

    return NextResponse.json({ success: true, resetCount });
  } catch (error: any) {
    console.error('[RESET API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
