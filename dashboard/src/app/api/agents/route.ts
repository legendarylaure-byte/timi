import { NextResponse } from 'next/server';
import { getAdminFirestore, getAdminAuth } from '@/lib/firebase-admin';
import { rateLimitMiddleware } from '@/lib/rate-limit';

import { requireUser } from '@/lib/api-auth';

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

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;
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
  const rateLimitResponse = rateLimitMiddleware(request, 20);
  if (rateLimitResponse) return rateLimitResponse;

  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;
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
