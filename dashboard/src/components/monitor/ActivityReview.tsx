'use client';

import { Card } from '@/components/ui/Card';
import { BarChart3, AlertTriangle, Flame, Snowflake } from 'lucide-react';
import { ReviewPayload, ReviewVideo } from '@/lib/monitor';

function classify(v: ReviewVideo): 'hot' | 'cold' | 'steady' {
  const predicted = v.predicted_views_7d || v.predicted_views_30d;
  if (!predicted) return 'steady';
  if (v.views >= predicted * 1.1) return 'hot';
  if (predicted > 0 && v.views < predicted * 0.5) return 'cold';
  return 'steady';
}

function timeAgo(iso: string | null): string {
  if (!iso) return '—';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (diff < 1) return 'just now';
  if (diff < 60) return `${diff}m ago`;
  return `${Math.floor(diff / 60)}h ago`;
}

const HOT = { color: '#EF4444', label: 'Hot', Icon: Flame };
const COLD = { color: '#60A5FA', label: 'Cold', Icon: Snowflake };
const STEADY = { color: '#F59E0B', label: 'Steady', Icon: BarChart3 };

export function ActivityReview({ data }: { data: ReviewPayload | null }) {
  const hot = data?.videos.filter((v) => classify(v) === 'hot') || [];
  const cold = data?.videos.filter((v) => classify(v) === 'cold') || [];

  const videoRow = (v: ReviewVideo) => {
    const c = classify(v);
    const meta = c === 'hot' ? HOT : c === 'cold' ? COLD : STEADY;
    const MetaIcon = meta.Icon;
    return (
      <div key={v.id} className="flex items-center gap-3 py-2 border-b border-light-border/30 dark:border-dark-border/30 last:border-0">
        <MetaIcon className="w-4 h-4 shrink-0" style={{ color: meta.color }} />
        <div className="flex-1 min-w-0">
          <p className="text-xs font-medium text-light-text dark:text-dark-text truncate">{v.title || 'Untitled'}</p>
          <p className="text-[10px] text-light-muted dark:text-dark-muted truncate">{v.format} · {v.status}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs font-bold text-light-text dark:text-dark-text">{v.views}</p>
          <p className="text-[10px] text-light-muted dark:text-dark-muted">views</p>
        </div>
      </div>
    );
  };

  return (
    <Card icon={BarChart3} iconColor="text-light-primary dark:text-dark-primary">
      <h3 className="text-sm font-bold text-light-text dark:text-dark-text mb-1">Performance Review</h3>
      <p className="text-[11px] text-light-muted dark:text-dark-muted mb-4">
        Last {data?.videos.length || 0} videos · what&apos;s catching (hot) vs missing (cold) vs predicted
      </p>

      <div className="grid grid-cols-3 gap-2 mb-4">
        {[
          { label: 'Runs', value: data?.pipeline.total_runs ?? 0 },
          { label: 'Success', value: `${data?.pipeline.success_rate ?? 0}%` },
          { label: 'Avg time', value: data?.pipeline.avg_duration_sec ? `${Math.round((data?.pipeline.avg_duration_sec ?? 0) / 60)}m` : '—' },
        ].map((s) => (
          <div key={s.label} className="rounded-xl bg-light-bg/60 dark:bg-dark-bg/60 border border-light-border/30 dark:border-dark-border/30 p-2.5 text-center">
            <p className="text-lg font-bold text-light-text dark:text-dark-text">{s.value}</p>
            <p className="text-[10px] text-light-muted dark:text-dark-muted">{s.label}</p>
          </div>
        ))}
      </div>

      <div className="mb-4">
        <div className="flex items-center gap-1.5 mb-2">
          <Snowflake className="w-3.5 h-3.5 text-blue-400" />
          <span className="text-[11px] font-bold text-light-text dark:text-dark-text">Underperformers</span>
        </div>
        {cold.length === 0 && <p className="text-[11px] text-light-muted dark:text-dark-muted italic">None recently — nice.</p>}
        {cold.length > 0 && <div>{cold.slice(0, 5).map(videoRow)}</div>}
      </div>

      <div>
        <div className="flex items-center gap-1.5 mb-2">
          <Flame className="w-3.5 h-3.5 text-red-500" />
          <span className="text-[11px] font-bold text-light-text dark:text-dark-text">Hot / catching</span>
        </div>
        {hot.length === 0 && <p className="text-[11px] text-light-muted dark:text-dark-muted italic">Nothing catching yet.</p>}
        {hot.length > 0 && <div>{hot.slice(0, 5).map(videoRow)}</div>}
      </div>

      {data?.pipeline.last_failures && data.pipeline.last_failures.length > 0 && (
        <div className="mt-4 pt-3 border-t border-light-border/40 dark:border-dark-border/40">
          <div className="flex items-center gap-1.5 mb-2">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
            <span className="text-[11px] font-bold text-light-text dark:text-dark-text">Recent failures</span>
          </div>
          <div className="space-y-1">
            {data.pipeline.last_failures.slice(0, 5).map((f, i) => (
              <div key={i} className="flex justify-between text-[11px]">
                <span className="text-light-muted dark:text-dark-muted truncate">{f.topic || 'unknown'} ({f.format})</span>
                <span className="text-light-muted/60 dark:text-dark-muted/60 shrink-0 ml-2">{timeAgo(f.created_at)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}