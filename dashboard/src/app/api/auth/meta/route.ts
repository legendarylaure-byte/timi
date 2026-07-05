import { NextRequest, NextResponse } from 'next/server';
import { APP_URL } from '@/lib/constants';
import { getAdminFirestore } from '@/lib/firebase-admin';

const FB_APP_ID = process.env.FACEBOOK_APP_ID || '';
const FB_APP_SECRET = process.env.FACEBOOK_APP_SECRET || '';
const FB_ACCESS_TOKEN = process.env.FACEBOOK_ACCESS_TOKEN || '';
const FB_PAGE_ID = process.env.FACEBOOK_PAGE_ID || '';
const IG_ACCOUNT_ID = process.env.INSTAGRAM_ACCOUNT_ID || '';

const GRAPH_BASE = 'https://graph.facebook.com/v25.0';

export async function GET(request: NextRequest) {
  const action = request.nextUrl.searchParams.get('action');

  if (action === 'connect') {
    if (!FB_ACCESS_TOKEN || !FB_APP_ID || !FB_APP_SECRET) {
      return NextResponse.json(
        { success: false, error: 'Meta credentials not configured on server' },
        { status: 500 },
      );
    }

    try {
      const token = await _ensure_long_lived_token(FB_ACCESS_TOKEN);
      if (!token) {
        return NextResponse.redirect(
          `${APP_URL}/dashboard/settings?error=facebook_token_invalid`,
        );
      }

      const pageToken = await _get_page_token(token);
      const pageId: string | null = FB_PAGE_ID || (await _discover_page_id(token)) || null;

      let igAccountId: string | null = IG_ACCOUNT_ID || null;
      if (!igAccountId && pageId) {
        igAccountId = await _discover_ig_account_id(token, pageId);
      }

      const db = getAdminFirestore();
      const now = new Date().toISOString();

      await db.collection('platform_settings').doc('facebook').set(
        {
          connected: true,
          access_token: pageToken || token,
          page_id: pageId,
          updated_at: now,
        },
        { merge: true },
      );

      if (igAccountId) {
        await db.collection('platform_settings').doc('instagram').set(
          {
            connected: true,
            access_token: pageToken || token,
            ig_account_id: igAccountId,
            page_id: pageId,
            updated_at: now,
          },
          { merge: true },
        );
      }

      return NextResponse.redirect(
        `${APP_URL}/dashboard/settings?facebook_connected=true`,
      );
    } catch (err: any) {
      console.error('[META AUTH] Connection failed:', err);
      return NextResponse.redirect(
        `${APP_URL}/dashboard/settings?error=facebook_connection_failed`,
      );
    }
  }

  return NextResponse.json({
    success: true,
    message: 'Meta auth endpoint',
    connected: true,
  });
}

async function _ensure_long_lived_token(token: string): Promise<string | null> {
  try {
    const resp = await fetch(
      `${GRAPH_BASE}/oauth/access_token?grant_type=fb_exchange_token&client_id=${FB_APP_ID}&client_secret=${FB_APP_SECRET}&fb_exchange_token=${token}`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (resp.ok) {
      const data = await resp.json();
      return data.access_token || token;
    }
    const me = await fetch(
      `${GRAPH_BASE}/me?access_token=${token}`,
      { signal: AbortSignal.timeout(10000) },
    );
    return me.ok ? token : null;
  } catch {
    return token;
  }
}

async function _get_page_token(token: string): Promise<string | null> {
  try {
    const resp = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${token}&fields=id,name,access_token`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const pages = data.data || [];
    if (FB_PAGE_ID) {
      const match = pages.find((p: any) => p.id === FB_PAGE_ID);
      if (match?.access_token) return match.access_token;
    }
    if (pages.length > 0 && pages[0].access_token) {
      return pages[0].access_token;
    }
    return null;
  } catch {
    return null;
  }
}

async function _discover_page_id(token: string): Promise<string | null> {
  try {
    const resp = await fetch(
      `${GRAPH_BASE}/me/accounts?access_token=${token}&fields=id`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    const pages = data.data || [];
    return pages.length > 0 ? pages[0].id : null;
  } catch {
    return null;
  }
}

async function _discover_ig_account_id(
  token: string,
  pageId: string,
): Promise<string | null> {
  try {
    const resp = await fetch(
      `${GRAPH_BASE}/${pageId}?access_token=${token}&fields=instagram_business_account`,
      { signal: AbortSignal.timeout(15000) },
    );
    if (!resp.ok) return null;
    const data = await resp.json();
    return data.instagram_business_account?.id || null;
  } catch {
    return null;
  }
}
