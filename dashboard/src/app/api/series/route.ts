import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { FieldValue } from 'firebase-admin/firestore';

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

const CHARACTER_NAMES = ['pixel', 'nova', 'ziggy', 'boop', 'sprout'] as const;
const BACKGROUNDS = ['gradient_sky', 'gradient_forest', 'gradient_ocean', 'gradient_space', 'gradient_sunset', 'gradient_night', 'gradient_garden', 'gradient_classroom', 'gradient_bedroom', 'gradient_underwater'] as const;
const POSES = ['idle', 'happy', 'wave', 'point', 'surprised', 'thinking', 'sleep', 'dance', 'growing', 'sad'] as const;
const MOODS = ['happy', 'calm', 'adventure', 'dreamy', 'playful', 'exciting'] as const;

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const db = getAdminFirestore();
    const snapshot = await db.collection('series').get();

    const series = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    return NextResponse.json({ success: true, series });
  } catch (error: any) {
    console.error('[SERIES API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();
    const { name, description, host, intro_text, outro_text, background, music_mood } = body;

    if (!name || !host) {
      return NextResponse.json({ success: false, error: 'Name and host are required' }, { status: 400 });
    }

    const db = getAdminFirestore();
    const seriesData = {
      name,
      description: description || '',
      host: host.toLowerCase(),
      host_pose: body.host_pose || 'wave',
      host_expression: body.host_expression || 'happy',
      intro_duration: body.intro_duration || 3.0,
      outro_duration: body.outro_duration || 3.0,
      categories: body.categories || [],
      character_placement: body.character_placement || { x: 0.5, y: 0.55 },
      intro_text: intro_text || `Welcome to ${name}!`,
      outro_text: outro_text || 'See you next time!',
      background: background || 'gradient_sky',
      music_mood: music_mood || 'happy',
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
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

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
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }

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
