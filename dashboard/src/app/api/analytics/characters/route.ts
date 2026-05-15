import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';

async function verifyAuth(request: Request): Promise<{ uid: string } | null> {
  const authHeader = request.headers.get('authorization');
  if (!authHeader?.startsWith('Bearer ')) return null;
  try {
    const token = authHeader.slice(7);
    const decoded = await getAdminAuth().verifyIdToken(token);
    return { uid: decoded.uid };
  } catch {
    return null;
  }
}

const CHARACTER_NAMES: Record<string, string> = {
  pixel: 'Pixel',
  nova: 'Nova',
  ziggy: 'Ziggy',
  boop: 'Boop',
  sprout: 'Sprout',
};

const CHARACTER_EMOJIS: Record<string, string> = {
  pixel: '🤖',
  nova: '⭐',
  ziggy: '🌈',
  boop: '🔵',
  sprout: '🌱',
};

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const snapshot = await db.collection('videos').limit(100).get();

    const charStats: Record<string, { total_views: number; video_count: number; categories: Record<string, number> }> = {};

    for (const doc of snapshot.docs) {
      const data = doc.data();
      const char = (data.character || '').toLowerCase();
      if (!char || !CHARACTER_NAMES[char]) continue;

      if (!charStats[char]) {
        charStats[char] = { total_views: 0, video_count: 0, categories: {} };
      }
      charStats[char].total_views += data.views || 0;
      charStats[char].video_count += 1;
      const cat = data.category || data.format || 'general';
      charStats[char].categories[cat] = (charStats[char].categories[cat] || 0) + 1;
    }

    const totalViews = Object.values(charStats).reduce((s, c) => s + c.total_views, 0) || 1;
    const characters = Object.entries(charStats)
      .map(([id, stats]) => ({
        id,
        name: CHARACTER_NAMES[id] || id,
        emoji: CHARACTER_EMOJIS[id] || '❓',
        total_views: stats.total_views,
        video_count: stats.video_count,
        share_pct: Math.round((stats.total_views / totalViews) * 100),
        top_categories: Object.entries(stats.categories)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([cat]) => cat),
      }))
      .sort((a, b) => b.total_views - a.total_views);

    return NextResponse.json({ success: true, characters, total_views: totalViews });
  } catch (error: any) {
    console.error('[CHARACTERS API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
