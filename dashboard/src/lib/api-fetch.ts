import { auth } from './firebase';

/**
 * The ONE way to call our own API from the browser.
 *
 * Every route under /api/ is gated by requireUser(), which needs
 * `Authorization: Bearer <idToken>`. Hand-rolling that header at each call
 * site is how 49 of them silently 401'd, so it lives here instead.
 *
 * Deliberately does NOT sign the user out on 401: a 401 can be transient, and
 * the allowlist bounce is handled explicitly in the login/signup + layout flow.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  const user = auth?.currentUser;
  if (user) headers.set('Authorization', `Bearer ${await user.getIdToken()}`);
  return fetch(path, { ...init, headers });
}

/**
 * Ask the server whether this account is on the allowlist.
 *
 * Returns the raw Response so a caller that reports the failure to a human can
 * read the real reason. A bare `.ok` is fine for a plain yes/no gate but throws
 * away the only thing that tells 403 (not allowed) apart from 500 (not working).
 *
 * No body: the route authenticates the `Authorization` header like every other
 * route in the API. It used to read `{action, idToken}` from a JSON body that
 * this never sent, which made it 400 on every login.
 *
 * The server owns the list — we deliberately do NOT ship a NEXT_PUBLIC_ copy of
 * the addresses: that would publish them in the JS bundle and give us a second
 * list to drift out of sync.
 */
export async function verifyAllowlist(): Promise<Response> {
  return apiFetch('/api/auth', { method: 'POST' });
}
