import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';

export async function POST(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  return NextResponse.json({
    success: true,
    message: 'Cleanup endpoint active — no legacy patterns configured',
  });
}
