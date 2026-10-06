/**
 * @jest-environment node
 */

/**
 * Reviewer role: requireUser returns role and restricts paths.
 *
 * A non-owner allowlisted email gets role 'reviewer' and can only access
 * /api/tiktok/composer/* and /api/auth. All other routes return 403.
 * This is the API-level gate; Firestore rules provide a second layer.
 */

const OWNER = 'legendarylaure@gmail.com';
const REVIEWER = 'reviewer@vyomai.cloud';
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

function loadRoute() {
  jest.resetModules();
  process.env.ALLOWED_EMAILS = `${OWNER},${REVIEWER}`;
  return require('@/lib/api-auth').requireUser as (r: Request) => Promise<any>;
}

function request(path: string, token?: string) {
  return new Request(`https://timi.vyomai.cloud${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

beforeEach(() => {
  tokenEmail = OWNER;
  verifyIdToken.mockClear();
});

describe('requireUser role detection', () => {
  it('returns role "owner" for the owner email', async () => {
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/videos', GOOD_TOKEN));
    expect(result.ok).toBe(true);
    expect(result.user.role).toBe('owner');
  });

  it('returns role "reviewer" for a non-owner allowlisted email', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/tiktok/composer/options', GOOD_TOKEN));
    expect(result.ok).toBe(true);
    expect(result.user.role).toBe('reviewer');
  });

  it('reviewer can access /api/tiktok/composer/*', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/tiktok/composer/publish', GOOD_TOKEN));
    expect(result.ok).toBe(true);
  });

  it('reviewer can access /api/auth', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/auth', GOOD_TOKEN));
    expect(result.ok).toBe(true);
  });

  it('reviewer is denied access to /api/videos', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/videos', GOOD_TOKEN));
    expect(result.ok).toBe(false);
    expect(result.response.status).toBe(403);
  });

  it('reviewer is denied access to /api/settings', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/settings', GOOD_TOKEN));
    expect(result.ok).toBe(false);
    expect(result.response.status).toBe(403);
  });

  it('reviewer is denied access to /api/env-vars', async () => {
    tokenEmail = REVIEWER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/env-vars', GOOD_TOKEN));
    expect(result.ok).toBe(false);
    expect(result.response.status).toBe(403);
  });

  it('owner can access any path', async () => {
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/videos', GOOD_TOKEN));
    expect(result.ok).toBe(true);
  });

  it('stranger is still denied with 403', async () => {
    tokenEmail = STRANGER;
    const requireUser = loadRoute();
    const result = await requireUser(request('/api/tiktok/composer/options', GOOD_TOKEN));
    expect(result.ok).toBe(false);
    expect(result.response.status).toBe(403);
  });
});

describe('isOwnerEmail', () => {
  it('returns true for the owner email', () => {
    jest.resetModules();
    process.env.ALLOWED_EMAILS = `${OWNER},${REVIEWER}`;
    const { isOwnerEmail } = require('@/lib/allowed-emails');
    expect(isOwnerEmail(OWNER)).toBe(true);
  });

  it('returns false for a non-owner allowlisted email', () => {
    jest.resetModules();
    process.env.ALLOWED_EMAILS = `${OWNER},${REVIEWER}`;
    const { isOwnerEmail } = require('@/lib/allowed-emails');
    expect(isOwnerEmail(REVIEWER)).toBe(false);
  });

  it('returns false for null/undefined', () => {
    jest.resetModules();
    process.env.ALLOWED_EMAILS = `${OWNER},${REVIEWER}`;
    const { isOwnerEmail } = require('@/lib/allowed-emails');
    expect(isOwnerEmail(null)).toBe(false);
    expect(isOwnerEmail(undefined)).toBe(false);
  });
});
