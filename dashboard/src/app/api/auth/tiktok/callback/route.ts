import { NextRequest, NextResponse } from 'next/server';
import { APP_URL } from '@/lib/constants';
import { getAdminFirestore } from '@/lib/firebase-admin';

const TIKTOK_CLIENT_KEY = process.env.TIKTOK_CLIENT_KEY || '';
const TIKTOK_CLIENT_SECRET = process.env.TIKTOK_CLIENT_SECRET || '';
const TIKTOK_REDIRECT_URI = process.env.TIKTOK_REDIRECT_URI || `${APP_URL}/api/auth/tiktok/callback`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  if (error) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=tiktok_${error}`
    );
  }

  if (!code) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=tiktok_missing_code`
    );
  }

  if (!TIKTOK_CLIENT_KEY || !TIKTOK_CLIENT_SECRET) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=tiktok_missing_oauth_config`
    );
  }

  try {
    const tokenResponse = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_key: TIKTOK_CLIENT_KEY,
        client_secret: TIKTOK_CLIENT_SECRET,
        code,
        grant_type: 'authorization_code',
        redirect_uri: TIKTOK_REDIRECT_URI,
      }),
    });

    if (!tokenResponse.ok) {
      const errBody = await tokenResponse.text();
      console.error('[TIKTOK CALLBACK] Token exchange failed:', tokenResponse.status, errBody);
      return NextResponse.redirect(
        `${APP_URL}/dashboard/settings?error=tiktok_token_exchange_failed`
      );
    }

    const tokens = await tokenResponse.json();

    const payload: Record<string, unknown> = {
      connected: true,
      access_token: tokens.access_token,
      open_id: tokens.open_id,
      scope: tokens.scope,
      token_type: tokens.token_type,
      expires_at: Date.now() + (tokens.expires_in || 86400) * 1000,
      updated_at: new Date().toISOString(),
    };
    if (tokens.refresh_token) {
      payload.refresh_token = tokens.refresh_token;
    }

    try {
      const db = getAdminFirestore();
      await db.collection('platform_settings').doc('tiktok').set(payload, { merge: true });
    } catch (firestoreError) {
      console.error('[TIKTOK CALLBACK] Failed to persist tokens:', firestoreError);
    }

    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?tiktok_connected=true`
    );
  } catch (error) {
    console.error('[TIKTOK CALLBACK] Error:', error);
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=tiktok_token_exchange_failed`
    );
  }
}
