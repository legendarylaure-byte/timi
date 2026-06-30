import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { read_ids, all_ids } = body;

    if (!read_ids && !all_ids) {
      return NextResponse.json(
        { success: false, error: 'Missing read_ids or all_ids' },
        { status: 400 },
      );
    }

    const db = getAdminFirestore();
    await db.collection('notifications').doc('user').set(
      all_ids ? { read_ids: all_ids } : { read_ids: read_ids },
      { merge: true },
    );
    return NextResponse.json({ success: true });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
