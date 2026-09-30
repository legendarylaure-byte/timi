// ponytail: single source of truth for dashboard auth
// Reads comma/space-separated emails from env, use only on server

const RAW = process.env.ALLOWED_EMAILS || '';
// Accept comma, semicolon, or space split
const ALLOWED = RAW.split(/[,;\s]+/).filter(Boolean).map(e => e.trim().toLowerCase());

export function isAllowedEmail(email: string | null | undefined): boolean {
  if (!email) return false;
  return ALLOWED.includes(email.trim().toLowerCase());
}

export function allowedEmails(): string[] {
  return ALLOWED;
}
