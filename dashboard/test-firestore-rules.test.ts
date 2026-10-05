/**
 * Firestore rules invariants.
 *
 * Run: npx tsx test-firestore-rules.test.ts
 *
 * These are the checks that a rules file cannot express about itself: that the
 * browser never reads a secrets collection, that every collection the browser
 * DOES read is still owner-readable, and that an unconfigured owner email
 * fails closed. Verified against the shipped file, not the intent.
 */
import { readFileSync, existsSync, readdirSync } from 'fs';
import { join } from 'path';

const RULES = join(__dirname, '..', 'firebase', 'firestore.rules');
// Comments must go before any structural check. These files document the
// patterns they replaced, so a naive grep reports the retired pattern as
// still present. Same trap as the legacy-teal AST test: prose about a colour
// is not the colour.
const code = (r: string) => r.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');

const src = readFileSync(RULES, 'utf8');

let failed = 0;
const ok = (m: string) => console.log(`  ok   ${m}`);
const bad = (m: string) => { failed++; console.log(`  FAIL ${m}`); };

// --- parse match blocks with real brace matching -----------------------------
const blocks: Record<string, string> = {};
for (const m of src.matchAll(/match \/(\w+)\/\{[^}]*\}\s*\{/g)) {
  let i = m.index! + m[0].length, depth = 1;
  while (i < src.length && depth) {
    if (src[i] === '{') depth++;
    else if (src[i] === '}') depth--;
    i++;
  }
  blocks[m[1]] = src.slice(m.index! + m[0].length, i - 1);
}

// --- what the browser actually touches -------------------------------------
const SRCDIR = join(__dirname, 'src');
// Both idioms count: the modular `collection(db, 'x')` and the member form
// `db.collection('x')`. Missing the second is how a secret read slips through —
// a check that only sees the first form cannot see a leak written in the other.
const ACCESS = /(?:collection|doc)\(\s*db\s*,\s*['"]([a-zA-Z_]+)['"]|db\.(?:collection|doc)\(\s*['"]([a-zA-Z_]+)['"]/g;
const clientCollections = new Set<string>();
const walk = (dir: string): void => {
  for (const e of require('fs').readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (/\.tsx?$/.test(e.name)) {
      const s = readFileSync(p, 'utf8');
      if (!s.includes('firebase/firestore')) continue;
      for (const m of s.matchAll(ACCESS)) clientCollections.add(m[1] || m[2]);
    }
  }
};
walk(SRCDIR);

console.log(`\n1. every grant is owner-gated (${Object.keys(blocks).length} blocks)`);
for (const [name, body] of Object.entries(blocks)) {
  for (const line of body.split('\n')) {
    const l = line.trim();
    if (l.startsWith('allow') && l.includes('if') && !l.includes('isOwner') && !l.includes('false')) {
      bad(`/${name} grants without isOwner(): ${l}`);
    }
  }
}
if (!failed) ok('no ungated allow rules');

console.log('\n2. no isBackend()-style hole (auth == null grants write)');
if (/request\.auth\s*==\s*null/.test(src) && /allow write[^\n]*isBackend/.test(src)) {
  bad('write access granted to unauthenticated callers');
} else ok('unauthenticated callers get no write access');

console.log('\n3. browser reads nothing secret');
for (const secret of ['env_vars', 'platform_settings']) {
  if (clientCollections.has(secret)) bad(`browser still reads /${secret}`);
  else ok(`/${secret} not client-accessed`);
}

console.log('\n4. every collection the browser reads is owner-readable');
for (const c of [...clientCollections].sort()) {
  const b = blocks[c];
  if (!b) { bad(`/${c} read by browser but has no match block (catch-all deny)`); continue; }
  if (/allow read[^:]*: if false|allow read, write: if false/.test(b)) {
    bad(`/${c} read by browser but denied by rules`);
  } else ok(`/${c} owner-readable`);
}

console.log('\n5. unconfigured owner email fails CLOSED');
const fn = src.match(/function ownerEmail\(\)\s*\{\s*return\s+"([^"]*)"/);
if (!fn) bad('ownerEmail() not found — cannot verify fail-closed behaviour');
else if (fn[1] === 'REPLACE_WITH_OWNER_EMAIL') ok('placeholder present: every isOwner() is false (fails closed)');
else if (!fn[1].includes('@')) bad(`ownerEmail() = "${fn[1]}" is not an email — deny-all?`);
else ok(`ownerEmail() configured: ${fn[1]}`);

console.log('\n6. catch-all deny is present and last');
if (/match \/\{document=\*\*\}\s*\{\s*allow read, write: if false;/.test(src)) ok('catch-all denies');
else bad('no catch-all deny — new collections would default to open?');

// --- structural sanity ------------------------------------------------------
// The Firestore rules compiler needs a JVM, which this box does not have, so
// this does not replace a real `firebase deploy --only firestore:rules`. It
// only catches the cheap, common breakage: unbalanced braces, a truncated
// line, a non-Firestore method call.
console.log('\n7. structural sanity (not a substitute for the rules compiler)');
{
  let depth = 0, min = 0;
  for (const ch of src) { if (ch === '{') depth++; else if (ch === '}') { depth--; min = Math.min(min, depth); } }
  if (depth !== 0) bad(`unbalanced braces (net ${depth})`);
  else if (min < 0) bad('a closing brace precedes its opener');
  else ok('braces balanced');

  const unterminated = src.split('\n').some((l) => (l.match(/"/g) || []).length % 2 !== 0 && !l.trim().startsWith('//'));
  if (unterminated) bad('a line has an odd number of quotes — likely a truncated string');
  else ok('quotes balanced per line');

  if (/rules_version\s*=\s*'2'/.test(src)) ok("rules_version = '2' declared");
  else bad("rules_version = '2' missing — recursive wildcards need it");

  const nonFs = [...src.matchAll(/\b(\w+)\s*\(\s*request\b/g)].map((m) => m[1]);
  const allowed = new Set(['allow', 'if', 'function', 'match', 'service', 'request']);
  const bogus = [...new Set(nonFs)].filter((n) => !allowed.has(n));
  if (bogus.length) bad(`not Firestore syntax: ${bogus.join(', ')}(...)`);
  else ok('no non-Firestore calls');
}

// --- storage is not configured, and nothing uses it --------------------------
// This section used to compare firebase/storage.rules against firestore.rules
// and assert it had no public read and no missing catch-all deny. The file is
// deleted now, so those three checks are gone -- and deleting the checks without
// replacing them is how a removed guard quietly comes back. So assert the
// stronger invariant instead: Storage is not configured at all.
//
// Deleting the checks would have been fine ONLY if Storage were actually unused.
// That premise is asserted here rather than assumed, because a stray
// import { getStorage } would make it false and nothing else would notice.
console.log('\n8. Storage is unconfigured and unused (no bucket, media is on R2)');
{
  const cfg = JSON.parse(readFileSync(join(__dirname, '..', 'firebase.json'), 'utf8'));
  if (cfg.storage) bad(`firebase.json still configures storage: ${JSON.stringify(cfg.storage)}`);
  else ok('firebase.json has no storage key');

  const rulesPath = join(__dirname, '..', 'firebase', 'storage.rules');
  if (existsSync(rulesPath)) bad('firebase/storage.rules exists again');
  else ok('no firebase/storage.rules');

  // The client SDK. `getStorage` would be a bucket-less crash waiting to happen.
  const users: string[] = [];
  const scan = (dir: string): void => {
    for (const e of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, e.name);
      if (e.isDirectory()) scan(p);
      else if (/\.tsx?$/.test(e.name)) {
        const s = readFileSync(p, 'utf8');
        // Strip comments: prose naming a retired colour/file is not the thing.
        if (/firebase\/storage|getStorage|uploadBytes|getDownloadURL/.test(code(s))) users.push(p);
      }
    }
  };
  scan(SRCDIR);
  if (users.length) bad(`dashboard imports Firebase Storage: ${users.map((u) => u.replace(__dirname, '..', '')).join(', ')}`);
  else ok('no Firebase Storage client usage');
}

// --- owner email copies -------------------------------------------------------
// Two copies remain in CI's reach: the rules file and the dashboard constant.
// The third was storage.rules, and deleting that file removed a copy that could
// have drifted from the other two with nothing comparing them. The live copy is
// ALLOWED_EMAILS in the Vercel Production env, which no test can read, so it is
// checked at boot by allowed-emails.ts.
console.log('\n9. both CI-visible copies of the owner email agree');
{
  const { OWNER_EMAIL } = require('./src/lib/allowed-emails');
  const ff = src.match(/function ownerEmail\(\)\s*\{\s*return\s+"([^"]*)"/)?.[1];
  if (ff !== OWNER_EMAIL) bad(`firestore.rules ownerEmail != dashboard OWNER_EMAIL`);
  else ok('firestore.rules matches dashboard constant');
}

// A config that omits a rules file deploys the OTHER rules silently. That is
// how the root firebase.json shipped with indexes but no `rules` key: the CI
// deploy job ran green from the repo root and published nothing, so nobody
// could tell that a rules edit never reached production.
console.log('\n10. firebase.json targets the rules file, and every target exists');
{
  const cfg = JSON.parse(readFileSync(join(__dirname, '..', 'firebase.json'), 'utf8'));
  const path = cfg.firestore?.rules;
  if (!path) bad('firebase.json has no target for firestore.rules');
  else if (!existsSync(join(__dirname, '..', path))) bad(`firebase.json points at ${path}, which does not exist`);
  else ok(`firestore.rules -> ${path} (exists)`);
  if (!cfg.firestore?.indexes) bad('firebase.json has no firestore.indexes target');
}

// The duplicate that let the two configs drift: firebase/deploy.sh used to cd
// into firebase/ and read a second, relative-path firebase.json. One config,
// read by both CI and the local script, is what prevents that class.
console.log('\n11. there is exactly ONE firebase.json, and it is at the root');
{
  const dup = join(__dirname, '..', 'firebase', 'firebase.json');
  if (existsSync(dup)) bad('firebase/firebase.json exists again -- deploy.sh and CI would read different configs');
  else ok('no nested firebase/firebase.json');

  const script = readFileSync(join(__dirname, '..', 'firebase', 'deploy.sh'), 'utf8');
  if (/cd "\$\(dirname "\$0"\)"/.test(script)) bad('deploy.sh still cd`s into firebase/ instead of the repo root');
  else ok('deploy.sh runs from the repo root');
}

console.log(failed ? `\n${failed} FAILED` : '\nOK — firestore rules invariants hold, storage unconfigured');

// jest claims this file because of the .test.ts name, but everything above runs
// at import. Calling process.exit() from a worker killed the worker, so jest
// reported "Test suite failed to run" — a red suite that asserted nothing, and a
// green run that executed zero assertions. Asserting in a real test is what
// makes this a gate. `failed` is the count from bad(); 0 means every invariant held.
test('firestore rules invariants hold and storage stays unconfigured', () => {
  expect(failed).toBe(0);
});
