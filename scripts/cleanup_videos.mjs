import { initializeApp, cert, getApps } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');

// Load .env if present
try {
  const envPath = resolve(projectRoot, '.env');
  const envContent = readFileSync(envPath, 'utf-8');
  for (const line of envContent.split('\n')) {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith('#')) {
      const eqIdx = trimmed.indexOf('=');
      if (eqIdx > 0) {
        const key = trimmed.slice(0, eqIdx).trim();
        let val = trimmed.slice(eqIdx + 1).trim();
        if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
          val = val.slice(1, -1);
        }
        if (!process.env[key]) {
          process.env[key] = val;
        }
      }
    }
  }
} catch {}

function initApp() {
  if (getApps().length > 0) return getApps()[0];

  const keyBase64 = process.env.FIREBASE_SERVICE_ACCOUNT_KEY;
  if (keyBase64) {
    const sa = JSON.parse(Buffer.from(keyBase64, 'base64').toString('utf-8'));
    return initializeApp({ credential: cert(sa) });
  }

  const keyPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH;
  if (keyPath) {
    const fullPath = resolve(projectRoot, keyPath);
    const sa = JSON.parse(readFileSync(fullPath, 'utf-8'));
    return initializeApp({ credential: cert(sa) });
  }

  return initializeApp({ projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'timi-childern-stories' });
}

const OLD_TITLE_PATTERNS = [
  'Magical Bedtime Adventure',
  "Father's Day Songs",
  'Fathers Day',
  'Ocean Adventure',
  'Kids Story',
  'Children Story',
  'Bedtime Story',
  'Mythology',
  'Mythological',
];

async function cleanup() {
  initApp();
  const db = getFirestore();
  console.log('Connected to Firestore. Scanning videos collection...\n');

  const snapshot = await db.collection('videos').get();
  console.log(`Total documents in videos: ${snapshot.docs.length}\n`);

  let deleted = 0;
  let skipped = 0;

  for (const doc of snapshot.docs) {
    const data = doc.data();
    const title = (data.title || '').trim();
    const category = data.category || '';

    const matchesOld = OLD_TITLE_PATTERNS.some(p => title.toLowerCase().includes(p.toLowerCase()));
    const hasValidCategory = category && [
      'AI Explained', 'Deep Tech', 'Paper Breakdowns', 'Tool Tutorials',
      'Industry Analysis', 'Code & Build', 'AI News', 'Career & Learning',
    ].includes(category);

    if (matchesOld || (!category && !hasValidCategory && (title.toLowerCase().includes('magical') || title.toLowerCase().includes('bedtime') || title.toLowerCase().includes('ocean') || title.toLowerCase().includes('father')))) {
      console.log(`DELETING: "${title}" (${doc.id})`);
      await doc.ref.delete();
      deleted++;
    } else {
      skipped++;
    }
  }

  console.log(`\nDone. Deleted: ${deleted} | Skipt: ${skipped}`);
  process.exit(0);
}

cleanup().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
