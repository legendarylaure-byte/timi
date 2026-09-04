import { NextRequest, NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

const FB_APP_ID = process.env.FACEBOOK_APP_ID || '';
const FB_APP_SECRET = process.env.FACEBOOK_APP_SECRET || '';
const APP_URL = process.env.NEXT_PUBLIC_APP_URL || 'https://timi.vyomai.cloud';
const FB_REDIRECT_URI = process.env.FACEBOOK_REDIRECT_URI || `${APP_URL}/api/auth/meta/callback`;

const GRAPH_BASE = 'https://graph.facebook.com/v25.0';
const REDIRECT_OK = `${APP_URL}/dashboard/settings?meta_connected=true`;
const REDIRECT_ERR = (code: string) => `${APP_URL}/dashboard/settings?error=meta_${code}`;

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');
  const errorDescription = searchParams.get('error_description') || searchParams.get('error_reason') || '';
  const state = searchParams.get('state') || '';

  // Demo mode: an OAuth round-trip initiated from the public /review page for
  // Meta App Review. It demonstrates the consent flow but never persists the
  // resulting token, so the live pipeline's production FACEBOOK token is never
  // overwritten by a reviewer's account.
  const demo = state.startsWith('demo-');
  const REDIRECT_OK_DEMO = `${APP_URL}/review?demo_connected=true`;
  const REDIRECT_ERR_DEMO = (code: string) => `${APP_URL}/review?error=meta_${code}`;

  if (error) {
    console.error('[META CALLBACK] OAuth error:', error, errorDescription);
    return NextResponse.redirect(demo ? REDIRECT_ERR_DEMO('oauth_denied') : REDIRECT_ERR('oauth_denied'));
  }

  if (!code) {
    return NextResponse.redirect(demo ? REDIRECT_ERR_DEMO('missing_code') : REDIRECT_ERR('missing_code'));
  }

  if (!FB_APP_ID || !FB_APP_SECRET) {
    return NextResponse.redirect(demo ? REDIRECT_ERR_DEMO('missing_oauth_config') : REDIRECT_ERR('missing_oauth_config'));
  }

  try {
    // 1. Exchange the authorization code for a short-lived user access token.
    const tokenResp = await fetch(
      `${GRAPH_BASE}/oauth/access_token?client_id=${FB_APP_ID}&client_secret=${FB_APP_SECRET}&redirect_uri=${FB_REDIRECT_URI}&code=${code}`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (!tokenResp.ok) {
      const body = await tokenResp.text();
      console.error('[META CALLBACK] Token exchange failed:', tokenResp.status, body);
      return NextResponse.redirect(demo ? REDIRECT_ERR_DEMO('token_exchange_failed') : REDIRECT_ERR('token_exchange_failed'));
    }
    const tokenData = await tokenResp.json();
    const shortToken: string = tokenData.access_token || '';

    // 2. Upgrade to a long-lived (60-day) user token.
    const longResp = await fetch(
      `${GRAPH_BASE}/oauth/access_token?grant_type=fb_exchange_token&client_id=${FB_APP_ID}&client_secret=${FB_APP_SECRET}&fb_exchange_token=${shortToken}`,
      { signal: AbortSignal.timeout(15000) },
    );
    const userToken = longResp.ok
      ? (await longResp.json()).access_token || shortToken
      : shortToken;

    // Demo mode: verify the token exchanged cleanly, redirect back to /review,
    // and DO NOT persist any token (protects the live production token).
    if (demo) {
      return NextResponse.redirect(REDIRECT_OK_DEMO);
    }

    // 3. Discover the managed Page and its token.
    const accountsResp = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${userToken}&fields=id,name,access_token`,
      { signal: AbortSignal.timeout(15000) },
    );
    const accounts = accountsResp.ok ? (await accountsResp.json()).data || [] : [];

    const page = accounts.find((a: any) => a.id === process.env.FACEBOOK_PAGE_ID) || accounts[0];
    const pageId: string | null = page?.id || null;
    const pageToken: string | null = page?.access_token || userToken;

    // 4. Resolve the linked Instagram business account via the Page.
    let igAccountId: string | null = null;
    if (pageId) {
      const igResp = await fetch(
        `${GRAPH_BASE}/${pageId}?fields=instagram_business_account&access_token=${userToken}`,
        { signal: AbortSignal.timeout(15000) },
      );
      if (igResp.ok) {
        const igData = await igResp.json();
        igAccountId = igData.instagram_business_account?.id || null;
      }
    }

    // 5. Persist to Firestore (both platform_settings and env_vars for the pipeline).
    const now = new Date().toISOString();
    try {
      const db = getAdminFirestore();

      // Platform settings: facebook + instagram.
      await db.collection('platform_settings').doc('facebook').set(
        {
          connected: true,
          access_token: pageToken || userToken,
          page_id: pageId,
          user_token: userToken,
          scope: 'instagram_content_publish,instagram_basic,pages_manage_posts,pages_read_engagement,pages_show_list,public_profile',
          updated_at: now,
        },
        { merge: true },
      );

      if (igAccountId) {
        await db.collection('platform_settings').doc('instagram').set(
          {
            connected: true,
            access_token: pageToken || userToken,
            ig_account_id: igAccountId,
            page_id: pageId,
            updated_at: now,
          },
          { merge: true },
        );
      }

      // env_vars drives sync_env_from_firestore at pipeline boot — keep tokens +
      // account ids in sync so the pipeline uses this freshly-granted token.
      await db.collection('env_vars').doc('FACEBOOK_ACCESS_TOKEN').set(
        { value: pageToken || userToken, updated_at: now },
        { merge: true },
      );
      await db.collection('env_vars').doc('FACEBOOK_PAGE_ID').set(
        { value: pageId || '', updated_at: now },
        { merge: true },
      );
      if (igAccountId) {
        await db.collection('env_vars').doc('INSTAGRAM_ACCOUNT_ID').set(
          { value: igAccountId, updated_at: now },
          { merge: true },
        );
      }
    } catch (firestoreError) {
      console.error('[META CALLBACK] Firestore persist failed:', firestoreError);
    }

    return NextResponse.redirect(REDIRECT_OK);
  } catch (err: any) {
    console.error('[META CALLBACK] Error:', err);
    return NextResponse.redirect(REDIRECT_ERR('token_exchange_failed'));
  }
}