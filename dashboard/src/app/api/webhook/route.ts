import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || '';

function verifySignature(request: Request): boolean {
  const signature = request.headers.get('x-webhook-signature');
  if (!WEBHOOK_SECRET) return true; // no secret configured — allow
  if (!signature) return false;
  return signature === WEBHOOK_SECRET;
}

export async function POST(request: Request) {
  if (!verifySignature(request)) {
    return NextResponse.json({ success: false, error: 'Invalid signature' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const { event, source, payload, timestamp } = body;

    if (!event || !source) {
      return NextResponse.json({ success: false, error: 'Missing event or source' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('webhook_events').add({
      event,
      source,
      payload: payload || {},
      received_at: new Date().toISOString(),
      event_timestamp: timestamp || null,
      status: 'pending',
    });

    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[WEBHOOK] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
