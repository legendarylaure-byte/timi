import { NextResponse } from 'next/server';
import { getAdminAuth } from '@/lib/firebase-admin';
import { isAllowedEmail } from '@/lib/allowed-emails';

export async function POST(request: Request) {
  // A malformed body and a bad token are the caller's fault, not a server
  // fault. Both used to fall through to a 500, which reads as "the app is
  // broken" when the truth is "you are not logged in".
  let action: string | undefined;
  let idToken: string | undefined;
  try {
    ({ action, idToken } = await request.json());
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid JSON body' }, { status: 400 });
  }

  if (action !== 'verify') {
    return NextResponse.json({ success: false, message: 'Unsupported action' }, { status: 400 });
  }
  if (!idToken) {
    return NextResponse.json({ success: false, message: 'Missing idToken' }, { status: 400 });
  }

  let decoded;
  try {
    decoded = await getAdminAuth().verifyIdToken(idToken);
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid or expired token' }, { status: 401 });
  }

  if (!isAllowedEmail(decoded.email)) {
    return NextResponse.json(
      { success: false, message: 'Not authorized', email: decoded.email || null },
      { status: 403 }
    );
  }
  return NextResponse.json({ success: true, uid: decoded.uid, email: decoded.email });
}
