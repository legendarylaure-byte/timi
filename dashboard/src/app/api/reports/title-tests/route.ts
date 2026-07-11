import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

async function verifyAuth(request: Request): Promise<{ uid: string } | null> {
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  try {
    const token = authHeader.slice(7);
    const { getAdminAuth } = await import('@/lib/firebase-admin');
    const decoded = await getAdminAuth().verifyIdToken(token);
    return { uid: decoded.uid };
  } catch {
    return null;
  }
}

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const videosSnap = await db.collection('videos')
      .orderBy('created_at', 'desc')
      .limit(100)
      .get();

    const tests = [];
    for (const doc of videosSnap.docs) {
      const data = doc.data();
      const ytId = data.youtube_id || data.yt_video_id || '';
      if (!ytId) continue;
      const titleTests = data.title_tests || data.ab_testing || null;
      if (titleTests) {
        tests.push({
          videoId: doc.id,
          youtubeId: ytId,
          title: data.title || data.topic || '',
          variants: titleTests.variants || [],
          currentIndex: titleTests.current_index ?? titleTests.currentIndex ?? 0,
          status: titleTests.status || 'unknown',
          startedAt: titleTests.started_at || titleTests.startedAt || '',
          stageEnd: titleTests.stage_end || titleTests.stageEnd || '',
          results: titleTests.results || {},
          winner: titleTests.winner || null,
          format: data.format || 'unknown',
          category: data.category || '',
          publishedAt: data.published_at || data.publish_at || '',
        });
      }
    }

    const { execSync } = await import('child_process');
    let localTests = [];
    try {
      const localDir = '/Users/Ai Mark/timi/agents/data/title_tests';
      const { readdirSync, existsSync, readFileSync } = await import('fs');
      if (existsSync(localDir)) {
        for (const f of readdirSync(localDir)) {
          if (!f.endsWith('.json')) continue;
          try {
            const content = readFileSync(`${localDir}/${f}`, 'utf-8');
            localTests.push(JSON.parse(content));
          } catch { /* skip corrupt files */ }
        }
      }
    } catch { /* no local data */ }

    return NextResponse.json({
      success: true,
      tests,
      localTests,
      total: tests.length + localTests.length,
    });
  } catch (error: any) {
    console.error('[TITLE TESTS] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { videoId, action } = body;

    if (!videoId || !action) {
      return NextResponse.json({ success: false, error: 'videoId and action required' }, { status: 400 });
    }

    const db = getAdminFirestore();

    if (action === 'advance') {
      const { execSync } = await import('child_process');
      try {
        execSync(
          `cd /Users/Ai Mark/timi/agents && python3 -c "from utils.title_tester import advance_title_test; r = advance_title_test('${videoId.replace(/'/g, "\\'")}'); print(r)"`,
          { timeout: 30000 }
        );
        return NextResponse.json({ success: true, message: 'Test advanced' });
      } catch (e: any) {
        return NextResponse.json({ success: false, error: e.message }, { status: 500 });
      }
    }

    if (action === 'stop') {
      await db.collection('videos').doc(videoId).update({
        'title_tests.status': 'stopped',
        'title_tests.stopped_at': new Date().toISOString(),
      });
      return NextResponse.json({ success: true, message: 'Test stopped' });
    }

    return NextResponse.json({ success: false, error: 'Unknown action' }, { status: 400 });
  } catch (error: any) {
    console.error('[TITLE TESTS POST] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
