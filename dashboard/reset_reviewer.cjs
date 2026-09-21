const { initializeApp, cert } = require('firebase-admin/app');
const { getAuth } = require('firebase-admin/auth');
const sa = require('/Users/Ai Mark/timi/firebase/serviceAccountKey.json');
initializeApp({ credential: cert(sa) });
const auth = getAuth();
(async () => {
  try {
    const user = await auth.getUserByEmail('reviewer@vyomai.cloud');
    await auth.updateUser(user.uid, { password: 'TikTokDemo2026!' });
    console.log('RESET OK', user.uid);
  } catch (e) {
    if (e.code === 'auth/user-not-found') {
      const u = await auth.createUser({ email: 'reviewer@vyomai.cloud', password: 'TikTokDemo2026!', displayName: 'TikTok Reviewer', emailVerified: true });
      console.log('CREATED', u.uid);
    } else { throw e; }
  }
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
