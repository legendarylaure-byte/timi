'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { auth } from '@/lib/firebase';
import { Clock, Play, Pause, Calendar, Layers, ChevronLeft, ChevronRight, Edit3, Trash2, Check, X, Loader2 } from 'lucide-react';

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

interface SeriesPlanOption {
  id: string;
  title: string;
  parts: { part: number; title: string; estimated_duration: string }[];
  categories: string[];
}

const gradients: Record<string, string> = {
  primary: 'linear-gradient(135deg, #FF6969, #C80036)',
  warm: 'linear-gradient(135deg, #FF6969, #FFF5E1)',
  cool: 'linear-gradient(135deg, #C80036, #0C1844)',
  success: 'linear-gradient(135deg, #FF6969, #0C1844)',
};

export default function SchedulerPage() {
  const [scheduler, setScheduler] = useState<SchedulerStatus | null>(null);
  const [plan, setPlan] = useState<PlanItem[]>([]);
  const [pendingTriggers, setPendingTriggers] = useState<PendingTrigger[]>([]);
  const [seriesPlans, setSeriesPlans] = useState<SeriesPlanOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [topic, setTopic] = useState('');
  const [format, setFormat] = useState<'shorts' | 'long'>('shorts');
  const [category, setCategory] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [triggering, setTriggering] = useState(false);

  // Calendar state
  const [calendarDate, setCalendarDate] = useState(new Date());
  const [showCalendar, setShowCalendar] = useState(false);

  // Edit state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({ title: '', category: '', format: 'shorts' as string, scheduled_at: '', status: '' });

  // Series scheduling state
  const [showSeriesScheduler, setShowSeriesScheduler] = useState(false);
  const [selectedSeriesPlan, setSelectedSeriesPlan] = useState('');
  const [seriesStartDate, setSeriesStartDate] = useState('');
  const [seriesScheduling, setSeriesScheduling] = useState(false);

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
        setSeriesPlans(data.series_plans || []);
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

  const deletePlanItem = async (id: string) => {
    if (!confirm('Delete this plan item?')) return;
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      await fetch(`/api/scheduler?id=${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });
      await loadData();
    } catch (e) {
      console.error('[SCHEDULER] Delete error:', e);
    }
  };

  const startEdit = (item: PlanItem) => {
    setEditingId(item.id);
    setEditForm({
      title: item.title,
      category: item.category,
      format: item.format,
      scheduled_at: item.scheduled_at ? new Date(item.scheduled_at).toISOString().slice(0, 16) : '',
      status: item.status,
    });
  };

  const saveEdit = async () => {
    if (!editingId) return;
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      await fetch('/api/scheduler', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ id: editingId, ...editForm }),
      });
      setEditingId(null);
      await loadData();
    } catch (e) {
      console.error('[SCHEDULER] Edit error:', e);
    }
  };

  const scheduleSeries = async () => {
    if (!selectedSeriesPlan || !seriesStartDate) return;
    setSeriesScheduling(true);
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      await fetch('/api/scheduler', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          action: 'schedule_series',
          series_plan_id: selectedSeriesPlan,
          start_date: seriesStartDate,
        }),
      });
      setShowSeriesScheduler(false);
      setSelectedSeriesPlan('');
      setSeriesStartDate('');
      await loadData();
    } catch (e) {
      console.error('[SCHEDULER] Series scheduling error:', e);
    } finally {
      setSeriesScheduling(false);
    }
  };

  // Calendar helpers
  const getDaysInMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  const getFirstDayOfMonth = (date: Date) => new Date(date.getFullYear(), date.getMonth(), 1).getDay();
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  const prevMonth = () => setCalendarDate(new Date(calendarDate.getFullYear(), calendarDate.getMonth() - 1, 1));
  const nextMonth = () => setCalendarDate(new Date(calendarDate.getFullYear(), calendarDate.getMonth() + 1, 1));

  const daysInMonth = getDaysInMonth(calendarDate);
  const firstDay = getFirstDayOfMonth(calendarDate);
  const planByDate: Record<string, PlanItem[]> = {};
  plan.forEach(item => {
    if (item.scheduled_at) {
      const d = new Date(item.scheduled_at);
      const key = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      if (!planByDate[key]) planByDate[key] = [];
      planByDate[key].push(item);
    }
  });

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-8 h-8 text-light-muted animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: gradients.primary }}>
            <Clock className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Scheduler</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Manage content scheduling and automated publishing</p>
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl glass-strong border border-red-500/30 p-6 text-center">
          <p className="text-red-400">{error}</p>
          <button onClick={loadData} className="mt-3 px-4 py-2 rounded-lg text-white text-sm font-medium" style={{ background: gradients.primary }}>Retry</button>
        </motion.div>
      )}

      {/* Scheduler Status */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6">
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
              className="px-4 py-2 rounded-xl text-sm font-medium transition-all flex items-center gap-2 disabled:opacity-50"
              style={{
                background: scheduler.running
                  ? 'rgba(234,179,8,0.2)'
                  : 'linear-gradient(135deg, #22c55e, #10b981)',
                color: scheduler.running ? '#eab308' : 'white',
                border: scheduler.running ? '1px solid rgba(234,179,8,0.3)' : 'none',
              }}
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : scheduler.running ? <><Pause className="w-4 h-4" /> Pause</> : <><Play className="w-4 h-4" /> Resume</>}
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

      {/* Quick Actions Row */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => setShowCalendar(!showCalendar)}
          className="px-4 py-2.5 rounded-xl text-sm font-medium transition-all flex items-center gap-2"
          style={{
            background: showCalendar ? gradients.primary : 'rgba(255,255,255,0.05)',
            color: showCalendar ? 'white' : 'var(--color-text, inherit)',
            border: showCalendar ? 'none' : '1px solid rgba(255,255,255,0.1)',
          }}
        >
          <Calendar className="w-4 h-4" /> {showCalendar ? 'Hide' : 'Show'} Calendar
        </button>
        <button
          onClick={() => setShowSeriesScheduler(true)}
          disabled={seriesPlans.length === 0}
          className="px-4 py-2.5 rounded-xl text-sm font-medium transition-all flex items-center gap-2 disabled:opacity-50"
          style={{ background: gradients.success, color: 'white' }}
        >
          <Layers className="w-4 h-4" /> Schedule Series
        </button>
      </div>

      {/* Calendar View */}
      {showCalendar && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6"
        >
          <div className="flex items-center justify-between mb-4">
            <button onClick={prevMonth} className="p-2 rounded-lg hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors">
              <ChevronLeft className="w-5 h-5 text-light-text dark:text-dark-text" />
            </button>
            <h3 className="text-lg font-bold text-light-text dark:text-dark-text">
              {MONTHS[calendarDate.getMonth()]} {calendarDate.getFullYear()}
            </h3>
            <button onClick={nextMonth} className="p-2 rounded-lg hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors">
              <ChevronRight className="w-5 h-5 text-light-text dark:text-dark-text" />
            </button>
          </div>
          <div className="grid grid-cols-7 gap-1">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
              <div key={d} className="text-center text-xs text-light-muted dark:text-dark-muted font-medium py-2">{d}</div>
            ))}
            {Array.from({ length: firstDay }).map((_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }).map((_, i) => {
              const day = i + 1;
              const dateKey = `${calendarDate.getFullYear()}-${calendarDate.getMonth()}-${day}`;
              const dayPlans = planByDate[dateKey] || [];
              const isToday = new Date().toDateString() === new Date(calendarDate.getFullYear(), calendarDate.getMonth(), day).toDateString();
              return (
                <motion.div
                  key={day}
                  whileHover={{ scale: 1.1 }}
                  className={`p-2 rounded-lg text-center cursor-pointer transition-colors ${
                    isToday
                      ? 'bg-light-primary/20 border border-light-primary/30'
                      : 'hover:bg-light-bg/30 dark:hover:bg-dark-bg/30'
                  }`}
                >
                  <span className={`text-sm font-medium ${isToday ? 'text-light-primary' : 'text-light-text dark:text-dark-text'}`}>{day}</span>
                  {dayPlans.length > 0 && (
                    <div className="flex justify-center gap-0.5 mt-1">
                      {dayPlans.slice(0, 3).map(p => (
                        <div
                          key={p.id}
                          className={`w-1.5 h-1.5 rounded-full ${
                            p.format === 'shorts' ? 'bg-red-400' : 'bg-blue-400'
                          }`}
                        />
                      ))}
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        </motion.div>
      )}

      {/* Schedule Series Modal */}
      {showSeriesScheduler && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6"
        >
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
            <Layers className="w-5 h-5" /> Schedule Series
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Series Plan</label>
              <select
                value={selectedSeriesPlan}
                onChange={e => setSelectedSeriesPlan(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary"
              >
                <option value="">Select a plan...</option>
                {seriesPlans.map(sp => (
                  <option key={sp.id} value={sp.id}>{sp.title} ({sp.parts.length} parts)</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Start Date</label>
              <input
                type="date"
                value={seriesStartDate}
                onChange={e => setSeriesStartDate(e.target.value)}
                min={new Date().toISOString().slice(0, 10)}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                onClick={scheduleSeries}
                disabled={!selectedSeriesPlan || !seriesStartDate || seriesScheduling}
                className="flex-1 py-2.5 rounded-xl text-white text-sm font-semibold transition-opacity disabled:opacity-50"
                style={{ background: gradients.primary }}
              >
                {seriesScheduling ? 'Scheduling...' : 'Schedule'}
              </button>
              <button
                onClick={() => { setShowSeriesScheduler(false); setSelectedSeriesPlan(''); setSeriesStartDate(''); }}
                className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-dark-border text-light-muted dark:text-dark-muted text-sm font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
          {selectedSeriesPlan && (
            <p className="text-xs text-light-muted dark:text-dark-muted mt-3">
              Parts will be scheduled on consecutive days starting from the selected date.
            </p>
          )}
        </motion.div>
      )}

      {/* Manual Trigger */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Manual Trigger</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Topic (optional)</label>
            <input
              type="text"
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="e.g., Transformers Explained"
              className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary"
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
                      ? 'text-white shadow-lg'
                      : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-muted dark:text-dark-muted'
                  }`}
                  style={format === f ? { background: gradients.primary } : {}}
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
              placeholder="e.g., AI Explained"
              className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary"
            />
          </div>
        </div>
        <button
          onClick={() => handleAction('trigger')}
          disabled={triggering}
          className="mt-4 w-full py-3 rounded-xl text-white font-semibold text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
          style={{ background: gradients.primary }}
        >
          {triggering ? 'Triggering...' : 'Trigger Content Generation'}
        </button>
      </motion.div>

      {/* Content Plan with Edit/Delete */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }} className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6">
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
                  <th className="text-right py-2.5 px-3 text-light-muted dark:text-dark-muted font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {plan.map(item => (
                  <tr key={item.id} className="border-b border-light-border/20 dark:border-white/5 hover:bg-light-bg/30 dark:hover:bg-dark-bg/30">
                    {editingId === item.id ? (
                      <>
                        <td className="py-2 px-3">
                          <input
                            type="text"
                            value={editForm.title}
                            onChange={e => setEditForm({ ...editForm, title: e.target.value })}
                            className="w-full px-2 py-1 rounded bg-light-bg dark:bg-dark-bg border border-light-border text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-1 focus:ring-light-primary"
                          />
                        </td>
                        <td className="py-2 px-3">
                          <input
                            type="text"
                            value={editForm.category}
                            onChange={e => setEditForm({ ...editForm, category: e.target.value })}
                            className="w-full px-2 py-1 rounded bg-light-bg dark:bg-dark-bg border border-light-border text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-1 focus:ring-light-primary"
                          />
                        </td>
                        <td className="py-2 px-3">
                          <select
                            value={editForm.format}
                            onChange={e => setEditForm({ ...editForm, format: e.target.value })}
                            className="px-2 py-1 rounded bg-light-bg dark:bg-dark-bg border border-light-border text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-1 focus:ring-light-primary"
                          >
                            <option value="shorts">Shorts</option>
                            <option value="long">Long</option>
                          </select>
                        </td>
                        <td className="py-2 px-3">
                          <input
                            type="datetime-local"
                            value={editForm.scheduled_at}
                            onChange={e => setEditForm({ ...editForm, scheduled_at: e.target.value })}
                            className="w-full px-2 py-1 rounded bg-light-bg dark:bg-dark-bg border border-light-border text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-1 focus:ring-light-primary"
                          />
                        </td>
                        <td className="py-2 px-3">
                          <select
                            value={editForm.status}
                            onChange={e => setEditForm({ ...editForm, status: e.target.value })}
                            className="px-2 py-1 rounded bg-light-bg dark:bg-dark-bg border border-light-border text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-1 focus:ring-light-primary"
                          >
                            <option value="planned">planned</option>
                            <option value="generated">generated</option>
                            <option value="published">published</option>
                            <option value="failed">failed</option>
                          </select>
                        </td>
                        <td className="py-2 px-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={saveEdit} className="p-1.5 rounded-lg hover:bg-light-success/20 text-emerald-400 transition-colors">
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={() => setEditingId(null)} className="p-1.5 rounded-lg hover:bg-light-primary/20 text-light-primary transition-colors">
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-2.5 px-3 text-light-text dark:text-dark-text font-medium truncate max-w-[200px]">{item.title}</td>
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
                        <td className="py-2.5 px-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button onClick={() => startEdit(item)} className="p-1.5 rounded-lg hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 text-light-muted hover:text-light-text transition-colors">
                              <Edit3 className="w-4 h-4" />
                            </button>
                            <button onClick={() => deletePlanItem(item.id)} className="p-1.5 rounded-lg hover:bg-light-primary/20 text-light-primary transition-colors">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </motion.div>

      {/* Pending Triggers */}
      {pendingTriggers.length > 0 && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6">
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
