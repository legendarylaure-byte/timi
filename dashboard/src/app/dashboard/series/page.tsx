'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { auth, db } from '@/lib/firebase';
import { collection, onSnapshot, doc, deleteDoc } from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import { GradientCard } from '@/components/ui/GradientCard';
import { Clapperboard, Plus, ExternalLink, Sparkles, Trash2, Edit3, Layers, CheckCircle, ChevronDown, ChevronUp, X } from 'lucide-react';

interface Series {
  id: string;
  name: string;
  description?: string;
  category: string;
  youtube_playlist_link?: string;
  auto_generated?: boolean;
  created_at?: any;
}

interface SeriesPlan {
  id: string;
  series_id: string;
  title: string;
  description: string;
  categories: string[];
  parts: SeriesPart[];
  target_audience: string;
  estimated_total_watch_time_minutes: number;
  status: string;
  created_at?: any;
}

interface SeriesPart {
  part: number;
  title: string;
  description: string;
  estimated_duration: string;
}

const gradients: Record<string, string> = {
  primary: 'linear-gradient(135deg, #FF6969, #C80036)',
  warm: 'linear-gradient(135deg, #FF6969, #FFF5E1)',
  cool: 'linear-gradient(135deg, #C80036, #0C1844)',
  success: 'linear-gradient(135deg, #FF6969, #0C1844)',
};

export default function SeriesPage() {
  const [series, setSeries] = useState<Series[]>([]);
  const [plans, setPlans] = useState<SeriesPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Series | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedPlan, setExpandedPlan] = useState<string | null>(null);
  const [promoting, setPromoting] = useState<string | null>(null);

  const [form, setForm] = useState({
    name: '', description: '', category: 'AI Explained', youtube_playlist_link: '', auto_generated: false,
  });

  useEffect(() => {
    loadSeries();
    loadPlans();
  }, []);

  const loadSeries = async () => {
    setLoading(true);
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const res = await fetch('/api/series', { headers: { Authorization: `Bearer ${token}` } });
      const data = await res.json();
      if (data.success) setSeries(data.series);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadPlans = () => {
    const unsub = onSnapshot(collection(db, 'series_plans'),
      (snap) => {
        const items: SeriesPlan[] = [];
        snap.forEach(d => {
          items.push({ id: d.id, ...d.data() } as SeriesPlan);
        });
        setPlans(items.sort((a, b) => {
          const aTime = a.created_at?.toDate?.()?.getTime() || 0;
          const bTime = b.created_at?.toDate?.()?.getTime() || 0;
          return bTime - aTime;
        }));
      },
      (error) => {
        console.error('[Series] series_plans:', error);
      }
    );
    return () => unsub();
  };

  const openNew = () => {
    setForm({ name: '', description: '', category: 'AI Explained', youtube_playlist_link: '', auto_generated: false });
    setEditing(null);
    setShowForm(true);
  };

  const openEdit = (s: Series) => {
    setForm({
      name: s.name, description: s.description || '', category: s.category,
      youtube_playlist_link: s.youtube_playlist_link || '', auto_generated: s.auto_generated || false,
    });
    setEditing(s);
    setShowForm(true);
  };

  const save = async () => {
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const headers = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };

      if (editing) {
        await fetch('/api/series', {
          method: 'PUT', headers,
          body: JSON.stringify({ id: editing.id, ...form }),
        });
      } else {
        await fetch('/api/series', {
          method: 'POST', headers,
          body: JSON.stringify(form),
        });
      }

      setShowForm(false);
      setEditing(null);
      await loadSeries();
    } catch (e) { console.error(e); }
  };

  const remove = async (id: string) => {
    if (!confirm('Delete this series?')) return;
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      await fetch(`/api/series?id=${id}`, {
        method: 'DELETE', headers: { Authorization: `Bearer ${token}` },
      });
      await loadSeries();
    } catch (e) { console.error(e); }
  };

  const promotePlan = async (plan: SeriesPlan) => {
    setPromoting(plan.id);
    try {
      for (const part of plan.parts) {
        const seriesData = {
          name: `${plan.title} — Part ${part.part}`,
          description: part.description,
          category: plan.categories[0] || 'AI Explained',
          youtube_playlist_link: '',
          auto_generated: true,
        };
        const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
        await fetch('/api/series', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify(seriesData),
        });
      }
      await fetch(`/api/series-plans/${plan.id}`, { method: 'DELETE' });
      await loadSeries();
    } catch (e) { console.error(e); }
    finally { setPromoting(null); }
  };

  const deletePlan = async (id: string) => {
    if (!confirm('Delete this auto-generated plan?')) return;
    try {
      await fetch(`/api/series-plans/${id}`, { method: 'DELETE' });
    } catch (e) { console.error(e); }
  };

  const formatDate = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: gradients.primary }}>
              <Clapperboard className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Series</h1>
              <p className="text-light-muted dark:text-dark-muted mt-1">Topic-based playlist manager</p>
            </div>
          </div>
          <button
            onClick={openNew}
            className="px-4 py-2.5 rounded-xl text-white text-sm font-semibold hover:opacity-90 transition-opacity flex items-center gap-2"
            style={{ background: gradients.primary }}
          >
            <Plus className="w-4 h-4" /> New Series
          </button>
        </div>
      </motion.div>

      {showForm && (
        <GradientCard gradient="primary">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">
            {editing ? `Edit: ${editing.name}` : 'Create New Series'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Name</label>
              <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Category</label>
              <select value={form.category} onChange={e => setForm({ ...form, category: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary">
                {CONTENT_CATEGORIES.map(cat => <option key={cat.name} value={cat.name}>{cat.name}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Description</label>
              <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary" />
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">YouTube Playlist Link</label>
              <input type="url" value={form.youtube_playlist_link} onChange={e => setForm({ ...form, youtube_playlist_link: e.target.value })}
                placeholder="https://youtube.com/playlist?list=..."
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary" />
            </div>
            <div className="flex items-center gap-3">
              <label className="text-sm font-medium text-light-text dark:text-dark-text">Auto-Generated</label>
              <button
                onClick={() => setForm({ ...form, auto_generated: !form.auto_generated })}
                className={`w-10 h-6 rounded-full transition-all duration-200 ${
                  form.auto_generated ? 'bg-light-success' : 'bg-light-muted dark:bg-dark-muted'
                }`}
              >
                <motion.div
                  className="w-5 h-5 rounded-full bg-white shadow-sm"
                  animate={{ x: form.auto_generated ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              </button>
              <span className="text-xs text-light-muted dark:text-dark-muted">Mark as auto-generated by AI pipeline</span>
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button onClick={save}
              className="px-6 py-2.5 rounded-xl bg-light-success text-white text-sm font-semibold hover:opacity-90 transition-opacity">
              {editing ? 'Update' : 'Create'}
            </button>
            <button onClick={() => { setShowForm(false); setEditing(null); }}
              className="px-6 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-dark-border text-light-muted dark:text-dark-muted text-sm font-medium hover:bg-light-border/50 transition-colors">
              Cancel
            </button>
          </div>
        </GradientCard>
      )}

      {/* Auto-Generated Plans */}
      {plans.length > 0 && (
        <div>
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-light-primary" /> Auto-Generated Plans ({plans.length})
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {plans.map((plan, i) => {
              const isExpanded = expandedPlan === plan.id;
              return (
                <motion.div
                  key={plan.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="rounded-2xl overflow-hidden glass-strong border border-light-primary/20 dark:border-light-primary/20 p-5"
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: gradients.primary }}>
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>
                      <h3 className="font-bold text-light-text dark:text-dark-text truncate">{plan.title}</h3>
                    </div>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-light-primary/10 text-light-primary font-medium">
                      {plan.parts.length} parts
                    </span>
                  </div>
                  <p className="text-sm text-light-muted dark:text-dark-muted mb-3 line-clamp-2">{plan.description}</p>
                  <div className="flex items-center gap-2 mb-3 flex-wrap">
                    {plan.categories.map(cat => (
                      <span key={cat} className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ background: 'linear-gradient(135deg, #FF6969, #C80036)', color: 'white' }}>
                        {cat}
                      </span>
                    ))}
                    <span className="text-xs text-light-muted dark:text-dark-muted">
                      {plan.target_audience} · ~{plan.estimated_total_watch_time_minutes}min total
                    </span>
                  </div>

                  {/* Expandable parts */}
                  <button
                    onClick={() => setExpandedPlan(isExpanded ? null : plan.id)}
                    className="flex items-center gap-1 text-xs text-light-primary hover:text-light-secondary transition-colors mb-3"
                  >
                    <Layers className="w-3 h-3" />
                    {isExpanded ? 'Hide' : 'View'} parts
                    {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  {isExpanded && (
                    <div className="space-y-2 mb-3">
                      {plan.parts.map(part => (
                        <div key={part.part} className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-light-text dark:text-dark-text">Part {part.part}: {part.title}</span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold ${
                              part.estimated_duration === 'shorts' ? 'bg-red-500/20 text-red-400' : 'bg-blue-500/20 text-blue-400'
                            }`}>{part.estimated_duration}</span>
                          </div>
                          <p className="text-[10px] text-light-muted dark:text-dark-muted mt-0.5">{part.description}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => promotePlan(plan)}
                      disabled={promoting === plan.id}
                      className="flex-1 py-2 rounded-lg bg-light-success text-white text-xs font-medium hover:opacity-90 transition-opacity flex items-center justify-center gap-1 disabled:opacity-50"
                    >
                      {promoting === plan.id ? (
                        'Creating...'
                      ) : (
                        <><CheckCircle className="w-3 h-3" /> Create Series</>
                      )}
                    </button>
                    <button onClick={() => deletePlan(plan.id)}
                      className="px-4 py-2 rounded-lg bg-light-primary/10 border border-light-primary/20 text-light-primary text-xs font-medium hover:bg-light-primary/20 transition-colors flex items-center gap-1">
                      <X className="w-3 h-3" /> Dismiss
                    </button>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}

      {/* Manual Series */}
      {loading ? (
        <div className="rounded-2xl p-12 text-center glass-strong">
          <p className="text-light-muted dark:text-dark-muted">Loading series...</p>
        </div>
      ) : series.length === 0 ? (
        <div className="rounded-2xl p-12 text-center glass-strong">
          <Clapperboard className="w-12 h-12 text-light-muted mx-auto mb-3" />
          <p className="text-light-muted dark:text-dark-muted">No series yet. Create your first playlist or promote an auto-generated plan above!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {series.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-dark-border p-5"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: gradients.primary }}>
                    <Clapperboard className="w-4 h-4 text-white" />
                  </div>
                  <h3 className="font-bold text-light-text dark:text-dark-text truncate">{s.name}</h3>
                </div>
                {s.auto_generated && (
                  <Sparkles className="w-4 h-4 text-light-primary" />
                )}
              </div>
              {s.description && (
                <p className="text-sm text-light-muted dark:text-dark-muted mb-3 line-clamp-2">{s.description}</p>
              )}
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{
                  background: 'linear-gradient(135deg, #FF6969, #C80036)',
                  color: 'white',
                }}>
                  {s.category}
                </span>
                {formatDate(s.created_at) && (
                  <span className="text-xs text-light-muted dark:text-dark-muted">{formatDate(s.created_at)}</span>
                )}
              </div>
              {s.youtube_playlist_link && (
                <a href={s.youtube_playlist_link} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs text-light-primary hover:text-light-secondary transition-colors mb-3">
                  <ExternalLink className="w-3 h-3" /> Open Playlist
                </a>
              )}
              <div className="flex gap-2">
                <button onClick={() => openEdit(s)}
                  className="flex-1 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-dark-border text-light-text dark:text-dark-text text-xs font-medium hover:bg-light-border/50 transition-colors flex items-center justify-center gap-1">
                  <Edit3 className="w-3 h-3" /> Edit
                </button>
                <button onClick={() => remove(s.id)}
                  className="px-4 py-2 rounded-lg bg-light-primary/10 border border-light-primary/20 text-light-primary text-xs font-medium hover:bg-light-primary/20 transition-colors flex items-center gap-1">
                  <Trash2 className="w-3 h-3" /> Delete
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
