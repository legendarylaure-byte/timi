'use client';

import { Card } from '@/components/ui/Card';
import { TrendingUp } from 'lucide-react';
import { ReviewPayload } from '@/lib/monitor';

const SUBS_TARGET = 1000;
const HOURS_TARGET = 4000;

function spark(values: number[], color: string) {
  if (!values || values.length < 2) return null;
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * 100;
    const y = 28 - ((v - min) / range) * 24;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="w-full h-8">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function GrowthView({ data }: { data: ReviewPayload | null }) {
  const subs = data?.channel.subscribers ?? 0;
  const hours = data?.channel.total_watch_hours ?? 0;
  const subsPct = Math.min(100, (subs / SUBS_TARGET) * 100);
  const hoursPct = Math.min(100, (hours / HOURS_TARGET) * 100);

  const viewsTrend: number[] = (data?.videos.slice().reverse() || []).map((v) => v.views);

  return (
    <Card icon={TrendingUp} iconColor="text-light-success dark:text-dark-success" className="h-full">
      <h3 className="text-sm font-bold text-light-text dark:text-dark-text mb-4">Growth to Monetization</h3>

      <div className="space-y-4">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-light-muted dark:text-dark-muted">Subscribers</span>
            <span className="font-bold text-light-text dark:text-dark-text">{subs} / {SUBS_TARGET}</span>
          </div>
          <div className="w-full h-2.5 rounded-full bg-light-border/40 dark:bg-dark-border/40 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-light-primary to-light-secondary transition-all duration-700" style={{ width: `${subsPct}%` }} />
          </div>
          <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">{SUBS_TARGET - subs} to go</p>
        </div>

        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-light-muted dark:text-dark-muted">Watch hours</span>
            <span className="font-bold text-light-text dark:text-dark-text">{Math.round(hours)} / {HOURS_TARGET}</span>
          </div>
          <div className="w-full h-2.5 rounded-full bg-light-border/40 dark:bg-dark-border/40 overflow-hidden">
            <div className="h-full rounded-full bg-gradient-to-r from-light-success to-light-info transition-all duration-700" style={{ width: `${hoursPct}%` }} />
          </div>
          <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">{Math.round(HOURS_TARGET - hours)} hours to go</p>
        </div>

        <div className="pt-2 border-t border-light-border/40 dark:border-dark-border/40 space-y-1">
          <p className="text-[11px] font-bold text-light-muted dark:text-dark-muted">Views trend (recent videos)</p>
          {spark(viewsTrend, '#EC133E')}
          <p className="text-[10px] text-light-muted/60 dark:text-dark-muted/60">Total views: {data?.channel.total_views ?? 0}</p>
        </div>
      </div>
    </Card>
  );
}