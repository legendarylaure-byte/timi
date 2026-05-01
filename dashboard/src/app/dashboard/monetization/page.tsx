'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, setDoc, getDoc } from 'firebase/firestore';
import Image from 'next/image';

interface RevenueData {
  totalRevenue: number;
  currentMonth: number;
  lastMonth: number;
  rpm: number;
  cpm: number;
  estimatedYearly: number;
  milestones: Milestone[];
  dailyRevenue: DailyEntry[];
  platformBreakdown: PlatformRevenue[];
}

interface Milestone {
  label: string;
  target: number;
  current: number;
  icon: string;
  achieved: boolean;
  achievedDate?: string;
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

export default function MonetizationPage() {
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [showDemo, setShowDemo] = useState(false);

  useEffect(() => {
    loadRevenue();
  }, []);

  const loadRevenue = async () => {
    try {
      const snap = await getDoc(doc(db, 'monetization', 'revenue'));
      if (snap.exists()) {
        setRevenue(snap.data() as RevenueData);
      } else {
        const demo = generateDemoData();
        setRevenue(demo);
        setShowDemo(true);
        await setDoc(doc(db, 'monetization', 'revenue'), demo);
      }
    } catch {
      setRevenue(generateDemoData());
      setShowDemo(true);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="text-3xl">💰</motion.div>
      </div>
    );
  }

  if (!revenue) return null;

  const milestones = [
    { label: '1,000 Subscribers', target: 1000, current: 847, icon: '👥' },
    { label: '4,000 Watch Hours', target: 4000, current: 3200, icon: '⏰' },
    { label: '$100/month', target: 100, current: revenue.currentMonth, icon: '💵' },
    { label: '$1,000/month', target: 1000, current: revenue.currentMonth, icon: '💰' },
    { label: '$10,000 Total', target: 10000, current: revenue.totalRevenue, icon: '🏆' },
    { label: '100K Total Views', target: 100000, current: 78500, icon: '👁️' },
  ];

  return (
    <div className="space-y-6 max-w-6xl">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-yellow-500/20 to-green-500/20 flex items-center justify-center">
              <span className="text-2xl">💰</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Monetization</h1>
              <p className="text-light-muted dark:text-dark-muted mt-1">Revenue tracking and growth milestones</p>
            </div>
          </div>
          {showDemo && (
            <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-yellow-500/20 text-yellow-400 border border-yellow-500/30">
              Demo Mode — Connect YouTube API for real data
            </span>
          )}
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

      {/* Revenue Chart (simple bar) */}
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

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Breakdown */}
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

        {/* Milestones */}
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
      </div>

      {/* CPM Info */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">CPM Rates for Kids' Content</h2>
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
    </div>
  );
}

function generateDemoData(): RevenueData {
  const daily = [];
  for (let i = 13; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    daily.push({
      date: d.toISOString().slice(0, 10),
      revenue: Math.floor(Math.random() * 50) + 10,
      views: Math.floor(Math.random() * 5000) + 1000,
    });
  }
  const total = daily.reduce((s, d) => s + d.revenue, 0);
  const currentMonth = daily.filter(d => d.date.startsWith(new Date().toISOString().slice(0, 7))).reduce((s, d) => s + d.revenue, 0);

  return {
    totalRevenue: total + 1847,
    currentMonth: currentMonth,
    lastMonth: currentMonth + Math.floor(Math.random() * 100),
    rpm: 2.15,
    cpm: 3.80,
    estimatedYearly: (total + 1847) + currentMonth * 11,
    milestones: [],
    dailyRevenue: daily,
    platformBreakdown: [
      { platform: 'YouTube', icon: '🔴', revenue: Math.floor((total + 1847) * 0.72), percentage: 72, rpm: 2.45 },
      { platform: 'TikTok', icon: '🎵', revenue: Math.floor((total + 1847) * 0.15), percentage: 15, rpm: 0.65 },
      { platform: 'Instagram', icon: '📸', revenue: Math.floor((total + 1847) * 0.08), percentage: 8, rpm: 1.20 },
      { platform: 'Facebook', icon: '👤', revenue: Math.floor((total + 1847) * 0.05), percentage: 5, rpm: 0.95 },
    ],
  };
}

function formatNumber(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}
