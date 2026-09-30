/**
 * @jest-environment node
 */

/**
 * The contract between the browser and POST /api/auth.
 *
 * This route used to parse `{action, idToken}` out of a JSON body, while the
 * browser sent no body at all and carried the token in the `Authorization`
 * header. `await request.json()` therefore threw on every single sign-in and
 * answered `400 Invalid JSON body` -- which the UI then rendered as "your email
 * is not on the allowlist". Nobody could log in.
 *
 * The test exists because that failure was invisible from the outside: the
 * allowlist was correct, the account was correct, and the dashboard still locked
 * everyone out. The only way to catch this class is to send the exact request
 * the client sends, with no body.
 *
 * `getAdminAuth` is mocked, so no real credentials and no network are used.
 * The node environment is required because this is a server route handler and
 * jsdom does not provide Request/Response/fetch.
 */

const OWNER = 'legendarylaure@gmail.com';
const STRANGER = 'stranger@example.com';
const GOOD_TOKEN = 'good.jwt.token';

let tokenEmail = OWNER;
const verifyIdToken = jest.fn(async (token: string) => {
  if (token !== GOOD_TOKEN) throw new Error('bad token');
  return { uid: 'uid-123', email: tokenEmail };
});

jest.mock('@/lib/firebase-admin', () => ({
  getAdminAuth: () => ({ verifyIdToken }),
}));

/**
 * allowed-emails.ts snapshots process.env.ALLOWED_EMAILS at import time, so the
 * env has to be set *before* the module loads. That is why this uses require()
 * after setting the env instead of a top-level import.
 */
function loadRoute() {
  jest.resetModules();
  process.env.ALLOWED_EMAILS = OWNER;
  return require('@/app/api/auth/route').POST as (r: Request) => Promise<Response>;
}

/** A bodyless POST carrying only the header, exactly as apiFetch() sends it. */
function bodylessRequest(token?: string) {
  return new Request('https://timi.vyomai.cloud/api/auth', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

beforeEach(() => {
  tokenEmail = OWNER;
  verifyIdToken.mockClear();
});

describe('POST /api/auth', () => {
  it('accepts a bodyless request authenticated by the Authorization header', async () => {
    // THE regression: no body, token in the header. This returned 400 before.
    const POST = loadRoute();
    const res = await POST(bodylessRequest(GOOD_TOKEN));

    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toMatchObject({ success: true, email: OWNER });
  });

  it('never reads a request body, so a missing one cannot produce a 400', async () => {
    const POST = loadRoute();
    const res = await POST(bodylessRequest(GOOD_TOKEN));

    expect(res.status).not.toBe(400);
  });

  it('rejects a valid token for an address that is not on the allowlist', async () => {
    tokenEmail = STRANGER;
    const POST = loadRoute();
    const res = await POST(bodylessRequest(GOOD_TOKEN));

    expect(res.status).toBe(403);
    // The exact string isDefinitiveDenial() matches on. A renamed field would
    // silently stop the UI from ever reporting a real rejection.
    await expect(res.json()).resolves.toMatchObject({ error: 'Not authorized' });
  });

  it('rejects a request with no Authorization header', async () => {
    const POST = loadRoute();
    const res = await POST(bodylessRequest());

    expect(res.status).toBe(401);
    expect(verifyIdToken).not.toHaveBeenCalled();
  });

  it('rejects a malformed token without leaking the verify error', async () => {
    const POST = loadRoute();
    const res = await POST(bodylessRequest('garbage'));

    expect(res.status).toBe(401);
    await expect(res.json()).resolves.toMatchObject({ error: 'Unauthorized' });
  });

  it('agrees with the committed owner email, so this list cannot be stale', () => {
    // A second copy of the allowlist is how they drift. The list the route reads
    // is the same constant the rules-parity test pins against Firestore rules.
    loadRoute();
    const { OWNER_EMAIL } = require('@/lib/allowed-emails');

    expect(OWNER_EMAIL).toBe(OWNER);
  });
});
