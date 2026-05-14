import { NextResponse } from 'next/server';
import { getAdminAuth } from '@/lib/firebase-admin';

export async function POST(request: Request) {
  try {
    const { action, idToken } = await request.json();

    if (action === 'verify') {
      if (!idToken) {
        return NextResponse.json({ success: false, message: 'Missing idToken' }, { status: 400 });
      }
      const decoded = await getAdminAuth().verifyIdToken(idToken);
      return NextResponse.json({ success: true, uid: decoded.uid, email: decoded.email });
    }

    return NextResponse.json({
      success: true,
      message: `Auth action "${action}" processed`,
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, message: error.message || 'Authentication error' },
      { status: 500 }
    );
  }
}
