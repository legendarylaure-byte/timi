import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Missing agent id' }, { status: 400 });
  }

  try {
    const body = await request.json();
    const { enabled } = body;

    if (typeof enabled !== 'boolean') {
      return NextResponse.json({ error: 'enabled must be a boolean' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('agent_status').doc(id).update({ enabled });

    return NextResponse.json({ success: true, agent_id: id, enabled });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to toggle agent' },
      { status: 500 },
    );
  }
}
