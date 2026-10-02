// Guards the bug that made the whole status bar lie.
//
// GlobalStatusBar and SystemStatusWidgets each had a copied `fetchJson` that
// called bare `fetch(url)`. /api/docker, /api/firebase and /api/storage are all
// `requireUser`-gated, and requireUser reads ONLY the `Authorization: Bearer`
// header (api-auth.ts) — there is no cookie fallback. So every poll 401'd,
// fetchJson swallowed it into `null`, and each widget fell through to its error
// branch: Docker "Offline", Firebase "Disconnected", Storage "R2 error" — on
// localhost AND on live, while `docker ps` showed the container up and healthy
// and all four R2 vars were present in Vercel production.
//
// A bare fetch is not a style choice here, it is the bug. These tests render
// the components for real and assert the *connected* state appears, which is
// the assertion the old code could never satisfy. Reverting `apiFetch` to
// `fetch` makes apiFetch's mock never called, every payload become undefined,
// and both the "connected" assertions and the "not Offline" assertions fail.

const payloads: Record<string, unknown> = {
  '/api/health': { status: 'ok', checks: { agent_heartbeat: { status: 'ok' } } },
  '/api/docker': { available: true, all_running: true, container_count: 1 },
  '/api/firebase': { connected: true, latency_ms: 142 },
  '/api/storage': {
    connected: true,
    configured: true,
    total_size_gb: 2.4,
    limit_gb: 10,
    objects: 7,
    free_percent: 76,
  },
};

const apiFetchMock = jest.fn(async (url: string) => {
  const body = payloads[url];
  if (body === undefined) throw new Error(`unexpected url: ${url}`);
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
});

jest.mock('@/lib/api-fetch', () => ({ apiFetch: (...a: unknown[]) => apiFetchMock(...(a as [string])) }));

// The bar also subscribes to Firestore client-side. Nothing here is under test,
// so hand it empty snapshots and keep the real @/lib/api-fetch mock visible.
jest.mock('@/lib/firebase', () => ({ db: {} }));
jest.mock('firebase/firestore', () => ({
  doc: () => ({}),
  collection: () => ({}),
  Timestamp: class {},
  onSnapshot: (_ref: unknown, next: (s: unknown) => void) => {
    next({ exists: () => false, data: () => ({}), docs: [] });
    return () => {};
  },
}));
jest.mock('@/lib/constants', () => ({
  getNextUploadDisplay: () => ({ nptTime: '08:50 PM', hours: 5, minutes: 45 }),
}));

import { render, screen } from '@testing-library/react';
import { GlobalStatusBar } from '@/components/status/GlobalStatusBar';
import { DockerStatus } from '@/components/status/SystemStatusWidgets';

beforeEach(() => {
  apiFetchMock.mockClear();
});

describe('status components authenticate their polls', () => {
  it('sends every poll through apiFetch, not bare fetch', async () => {
    render(<GlobalStatusBar />);
    await screen.findByText('1 container');
    for (const url of ['/api/health', '/api/docker', '/api/firebase', '/api/storage']) {
      expect(apiFetchMock).toHaveBeenCalledWith(url, expect.anything());
    }
  });

  it('shows the real Docker/Firebase/Storage state, not the 401 fallback', async () => {
    render(<GlobalStatusBar />);
    await screen.findByText('1 container');
    expect(await screen.findByText('142ms')).toBeTruthy();
    expect(screen.getByText('2.4GB / 10GB')).toBeTruthy();
    // The three strings a headerless fetch produced.
    expect(screen.queryByText('Offline')).toBeNull();
    expect(screen.queryByText('Disconnected')).toBeNull();
    expect(screen.queryByText('R2 error')).toBeNull();
  });

  it('renders the container count in the sibling widget too', async () => {
    render(<DockerStatus />);
    expect(await screen.findByText('1 container')).toBeTruthy();
    expect(apiFetchMock).toHaveBeenCalledWith('/api/docker', expect.anything());
  });
});