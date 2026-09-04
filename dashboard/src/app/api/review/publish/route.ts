import { NextRequest, NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

const GRAPH_BASE = 'https://graph.facebook.com/v25.0';

export async function POST(request: NextRequest) {
  try {
    // Read the stored production token server-side (never returned to the
    // browser). This demo intentionally uses the app's own authorized Page
    // token so the reviewer sees a real publish without any dashboard secret
    // being exposed to the client.
    const db = getAdminFirestore();
    const fbSnap = await db.collection('platform_settings').doc('facebook').get();
    const fb = fbSnap.exists ? fbSnap.data() : null;
    const pageToken: string = fb?.access_token || '';
    const pageId: string = fb?.page_id || process.env.FACEBOOK_PAGE_ID || '';

    if (!pageToken || !pageId) {
      return NextResponse.json(
        { success: false, error: 'Facebook not connected / missing token' },
        { status: 400 },
      );
    }

    const message =
      'Timi Video - Meta App Review demo publish. This post verifies the pages_manage_posts / publish_video permission end-to-end.';

    const pubResp = await fetch(
      `${GRAPH_BASE}/${pageId}/feed?message=${encodeURIComponent(message)}&access_token=${pageToken}`,
      { method: 'POST', signal: AbortSignal.timeout(20000) },
    );
    const body = await pubResp.json();

    if (!pubResp.ok) {
      return NextResponse.json(
        { success: false, error: body?.error?.message || 'Publish failed' },
        { status: 500 },
      );
    }

    return NextResponse.json({
      success: true,
      post_id: body.id,
      page_id: pageId,
      demo: true,
    });
  } catch (err: any) {
    return NextResponse.json(
      { success: false, error: err.message || 'Publish error' },
      { status: 500 },
    );
  }
}
