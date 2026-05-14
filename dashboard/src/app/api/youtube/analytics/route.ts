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

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json(
        { success: false, error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const { searchParams } = new URL(request.url);
    const limitParam = parseInt(searchParams.get('limit') || '20');

    const db = getAdminFirestore();
    const snapshot = await db
      .collection('videos')
      .orderBy('created_at', 'desc')
      .limit(limitParam)
      .get();

    const videos = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        video_id: data.video_id || doc.id,
        title: data.title || '',
        format: data.format || 'shorts',
        status: data.status || '',
        views: data.views || 0,
        likes: data.likes || 0,
        comments: data.comments || 0,
        youtube_id: data.youtube_id || null,
        publish_urls: data.publish_urls || {},
        created_at: data.created_at?.toDate?.()?.toISOString() || data.created_at || null,
        analytics_updated_at: data.analytics_updated_at?.toDate?.()?.toISOString() || data.analytics_updated_at || null,
      };
    });

    const totalViews = videos.reduce((sum, v) => sum + (v.views || 0), 0);
    const totalLikes = videos.reduce((sum, v) => sum + (v.likes || 0), 0);
    const totalComments = videos.reduce((sum, v) => sum + (v.comments || 0), 0);
    const publishedVideos = videos.filter(v => v.status === 'uploaded' || v.status === 'published');

    return NextResponse.json({
      success: true,
      summary: {
        total_videos: videos.length,
        published_videos: publishedVideos.length,
        total_views: totalViews,
        total_likes: totalLikes,
        total_comments: totalComments,
        last_updated: new Date().toISOString(),
      },
      videos: publishedVideos,
    });
  } catch (error: any) {
    console.error('[ANALYTICS API] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message, summary: { total_videos: 0, published_videos: 0, total_views: 0, total_likes: 0, total_comments: 0 }, videos: [] },
      { status: 500 }
    );
  }
}
