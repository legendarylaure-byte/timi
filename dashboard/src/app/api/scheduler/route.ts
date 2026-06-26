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

    const planSnap = await db.collection('content_plan').orderBy('scheduled_at', 'desc').limit(50).get();
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

    const seriesPlansSnap = await db.collection('series_plans').where('status', '==', 'active').get();
    const seriesPlans = seriesPlansSnap.docs.map(doc => ({
      id: doc.id,
      title: doc.data().title || '',
      parts: doc.data().parts || [],
      categories: doc.data().categories || [],
    }));

    return NextResponse.json({ success: true, scheduler, plan, pending_triggers, series_plans: seriesPlans });
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

    if (!action || !['trigger', 'pause', 'resume', 'schedule_series'].includes(action)) {
      return NextResponse.json({ success: false, message: 'Invalid action. Must be trigger, pause, resume, or schedule_series' }, { status: 400 });
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

    if (action === 'schedule_series') {
      const { series_plan_id, start_date } = body;
      if (!series_plan_id || !start_date) {
        return NextResponse.json({ success: false, message: 'series_plan_id and start_date are required' }, { status: 400 });
      }

      const planDoc = await db.collection('series_plans').doc(series_plan_id).get();
      if (!planDoc.exists) {
        return NextResponse.json({ success: false, message: 'Series plan not found' }, { status: 404 });
      }

      const plan = planDoc.data()!;
      const parts = plan.parts || [];
      const startDate = new Date(start_date);

      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        const scheduledDate = new Date(startDate);
        scheduledDate.setDate(scheduledDate.getDate() + i);

        await db.collection('content_plan').add({
          title: `${plan.title || 'Series'} — Part ${part.part}`,
          category: (plan.categories || [])[0] || 'AI Explained',
          format: part.estimated_duration || 'shorts',
          scheduled_at: scheduledDate,
          status: 'planned',
          series_plan_id: series_plan_id,
          part_number: part.part,
          created_at: FieldValue.serverTimestamp(),
        });
      }

      return NextResponse.json({ success: true, message: `Scheduled ${parts.length} parts from series plan` });
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

export async function PUT(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { id, title, category, format, scheduled_at, status } = body;
    if (!id) {
      return NextResponse.json({ success: false, error: 'Plan item id is required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    const updateData: Record<string, any> = {};
    if (title !== undefined) updateData.title = title;
    if (category !== undefined) updateData.category = category;
    if (format !== undefined) updateData.format = format;
    if (scheduled_at !== undefined) updateData.scheduled_at = new Date(scheduled_at);
    if (status !== undefined) updateData.status = status;
    updateData.updated_at = FieldValue.serverTimestamp();

    await db.collection('content_plan').doc(id).update(updateData);
    return NextResponse.json({ success: true, message: 'Plan item updated' });
  } catch (error: any) {
    console.error('[SCHEDULER API] PUT Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    if (!id) {
      return NextResponse.json({ success: false, error: 'Plan item id is required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('content_plan').doc(id).delete();
    return NextResponse.json({ success: true, message: 'Plan item deleted' });
  } catch (error: any) {
    console.error('[SCHEDULER API] DELETE Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
