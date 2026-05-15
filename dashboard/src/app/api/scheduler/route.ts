import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';

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

    const schedulerDoc = await db.collection('system').doc('scheduler_status').get();
    const scheduler = schedulerDoc.exists
      ? {
          running: schedulerDoc.data()?.running ?? false,
          last_run: schedulerDoc.data()?.last_run?.toDate?.()?.toISOString() ?? null,
          next_run: schedulerDoc.data()?.next_run?.toDate?.()?.toISOString() ?? null,
          pid: schedulerDoc.data()?.pid ?? null,
          uptime_minutes: schedulerDoc.data()?.uptime_minutes ?? 0,
        }
      : { running: false, last_run: null, next_run: null, pid: null, uptime_minutes: 0 };

    const planSnap = await db.collection('content_plan').orderBy('scheduled_at', 'desc').limit(20).get();
    const plan = planSnap.docs.map(doc => {
      const d = doc.data();
      return {
        id: doc.id,
        title: d.title || '',
        category: d.category || '',
        format: d.format || 'shorts',
        scheduled_at: d.scheduled_at?.toDate?.()?.toISOString() ?? null,
        status: d.status || 'planned',
      };
    });

    const triggersSnap = await db.collection('pipeline_triggers').where('status', '==', 'pending').limit(10).get();
    const pending_triggers = triggersSnap.docs.map(doc => {
      const d = doc.data();
      return {
        id: doc.id,
        type: d.type || 'manual',
        topic: d.topic || '',
        format: d.format || 'shorts',
        created_at: d.created_at?.toDate?.()?.toISOString() ?? null,
      };
    });

    return NextResponse.json({ success: true, scheduler, plan, pending_triggers });
  } catch (error: any) {
    console.error('[SCHEDULER API] Error:', error);
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
    const { action } = body;

    if (!action || !['trigger', 'pause', 'resume'].includes(action)) {
      return NextResponse.json({ success: false, message: 'Invalid action. Must be trigger, pause, or resume' }, { status: 400 });
    }

    const db = getAdminFirestore();

    if (action === 'trigger') {
      const { topic, format, category } = body;
      await db.collection('pipeline_triggers').add({
        type: 'manual',
        topic: topic || '',
        format: format || 'shorts',
        category: category || '',
        status: 'pending',
        created_at: FieldValue.serverTimestamp(),
      });
      return NextResponse.json({ success: true, message: 'Manual trigger created successfully' });
    }

    if (action === 'pause' || action === 'resume') {
      await db.collection('system').doc('scheduler_status').set(
        { running: action === 'resume', updated_at: FieldValue.serverTimestamp() },
        { merge: true }
      );
      return NextResponse.json({ success: true, message: `Scheduler ${action === 'resume' ? 'resumed' : 'paused'} successfully` });
    }

    return NextResponse.json({ success: false, message: 'Unknown action' }, { status: 400 });
  } catch (error: any) {
    console.error('[SCHEDULER API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
