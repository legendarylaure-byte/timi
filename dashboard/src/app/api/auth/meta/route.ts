import { randomBytes } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';

const FB_APP_ID = process.env.FACEBOOK_APP_ID || '';
const FB_REDIRECT_URI =
  process.env.FACEBOOK_REDIRECT_URI || `${process.env.NEXT_PUBLIC_APP_URL || 'https://timi.vyomai.cloud'}/api/auth/meta/callback`;

const META_SCOPES =
  'instagram_content_publish,instagram_basic,pages_manage_posts,pages_read_engagement,pages_show_list,public_profile';

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get('action');
  const demo = request.nextUrl.searchParams.get('demo') === '1';

  if (action === 'connect') {
    if (!FB_APP_ID) {
      return NextResponse.json(
        { success: false, error: 'Meta App ID not configured on server' },
        { status: 500 },
      );
    }

    // CSRF state token, passed back to the callback to verify the round-trip.
    // In demo mode the state carries a marker so the callback performs the
    // OAuth exchange WITHOUT persisting tokens (keeps the live pipeline's
    // production token untouched — created for Meta App Review reviewers).
    const state = demo ? `demo-${randomBytes(16).toString('hex')}` : randomBytes(16).toString('hex');

    const authUrl = new URL('https://www.facebook.com/v25.0/dialog/oauth');
    authUrl.searchParams.set('client_id', FB_APP_ID);
    authUrl.searchParams.set('redirect_uri', FB_REDIRECT_URI);
    authUrl.searchParams.set('scope', META_SCOPES);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('state', state);

    return NextResponse.redirect(authUrl.toString());
  }

  return NextResponse.json({
    success: true,
    message: 'Meta auth endpoint',
    connected: true,
  });
}