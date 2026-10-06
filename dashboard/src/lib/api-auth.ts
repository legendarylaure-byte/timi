// ponytail: all API routes must call this, not their own verification
import { NextResponse } from 'next/server';
import { getAdminAuth } from '@/lib/firebase-admin';
import { isAllowedEmail, isOwnerEmail } from './allowed-emails';

export type Authed = { uid: string; email: string; role: 'owner' | 'reviewer' };
export type AuthResult =
  | { ok: true; user: Authed }
  | { ok: false; response: NextResponse };

/**
 * Never throws: it returns either the caller or a ready-to-return 401/403.
 *
 * Every route has a generic `catch` that answers 500, so a thrown auth error
 * would surface as "server error" for what is really "not logged in".
 *
 *   const auth = await requireUser(request);
 *   if (!auth.ok) return auth.response;
 *
 * Reviewer role: any allowlisted non-owner email gets role 'reviewer' and can
 * only access /api/tiktok/composer/* and /api/auth. All other routes return 403.
 * This is the API-level gate; Firestore rules provide a second layer.
 */
export async function requireUser(request: Request): Promise<AuthResult> {
  const denied = (status: number, error: string): AuthResult => ({
    ok: false,
    response: NextResponse.json({ success: false, error }, { status }),
  });

  const header = request.headers.get('authorization');
  if (!header?.startsWith('Bearer ')) return denied(401, 'Unauthorized');

  let decoded;
  try {
    decoded = await getAdminAuth().verifyIdToken(header.slice(7));
  } catch {
    return denied(401, 'Unauthorized');
  }

  if (!isAllowedEmail(decoded.email)) return denied(403, 'Not authorized');

  const role: 'owner' | 'reviewer' = isOwnerEmail(decoded.email) ? 'owner' : 'reviewer';

  if (role === 'reviewer') {
    const url = new URL(request.url);
    const path = url.pathname;
    const allowed = path.startsWith('/api/tiktok/composer/') || path === '/api/auth';
    if (!allowed) return denied(403, 'Not authorized');
  }

  return { ok: true, user: { uid: decoded.uid, email: decoded.email ?? '', role } };
}
