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
export function signInErrorMessage(
  status: number,
  message: string | null | undefined,
  email: string | null | undefined
): string {
  if (isDefinitiveDenial(status, message)) {
    return `Signed in as ${email ?? 'an account with no email'}, which is not on the allowlist.`;
  }
  return `Sign-in check failed (HTTP ${status}${message ? `: ${message}` : ''}). Try again in a moment.`;
}

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
