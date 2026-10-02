import { isDefinitiveDenial, signInErrorMessage, denialDetail, DENIAL_HEADLINE } from '@/lib/auth-errors';
import { CONTACT_EMAIL } from '@/lib/brand';

const OWNER = 'legendarylaure@gmail.com';

describe('signInErrorMessage', () => {
  it('names the rejected account on a real allowlist rejection', () => {
    const msg = signInErrorMessage(403, 'Not authorized', 'someone.else@gmail.com');
    expect(msg).toContain('someone.else@gmail.com');
    expect(msg).toContain('not on the access list');
  });

  it('copes with a token that carries no email claim', () => {
    const msg = signInErrorMessage(403, 'Not authorized', null);
    // The old text said "an account with no email", which told the user
    // something about their own account that we do not actually know. "this
    // account" is true whether or not the token carried a claim.
    expect(msg).toContain('this account');
    expect(msg).not.toContain('undefined');
    expect(msg).not.toContain('null');
  });

  // The bug this exists to prevent: a bare `.ok` check collapsed a rejected
  // token and a genuine allowlist rejection into one boolean, and the UI then
  // told the user their email was not allowed when it was. A 401 must never
  // get the allowlist wording.
  it('does NOT blame the allowlist when the token itself was rejected', () => {
    const msg = signInErrorMessage(401, 'Invalid or expired token', OWNER);
    expect(msg).not.toContain('allowlist');
    expect(msg).toContain('401');
    expect(msg).toContain('Invalid or expired token');
  });

  it('does NOT blame the allowlist when the route itself fails', () => {
    const msg = signInErrorMessage(500, null, OWNER);
    expect(msg).not.toContain('allowlist');
    expect(msg).toContain('500');
  });

  it('only uses allowlist wording when the server actually said so', () => {
    // A 403 alone is not proof: the body is what distinguishes "denied by the
    // allowlist" from any other 403, so a 403 with a different message must not
    // claim the address was rejected.
    const msg = signInErrorMessage(403, 'Missing idToken', OWNER);
    expect(msg).not.toContain('not on the access list');
    expect(msg).toContain('Missing idToken');
  });

  // A denial is the one failure that has a way forward, so it is the one that
  // may show an email address. A 500 shown next to "email us" sends people off
  // to request access they already have, and hides a broken deploy.
  it('offers contact details on a denial, and on nothing else', () => {
    expect(signInErrorMessage(403, 'Not authorized', OWNER)).toContain(CONTACT_EMAIL);
    const notDenials: Array<[number, string | null]> = [[401, 'nope'], [500, null], [503, 'busy'], [403, 'Missing idToken']];
    for (const [status, message] of notDenials) {
      expect(signInErrorMessage(status, message, OWNER)).not.toContain(CONTACT_EMAIL);
    }
  });
});

describe('denialDetail', () => {
  it('agrees with signInErrorMessage on the denial path', () => {
    expect(denialDetail(403, 'Not authorized', OWNER))
      .toBe(signInErrorMessage(403, 'Not authorized', OWNER));
  });

  // The split exists so the UI can pick a headline without string-matching the
  // message. If this ever leaked contact copy for a non-denial, that is the bug
  // this assertion is for -- the page would tell someone to request access
  // because the server was down.
  it('refuses to return contact copy for a failure that is not a denial', () => {
    const notDenials: Array<[number, string | null]> = [[401, 'nope'], [500, null], [403, 'Missing idToken']];
    for (const [status, message] of notDenials) {
      expect(denialDetail(status, message, OWNER)).not.toContain(CONTACT_EMAIL);
    }
  });

  it('has a headline that does not leak the allowlist implementation detail', () => {
    // "Allowlist" is how this is implemented. The user needs to know they are
    // not admitted, not which table missed them.
    expect(DENIAL_HEADLINE).not.toContain('allowlist');
    expect(DENIAL_HEADLINE.length).toBeGreaterThan(0);
  });
});

/**
 * This predicate decides whether a real sign-in gets thrown away, at four call
 * sites (login, signup, the dashboard layout, and the Go-to-dashboard button).
 * Every gate used to sign the user out on ANY non-ok response, so one 500 or
 * dropped request logged the owner out of a working session. A refusal is an
 * answer; a failure to answer is not a refusal.
 */
describe('isDefinitiveDenial', () => {
  it('recognises the one genuine refusal the server can return', () => {
    expect(isDefinitiveDenial(403, 'Not authorized')).toBe(true);
  });

  it('does NOT end the session for a rejected token', () => {
    // An expired ID token is a blip, not a statement about permissions.
    expect(isDefinitiveDenial(401, 'Unauthorized')).toBe(false);
  });

  it('does NOT end the session when the route is broken', () => {
    expect(isDefinitiveDenial(500, null)).toBe(false);
    expect(isDefinitiveDenial(500, 'boom')).toBe(false);
  });

  it('does NOT end the session for the 400 that broke every login', () => {
    // The exact response this whole fix removes. If this ever returned true,
    // the old bug would come back as "you are not allowed" instead of a 400.
    expect(isDefinitiveDenial(400, 'Invalid JSON body')).toBe(false);
  });

  it('does NOT end the session when the body cannot be read at all', () => {
    // A dropped connection or unparseable body is silence, not refusal.
    expect(isDefinitiveDenial(403, null)).toBe(false);
    expect(isDefinitiveDenial(403, undefined)).toBe(false);
    expect(isDefinitiveDenial(403, '')).toBe(false);
  });

  it('requires both the status and the message, not either alone', () => {
    expect(isDefinitiveDenial(403, 'Something else entirely')).toBe(false);
    expect(isDefinitiveDenial(200, 'Not authorized')).toBe(false);
  });
});
