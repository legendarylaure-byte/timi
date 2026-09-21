'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Activity, ToggleRight, ToggleLeft, Clock, MessageSquare,
  Signal, RefreshCw, Newspaper, TrendingUp, Zap,
  Share2, ExternalLink, CheckCircle, XCircle, BarChart3, Globe,
} from 'lucide-react';
import Image from 'next/image';

interface ViralStatus {
  active: boolean;
  last_check: string | null;
  posts_today: number;
  scans_today: number;
  articles_scanned_today: number;
  errors_today: number;
  highest_score_today: number;
  viral_threshold: number;
  hold_threshold: number;
  max_per_day: number;
  cooldown_hours: number;
  check_interval_minutes: number;
}

interface ViralActivity {
  id: string;
  action: string;
  timestamp: string;
  details?: Record<string, any>;
}

interface ViralPost {
  id: string;
  title: string;
  source: string;
  category: string;
  virality_score: number;
  score_breakdown?: Record<string, number>;
  caption: string;
  platform_results?: Record<string, { success: boolean; url?: string; error?: string }>;
  posted_at: string;
}

interface ViralStory {
  id: string;
  title: string;
  source: string;
  category: string;
  link: string;
  virality_score: number;
  score_breakdown?: Record<string, number>;
  scanned_at?: string;
  is_viral?: boolean;
  is_hold?: boolean;
}

const BREAKDOWN_FACTORS: { key: string; label: string; max: number }[] = [
  { key: 'source', label: 'Source', max: 25 },
  { key: 'keywords', label: 'Keywords', max: 25 },
  { key: 'recency', label: 'Recency', max: 20 },
  { key: 'completeness', label: 'Completeness', max: 15 },
  { key: 'social_signals', label: 'Social', max: 15 },
];

function formatTimeAgo(iso: string): string {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function ScorePill({ score, status }: { score: number; status?: ViralStatus | null }) {
  const t = status?.viral_threshold ?? 60;
  if (score >= t) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 text-xs font-bold">
      <Zap className="w-3 h-3" /> VIRAL
    </span>
  );
  if (score >= (status?.hold_threshold ?? 45)) return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 text-xs font-bold">
      <Signal className="w-3 h-3" /> HOLD
    </span>
  );
  return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-500/20 text-gray-400 text-xs font-bold">NORMAL</span>;
}

function BreakdownBars({ breakdown }: { breakdown: Record<string, number> }) {
  return (
    <div className="grid grid-cols-5 gap-2 mt-2">
      {BREAKDOWN_FACTORS.map(f => {
        const val = breakdown?.[f.key] ?? 0;
        const pct = Math.min(100, (val / f.max) * 100);
        return (
          <div key={f.key}>
            <div className="h-1.5 rounded-full bg-light-bg dark:bg-dark-bg overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-light-primary to-purple-500"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.6 }}
              />
            </div>
            <p className="mt-1 text-[10px] text-light-muted dark:text-dark-muted flex justify-between">
              <span>{f.label}</span>
              <span className="font-bold text-light-text dark:text-dark-text">{Math.round(val)}</span>
            </p>
          </div>
        );
      })}
    </div>
  );
}

export default function SocialMediaPostPage() {
  const [status, setStatus] = useState<ViralStatus | null>(null);
  const [activities, setActivities] = useState<ViralActivity[]>([]);
  const [posts, setPosts] = useState<ViralPost[]>([]);
  const [stories, setStories] = useState<ViralStory[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testMsg, setTestMsg] = useState<string | null>(null);
  const [testErr, setTestErr] = useState<string | null>(null);
  const [editThreshold, setEditThreshold] = useState(false);
  const [thr, setThr] = useState({ viral_threshold: 60, hold_threshold: 45, max_per_day: 2, cooldown_hours: 6 });
  const [savingThr, setSavingThr] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const loadAll = useCallback(async () => {
    try {
      const [sRes, aRes, pRes, iRes] = await Promise.all([
        fetch('/api/viral/status'),
        fetch('/api/viral/activity'),
        fetch('/api/viral/posts'),
        fetch('/api/viral/insights'),
      ]);
      if (sRes.ok) {
        const s = await sRes.json();
        setStatus(s);
        setThr({
          viral_threshold: s.viral_threshold ?? 60,
          hold_threshold: s.hold_threshold ?? 45,
          max_per_day: s.max_per_day ?? 2,
          cooldown_hours: s.cooldown_hours ?? 6,
        });
      }
      if (aRes.ok) setActivities((await aRes.json()).activities || []);
      if (pRes.ok) setPosts((await pRes.json()).posts || []);
      if (iRes.ok) setStories((await iRes.json()).stories || []);
    } catch (e: any) {
      console.error('[SocialMedia]', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll, refreshKey]);

  useEffect(() => {
    const t = setInterval(() => setRefreshKey(k => k + 1), 60000);
    return () => clearInterval(t);
  }, []);

  const handleToggle = async () => {
    if (!status) return;
    setToggling(true);
    try {
      const res = await fetch('/api/viral/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !status.active }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(prev => prev ? { ...prev, active: data.active } : prev);
      }
    } finally { setToggling(false); }
  };

  const handleTestNow = async () => {
    setTesting(true); setTestMsg(null); setTestErr(null);
    try {
      const res = await fetch('/api/viral/test-now', { method: 'POST' });
      const data = await res.json();
      if (res.ok) setTestMsg(data.message || `Triggered (${data.trigger_id})`);
      else setTestErr(data.error || 'Failed to trigger');
    } catch {
      setTestErr('Failed to reach the trigger API');
    } finally { setTesting(false); }
  };

  const handleSaveThreshold = async () => {
    setSavingThr(true); setTestErr(null); setTestMsg(null);
    try {
      const res = await fetch('/api/viral/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(thr),
      });
      const data = await res.json();
      if (res.ok) {
        setEditThreshold(false);
        setTestMsg(`Thresholds saved — viral ${data.after.viral_threshold} / hold ${data.after.hold_threshold}. Live on next scan (≤5 min).`);
        setRefreshKey(k => k + 1);
      } else setTestErr(data.error || 'Save failed');
    } catch {
      setTestErr('Failed to save thresholds');
    } finally { setSavingThr(false); }
  };

  if (loading) return (
    <div className="space-y-6">
      <div className="h-8 bg-light-bg dark:bg-dark-bg rounded-lg w-64 animate-pulse" />
      <div className="h-32 bg-light-bg dark:bg-dark-bg rounded-xl animate-pulse" />
      <div className="h-64 bg-light-bg dark:bg-dark-bg rounded-xl animate-pulse" />
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Hero */}
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text flex items-center gap-2">
              <Share2 className="w-7 h-7 text-light-primary" /> Social Media Post
            </h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">
              Viral news auto-posts to Facebook, Instagram &amp; YouTube Community — independent of the video pipeline.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleTestNow}
              disabled={testing}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-light-primary hover:bg-light-primary/90 text-white font-medium text-sm transition-all disabled:opacity-50"
            >
              {testing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
              {testing ? 'Scanning...' : 'Run Now'}
            </button>
            <button
              onClick={() => setRefreshKey(k => k + 1)}
              className="px-3 py-2 rounded-xl border border-light-border dark:border-dark-border text-light-muted dark:text-dark-muted hover:text-light-text transition-colors"
              title="Refresh"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>
        </div>
      </motion.div>

      {(testMsg || testErr) && (
        <div className={`rounded-xl p-4 text-sm border ${testErr ? 'border-red-500/30 bg-red-500/10 text-red-400' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'}`}>
          {testErr || testMsg}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { icon: Newspaper, label: 'Posts Today', value: status?.posts_today ?? 0 },
          { icon: TrendingUp, label: 'Best Score', value: status?.highest_score_today ?? 0 },
          { icon: Activity, label: 'Scans Today', value: status?.scans_today ?? 0 },
          { icon: Signal, label: 'Articles', value: status?.articles_scanned_today ?? 0 },
        ].map(stat => (
          <div key={stat.label} className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</span>
              <stat.icon className="w-4 h-4 text-light-primary" />
            </div>
            <p className="text-2xl font-bold text-light-text dark:text-dark-text">{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Status bar */}
      <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold ${status?.active ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}>
              <span className={`w-2 h-2 rounded-full ${status?.active ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
              {status?.active ? 'AGENT ACTIVE' : 'AGENT PAUSED'}
            </span>
            <span className="text-xs text-light-muted dark:text-dark-muted">
              Last scan {formatTimeAgo(status?.last_check || '')}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleToggle}
              disabled={toggling}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border text-sm font-medium transition-all ${status?.active ? 'border-amber-500/40 text-amber-500 hover:bg-amber-500/10' : 'border-emerald-500/40 text-emerald-500 hover:bg-emerald-500/10'}`}
            >
              {status?.active ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
              {status?.active ? 'Pause' : 'Activate'}
            </button>
            <button
              onClick={() => setEditThreshold(!editThreshold)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-xl border border-light-border dark:border-dark-border text-sm font-medium text-light-muted dark:text-dark-muted hover:text-light-text transition-colors"
            >
              <BarChart3 className="w-4 h-4" /> Thresholds
            </button>
          </div>
        </div>

        {editThreshold && (
          <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="border-t border-light-border/40 dark:border-dark-border/40 mt-4 pt-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <label className="block">
                <span className="text-xs text-light-muted dark:text-dark-muted">Viral Threshold</span>
                <input type="number" value={thr.viral_threshold} min={0} max={100}
                  onChange={e => setThr({ ...thr, viral_threshold: Number(e.target.value) })}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text" />
              </label>
              <label className="block">
                <span className="text-xs text-light-muted dark:text-dark-muted">Hold Threshold</span>
                <input type="number" value={thr.hold_threshold} min={0} max={100}
                  onChange={e => setThr({ ...thr, hold_threshold: Number(e.target.value) })}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text" />
              </label>
              <label className="block">
                <span className="text-xs text-light-muted dark:text-dark-muted">Max / Day</span>
                <input type="number" value={thr.max_per_day} min={1} max={10}
                  onChange={e => setThr({ ...thr, max_per_day: Number(e.target.value) })}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text" />
              </label>
              <label className="block">
                <span className="text-xs text-light-muted dark:text-dark-muted">Cooldown (h)</span>
                <input type="number" value={thr.cooldown_hours} min={0} max={24} step={1}
                  onChange={e => setThr({ ...thr, cooldown_hours: Number(e.target.value) })}
                  className="mt-1 w-full px-3 py-2 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text" />
              </label>
            </div>
            <div className="mt-4 flex gap-3">
              <button onClick={handleSaveThreshold} disabled={savingThr}
                className="px-4 py-2 rounded-xl bg-light-primary hover:bg-light-primary/90 text-white text-sm font-medium transition-all disabled:opacity-50">
                {savingThr ? 'Saving...' : 'Save Thresholds'}
              </button>
              <button onClick={() => setEditThreshold(false)}
                className="px-4 py-2 rounded-xl border border-light-border dark:border-dark-border text-sm text-light-muted dark:text-dark-muted hover:text-light-text transition-colors">
                Cancel
              </button>
            </div>
          </motion.div>
        )}
      </div>

      {/* Live feed + posts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Live feed */}
        <div className="lg:col-span-2 rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden">
          <div className="p-4 border-b border-light-border/50 dark:border-dark-border/50 flex items-center justify-between">
            <h2 className="text-sm font-bold text-light-text dark:text-dark-text flex items-center gap-2">
              <Activity className="w-4 h-4 text-light-primary" /> Live Viral Feed
            </h2>
            <span className="text-xs text-light-muted dark:text-dark-muted">Top {stories.length} this scan</span>
          </div>
          <div className="divide-y divide-light-border/30 dark:divide-dark-border/30 max-h-[560px] overflow-y-auto">
            {stories.length === 0 ? (
              <div className="p-8 text-center text-sm text-light-muted dark:text-dark-muted">
                No scored stories yet — press <span className="font-bold text-light-primary">Run Now</span> or wait for the next scan (every 5 min).
              </div>
            ) : (
              stories.map(story => (
                <div key={story.id || story.title} className="p-4 hover:bg-light-bg/30 dark:hover:bg-dark-bg/30 transition-colors">
                  <div className="flex items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <p className="text-sm font-semibold text-light-text dark:text-dark-text">{story.title}</p>
                        <ScorePill score={story.virality_score || 0} status={status} />
                        <span className="text-xl font-bold text-light-primary dark:text-dark-primary">{story.virality_score || 0}</span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-light-muted dark:text-dark-muted mb-1">
                        <span className="flex items-center gap-1"><Newspaper className="w-3 h-3" />{story.source}</span>
                        <span className="flex items-center gap-1"><Globe className="w-3 h-3" />{story.category}</span>
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{formatTimeAgo(story.scanned_at || '')}</span>
                        {story.link && (
                          <a href={story.link} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-light-primary hover:underline">
                            <ExternalLink className="w-3 h-3" />source
                          </a>
                        )}
                      </div>
                      <BreakdownBars breakdown={story.score_breakdown || {}} />
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Posts */}
        <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden">
          <div className="p-4 border-b border-light-border/50 dark:border-dark-border/50">
            <h2 className="text-sm font-bold text-light-text dark:text-dark-text flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-light-primary" /> Published Posts
            </h2>
          </div>
          <div className="max-h-[560px] overflow-y-auto divide-y divide-light-border/30 dark:divide-dark-border/30">
            {posts.length === 0 ? (
              <div className="p-8 text-center text-sm text-light-muted dark:text-dark-muted">No posts yet</div>
            ) : (
              posts.map(post => (
                <div key={post.id} className="p-4">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="text-sm font-medium text-light-text dark:text-dark-text truncate">{post.title}</p>
                  </div>
                  <div className="flex items-center gap-3 text-xs text-light-muted dark:text-dark-muted mb-2">
                    <span>{post.source}</span>
                    <span>{formatTimeAgo(post.posted_at)}</span>
                    <span className="font-bold text-light-primary">{post.virality_score || 0}pts</span>
                  </div>
                  {post.platform_results && (
                    <div className="flex flex-wrap items-center gap-2">
                      {Object.entries(post.platform_results).map(([platform, r]) => (
                        <a key={platform} href={r.url}
                          target="_blank" rel="noreferrer"
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${r.success ? 'bg-emerald-500/15 text-emerald-400' : 'bg-red-500/15 text-red-400'}`}
                          title={r.error || platform}>
                          {r.success ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                          {platform}
                        </a>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Activity timeline */}
      <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden">
        <div className="p-4 border-b border-light-border/50 dark:border-dark-border/50 flex items-center justify-between">
          <h2 className="text-sm font-bold text-light-text dark:text-dark-text flex items-center gap-2">
            <Activity className="w-4 h-4 text-light-primary" /> Activity
          </h2>
          {status && status.errors_today > 0 && (
            <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-red-500/15 text-red-400">{status.errors_today} errors today</span>
          )}
        </div>
        <div className="max-h-64 overflow-y-auto p-2 space-y-1">
          {activities.length === 0 ? (
            <div className="p-4 text-center text-sm text-light-muted dark:text-dark-muted">No activity yet</div>
          ) : (
            activities.map(a => (
              <div key={a.id} className="px-3 py-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/30 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-light-text dark:text-dark-text truncate">{a.action}</span>
                  <span className="text-light-muted dark:text-dark-muted shrink-0">{formatTimeAgo(a.timestamp)}</span>
                </div>
                {Object.keys(a.details || {}).length > 0 && (
                  <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1 truncate">
                    {JSON.stringify(a.details)}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}