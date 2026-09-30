import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';

/**
 * Redacted view of /platform_settings.
 *
 * These docs hold OAuth access/refresh tokens. Firestore rules cannot do
 * field-level reads, so the browser previously downloaded the tokens in full
 * (publishing/page.tsx spread `...d.data()` into state, and settings/page.tsx
 * subscribed to the whole collection) and only happened not to render them.
 * Anything in the JS payload is already leaked to the user's browser, so the
 * fix is to stop serving the documents at all.
 *
 * Pinned by ALLOWED_FIELDS rather than "strip the known-bad keys": a token
 * added to a doc later is then excluded by default instead of by memory.
 */
const ALLOWED_FIELDS = [
  'name', 'icon', 'color', 'connected', 'followers',
  'videosPublished', 'lastPublished', 'scope', 'autoPublish',
] as const;

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const snap = await getAdminFirestore().collection('platform_settings').get();
    const platforms = snap.docs.map((d) => {
      const data = d.data() as Record<string, unknown>;
      const safe: Record<string, unknown> = { id: d.id };
      for (const f of ALLOWED_FIELDS) {
        if (data[f] !== undefined) safe[f] = data[f];
      }
      return safe;
    });

    return NextResponse.json({ success: true, platforms });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
