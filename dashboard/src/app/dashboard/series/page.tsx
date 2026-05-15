'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { auth } from '@/lib/firebase';

interface Series {
  id: string;
  name: string;
  description?: string;
  host: string;
  host_pose?: string;
  host_expression?: string;
  intro_duration?: number;
  outro_duration?: number;
  categories?: string[];
  character_placement?: { x: number; y: number };
  intro_text?: string;
  outro_text?: string;
  background?: string;
  music_mood?: string;
  color_palette?: string[];
}

const AVAILABLE_HOSTS = ['pixel', 'nova', 'ziggy', 'boop', 'sprout'];
const AVAILABLE_BACKGROUNDS = [
  'gradient_sky', 'gradient_forest', 'gradient_ocean', 'gradient_space',
  'gradient_sunset', 'gradient_night', 'gradient_garden', 'gradient_classroom',
  'gradient_bedroom', 'gradient_underwater',
];
const AVAILABLE_MOODS = ['happy', 'calm', 'adventure', 'dreamy', 'playful', 'exciting'];
const ALL_CATEGORIES = [
  'Self-Learning', 'Science for Kids', 'Bedtime Stories', 'Mythology Stories',
  'Animated Fables', 'Rhymes & Songs', 'Colors & Shapes', 'Tech & AI', 'DIY & Crafts',
];
const CHAR_EMOJIS: Record<string, string> = {
  pixel: '🤖', nova: '⭐', ziggy: '🌈', boop: '🔵', sprout: '🌱',
};

export default function SeriesPage() {
  const [series, setSeries] = useState<Series[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<Series | null>(null);
  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState({
    name: '', description: '', host: 'pixel', host_pose: 'wave', host_expression: 'happy',
    intro_duration: 3, outro_duration: 3, categories: [] as string[],
    intro_text: '', outro_text: '', background: 'gradient_sky', music_mood: 'happy',
  });

  useEffect(() => { loadSeries(); }, []);

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

  const openNew = () => {
    setForm({ name: '', description: '', host: 'pixel', host_pose: 'wave', host_expression: 'happy',
      intro_duration: 3, outro_duration: 3, categories: [],
      intro_text: '', outro_text: '', background: 'gradient_sky', music_mood: 'happy' });
    setEditing(null);
    setShowForm(true);
  };

  const openEdit = (s: Series) => {
    setForm({
      name: s.name, description: s.description || '', host: s.host, host_pose: s.host_pose || 'wave',
      host_expression: s.host_expression || 'happy', intro_duration: s.intro_duration || 3,
      outro_duration: s.outro_duration || 3, categories: s.categories || [],
      intro_text: s.intro_text || '', outro_text: s.outro_text || '',
      background: s.background || 'gradient_sky', music_mood: s.music_mood || 'happy',
    });
    setEditing(s);
    setShowForm(true);
  };

  const toggleCategory = (cat: string) => {
    setForm(prev => ({
      ...prev,
      categories: prev.categories.includes(cat)
        ? prev.categories.filter(c => c !== cat)
        : [...prev.categories, cat],
    }));
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

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
              <span className="text-2xl">🎬</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Series</h1>
              <p className="text-light-muted dark:text-dark-muted mt-1">Manage character series and their intro/outro templates</p>
            </div>
          </div>
          <button
            onClick={openNew}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 text-white text-sm font-semibold hover:opacity-90 transition-opacity"
          >
            + New Series
          </button>
        </div>
      </motion.div>

      {showForm && (
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">
            {editing ? `Edit: ${editing.name}` : 'Create New Series'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Name</label>
              <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Host Character</label>
              <select value={form.host} onChange={e => setForm({ ...form, host: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                {AVAILABLE_HOSTS.map(h => <option key={h} value={h}>{CHAR_EMOJIS[h] || '❓'} {h}</option>)}
              </select>
            </div>
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Description</label>
              <input type="text" value={form.description} onChange={e => setForm({ ...form, description: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Background</label>
              <select value={form.background} onChange={e => setForm({ ...form, background: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                {AVAILABLE_BACKGROUNDS.map(b => <option key={b} value={b}>{b.replace('gradient_', '')}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Music Mood</label>
              <select value={form.music_mood} onChange={e => setForm({ ...form, music_mood: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                {AVAILABLE_MOODS.map(m => <option key={m} value={m}>{m}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Intro Duration (s)</label>
              <input type="number" step="0.5" min="1" max="10" value={form.intro_duration}
                onChange={e => setForm({ ...form, intro_duration: parseFloat(e.target.value) || 3 })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Outro Duration (s)</label>
              <input type="number" step="0.5" min="1" max="10" value={form.outro_duration}
                onChange={e => setForm({ ...form, outro_duration: parseFloat(e.target.value) || 3 })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Intro Text</label>
              <input type="text" value={form.intro_text} onChange={e => setForm({ ...form, intro_text: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
            <div>
              <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-1">Outro Text</label>
              <input type="text" value={form.outro_text} onChange={e => setForm({ ...form, outro_text: e.target.value })}
                className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
            </div>
          </div>

          <div className="mt-4">
            <label className="block text-sm font-medium text-light-text dark:text-dark-text mb-2">Categories</label>
            <div className="flex flex-wrap gap-2">
              {ALL_CATEGORIES.map(cat => (
                <button key={cat} onClick={() => toggleCategory(cat)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    form.categories.includes(cat)
                      ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                      : 'bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/10 text-light-muted dark:text-dark-muted'
                  }`}>
                  {cat}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-3 mt-6">
            <button onClick={save}
              className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 text-white text-sm font-semibold hover:opacity-90 transition-opacity">
              {editing ? 'Update' : 'Create'}
            </button>
            <button onClick={() => { setShowForm(false); setEditing(null); }}
              className="px-6 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/10 text-light-muted dark:text-dark-muted text-sm font-medium hover:bg-light-border/50 transition-colors">
              Cancel
            </button>
          </div>
        </motion.div>
      )}

      {loading ? (
        <div className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-12 text-center">
          <p className="text-light-muted dark:text-dark-muted">Loading series...</p>
        </div>
      ) : series.length === 0 ? (
        <div className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-12 text-center">
          <p className="text-light-muted dark:text-dark-muted">No series yet. Create your first series to get started!</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {series.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-5"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className="text-3xl">{CHAR_EMOJIS[s.host] || '❓'}</span>
                <div className="flex-1 min-w-0">
                  <h3 className="font-bold text-light-text dark:text-dark-text truncate">{s.name}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted capitalize">Host: {s.host}</p>
                </div>
              </div>
              {s.description && (
                <p className="text-sm text-light-muted dark:text-dark-muted mb-3 line-clamp-2">{s.description}</p>
              )}
              <div className="flex flex-wrap gap-1 mb-3">
                {(s.categories || []).map(cat => (
                  <span key={cat} className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400">{cat}</span>
                ))}
              </div>
              <div className="flex items-center justify-between text-xs text-light-muted dark:text-dark-muted mb-3">
                <span>🎵 {s.music_mood}</span>
                <span>🎬 {s.intro_duration}s / {s.outro_duration}s</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => openEdit(s)}
                  className="flex-1 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/10 text-light-text dark:text-dark-text text-xs font-medium hover:bg-light-border/50 transition-colors">
                  Edit
                </button>
                <button onClick={() => remove(s.id)}
                  className="px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium hover:bg-red-500/20 transition-colors">
                  Delete
                </button>
              </div>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
}
