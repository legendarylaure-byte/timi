import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const snapshot = await db.collection('viral_news_activity')
      .orderBy('timestamp', 'desc')
      .limit(50)
      .get();

    const activities = snapshot.docs.map(d => {
      const data = d.data();
      return {
        id: d.id,
        action: data.event || d.id,
        timestamp: data.timestamp || data.created_at || null,
        details: data.details || {},
      };
    });

    return NextResponse.json({ activities });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch activity' },
      { status: 500 },
    );
  }
}