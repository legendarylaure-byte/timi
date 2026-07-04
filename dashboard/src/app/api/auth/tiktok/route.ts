import { NextRequest, NextResponse } from 'next/server';

const TIKTOK_CLIENT_KEY = process.env.TIKTOK_CLIENT_KEY || '';
const TIKTOK_REDIRECT_URI = process.env.TIKTOK_REDIRECT_URI || 'http://localhost:5001/api/auth/tiktok/callback';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const action = searchParams.get('action');

  if (action === 'connect') {
    if (!TIKTOK_CLIENT_KEY) {
      return NextResponse.json({ success: false, error: 'TikTok OAuth not configured' }, { status: 500 });
    }
    const authUrl = new URL('https://www.tiktok.com/v2/auth/authorize/');
    authUrl.searchParams.set('client_key', TIKTOK_CLIENT_KEY);
    authUrl.searchParams.set('scope', 'user.info.basic,video.upload');
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('redirect_uri', TIKTOK_REDIRECT_URI);
    authUrl.searchParams.set('state', 'production_timi');

    return NextResponse.redirect(authUrl.toString());
  }

  return NextResponse.json({
    success: true,
    message: 'TikTok auth endpoint',
    connected: true,
  });
}
