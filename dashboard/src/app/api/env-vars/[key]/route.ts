import { NextRequest, NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';

async function verifyAuth(request: Request): Promise<{ uid: string } | null> {
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  try {
    const token = authHeader.slice(7);
    const decoded = await getAdminAuth().verifyIdToken(token);
    return { uid: decoded.uid };
  } catch {
    return null;
  }
}

const VERCEL_TOKEN = process.env.VERCEL_TOKEN || '';
const VERCEL_PROJECT_ID = 'prj_ALkaTWucBOWJkIpRsydJjtbyrUXC';

const SENSITIVE_KEYS = new Set([
  'FACEBOOK_ACCESS_TOKEN', 'FACEBOOK_APP_SECRET',
  'GEMINI_API_KEY', 'GROQ_API_KEY',
  'PEXELS_API_KEY', 'PIXABAY_API_KEY',
  'TELEGRAM_BOT_TOKEN', 'SENTRY_DSN',
  'CLOUDFLARE_R2_ACCESS_KEY_ID', 'CLOUDFLARE_R2_SECRET_ACCESS_KEY',
  'TIKTOK_CLIENT_SECRET', 'TIKTOK_ACCESS_TOKEN', 'TIKTOK_REFRESH_TOKEN',
  'YOUTUBE_CLIENT_SECRET',
]);

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ key: string }> },
) {
  const { key } = await params;
  if (!key || key !== key.toUpperCase()) {
    return NextResponse.json({ success: false, error: 'Invalid key name' }, { status: 400 });
  }

  const user = await verifyAuth(request);
  if (!user) {
    return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
  }

  try {
    const body = await request.json();
    const value = body.value;
    if (value === undefined || value === null) {
      return NextResponse.json({ success: false, error: 'Missing value' }, { status: 400 });
    }

    const now = new Date().toISOString();

    // 1. Save to Firestore
    const db = getAdminFirestore();
    await db.collection('env_vars').doc(key).set(
      { value, updated_at: now },
      { merge: true },
    );

    // 2. Update Vercel env var
    let vercelResult: any = { ok: true };
    if (VERCEL_TOKEN) {
      try {
        const isSecret = SENSITIVE_KEYS.has(key);
        const vercelResp = await fetch(
          `https://api.vercel.com/v10/projects/${VERCEL_PROJECT_ID}/env`,
          {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${VERCEL_TOKEN}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              key,
              value,
              target: ['production'],
              type: isSecret ? 'encrypted' : 'plain',
            }),
          },
        );
        vercelResult = await vercelResp.json();
        if (!vercelResp.ok) {
          console.error(`[ENV-VARS] Vercel API error for ${key}:`, vercelResult);
        }
      } catch (vercelErr: any) {
        console.error(`[ENV-VARS] Vercel call failed for ${key}:`, vercelErr.message);
        vercelResult = { error: vercelErr.message };
      }
    }

    return NextResponse.json({
      success: true,
      key,
      updated_at: now,
      vercel: vercelResult.error ? `update skipped: ${vercelResult.error}` : 'synced',
    });
  } catch (err: any) {
    console.error(`[ENV-VARS] Failed to update ${key}:`, err);
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
