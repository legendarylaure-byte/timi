import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET() {
  try {
    const db = getAdminFirestore();
    const events: any[] = [];

    // Scheduled/failed content from the videos collection (canonical publish state)
    const videosSnap = await db.collection('videos')
      .where('status', 'in', ['scheduled', 'uploaded', 'upload_failed', 'processing', 'generating'])
      .orderBy('publish_at', 'asc')
      .limit(300)
      .get();

    for (const doc of videosSnap.docs) {
      const d = doc.data();
      const scheduledTime = d.publish_at || d.created_at || '';
      if (!scheduledTime) continue;
      events.push({
        id: doc.id,
        title: d.title || 'Untitled video',
        scheduledTime,
        status: d.status === 'uploaded' ? 'published' : d.status,
        format: d.format || 'short',
        thumbnailUrl: d.youtube_url || '',
      });
    }

    // Pending plan slots from the content_plan collection
    const planSnap = await db.collection('content_plan')
      .where('status', 'in', ['planned', 'scheduled', 'pending'])
      .orderBy('scheduled_at', 'asc')
      .limit(300)
      .get();

    for (const doc of planSnap.docs) {
      const d = doc.data();
      const scheduledTime = d.scheduled_at?.toDate?.()?.toISOString() || d.scheduled_at || '';
      if (!scheduledTime) continue;
      if (events.some((e) => e.title === (d.title || ''))) continue;
      events.push({
        id: doc.id,
        title: d.title || 'Content Slot',
        scheduledTime,
        status: 'scheduled',
        format: d.format === 'long' ? 'long' : 'shorts',
      });
    }

    events.sort((a, b) => new Date(a.scheduledTime).getTime() - new Date(b.scheduledTime).getTime());

    return NextResponse.json({ events });
  } catch (error: any) {
    console.error('[CONTENT-CALENDAR API] Error:', error?.message || error);
    return NextResponse.json({ events: [], note: 'Error reading Firestore' });
  }
}
