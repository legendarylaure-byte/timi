import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';

export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;
    const { id } = await params;
    const body = await request.json();
    const db = getAdminFirestore();
    await db.collection('platform_settings').doc(id).set(body, { merge: true });
    return NextResponse.json({ success: true });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
