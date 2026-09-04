'use client';

import { Card } from '@/components/ui/Card';
import { Gauge } from 'lucide-react';
import { LivePayload } from '@/lib/monitor';

function pctColor(v: number | null | undefined): string {
  if (v == null) return '#9CA3AF';
  if (v >= 90) return '#EF4444';
  if (v >= 75) return '#F59E0B';
  return '#10B981';
}

function bar(v: number | null | undefined, label: string) {
  const pct = v == null ? 0 : Math.min(100, Math.max(0, v));
  const color = pctColor(v);
  return (
    <div>
      <div className="flex justify-between text-[11px] mb-1">
        <span className="text-light-muted dark:text-dark-muted">{label}</span>
        <span className="font-medium" style={{ color }}>{v == null ? '—' : `${Math.round(pct)}%`}</span>
      </div>
      <div className="w-full h-2 rounded-full bg-light-border/40 dark:bg-dark-border/40 overflow-hidden">
        <div className="h-full rounded-full transition-all duration-700" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

export function ResourceHealth({ live }: { live: LivePayload | null }) {
  const hb = live?.heartbeat;
  return (
    <Card icon={Gauge} iconColor="text-light-info dark:text-dark-info">
      <h3 className="text-sm font-bold text-light-text dark:text-dark-text mb-4">Machine Health</h3>
      <div className="space-y-4">
        {bar(hb?.cpu_percent, 'CPU')}
        {bar(hb?.memory_percent, 'Memory')}
        {bar(hb?.disk_percent, 'Disk')}
      </div>
      <div className="mt-4 pt-4 border-t border-light-border/40 dark:border-dark-border/40 flex items-center justify-between text-xs">
        <span className="text-light-muted dark:text-dark-muted">Pipeline heartbeat</span>
        <span className={`inline-flex items-center gap-1.5 font-medium ${hb?.status === 'fresh' ? 'text-emerald-500' : hb?.status === 'stale' ? 'text-amber-500' : 'text-red-500'}`}>
          <span className={`w-2 h-2 rounded-full ${hb?.status === 'fresh' ? 'bg-emerald-500' : hb?.status === 'stale' ? 'bg-amber-500' : 'bg-red-500'} ${hb?.status === 'fresh' ? 'animate-pulse' : ''}`} />
          {hb?.status === 'fresh' ? 'Live' : hb?.status === 'stale' ? 'Stale' : hb?.status === 'dead' ? 'Down' : 'Never seen'}
        </span>
      </div>
      {hb?.ollama_available != null && (
        <div className="mt-2 flex items-center justify-between text-xs">
          <span className="text-light-muted dark:text-dark-muted">Local AI (Ollama)</span>
          <span className={hb.ollama_available ? 'text-emerald-500' : 'text-red-500'}>{hb.ollama_available ? 'Ready' : 'Unavailable'}</span>
        </div>
      )}
    </Card>
  );
}