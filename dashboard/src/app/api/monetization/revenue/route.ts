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

export async function GET(request: Request) {
  try {
    const user = await verifyAuth(request);
    if (!user) {
      return NextResponse.json(
        { success: false, error: 'Unauthorized' },
        { status: 401 }
      );
    }

    const db = getAdminFirestore();
    const doc = await db.collection('monetization').doc('revenue').get();

    if (!doc.exists) {
      return NextResponse.json({
        success: true,
        revenue: null,
        message: 'No revenue data available yet. The daily revenue pipeline will populate this after analytics are collected.',
      });
    }

    const data = doc.data()!;

    const revenue = {
      totalRevenue: data.totalRevenue || 0,
      currentMonth: data.currentMonth || 0,
      lastMonth: data.lastMonth || 0,
      rpm: data.rpm || 0,
      cpm: data.cpm || 0,
      estimatedYearly: data.estimatedYearly || 0,
      dailyRevenue: data.dailyRevenue || [],
      platformBreakdown: data.platformBreakdown || [],
      dataSource: data.dataSource || 'estimated',
      lastUpdated: data.lastUpdated || null,
    };

    return NextResponse.json({ success: true, revenue });
  } catch (error: any) {
    console.error('[REVENUE API] Error:', error);
    return NextResponse.json(
      { success: false, error: error.message },
      { status: 500 }
    );
  }
}
