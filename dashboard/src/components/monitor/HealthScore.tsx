'use client';

import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';
import { Activity } from 'lucide-react';
import { healthColor, healthLabel } from '@/lib/monitor';

interface HealthScoreProps {
  successRate: number;
  heartbeatLive: boolean;
  videoTrendGood: boolean;
}

export function HealthScore({ successRate, heartbeatLive, videoTrendGood }: HealthScoreProps) {
  let score = Math.round(successRate * 0.5);
  if (heartbeatLive) score += 20;
  if (videoTrendGood) score += 15;
  score = Math.max(0, Math.min(100, score + 10));

  const color = healthColor(score);
  const label = healthLabel(score);

  return (
    <Card icon={Activity} iconColor="text-light-primary dark:text-dark-primary" iconBgClass="bg-light-primary/10 dark:bg-dark-primary/10" className="h-full">
      <div className="flex items-center gap-5">
        <div className="relative w-28 h-28 shrink-0">
          <svg viewBox="0 0 120 120" className="w-full h-full -rotate-90">
            <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" className="text-light-border/40 dark:text-dark-border/40" strokeWidth="12" />
            <motion.circle
              cx="60" cy="60" r="52" fill="none"
              stroke={color} strokeWidth="12" strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 52}
              initial={{ strokeDashoffset: 2 * Math.PI * 52 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 52 * (1 - score / 100) }}
              transition={{ duration: 1 }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold" style={{ color }}>{score}</span>
            <span className="text-[9px] uppercase tracking-widest text-light-muted dark:text-dark-muted">health</span>
          </div>
        </div>
        <div className="space-y-1">
          <h3 className="text-sm font-bold gradient-text">Mission Health</h3>
          <p className="text-xs font-medium" style={{ color }}>
            {label}
          </p>
          <p className="text-[11px] text-light-muted dark:text-dark-muted leading-relaxed">
            {heartbeatLive
              ? 'Pipeline is alive and reporting.'
              : 'Pipeline heartbeat is down or stale.'}
          </p>
        </div>
      </div>
      <div className="mt-4 pt-4 border-t border-light-border/40 dark:border-dark-border/40 space-y-1.5 text-[11px] text-light-muted dark:text-dark-muted">
        <div className="flex justify-between"><span>Pipeline success rate</span><span className="font-medium" style={{ color: healthColor(successRate) }}>{successRate}%</span></div>
        <div className="flex justify-between"><span>Heartbeat</span><span className={heartbeatLive ? 'text-emerald-500' : 'text-red-500'}>{heartbeatLive ? 'Live' : 'Down'}</span></div>
        <div className="flex justify-between"><span>Performance trend</span><span className={videoTrendGood ? 'text-emerald-500' : 'text-light-muted'}>{videoTrendGood ? 'Improving' : 'Mixed'}</span></div>
      </div>
    </Card>
  );
}