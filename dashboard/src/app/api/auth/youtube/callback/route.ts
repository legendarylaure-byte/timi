import { NextRequest, NextResponse } from 'next/server';
import { APP_URL } from '@/lib/constants';
import { getAdminFirestore } from '@/lib/firebase-admin';

const YOUTUBE_CLIENT_ID = process.env.YOUTUBE_CLIENT_ID || '';
const YOUTUBE_CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET || '';
const YOUTUBE_REDIRECT_URI = process.env.YOUTUBE_REDIRECT_URI || `${APP_URL}/api/auth/youtube/callback`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');
  const state = searchParams.get('state'); // user UID from init

  if (error) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=${error}`
    );
  }

  if (!code) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=missing_code`
    );
  }

  if (!state) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=missing_state`
    );
  }

  if (!YOUTUBE_CLIENT_ID || !YOUTUBE_CLIENT_SECRET) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=missing_oauth_config`
    );
  }

  try {
    const tokenResponse = await fetch('https://oauth2.googleapis.com/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code,
        client_id: YOUTUBE_CLIENT_ID,
        client_secret: YOUTUBE_CLIENT_SECRET,
        redirect_uri: YOUTUBE_REDIRECT_URI,
        grant_type: 'authorization_code',
      }),
    });

    if (!tokenResponse.ok) {
      throw new Error('Failed to exchange code for tokens');
    }

    const tokens = await tokenResponse.json();

    // Persist tokens to Firestore for the user
    try {
      const db = getAdminFirestore();
      await db.collection('platform_settings').doc('youtube').set({
        connected: true,
        access_token: tokens.access_token,
        refresh_token: tokens.refresh_token,
        scope: tokens.scope,
        token_type: tokens.token_type,
        expires_at: Date.now() + (tokens.expires_in || 3600) * 1000,
        updated_at: new Date().toISOString(),
        userId: state,
      }, { merge: true });
    } catch (firestoreError) {
      console.error('[YOUTUBE CALLBACK] Failed to persist tokens:', firestoreError);
    }

    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?youtube_connected=true`
    );
  } catch (error) {
    console.error('[YOUTUBE CALLBACK] Error:', error);
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=token_exchange_failed`
    );
  }
}
