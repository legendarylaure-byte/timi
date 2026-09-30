import { signInErrorMessage } from '@/lib/auth-errors';

const OWNER = 'legendarylaure@gmail.com';

describe('signInErrorMessage', () => {
  it('names the rejected account on a real allowlist rejection', () => {
    const msg = signInErrorMessage(403, 'Not authorized', 'someone.else@gmail.com');
    expect(msg).toContain('someone.else@gmail.com');
    expect(msg).toContain('not on the allowlist');
  });

  it('copes with a token that carries no email claim', () => {
    const msg = signInErrorMessage(403, 'Not authorized', null);
    expect(msg).toContain('no email');
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
    expect(msg).not.toContain('not on the allowlist');
    expect(msg).toContain('Missing idToken');
  });
});
