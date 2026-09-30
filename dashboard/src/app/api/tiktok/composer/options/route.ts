import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

// Audit-compliance: fetch the creator's allowed publish options (privacy levels,
// comment/duet/stitch availability) from /v2/post/publish/creator_info/query/.
// The UI must NOT preselect a default privacy level.
export async function GET(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  const db = getAdminFirestore();

  async function loadToken() {
    const doc = await db.collection('platform_settings').doc('tiktok').get();
    if (!doc.exists) return '';
    return (doc.data() || {}).access_token || '';
  }

  async function refreshAccessToken(): Promise<string | null> {
    const getEnv = async (k: string) => {
      const d = await db.collection('env_vars').doc(k).get();
      return d.exists ? ((d.data() || {}).value ?? '') : '';
    };
    const [refreshToken, clientKey, clientSecret] = await Promise.all([
      getEnv('TIKTOK_REFRESH_TOKEN'),
      getEnv('TIKTOK_CLIENT_KEY'),
      getEnv('TIKTOK_CLIENT_SECRET'),
    ]);
    if (!refreshToken || !clientKey || !clientSecret) return null;
    try {
      const resp = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_key: clientKey,
          client_secret: clientSecret,
          grant_type: 'refresh_token',
          refresh_token: refreshToken,
        }),
        signal: AbortSignal.timeout(15000),
      });
      if (!resp.ok) return null;
      const body = await resp.json().catch(() => ({}));
      const newToken = body.access_token;
      if (!newToken) return null;
      const newRefresh = body.refresh_token || refreshToken;
      await db.collection('platform_settings').doc('tiktok').update({ access_token: newToken }).catch(() => {});
      await db.collection('env_vars').doc('TIKTOK_ACCESS_TOKEN').update({ value: newToken }).catch(() => {});
      if (newRefresh !== refreshToken) {
        await db.collection('env_vars').doc('TIKTOK_REFRESH_TOKEN').update({ value: newRefresh }).catch(() => {});
      }
      return newToken;
    } catch {
      return null;
    }
  }

  async function queryCreatorInfo(accessToken: string) {
    const resp = await fetch('https://open.tiktokapis.com/v2/post/publish/creator_info/query/', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ common_info: {} }),
      signal: AbortSignal.timeout(15000),
    });
    const body = await resp.json().catch(() => ({}));
    return { ok: resp.ok, status: resp.status, body };
  }

  try {
    let accessToken = await loadToken();
    if (!accessToken) {
      return NextResponse.json({ success: false, error: 'TikTok access token missing' }, { status: 400 });
    }

    let { ok, status, body } = await queryCreatorInfo(accessToken);
    if (!ok && status === 401) {
      const fresh = await refreshAccessToken();
      if (fresh) {
        accessToken = fresh;
        ({ ok, status, body } = await queryCreatorInfo(accessToken));
      }
    }

    if (!ok) {
      return NextResponse.json(
        { success: false, error: `creator_info query failed (${status}): ${JSON.stringify(body).slice(0, 300)}` },
        { status },
      );
    }

    const info = body?.data || {};
    return NextResponse.json({
      success: true,
      creator_nickname: info.creator_nickname || '',
      creator_username: info.creator_username || '',
      creator_avatar_url: info.creator_avatar_url || '',
      max_video_post_duration_sec: Number(info.max_video_post_duration_sec) || 0,
      privacy_level_options: info.privacy_level_options || [],
      comment_disabled: !!info.comment_disabled,
      duet_disabled: !!info.duet_disabled,
      stitch_disabled: !!info.stitch_disabled,
      vid_private: !!info.vid_private,
      display_privacy: info.display_privacy ?? '',
    });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}