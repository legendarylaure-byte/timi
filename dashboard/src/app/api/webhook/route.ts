import { NextResponse } from 'next/server';
import { timingSafeEqual } from 'crypto';
import { getAdminFirestore } from '@/lib/firebase-admin';

const WEBHOOK_SECRET = process.env.WEBHOOK_SECRET || '';

function verifySignature(request: Request): boolean {
  // Fail CLOSED: an unset secret means nobody can authenticate, which is the
  // safe reading. The previous `if (!WEBHOOK_SECRET) return true` let anyone
  // POST forged webhook_events rows.
  if (!WEBHOOK_SECRET) {
    console.error('[WEBHOOK] WEBHOOK_SECRET is not configured — rejecting all inbound webhooks');
    return false;
  }
  const signature = request.headers.get('x-webhook-signature');
  if (!signature) return false;
  const a = Buffer.from(signature);
  const b = Buffer.from(WEBHOOK_SECRET);
  return a.length === b.length && timingSafeEqual(a, b);
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
