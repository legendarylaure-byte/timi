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

const AGENT_LABELS: Record<string, string> = {
  scriptwriter: 'Scriptwriter',
  storyboard: 'Storyboard Artist',
  voice: 'Voice Actor',
  composer: 'Composer',
  animator: 'Animator',
  editor: 'Video Editor',
  thumbnail: 'Thumbnail Creator',
  metadata: 'Metadata Writer',
  publisher: 'Publisher',
};

export async function GET() {
  try {
    const db = getAdminFirestore();
    const snapshot = await db.collection('agent_status').get();
    const agents = AGENT_LABELS;
    const agentList = Object.entries(agents).map(([id, name]) => {
      const doc = snapshot.docs.find(d => d.id === id);
      if (doc?.exists) {
        const data = doc.data();
        return { id, name, status: data.status || 'idle', task: data.current_action || null };
      }
      return { id, name, status: 'idle', task: null };
    });
    return NextResponse.json({ agents: agentList });
  } catch (error: any) {
    console.error('[AGENTS API] Error:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json({ success: false, error: 'Unauthorized' }, { status: 401 });
    }
    const { agentId, action } = await request.json();
    if (!agentId || !action) {
      return NextResponse.json({ success: false, message: 'Missing agentId or action' }, { status: 400 });
    }
    if (action === 'pause' || action === 'resume') {
      const db = getAdminFirestore();
      const enabled = action === 'resume';
      await db.collection('agent_status').doc(agentId).set({ enabled }, { merge: true });
    }
    return NextResponse.json({ success: true, agentId, action });
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid request' }, { status: 400 });
  }
}
