import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const { action, data } = await request.json();

    return NextResponse.json({
      success: true,
      message: `Auth action "${action}" processed`,
      data,
    });
  } catch (error) {
    return NextResponse.json(
      { success: false, message: 'Authentication error' },
      { status: 500 }
    );
  }
}
