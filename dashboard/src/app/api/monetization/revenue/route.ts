import { NextResponse } from 'next/server';
import { getAdminFirestore } from '@/lib/firebase-admin';
import { requireUser } from '@/lib/api-auth';

export async function GET(request: Request) {
  try {
    const auth = await requireUser(request);
    if (!auth.ok) return auth.response;

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
