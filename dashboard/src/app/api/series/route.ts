import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';
import { FieldValue } from 'firebase-admin/firestore';

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const db = getAdminFirestore();
    const snapshot = await db.collection('series').orderBy('created_at', 'desc').get();

    const series = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    return NextResponse.json({ success: true, series });
  } catch (error: any) {
    console.error('[SERIES API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const body = await request.json();
    const { name, description, category, youtube_playlist_link, auto_generated } = body;

    if (!name || !category) {
      return NextResponse.json({ success: false, error: 'Name and category are required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    const seriesData = {
      name,
      description: description || '',
      category,
      youtube_playlist_link: youtube_playlist_link || '',
      auto_generated: auto_generated || false,
      created_at: FieldValue.serverTimestamp(),
      updated_at: FieldValue.serverTimestamp(),
    };

    const docRef = await db.collection('series').add(seriesData);
    return NextResponse.json({ success: true, id: docRef.id });
  } catch (error: any) {
    console.error('[SERIES API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function PUT(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const body = await request.json();
    const { id, ...data } = body;
    if (!id) {
      return NextResponse.json({ success: false, error: 'Series id is required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    data.updated_at = FieldValue.serverTimestamp();
    await db.collection('series').doc(id).update(data);
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[SERIES API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function DELETE(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

    const { searchParams } = new URL(request.url);
    const id = searchParams.get('id');
    if (!id) {
      return NextResponse.json({ success: false, error: 'Series id is required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    await db.collection('series').doc(id).delete();
    return NextResponse.json({ success: true });
  } catch (error: any) {
    console.error('[SERIES API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
