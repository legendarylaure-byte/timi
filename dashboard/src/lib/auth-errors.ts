/**
 * Why the post-sign-in check failed, in the user's words.
 *
 * The allowlist check is a bare `.ok`, so a rejected token (401), a broken route
 * (500) and a genuine allowlist rejection (403) all arrive at the
 * login page as one boolean. The UI used to render all three as "not on the
 * allowlist" -- asserting a cause it never checked, which is how a real failure
 * became undiagnosable. Only a 403 whose body says so gets the allowlist
 * wording; everything else reports the real status, so the next person is not
 * sent to the wrong place.
 *
 * Deliberately dependency-free: it is a pure function, and keeping it out of
 * `api-fetch.ts` is what lets it be unit-tested without loading the Firebase SDK
 * (which needs TextEncoder and blows up under jest's node environment).
 */
import { CONTACT_EMAIL } from './brand';
export function signInErrorMessage(
  status: number,
  message: string | null | undefined,
  email: string | null | undefined
): string {
  if (isDefinitiveDenial(status, message)) {
    return denialDetail(status, message, email);
  }
  return `Sign-in check failed (HTTP ${status}${message ? `: ${message}` : ''}). Try again in a moment.`;
}

/**
 * The human-readable detail of a definitive denial.
 *
 * Split out from signInErrorMessage so the login and signup pages can render the
 * short headline next to this line, without the UI having to string-match the
 * message to work out which kind of failure it is looking at.
 */
export function denialDetail(
  status: number,
  message: string | null | undefined,
  email: string | null | undefined
): string {
  if (!isDefinitiveDenial(status, message)) {
    // Called on the wrong failure. Return the technical string rather than
    // contact copy, so a 500 can never be shown as "ask us for access".
    return `Sign-in check failed (HTTP ${status}${message ? `: ${message}` : ''}). Try again in a moment.`;
  }
  const who = email ?? 'this account';
  return `You signed in as ${who}, which is not on the access list. If you are expecting access, email ${CONTACT_EMAIL} and we'll add it.`;
}

/** The short headline that goes above a denial. */
export const DENIAL_HEADLINE = 'That account is not on the access list';

/**
 * Did the server actually say "you are not allowed", as opposed to "I could not
 * check"? Only this ends the session.
 *
 * Every gate used to sign the user out on ANY non-ok response, so a 401 from an
 * expired token, a 500 from a bad deploy, or one dropped request destroyed a
 * legitimate session. That is the same class of bug as claiming a failure cause
 * we never checked: the UI asserting something it had not verified. A refusal is
 * an answer; a failure to answer is not a refusal.
 *
 * Deliberately narrow: 403 is the status the allowlist check returns, and
 * 'Not authorized' is the only message on it. Anything else -- a 401, a 500, an
 * unparseable body, a network error -- is left to the per-route requireUser()
 * gate, which is the real access control anyway.
 */
export function isDefinitiveDenial(
  status: number,
  message: string | null | undefined
): boolean {
  return status === 403 && message === 'Not authorized';
}
