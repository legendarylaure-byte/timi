import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';

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
