// ponytail: single source of truth for dashboard auth
// Reads comma/space-separated emails from env, use only on server

/**
 * Single committed source of truth for the owner address.
 *
 * It must match all three of:
 *   1. ownerEmail() in firebase/firestore.rules
 *   2. ownerEmail() in firebase/storage.rules
 *   3. ALLOWED_EMAILS in the Vercel Production environment
 *
 * (1) and (2) are enforced in CI by dashboard/test-firestore-rules.test.ts.
 * (3) cannot be checked from CI, so it is checked at boot below — a rules file
 * cannot read an env var, and a Vercel secret cannot be read from a test, which
 * is why this value was once wrong in exactly one of the three and every
 * dashboard request 403'd with no way to tell which copy had drifted.
 */
export const OWNER_EMAIL = 'legendarylaure@gmail.com';

const RAW = process.env.ALLOWED_EMAILS || '';
// Accept comma, semicolon, or space split
const ALLOWED = RAW.split(/[,;\s]+/).filter(Boolean).map(e => e.trim().toLowerCase());

// Log whether the allowlist is populated and agrees with the rules files.
// Deliberately logs NO email characters: a count plus a boolean is enough to act
// on, and keeps the address out of logs that get shipped to third parties.
{
  const n = ALLOWED.length;
  const agrees = ALLOWED.includes(OWNER_EMAIL);
  console.warn(
    `[auth] allowlist: ${n} ${n === 1 ? 'entry' : 'entries'}; ` +
      `matches rules ownerEmail(): ${agrees}` +
      (agrees ? '' : ' — DRIFT: every dashboard request will be denied')
  );
}

export function isAllowedEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return ALLOWED.includes(email.trim().toLowerCase());
}

export function allowedEmails(): string[] {
  return ALLOWED;
}
