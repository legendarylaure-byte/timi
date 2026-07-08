import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { CONTENT_CATEGORIES } from '@/lib/constants';

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

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const videosSnap = await db.collection('videos')
      .orderBy('created_at', 'desc')
      .limit(200)
      .get();

    const categoryData: Record<string, {
      lastPost: Date | null; totalViews: number;
      count: number; qualityScores: number[];
    }> = {};

    const allCategoryNames = new Set(CONTENT_CATEGORIES.map(c => c.name));

    for (const doc of videosSnap.docs) {
      const d = doc.data();
      const cat = d.category || 'Unknown';
      const createdAt = d.created_at?.toDate?.();
      if (!createdAt) continue;

      if (!categoryData[cat]) {
        categoryData[cat] = { lastPost: null, totalViews: 0, count: 0, qualityScores: [] };
      }

      if (!categoryData[cat].lastPost || createdAt > categoryData[cat].lastPost) {
        categoryData[cat].lastPost = createdAt;
      }
      categoryData[cat].totalViews += d.views || 0;
      categoryData[cat].count++;
      if (d.quality_score) categoryData[cat].qualityScores.push(d.quality_score);
    }

    const now = new Date();
    const gaps = Array.from(allCategoryNames).map(cat => {
      const data = categoryData[cat];
      let daysSinceLastPost = 999;
      if (data?.lastPost) {
        daysSinceLastPost = Math.floor((now.getTime() - data.lastPost.getTime()) / 86400000);
      }
      const avgViews = data && data.count > 0 ? Math.round(data.totalViews / data.count) : 0;
      const avgScore = data && data.qualityScores.length > 0
        ? Math.round(data.qualityScores.reduce((a, b) => a + b, 0) / data.qualityScores.length)
        : 0;

      let recommendation = '';
      if (daysSinceLastPost === 999) {
        recommendation = 'Never posted in this category — consider creating content';
      } else if (daysSinceLastPost > 30) {
        recommendation = `Over a month since last post — revisit this category`;
      } else if (daysSinceLastPost > 14) {
        recommendation = `Two weeks without content — good opportunity for fresh content`;
      } else {
        recommendation = `Active ${daysSinceLastPost}d ago — maintain consistency`;
      }

      const isTrending = avgViews > 100;

      return {
        category: cat,
        daysSinceLastPost,
        lastPosted: data?.lastPost?.toISOString() || null,
        isTrending,
        avgViews,
        avgScore,
        totalVideos: data?.count || 0,
        recommendation,
      };
    });

    gaps.sort((a, b) => {
      if (a.isTrending !== b.isTrending) return a.isTrending ? -1 : 1;
      return b.daysSinceLastPost - a.daysSinceLastPost;
    });

    return NextResponse.json({ gaps });
  } catch (error: any) {
    console.error('[CONTENT GAPS] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
