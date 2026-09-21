import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const snapshot = await db.collection('viral_news_insights')
      .orderBy('virality_score', 'desc')
      .limit(8)
      .get();

    const stories = snapshot.docs.map(d => ({ id: d.id, ...d.data() }));
    return NextResponse.json({ stories });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch insights' },
      { status: 500 },
    );
  }
}