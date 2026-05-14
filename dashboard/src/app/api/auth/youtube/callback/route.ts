import { NextRequest, NextResponse } from 'next/server';
import { APP_URL } from '@/lib/constants';

const YOUTUBE_CLIENT_ID = process.env.YOUTUBE_CLIENT_ID || '';
const YOUTUBE_CLIENT_SECRET = process.env.YOUTUBE_CLIENT_SECRET || '';
const YOUTUBE_REDIRECT_URI = process.env.YOUTUBE_REDIRECT_URI || `${APP_URL}/api/auth/youtube/callback`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

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

    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?youtube_connected=true`
    );
  } catch (error) {
    return NextResponse.redirect(
      `${APP_URL}/dashboard/settings?error=token_exchange_failed`
    );
  }
}
