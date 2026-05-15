'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { auth } from '@/lib/firebase';

interface SchedulerStatus {
  running: boolean;
  last_run: string | null;
  next_run: string | null;
  pid: number | null;
  uptime_minutes: number;
}

interface PlanItem {
  id: string;
  title: string;
  category: string;
  format: string;
  scheduled_at: string | null;
  status: string;
}

interface PendingTrigger {
  id: string;
  type: string;
  topic: string;
  format: string;
  created_at: string | null;
}

export default function SchedulerPage() {
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [plan, setPlan] = useState<PlanItem[]>([]);
  const [pendingTriggers, setPendingTriggers] = useState<PendingTrigger[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [topic, setTopic] = useState('');
  const [format, setFormat] = useState<'shorts' | 'long'>('shorts');
  const [category, setCategory] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [triggering, setTriggering] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch('/api/scheduler', { headers });
      const data = await res.json();

      if (data.success) {
        setScheduler(data.scheduler);
        setPlan(data.plan);
        setPendingTriggers(data.pending_triggers);
      } else {
        setError(data.error || 'Failed to load scheduler data');
      }
    } catch (e) {
      console.error('[SCHEDULER] Failed to load:', e);
      setError('Failed to load scheduler data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAction = async (action: 'trigger' | 'pause' | 'resume') => {
    try {
      if (action === 'trigger') setTriggering(true);
      else setSubmitting(true);

      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const body: any = { action };
      if (action === 'trigger') {
        if (topic) body.topic = topic;
        if (format) body.format = format;
        if (category) body.category = category;
      }

      const res = await fetch('/api/scheduler', {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (data.success) {
        await loadData();
        if (action === 'trigger') {
          setTopic('');
          setCategory('');
        }
      } else {
        console.error('[SCHEDULER] Action failed:', data.message);
      }
    } catch (e) {
      console.error('[SCHEDULER] Action error:', e);
    } finally {
      setSubmitting(false);
      setTriggering(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="text-3xl">⏰</motion.div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center">
            <span className="text-2xl">⏰</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Scheduler</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Manage content scheduling and automated publishing</p>
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative rounded-2xl overflow-hidden glass-strong border border-red-500/30 p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button onClick={loadData} className="mt-3 px-4 py-2 rounded-lg bg-gradient-to-r from-purple-500 to-blue-500 text-white text-sm font-medium">Retry</button>
        </motion.div>
      )}

      {/* Scheduler Status */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${scheduler?.running ? 'bg-green-400 shadow-[0_0_8px_rgba(74,222,128,0.6)]' : 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]'}`} />
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text">
              Scheduler {scheduler?.running ? 'Running' : 'Stopped'}
            </h2>
          </div>
          {scheduler && (
            <button
              onClick={() => handleAction(scheduler.running ? 'pause' : 'resume')}
              disabled={submitting}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                scheduler.running
                  ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 hover:bg-yellow-500/30'
                  : 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:opacity-90'
              } disabled:opacity-50`}
            >
              {submitting ? '...' : scheduler.running ? 'Pause' : 'Resume'}
            </button>
          )}
        </div>
        {scheduler && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { label: 'Last Run', value: scheduler.last_run ? new Date(scheduler.last_run).toLocaleString() : '—' },
              { label: 'Next Run', value: scheduler.next_run ? new Date(scheduler.next_run).toLocaleString() : '—' },
              { label: 'PID', value: scheduler.pid ?? '—' },
              { label: 'Uptime', value: scheduler.uptime_minutes > 0 ? `${scheduler.uptime_minutes}m` : '—' },
            ].map(stat => (
              <div key={stat.label} className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
                <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
                <p className="text-sm font-semibold text-light-text dark:text-dark-text mt-1">{stat.value}</p>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* Manual Trigger Form */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Manual Trigger</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Topic (optional)</label>
            <input
              type="text"
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="e.g., The Solar System"
              className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Format</label>
            <div className="flex gap-2">
              {(['shorts', 'long'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-medium transition-all ${
                    format === f
                      ? 'bg-gradient-to-r from-blue-500 to-cyan-500 text-white shadow-lg'
                      : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-muted dark:text-dark-muted'
                  }`}
                >
                  {f === 'shorts' ? 'Shorts' : 'Long'}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Category (optional)</label>
            <input
              type="text"
              value={category}
              onChange={e => setCategory(e.target.value)}
              placeholder="e.g., Self-Learning"
              className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            />
          </div>
        </div>
        <button
          onClick={() => handleAction('trigger')}
          disabled={triggering}
          className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-blue-500 to-cyan-500 text-white font-semibold text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
        >
          {triggering ? 'Triggering...' : 'Trigger Content Generation'}
        </button>
      </motion.div>

      {/* Content Plan */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Content Plan ({plan.length})</h2>
        {plan.length === 0 ? (
          <p className="text-center text-light-muted dark:text-dark-muted py-8">No planned content yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-light-border/30 dark:border-white/5">
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Title</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Category</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Format</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Scheduled</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {plan.map(item => (
                  <tr key={item.id} className="border-b border-light-border/20 dark:border-white/5 hover:bg-light-bg/30 dark:hover:bg-dark-bg/30">
                    <td className="py-2.5 px-3 text-light-text dark:text-dark-text font-medium truncate max-w-[250px]">{item.title}</td>
                    <td className="py-2.5 px-3 text-light-muted dark:text-dark-muted">{item.category}</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        item.format === 'shorts' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>{item.format}</span>
                    </td>
                    <td className="py-2.5 px-3 text-light-muted dark:text-dark-muted text-xs">
                      {item.scheduled_at ? new Date(item.scheduled_at).toLocaleString() : '—'}
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        item.status === 'published' ? 'bg-green-500/20 text-green-400' :
                        item.status === 'generated' ? 'bg-blue-500/20 text-blue-400' :
                        item.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                        'bg-yellow-500/20 text-yellow-400'
                      }`}>{item.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* Pending Triggers */}
      {pendingTriggers.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Pending Triggers ({pendingTriggers.length})</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-light-border/30 dark:border-white/5">
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Type</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Topic</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Format</th>
                  <th className="text-left py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {pendingTriggers.map(t => (
                  <tr key={t.id} className="border-b border-light-border/20 dark:border-white/5 hover:bg-light-bg/30 dark:hover:bg-dark-bg/30">
                    <td className="py-2.5 px-3">
                      <span className="px-2 py-0.5 rounded text-xs font-bold bg-purple-500/20 text-purple-400">{t.type}</span>
                    </td>
                    <td className="py-2.5 px-3 text-light-text dark:text-dark-text">{t.topic || '—'}</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        t.format === 'shorts' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                      }`}>{t.format}</span>
                    </td>
                    <td className="py-2.5 px-3 text-light-muted dark:text-dark-muted text-xs">
                      {t.created_at ? new Date(t.created_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>
      )}
    </div>
  );
}
