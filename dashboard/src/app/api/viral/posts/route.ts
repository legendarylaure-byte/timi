import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const snapshot = await db.collection('viral_news_posts')
      .orderBy('posted_at', 'desc')
      .limit(30)
      .get();

    const posts = snapshot.docs.map(d => ({
      id: d.id,
      ...d.data(),
    }));

    return NextResponse.json({ posts });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch posts' },
      { status: 500 },
    );
  }
}
