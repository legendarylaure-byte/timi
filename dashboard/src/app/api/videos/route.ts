import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({
    videos: [],
    total: 0,
    today: { shorts: 0, long: 0 },
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    return NextResponse.json({ success: true, videoId: Date.now().toString(), ...body });
  } catch {
    return NextResponse.json({ success: false, message: 'Invalid request' }, { status: 400 });
  }
}
