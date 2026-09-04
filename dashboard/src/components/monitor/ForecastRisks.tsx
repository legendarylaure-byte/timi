'use client';

import { Card } from '@/components/ui/Card';
import { ShieldAlert } from 'lucide-react';
import { LivePayload, ReviewPayload } from '@/lib/monitor';

interface ForecastRisksProps {
  live: LivePayload | null;
  review: ReviewPayload | null;
}

export function ForecastRisks({ live, review }: ForecastRisksProps) {
  const hb = live?.heartbeat;
  const disk = hb?.disk_percent ?? null;
  const mem = hb?.memory_percent ?? null;

  const risks: Array<{ label: string; level: 'ok' | 'warn' | 'bad'; detail: string }> = [];

  if (disk == null) risks.push({ label: 'Disk space', level: 'warn', detail: 'Unknown — heartbeat not reporting.' });
  else if (disk >= 85) risks.push({ label: 'Disk space', level: 'bad', detail: `${Math.round(disk)}% full — cleanup needed soon.` });
  else risks.push({ label: 'Disk space', level: 'ok', detail: `Healthy at ${Math.round(disk)}% full.` });

  if (mem != null && mem >= 90) risks.push({ label: 'Memory pressure', level: 'bad', detail: `${Math.round(mem)}% — Ollama or compositor may be starved.` });
  else if (mem != null && mem >= 75) risks.push({ label: 'Memory pressure', level: 'warn', detail: `${Math.round(mem)}% — watch for slowdowns during render.` });
  else risks.push({ label: 'Memory pressure', level: 'ok', detail: `Fine (${mem == null ? '—' : Math.round(mem) + '%'}).` });

  const failRate = review?.pipeline.total_runs ? Math.round((1 - review.pipeline.success_rate / 100) * 100) : 0;
  if (failRate >= 40) risks.push({ label: 'Pipeline reliability', level: 'bad', detail: `${failRate}% recent runs failed — worth a review.` });
  else if (failRate >= 15) risks.push({ label: 'Pipeline reliability', level: 'warn', detail: `${failRate}% recent runs failed.` });
  else risks.push({ label: 'Pipeline reliability', level: 'ok', detail: `${failRate}% recent failures — stable.` });

  const bar = (v: number | null | undefined) => (v == null ? 0 : Math.min(100, Math.max(0, v)));

  return (
    <Card icon={ShieldAlert} iconColor="text-light-warning dark:text-dark-warning" className="h-full">
      <h3 className="text-sm font-bold text-light-text dark:text-dark-text mb-4">Forecast &amp; Risks</h3>
      <div className="space-y-3">
        {risks.map((r) => (
          <div key={r.label} className="flex items-start gap-2.5">
            <span className={`w-2.5 h-2.5 rounded-full mt-0.5 shrink-0 ${r.level === 'ok' ? 'bg-emerald-500' : r.level === 'warn' ? 'bg-amber-500' : 'bg-red-500'}`} />
            <div className="flex-1">
              <p className="text-xs font-medium text-light-text dark:text-dark-text">{r.label}</p>
              <p className="text-[11px] text-light-muted dark:text-dark-muted">{r.detail}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 pt-3 border-t border-light-border/40 dark:border-dark-border/40">
        <p className="text-[11px] font-bold text-light-muted dark:text-dark-muted mb-2">Resource snapshot</p>
        <div className="grid grid-cols-2 gap-2">
          <div className="text-center rounded-lg bg-light-bg/60 dark:bg-dark-bg/60 border border-light-border/30 dark:border-dark-border/30 p-2 text-xs">
            <p className="font-bold text-light-text dark:text-dark-text">{bar(disk)}%</p><p className="text-[10px] text-light-muted dark:text-dark-muted">Disk</p>
          </div>
          <div className="text-center rounded-lg bg-light-bg/60 dark:bg-dark-bg/60 border border-light-border/30 dark:border-dark-border/30 p-2 text-xs">
            <p className="font-bold text-light-text dark:text-dark-text">{bar(mem)}%</p><p className="text-[10px] text-light-muted dark:text-dark-muted">Memory</p>
          </div>
        </div>
      </div>
    </Card>
  );
}