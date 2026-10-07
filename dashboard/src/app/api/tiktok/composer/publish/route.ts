import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { Timestamp } from 'firebase-admin/firestore';

// Audit-compliance: reject when no privacy level is selected (no implicit default),
// matching the backend hard-fail. Comment/duet/stitch default to off.
export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const body = await request.json();
    const { video_id, title, description, format, category, privacy_level, comment_disabled, duet_disabled, stitch_disabled, brand_organic, brand_content, express_consent, music_usage_confirmed } = body;

    if (!video_id || !title) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields: video_id, title' },
        { status: 400 },
      );
    }
    if (!privacy_level || !privacy_level.trim()) {
      return NextResponse.json(
        { success: false, error: 'privacy_level is required (no default is preselected)' },
        { status: 400 },
      );
    }

    const db = getAdminFirestore();

    // An unaudited Direct Post app may only post with SELF_ONLY privacy; TikTok
    // refuses anything else at init with `unaudited_client_can_only_post_to_private_accounts`.
    // The single knob is TIKTOK_PRIVACY_LEVEL: while it is SELF_ONLY (or unset) only
    // SELF_ONLY posts are legal. When the audit grants, flip that env var to
    // PUBLIC_TO_EVERYONE and this restriction lifts automatically.
    const envDoc = await db.collection('env_vars').doc('TIKTOK_PRIVACY_LEVEL').get().catch(() => null);
    const privacyEnv = (envDoc?.exists && envDoc.data()?.value) || '';
    const unaudited = !privacyEnv || privacyEnv.toUpperCase() === 'SELF_ONLY';
    if (unaudited && privacy_level.trim().toUpperCase() !== 'SELF_ONLY') {
      return NextResponse.json(
        {
          success: false,
          error: `Your TikTok app is not yet audited, so TikTok only permits "Only me" (SELF_ONLY) posts. A private post still proves the publishing flow.`,
        },
        { status: 400 },
      );
    }
    if (!express_consent) {
      return NextResponse.json(
        { success: false, error: 'express_consent is required before publishing' },
        { status: 400 },
      );
    }
    if (!music_usage_confirmed) {
      return NextResponse.json(
        { success: false, error: 'music_usage_confirmed is required (Music Usage Confirmation)' },
        { status: 400 },
      );
    }

    const doc = await db.collection('tiktok_composer').add({
      video_id,
      title,
      description: description || '',
      format: format || 'shorts',
      category: category || '',
      privacy_level,
      comment_disabled: !!comment_disabled,
      duet_disabled: duet_disabled === undefined ? true : !!duet_disabled,
      stitch_disabled: stitch_disabled === undefined ? true : !!stitch_disabled,
      brand_organic: !!brand_organic,
      brand_content: !!brand_content,
      express_consent: !!express_consent,
      music_usage_confirmed: !!music_usage_confirmed,
      status: 'queued',
      created_at: Timestamp.now(),
    });

    return NextResponse.json({ success: true, intent_id: doc.id });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
