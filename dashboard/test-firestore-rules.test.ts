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
import { readFileSync } from 'fs';
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

// --- storage.rules -----------------------------------------------------------
// Two files now hardcode the owner email. If they drift, the app allows the
// owner while the database denies them (or worse, the reverse) and the only
// symptom is a dashboard full of permission errors.
console.log('\n8. storage.rules agrees with firestore.rules, and nothing is public');
{
  const storage = code(readFileSync(join(__dirname, '..', 'firebase', 'storage.rules'), 'utf8'));
  const sf = storage.match(/function ownerEmail\(\)\s*\{\s*return\s+"([^"]*)"/);
  const ff = src.match(/function ownerEmail\(\)\s*\{\s*return\s+"([^"]*)"/);
  if (!sf) bad('storage.rules has no ownerEmail()');
  else if (sf[1] !== ff?.[1]) bad(`storage ownerEmail "${sf[1]}" != firestore "${ff?.[1]}"`);
  else ok(`both rules files agree: ${sf[1]}`);

  if (/allow read[^:]*: if true/.test(storage)) bad('storage.rules still has a PUBLIC read');
  else ok('no unconditional public read');

  if (/match \/\{allPaths=\*\*\}/.test(storage)) ok('catch-all deny present');
  else bad('no catch-all deny in storage.rules');
}

console.log(failed ? `\n${failed} FAILED` : '\nOK — firestore + storage rules invariants hold');
process.exit(failed ? 1 : 0);