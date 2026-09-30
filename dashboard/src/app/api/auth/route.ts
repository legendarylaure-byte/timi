import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';

/**
 * Is the signed-in account on the allowlist?
 *
 * This used to parse `{action, idToken}` out of a JSON body while the client
 * sent NO body and put the token in the `Authorization` header -- so it answered
 * `400 Invalid JSON body` to every single login, and the UI rendered that as
 * "your email is not on the allowlist". Nobody could log in; the allowlist and
 * the account were both correct the whole time.
 *
 * Delegating to requireUser() removes the body entirely and reads the token from
 * the header, which is the contract every other route already uses. It also
 * retires the only hand-rolled verifyIdToken() in the API, so the check the
 * login page makes and the check the data routes make can no longer disagree.
 */
export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;
  return NextResponse.json({ success: true, uid: auth.user.uid, email: auth.user.email });
}
