import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const db = getAdminFirestore();
    await db.collection('settings').doc('general').set(body, { merge: true });
    return NextResponse.json({ success: true });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
