import { NextResponse } from 'next/server';
import { requireUser } from '@/lib/api-auth';
import { getAdminFirestore } from '@/lib/firebase-admin';

export async function GET(request: Request) {
  const auth = await requireUser(request);
  if (!auth.ok) return auth.response;

  try {
    const db = getAdminFirestore();

    const configDoc = await db.collection('viral_news_config').doc('settings').get();
    const rawConfig = configDoc.exists ? configDoc.data() : {};
    const config: Record<string, any> = rawConfig || {};

    const today = new Date().toISOString().slice(0, 10);
    const activitySnap = await db.collection('viral_news_activity')
      .where('timestamp', '>=', `${today}T00:00:00`)
      .limit(200)
      .get();

    let lastCheck: string | null = null;
    let scans = 0;
    let highestScore = 0;
    let articlesScanned = 0;
    let errorsToday = 0;
    activitySnap.docs.forEach(d => {
      const a = d.data();
      const ts = a.timestamp || '';
      if (a.event === 'scan_complete') {
        scans++;
        const checked = a.details?.checked || 0;
        articlesScanned += checked;
        const score = a.details?.highest_score || 0;
        if (score > highestScore) highestScore = score;
      } else if (a.event === 'error') {
        errorsToday++;
      }
      if (ts > (lastCheck || '')) lastCheck = ts;
    });

    const postsSnap = await db.collection('viral_news_posts')
      .where('date', '>=', today).get();

    return NextResponse.json({
      active: config.active !== false,
      last_check: lastCheck,
      posts_today: postsSnap.docs.length,
      scans_today: scans,
      articles_scanned_today: articlesScanned,
      errors_today: errorsToday,
      highest_score_today: highestScore,
      viral_threshold: config.viral_threshold ?? 60,
      hold_threshold: config.viral_hold_threshold ?? 45,
      max_per_day: config.viral_max_per_day ?? 2,
      cooldown_hours: config.viral_cooldown_hours ?? 6,
      check_interval_minutes: 5,
    });
  } catch (error: any) {
    return NextResponse.json(
      { error: error.message || 'Failed to fetch status' },
      { status: 500 },
    );
  }
}