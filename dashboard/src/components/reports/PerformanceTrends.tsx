'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, Eye, Users, DollarSign, Loader2 } from 'lucide-react';
import { auth } from '@/lib/firebase';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';

interface GrowthData {
  history: Array<{ date: string; subs: number; views: number; watchHours: number }>;
  projection: Array<{ date: string; subs: number; views: number }>;
  milestones: Array<{ target: number; metric: string; estimatedDate: string; confidence: string }>;
  freshness: string;
  currentStats: { subscribers: number; totalViews: number; watchHours: number; videoCount: number };
}

interface QualityData {
  trends: Array<{ date: string; avgQualityScore: number; avgViralityScore: number; avgViews: number; videoCount: number }>;
  freshness: string;
}

export function PerformanceTrends() {
  const [growth, setGrowth] = useState<GrowthData | null>(null);
  const [quality, setQuality] = useState<QualityData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [chartMode, setChartMode] = useState<'views' | 'subs' | 'watchHours'>('views');

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const user = auth.currentUser;
        if (!user) return;
        const token = await user.getIdToken();
        const headers = { authorization: `Bearer ${token}` };

        const [growthRes, qualityRes] = await Promise.all([
          fetch('/api/reports/growth-forecast', { headers }),
          fetch('/api/reports/quality-trends', { headers }),
        ]);

        if (!cancelled) {
          if (growthRes.ok) setGrowth(await growthRes.json());
          if (qualityRes.ok) setQuality(await qualityRes.json());
        }
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-sm text-red-400">Failed to load trends: {error}</p>
      </div>
    );
  }

  if (!growth) {
    return (
      <div className="glass rounded-xl p-12 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-light-muted" />
      </div>
    );
  }

  const chartData = growth.history.map(h => ({
    date: h.date.slice(5),
    views: h.views,
    subs: h.subs,
    watchHours: h.watchHours,
  }));

  const currentMetric = growth.currentStats;
  const yKey = chartMode === 'views' ? 'views' : chartMode === 'subs' ? 'subs' : 'watchHours';
  const yLabel = chartMode === 'views' ? 'Total Views' : chartMode === 'subs' ? 'Subscribers' : 'Watch Hours';

  const formatY = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return String(v);
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="glass rounded-xl p-4 border border-blue-500/20"
        >
          <div className="flex items-center gap-2 mb-1">
            <Eye className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-light-muted dark:text-dark-muted">Total Views</span>
          </div>
          <div className="text-xl font-bold text-light-text dark:text-dark-text">
            {formatY(currentMetric.totalViews)}
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="glass rounded-xl p-4 border border-emerald-500/20"
        >
          <div className="flex items-center gap-2 mb-1">
            <Users className="w-4 h-4 text-emerald-400" />
            <span className="text-xs text-light-muted dark:text-dark-muted">Subscribers</span>
          </div>
          <div className="text-xl font-bold text-light-text dark:text-dark-text">
            {formatY(currentMetric.subscribers)}
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="glass rounded-xl p-4 border border-purple-500/20"
        >
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-light-muted dark:text-dark-muted">Watch Hours</span>
          </div>
          <div className="text-xl font-bold text-light-text dark:text-dark-text">
            {formatY(currentMetric.watchHours)}
          </div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="glass rounded-xl p-4 border border-orange-500/20"
        >
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-orange-400" />
            <span className="text-xs text-light-muted dark:text-dark-muted">Videos</span>
          </div>
          <div className="text-xl font-bold text-light-text dark:text-dark-text">
            {currentMetric.videoCount}
          </div>
        </motion.div>
      </div>

      <div className="glass rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">Growth Over Time</h3>
          <div className="flex gap-1">
            {(['views', 'subs', 'watchHours'] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setChartMode(mode)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  chartMode === mode
                    ? 'bg-light-primary text-white'
                    : 'text-light-muted dark:text-dark-muted hover:bg-light-border/50'
                }`}
              >
                {mode === 'views' ? 'Views' : mode === 'subs' ? 'Subs' : 'Watch Hrs'}
              </button>
            ))}
          </div>
        </div>
        {chartData.length > 0 ? (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorMetric" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ec133e" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ec133e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                <YAxis tickFormatter={formatY} tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    fontSize: '12px',
                  }}
                  formatter={(value: any) => [formatY(Number(value) || 0), yLabel]}
                />
                <Area
                  type="monotone"
                  dataKey={yKey}
                  stroke="#ec133e"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorMetric)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-48 flex items-center justify-center text-sm text-light-muted">
            No growth history data yet. Data appears after the daily analytics pipeline runs.
          </div>
        )}
      </div>

      {quality && quality.trends.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4">Quality Score Trend</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={quality.trends} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorQuality" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    fontSize: '12px',
                  }}
                  formatter={(value: any) => [String(Number(value).toFixed(1)), '']}
                />
                <Area
                  type="monotone"
                  dataKey="avgQualityScore"
                  stroke="#10B981"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#colorQuality)"
                  name="Quality Score"
                />
                <Area
                  type="monotone"
                  dataKey="avgViralityScore"
                  stroke="#F59E0B"
                  strokeWidth={2}
                  fillOpacity={0}
                  name="Virality Score"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {growth.milestones.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-3">Projected Milestones</h3>
          <div className="space-y-2">
            {growth.milestones.map((m, i) => (
              <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-light-border/30 dark:bg-dark-border/30">
                <div>
                  <span className="text-sm font-medium text-light-text dark:text-dark-text">
                    {formatY(m.target)} {m.metric}
                  </span>
                  <span className="text-xs text-light-muted dark:text-dark-muted ml-2">
                    Confidence: {m.confidence}
                  </span>
                </div>
                <div className="text-sm text-light-primary font-medium">
                  Est. {m.estimatedDate}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
