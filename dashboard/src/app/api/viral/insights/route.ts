import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

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