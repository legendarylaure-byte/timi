import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

// Audit-compliance: fetch the creator's allowed publish options (privacy levels,
// comment/duet/stitch availability) from /v2/post/publish/creator_info/query/.
// The UI must NOT preselect a default privacy level.
export async function GET() {
  try {
    const db = getAdminFirestore();
    const doc = await db.collection('platform_settings').doc('tiktok').get();
    if (!doc.exists) {
      return NextResponse.json({ success: false, error: 'TikTok not connected' }, { status: 400 });
    }
    const data = doc.data() || {};
    const accessToken = data.access_token || '';
    if (!accessToken) {
      return NextResponse.json({ success: false, error: 'TikTok access token missing' }, { status: 400 });
    }

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
    if (!resp.ok) {
      return NextResponse.json(
        { success: false, error: `creator_info query failed (${resp.status}): ${JSON.stringify(body).slice(0, 300)}` },
        { status: resp.status },
      );
    }

    const info = body?.data || {};
    return NextResponse.json({
      success: true,
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
