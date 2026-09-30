// ponytail: CSRF token for the OAuth round-trip. The provider echoes `state`
// back to the callback; we compare it to a cookie only this browser holds.
// Without it, anyone can POST a crafted callback URL carrying a code from THEIR
// own OAuth flow, and the callback will happily write THEIR tokens into
// env_vars/platform_settings (verified: TikTok's `state` was the literal
// string 'timi_prod' and its callback checked nothing).
import { randomBytes, timingSafeEqual } from 'crypto';
import { cookies } from 'next/headers';

const COOKIE = 'oauth_state';
const MAX_AGE = 600; // 10 min: a connect flow is immediate

export async function setOAuthState(): Promise<string> {
  const state = randomBytes(16).toString('hex');
  (await cookies()).set(COOKIE, state, {
    httpOnly: true,
    sameSite: 'lax', // must survive the top-level redirect back from the provider
    secure: true,
    path: '/',
    maxAge: MAX_AGE,
  });
  return state;
}

/** Consumes the cookie. Returns false (and clears it) on any mismatch. */
export async function verifyOAuthState(returned: string | null): Promise<boolean> {
  const jar = await cookies();
  const expected = jar.get(COOKIE)?.value;
  jar.delete(COOKIE);
  if (!expected || !returned) return false;
  const a = Buffer.from(expected);
  const b = Buffer.from(returned);
  return a.length === b.length && timingSafeEqual(a, b);
}
