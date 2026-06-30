'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { doc, onSnapshot } from 'firebase/firestore';
import { calcTimeRemaining, formatNPT } from '@/lib/constants';
import type { TimeRemaining } from '@/lib/constants';

export function NextUploadTimer() {
  const [remaining, setRemaining] = useState<TimeRemaining>(calcTimeRemaining());
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [pipelinePaused, setPipelinePaused] = useState(false);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) {
        const data = snap.data();
        setPipelineRunning(data.running || false);
        setPipelinePaused(data.paused_by_user || false);
      }
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const timer = setInterval(() => {
      setRemaining(calcTimeRemaining());
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const nextNPT = new Date(Date.now() + remaining.totalSeconds * 1000);
  const nextTimeFormatted = formatNPT(nextNPT);

  const pad = (n: number) => n.toString().padStart(2, '0');

  return (
    <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 glass-warm p-4 glow-red">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold gradient-text flex items-center gap-1.5" title="Countdown to your next scheduled video upload — the daily run happens at 11:45 AM Nepal time">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Next Upload
        </h3>
        <span className="text-[10px] text-light-muted dark:text-dark-muted">
          Asia/Kathmandu
        </span>
      </div>

      {pipelineRunning ? (
        <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          Pipeline active — upload pending
        </div>
      ) : pipelinePaused ? (
        <div className="flex items-center gap-2 text-sm text-amber-500">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Pipeline paused
        </div>
      ) : (
        <div className="flex items-baseline gap-1.5">
          <motion.div
            key={`${remaining.hours}-${remaining.minutes}-${remaining.seconds}`}
            initial={{ scale: 1.1, opacity: 0.6 }}
            animate={{ scale: 1, opacity: 1 }}
            className="text-2xl font-bold font-mono text-light-text dark:text-dark-text tabular-nums tracking-tight"
          >
            {pad(remaining.hours)}:{pad(remaining.minutes)}:{pad(remaining.seconds)}
          </motion.div>
          <span className="text-xs text-light-muted dark:text-dark-muted">
            until {nextTimeFormatted} NPT
          </span>
        </div>
      )}

      <div className="mt-3 pt-3 border-t border-light-border/50 dark:border-dark-border/50">
        <p className="text-[10px] text-light-muted/60 dark:text-dark-muted/60">
          Daily schedule runs at <strong className="text-light-text dark:text-dark-text">06:00 UTC</strong> (11:45 AM NPT)
        </p>
      </div>
    </div>
  );
}
