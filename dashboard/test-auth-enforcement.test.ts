// Invariant: every non-public API route gates its handler with requireUser().
//
// The previous version of this test banned the *strings* "verifyIdToken"/"verifyAuth",
// which passed even when a route was left completely ungated. This asserts the
// positive property instead: each exported handler in a protected route must
// contain the guard. Mutation-tested in the commit that added it.
import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

const GUARD = 'if (!auth.ok) return auth.response;';

// Routes that legitimately serve no Firebase session, and why.
const PUBLIC: Record<string, string> = {
  'webhook': 'inbound webhook; guarded by its own x-webhook-signature',
  'health': 'liveness probe used by deploy checks',
  'heartbeat': 'read-only infra status + machine POSTs the heartbeat',
  'auth': 'the allowlist gate itself',
  'auth/meta': 'OAuth START: browser navigation carries no Authorization header; guarded by state cookie',
  'auth/tiktok': 'OAuth START: browser navigation carries no Authorization header; guarded by state cookie',
  'auth/youtube': 'OAuth START: browser navigation carries no Authorization header; guarded by state cookie',
  'auth/meta/callback': 'browser redirect back from provider; state-cookie validated',
  'auth/tiktok/callback': 'browser redirect back from provider; state-cookie validated',
  'auth/youtube/callback': 'browser redirect back from provider; state-cookie validated',
};

function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    statSync(p).isDirectory() ? walk(p, out) : p.endsWith('route.ts') && out.push(p);
  }
  return out;
}

let checked = 0;
const failures: string[] = [];

for (const file of walk('src/app/api')) {
  const route = file
    .replace(/\\/g, '/')
    .replace(/^src\/app\/api\//, '')
    .replace(/\/route\.ts$/, '');
  if (route in PUBLIC) continue;

  const src = readFileSync(file, 'utf8');
  const handlers = [...src.matchAll(/export async function (GET|POST|PUT|PATCH|DELETE)\(/g)];
  if (handlers.length === 0) {
    failures.push(`${route}: no exported handler found (parse problem?)`);
    continue;
  }
  for (let i = 0; i < handlers.length; i++) {
    const verb = handlers[i][1];
    const start = handlers[i].index!;
    const end = i + 1 < handlers.length ? handlers[i + 1].index! : src.length;
    const body = src.slice(start, end);
    checked++;
    if (!body.includes(GUARD)) {
      failures.push(`${route} [${verb}]: handler is NOT gated by requireUser()`);
    }
  }
}

if (failures.length) {
  console.error(`\nFAIL — ${failures.length} ungated handler(s):\n`);
  for (const f of failures) console.error('  x ' + f);
  process.exit(1);
}
console.log(`OK — all ${checked} handlers across the protected API surface call requireUser()`);
