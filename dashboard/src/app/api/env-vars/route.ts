import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const snapshot = await db.collection('env_vars').get();
    const vars: Record<string, { value: string; updated_at: string }> = {};
    snapshot.forEach((doc) => {
      const data = doc.data();
      vars[doc.id] = {
        value: data.value || '',
        updated_at: data.updated_at || '',
      };
    });
    return NextResponse.json({ success: true, vars });
  } catch (err: any) {
    console.error('[ENV-VARS] Failed to list:', err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
