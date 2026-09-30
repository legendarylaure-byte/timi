/**
 * Why the post-sign-in check failed, in the user's words.
 *
 * The check in `isAllowedUser()` is a bare `.ok`, so a rejected token (401), a
 * broken route (500) and a genuine allowlist rejection (403) all arrive at the
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
  if (message === 'Not authorized') {
    return `Signed in as ${email ?? 'an account with no email'}, which is not on the allowlist.`;
  }
  return `Sign-in check failed (HTTP ${status}${message ? `: ${message}` : ''}). Try again in a moment.`;
}
