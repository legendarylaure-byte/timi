import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    agents: [
      { id: 'scriptwriter', name: 'Scriptwriter', status: 'idle', task: null },
      { id: 'storyboard', name: 'Storyboard Artist', status: 'idle', task: null },
      { id: 'voice', name: 'Voice Actor', status: 'idle', task: null },
      { id: 'composer', name: 'Composer', status: 'idle', task: null },
      { id: 'animator', name: 'Animator', status: 'idle', task: null },
      { id: 'editor', name: 'Video Editor', status: 'idle', task: null },
      { id: 'thumbnail', name: 'Thumbnail Creator', status: 'idle', task: null },
      { id: 'metadata', name: 'Metadata Writer', status: 'idle', task: null },
      { id: 'publisher', name: 'Publisher', status: 'idle', task: null },
    ],
  });
}

export async function POST(request: Request) {
  try {
    const { agentId, action } = await request.json();
    return NextResponse.json({ success: true, agentId, action });
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid request' }, { status: 400 });
  }
}
