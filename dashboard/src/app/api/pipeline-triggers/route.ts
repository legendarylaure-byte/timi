import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { Timestamp } from 'firebase-admin/firestore';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { topic, category, format, publish_at } = body;

    if (!topic || !category || !format) {
      return NextResponse.json(
        { success: false, error: 'Missing required fields: topic, category, format' },
        { status: 400 },
      );
    }

    const db = getAdminFirestore();
    const doc = await db.collection('pipeline_triggers').add({
      topic,
      category,
      format,
      status: 'pending',
      publish_at: publish_at || null,
      created_at: Timestamp.now(),
    });

    return NextResponse.json({
      success: true,
      id: doc.id,
      message: `Triggered ${format}: "${topic}"`,
    });
  } catch (error: any) {
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 },
    );
  }
}
