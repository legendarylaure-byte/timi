'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Flame, Clock, Eye, Loader2, AlertTriangle, CheckCircle } from 'lucide-react';
import { auth } from '@/lib/firebase';

interface GapItem {
  category: string;
  daysSinceLastPost: number;
  lastPosted: string | null;
  isTrending: boolean;
  avgViews: number;
  avgScore: number;
  totalVideos: number;
  recommendation: string;
}

export function ContentGaps() {
  const [gaps, setGaps] = useState<GapItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const user = auth.currentUser;
        if (!user) return;
        const token = await user.getIdToken();
        const res = await fetch('/api/reports/content-gaps', {
          headers: { authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setGaps(json.gaps || []);
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-sm text-red-400">Failed to load content gaps: {error}</p>
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

  const formatNum = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return String(v);
  };

  const getGapColor = (days: number) => {
    if (days === 999) return 'text-red-400';
    if (days > 30) return 'text-orange-400';
    if (days > 14) return 'text-yellow-400';
    return 'text-emerald-400';
  };

  const getGapBg = (days: number) => {
    if (days === 999) return 'bg-red-500/5 border-red-500/10';
    if (days > 30) return 'bg-orange-500/5 border-orange-500/10';
    if (days > 14) return 'bg-yellow-500/5 border-yellow-500/10';
    return 'bg-emerald-500/5 border-emerald-500/10';
  };

  const neverPosted = gaps.filter(g => g.daysSinceLastPost === 999);
  const staleCategories = gaps.filter(g => g.daysSinceLastPost > 14 && g.daysSinceLastPost !== 999);
  const activeCategories = gaps.filter(g => g.daysSinceLastPost <= 14);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="glass rounded-xl p-4 border border-emerald-500/20"
        >
          <div className="text-xs text-light-muted uppercase tracking-wider mb-1">Active</div>
          <div className="text-2xl font-bold text-emerald-400">{activeCategories.length}</div>
          <div className="text-xs text-light-muted mt-1">Categories posted within 14 days</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="glass rounded-xl p-4 border border-yellow-500/20"
        >
          <div className="text-xs text-light-muted uppercase tracking-wider mb-1">Stale</div>
          <div className="text-2xl font-bold text-yellow-400">{staleCategories.length}</div>
          <div className="text-xs text-light-muted mt-1">Categories over 14 days since last post</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="glass rounded-xl p-4 border border-red-500/20"
        >
          <div className="text-xs text-light-muted uppercase tracking-wider mb-1">Untapped</div>
          <div className="text-2xl font-bold text-red-400">{neverPosted.length}</div>
          <div className="text-xs text-light-muted mt-1">Categories never posted in</div>
        </motion.div>
      </div>

      <div className="glass rounded-xl p-6">
        <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4">Category Status</h3>
        <div className="space-y-2">
          {gaps.length === 0 ? (
            <div className="text-center py-8">
              <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-sm text-light-muted">All categories are active — great content coverage!</p>
            </div>
          ) : (
            gaps.map((gap, i) => (
              <motion.div
                key={gap.category}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.03 }}
                className={`flex items-center justify-between p-3 rounded-lg border ${getGapBg(gap.daysSinceLastPost)}`}
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {gap.isTrending && gap.daysSinceLastPost > 14 && (
                    <Flame className="w-4 h-4 text-orange-400 shrink-0" />
                  )}
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-light-text dark:text-dark-text">
                        {gap.category}
                      </span>
                      {gap.isTrending && (
                        <span className="text-[10px] bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded-full font-medium">
                          Trending
                        </span>
                      )}
                      {gap.daysSinceLastPost === 999 && (
                        <span className="text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full font-medium">
                          Never Posted
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-light-muted mt-0.5">{gap.recommendation}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4 shrink-0 ml-4">
                  <div className="text-right">
                    <div className={`text-sm font-medium ${getGapColor(gap.daysSinceLastPost)}`}>
                      {gap.daysSinceLastPost === 999 ? '∞' : `${gap.daysSinceLastPost}d`}
                    </div>
                    <div className="text-[10px] text-light-muted">since last post</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-blue-400 flex items-center gap-1">
                      <Eye className="w-3 h-3" />
                      {formatNum(gap.avgViews)}
                    </div>
                    <div className="text-[10px] text-light-muted">avg views</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-medium text-light-muted">{gap.totalVideos}</div>
                    <div className="text-[10px] text-light-muted">videos</div>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
