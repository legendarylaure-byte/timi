import { NextResponse } from 'next/server';

const AGENTS_DIR = process.env.AGENTS_DIR || '';

export async function GET() {
  try {
    if (!AGENTS_DIR) {
      return NextResponse.json({ events: [], note: 'AGENTS_DIR not configured' });
    }

    const fs = await import('fs');
    const path = await import('path');

    const planPath = path.join(AGENTS_DIR, 'data', 'plans', 'content_plan.json');
    const trackingPath = path.join(AGENTS_DIR, 'data', 'plans', 'pipeline_tracking.json');

    const events: any[] = [];

    // Load pipeline tracking for scheduled/published content
    if (fs.existsSync(trackingPath)) {
      const tracking = JSON.parse(fs.readFileSync(trackingPath, 'utf-8'));
      if (Array.isArray(tracking)) {
        for (const item of tracking) {
          if (item.video_id) {
            events.push({
              id: item.video_id,
              title: item.title || item.topic || 'Untitled',
              scheduledTime: item.scheduled_time || item.created_at || new Date().toISOString(),
              status: item.status || 'pending',
              format: item.format || 'short',
            });
          }
        }
      }
    }

    // Load content plan for scheduled items
    if (fs.existsSync(planPath)) {
      const plan = JSON.parse(fs.readFileSync(planPath, 'utf-8'));
      const items = plan.items || plan.slots || plan.plan || [];
      if (Array.isArray(items)) {
        for (const item of items) {
          if (item.scheduled_time || item.time) {
            const existing = events.find(e => e.title === (item.title || item.topic));
            if (!existing) {
              events.push({
                id: item.id || `plan_${Math.random().toString(36).slice(2, 8)}`,
                title: item.title || item.topic || 'Content Slot',
                scheduledTime: item.scheduled_time || item.time,
                status: item.status || 'scheduled',
                format: item.format || 'short',
              });
            }
          }
        }
      }
    }

    // Sort by time
    events.sort((a, b) => new Date(a.scheduledTime).getTime() - new Date(b.scheduledTime).getTime());

    return NextResponse.json({ events });
  } catch {
    return NextResponse.json({ events: [] });
  }
}
