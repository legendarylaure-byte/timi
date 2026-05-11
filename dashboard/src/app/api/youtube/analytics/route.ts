import { NextResponse } from 'next/server';
import { getFirestore, collection, query, orderBy, getDocs, limit as firestoreLimit } from 'firebase/firestore';
import { initializeApp, getApps } from 'firebase/app';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function getFirestoreAdmin() {
  if (!getApps().length) {
    initializeApp(firebaseConfig);
  }
  return getFirestore();
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limitParam = parseInt(searchParams.get('limit') || '20');

    const db = getFirestoreAdmin();
    const q = query(
      collection(db, 'videos'),
      orderBy('created_at', 'desc'),
      firestoreLimit(limitParam)
    );
    const snapshot = await getDocs(q);

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
