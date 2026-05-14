'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, getDoc } from 'firebase/firestore';

interface RevenueData {
  totalRevenue: number;
  currentMonth: number;
  lastMonth: number;
  rpm: number;
  cpm: number;
  estimatedYearly: number;
  dailyRevenue: DailyEntry[];
  platformBreakdown: PlatformRevenue[];
}

interface Milestone {
  label: string;
  target: number;
  current: number;
  icon: string;
  achieved: boolean;
}

interface DailyEntry {
  date: string;
  revenue: number;
  views: number;
}

interface PlatformRevenue {
  platform: string;
  icon: string;
  revenue: number;
  percentage: number;
  rpm: number;
}

interface VideoStats {
  totalVideos: number;
  totalViews: number;
  uploadedCount: number;
}

export default function MonetizationPage() {
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [videoStats, setVideoStats] = useState<VideoStats | null>(null);
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubRevenue = onSnapshot(doc(db, 'monetization', 'revenue'), (snap) => {
      if (snap.exists()) {
        setRevenue(snap.data() as RevenueData);
      }
      setLoading(false);
    });

    const unsubChannel = onSnapshot(doc(db, 'system', 'channel_stats'), (snap) => {
      if (snap.exists()) {
        const d = snap.data();
        setMilestones(prev => {
          const m = [...prev];
          const subsIdx = m.findIndex(x => x.label.startsWith('1,000 Subscribers'));
          if (subsIdx >= 0) m[subsIdx] = { ...m[subsIdx], current: Number(d.subscribers) || 0, achieved: (Number(d.subscribers) || 0) >= 1000 };
          const whIdx = m.findIndex(x => x.label.startsWith('4,000 Watch Hours'));
          if (whIdx >= 0) m[whIdx] = { ...m[whIdx], current: Math.round(Number(d.total_watch_hours) || 0), achieved: (Number(d.total_watch_hours) || 0) >= 4000 };
          return m;
        });
      }
    });

    const unsubVideos = onSnapshot(collection(db, 'videos'), (snap) => {
      let totalViews = 0;
      let uploadedCount = 0;
      snap.forEach(doc => {
        const d = doc.data();
        totalViews += d.views || 0;
        if (d.status === 'uploaded' || d.status === 'completed') uploadedCount++;
      });
      setVideoStats({
        totalVideos: snap.size,
        totalViews,
        uploadedCount,
      });
    });

    return () => {
      unsubRevenue();
      unsubChannel();
      unsubVideos();
    };
  }, []);

  useEffect(() => {
    if (videoStats) {
      const subsTarget = 1000;
      const watchHoursTarget = 4000;
      const viewsTarget = 100000;
      const revenue100Target = 100;
      const revenue1kTarget = 1000;
      const totalRevTarget = 10000;

      const currentMonth = revenue?.currentMonth || 0;
      const totalRevenue = revenue?.totalRevenue || 0;

      setMilestones([
        { label: '1,000 Subscribers', target: subsTarget, current: 0, icon: '👥', achieved: false },
        { label: '4,000 Watch Hours', target: watchHoursTarget, current: 0, icon: '⏰', achieved: false },
        { label: '100K Total Views', target: viewsTarget, current: videoStats.totalViews, icon: '👁️', achieved: videoStats.totalViews >= viewsTarget },
        { label: '$100/month', target: revenue100Target, current: currentMonth, icon: '💵', achieved: currentMonth >= revenue100Target },
        { label: '$1,000/month', target: revenue1kTarget, current: currentMonth, icon: '💰', achieved: currentMonth >= revenue1kTarget },
        { label: '$10,000 Total', target: totalRevTarget, current: totalRevenue, icon: '🏆', achieved: totalRevenue >= totalRevTarget },
      ]);
    }
  }, [revenue, videoStats]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="text-3xl">💰</motion.div>
      </div>
    );
  }

  if (!revenue) {
    return (
      <div className="space-y-6 max-w-6xl">
        <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
          <div className="flex items-center gap-4 mb-2">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-yellow-500/20 to-green-500/20 flex items-center justify-center">
              <span className="text-2xl">💰</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Monetization</h1>
              <p className="text-light-muted dark:text-dark-muted mt-1">Revenue tracking and growth milestones</p>
            </div>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-12 text-center"
        >
          <div className="text-6xl mb-4">💰</div>
          <h2 className="text-xl font-bold text-light-text dark:text-dark-text mb-2">No Revenue Data Yet</h2>
          <p className="text-light-muted dark:text-dark-muted max-w-md mx-auto mb-6">
            Revenue data will appear here once your videos start earning. Connect your YouTube AdSense account to enable revenue tracking.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-2xl mx-auto">
            <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
              <p className="text-2xl mb-1">📹</p>
              <p className="text-sm font-medium text-light-text dark:text-dark-text">Upload Videos</p>
              <p className="text-xs text-light-muted dark:text-dark-muted mt-1">Content must be published and monetized</p>
            </div>
            <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
              <p className="text-2xl mb-1">💳</p>
              <p className="text-sm font-medium text-light-text dark:text-dark-text">Connect AdSense</p>
              <p className="text-xs text-light-muted dark:text-dark-muted mt-1">Link your Google AdSense account</p>
            </div>
            <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
              <p className="text-2xl mb-1">📊</p>
              <p className="text-sm font-medium text-light-text dark:text-dark-text">Track Revenue</p>
              <p className="text-xs text-light-muted dark:text-dark-muted mt-1">Revenue appears here automatically</p>
            </div>
          </div>
        </motion.div>

        <CPMInfoTable />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-yellow-500/20 to-green-500/20 flex items-center justify-center">
            <span className="text-2xl">💰</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Monetization</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Revenue tracking and growth milestones</p>
          </div>
        </div>
      </motion.div>

      {/* Revenue Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total Revenue', value: `$${revenue.totalRevenue.toLocaleString()}`, icon: '💰', color: 'text-emerald-400' },
          { label: 'This Month', value: `$${revenue.currentMonth.toLocaleString()}`, icon: '📅', color: 'text-blue-400' },
          { label: 'RPM', value: `$${revenue.rpm.toFixed(2)}`, icon: '📊', color: 'text-purple-400' },
          { label: 'Est. Yearly', value: `$${revenue.estimatedYearly.toLocaleString()}`, icon: '🚀', color: 'text-yellow-400' },
        ].map(stat => (
          <motion.div key={stat.label} className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{stat.icon}</span>
              <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
            </div>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Revenue Chart */}
      {revenue.dailyRevenue && revenue.dailyRevenue.length > 0 && (
        <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Revenue Trend (Last 14 Days)</h2>
          <div className="flex items-end gap-2 h-40">
            {revenue.dailyRevenue.map((entry, i) => {
              const maxRev = Math.max(...revenue.dailyRevenue.map(d => d.revenue));
              const height = maxRev > 0 ? (entry.revenue / maxRev) * 100 : 0;
              return (
                <motion.div
                  key={entry.date}
                  initial={{ height: 0 }}
                  animate={{ height: `${height}%` }}
                  transition={{ delay: i * 0.05, duration: 0.5 }}
                  className="flex-1 rounded-t-md bg-gradient-to-t from-emerald-500/60 to-emerald-400/80 relative group cursor-pointer min-w-[20px]"
                >
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                    <div className="px-2 py-1 rounded bg-dark-bg text-xs text-white whitespace-nowrap">
                      ${entry.revenue.toFixed(0)} · {entry.views.toLocaleString()} views
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
          <div className="flex gap-2 mt-2">
            {revenue.dailyRevenue.map((entry, i) => (
              <div key={entry.date} className="flex-1 text-center text-[9px] text-light-muted dark:text-dark-muted">
                {entry.date.slice(5)}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Breakdown */}
        {revenue.platformBreakdown && revenue.platformBreakdown.length > 0 && (
          <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Revenue by Platform</h2>
            <div className="space-y-4">
              {revenue.platformBreakdown.map(platform => (
                <div key={platform.platform}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{platform.icon}</span>
                      <span className="text-sm font-medium text-light-text dark:text-dark-text">{platform.platform}</span>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-bold text-light-text dark:text-dark-text">${platform.revenue.toLocaleString()}</p>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted">RPM: ${platform.rpm.toFixed(2)}</p>
                    </div>
                  </div>
                  <div className="w-full h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${platform.percentage}%` }}
                      transition={{ duration: 0.8 }}
                      className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-green-400"
                    />
                  </div>
                  <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">{platform.percentage}% of total</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Milestones */}
        {milestones.length > 0 && (
          <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Monetization Milestones</h2>
            <div className="space-y-3">
              {milestones.map((m, i) => {
                const progress = Math.min(100, (m.current / m.target) * 100);
                return (
                  <motion.div
                    key={m.label}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{m.icon}</span>
                        <span className="text-sm font-medium text-light-text dark:text-dark-text">{m.label}</span>
                      </div>
                      {m.achieved ? (
                        <span className="text-xs font-bold text-emerald-400">✅ Done</span>
                      ) : (
                        <span className="text-xs font-bold text-light-muted dark:text-dark-muted">{Math.round(progress)}%</span>
                      )}
                    </div>
                    <div className="w-full h-1.5 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${progress}%` }}
                        transition={{ duration: 0.5, delay: i * 0.1 }}
                        className={`h-full rounded-full ${progress >= 100 ? 'bg-emerald-400' : 'bg-gradient-to-r from-yellow-500 to-orange-400'}`}
                      />
                    </div>
                    <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">
                      {formatNumber(m.current)} / {formatNumber(m.target)}
                    </p>
                  </motion.div>
                );
              })}
            </div>
          </div>
        )}
      </div>

      <CPMInfoTable />
    </div>
  );
}

function CPMInfoTable() {
  return (
    <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
      <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">CPM Rates for Kids&apos; Content (Reference)</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { platform: 'YouTube', cpm: '$1.50 - $4.00', rpm: '$0.80 - $2.50', icon: '🔴' },
          { platform: 'TikTok', cpm: '$0.50 - $2.00', rpm: '$0.20 - $0.80', icon: '🎵' },
          { platform: 'Instagram', cpm: '$1.00 - $3.00', rpm: '$0.50 - $1.50', icon: '📸' },
          { platform: 'Facebook', cpm: '$1.20 - $3.50', rpm: '$0.60 - $2.00', icon: '👤' },
        ].map(p => (
          <div key={p.platform} className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5 text-center">
            <span className="text-2xl mb-2 block">{p.icon}</span>
            <p className="text-sm font-bold text-light-text dark:text-dark-text mb-1">{p.platform}</p>
            <p className="text-xs text-light-muted dark:text-dark-muted">CPM: {p.cpm}</p>
            <p className="text-xs text-light-muted dark:text-dark-muted">RPM: {p.rpm}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatNumber(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}
