'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Target, Plus, Trash2, Loader2, TrendingUp, Calendar, CheckCircle } from 'lucide-react';
import { auth } from '@/lib/firebase';

interface Goal {
  id: string;
  metric: string;
  metricLabel: string;
  target: number;
  current: number;
  deadline: string;
  createdAt: string;
  projectedDate: string | null;
  progress: number;
}

interface CurrentMetrics {
  subscribers: number;
  monthly_views: number;
  revenue: number;
  videos_published: number;
  watch_hours: number;
}

const METRICS = [
  { value: 'subscribers', label: 'Subscribers' },
  { value: 'monthly_views', label: 'Monthly Views' },
  { value: 'revenue', label: 'Monthly Revenue ($)' },
  { value: 'videos_published', label: 'Videos Published' },
  { value: 'watch_hours', label: 'Watch Hours' },
];

export function GoalsPanel() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [currentMetrics, setCurrentMetrics] = useState<CurrentMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formMetric, setFormMetric] = useState('subscribers');
  const [formTarget, setFormTarget] = useState('1000');
  const [formDeadline, setFormDeadline] = useState('');
  const [saving, setSaving] = useState(false);
  const [whatIfRate, setWhatIfRate] = useState('2');
  const [whatIfFormat, setWhatIfFormat] = useState('shorts');

  const fetchGoals = async () => {
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();
      const res = await fetch('/api/reports/goals', {
        headers: { authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setGoals(json.goals || []);
      setCurrentMetrics(json.currentMetrics || null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchGoals(); }, []);

  const handleCreate = async () => {
    setSaving(true);
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();
      const res = await fetch('/api/reports/goals', {
        method: 'POST',
        headers: { authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ metric: formMetric, target: Number(formTarget), deadline: formDeadline }),
      });
      if (!res.ok) throw new Error('Failed to create goal');
      setShowForm(false);
      setFormTarget('1000');
      setFormDeadline('');
      await fetchGoals();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      const user = auth.currentUser;
      if (!user) return;
      const token = await user.getIdToken();
      await fetch(`/api/reports/goals?id=${id}`, {
        method: 'DELETE',
        headers: { authorization: `Bearer ${token}` },
      });
      await fetchGoals();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const formatNum = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return String(v);
  };

  if (error && !goals.length) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-sm text-red-400">Failed to load goals: {error}</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="glass rounded-xl p-12 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-light-muted" />
      </div>
    );
  }

  const getProgressColor = (pct: number) => {
    if (pct >= 100) return 'from-emerald-500 to-emerald-600';
    if (pct >= 50) return 'from-blue-500 to-blue-600';
    if (pct >= 25) return 'from-yellow-500 to-yellow-600';
    return 'from-red-500 to-red-600';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">Your Goals</h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-light-primary text-white hover:bg-light-primary/90 transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Goal
        </button>
      </div>

      {showForm && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          className="glass rounded-xl p-4 space-y-3"
        >
          <div>
            <label className="text-xs text-light-muted">Metric</label>
            <select
              value={formMetric}
              onChange={e => setFormMetric(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text"
            >
              {METRICS.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-light-muted">Target</label>
            <input
              type="number"
              value={formTarget}
              onChange={e => setFormTarget(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text"
            />
          </div>
          <div>
            <label className="text-xs text-light-muted">Deadline</label>
            <input
              type="date"
              value={formDeadline}
              onChange={e => setFormDeadline(e.target.value)}
              className="w-full mt-1 px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text"
            />
          </div>
          <div className="flex gap-2">
            <button onClick={handleCreate} disabled={saving}
              className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-light-primary text-white hover:bg-light-primary/90 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Create Goal'}
            </button>
            <button onClick={() => setShowForm(false)}
              className="px-4 py-2 rounded-lg text-sm font-medium text-light-muted hover:bg-light-border/50"
            >
              Cancel
            </button>
          </div>
        </motion.div>
      )}

      {goals.length === 0 ? (
        <div className="glass rounded-xl p-8 text-center">
          <Target className="w-8 h-8 text-light-muted/30 mx-auto mb-2" />
          <p className="text-sm text-light-muted">No goals yet. Set your first content or growth goal!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {goals.map((goal, i) => (
            <motion.div
              key={goal.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="glass rounded-xl p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-sm font-medium text-light-text dark:text-dark-text">{goal.metricLabel}</span>
                  <span className="text-xs text-light-muted ml-2">
                    {formatNum(goal.current)} / {formatNum(goal.target)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {goal.progress >= 100 ? (
                    <span className="flex items-center gap-1 text-xs text-emerald-400">
                      <CheckCircle className="w-3 h-3" /> Achieved
                    </span>
                  ) : (
                    <span className="text-xs font-medium text-light-muted">{goal.progress}%</span>
                  )}
                  <button onClick={() => handleDelete(goal.id)} className="p-1 hover:bg-red-500/10 rounded">
                    <Trash2 className="w-3.5 h-3.5 text-red-400" />
                  </button>
                </div>
              </div>
              <div className="w-full h-2 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(100, goal.progress)}%` }}
                  transition={{ duration: 1, ease: 'easeOut' }}
                  className={`h-full rounded-full bg-gradient-to-r ${getProgressColor(goal.progress)}`}
                />
              </div>
              <div className="flex items-center justify-between mt-2 text-[10px] text-light-muted">
                <span>Deadline: {goal.deadline || 'No deadline'}</span>
                {goal.projectedDate && (
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3 h-3" />
                    Est. completion: {goal.projectedDate}
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {currentMetrics && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            What-If Simulator
          </h3>
          <p className="text-xs text-light-muted mb-3">
            See how changing your upload frequency affects projected growth.
          </p>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="text-xs text-light-muted">Videos per day</label>
              <input
                type="number"
                value={whatIfRate}
                onChange={e => setWhatIfRate(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text"
                min="1"
                max="10"
              />
            </div>
            <div>
              <label className="text-xs text-light-muted">Format</label>
              <select
                value={whatIfFormat}
                onChange={e => setWhatIfFormat(e.target.value)}
                className="w-full mt-1 px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text"
              >
                <option value="shorts">Shorts</option>
                <option value="long">Long Form</option>
                <option value="mixed">Mixed</option>
              </select>
            </div>
          </div>
          <div className="p-3 rounded-lg bg-light-border/30 dark:bg-dark-border/30">
            <p className="text-xs text-light-muted">
              At {whatIfRate} videos/day ({whatIfFormat}), projected monthly view growth:{' '}
              <span className="text-light-primary font-medium">
                ~{formatNum(Math.round((currentMetrics.monthly_views || 1) * (1 + Number(whatIfRate) * 0.15)))}
              </span>
              {' '}(vs current {formatNum(currentMetrics.monthly_views || 0)})
            </p>
          </div>
        </div>
      )}

      {currentMetrics && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-3">Current Stats</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {METRICS.map(m => {
              const val = currentMetrics[m.value as keyof CurrentMetrics] || 0;
              return (
                <div key={m.value} className="text-center p-2">
                  <div className="text-lg font-bold text-light-text dark:text-dark-text">{formatNum(val)}</div>
                  <div className="text-[10px] text-light-muted">{m.label}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
