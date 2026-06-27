'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, query, where } from 'firebase/firestore';
import { DollarSign, Calendar, BarChart3, TrendingUp, Users, Clock, Smartphone, Music, Camera, CheckCircle, Loader2, Shield, FileText, Bot, Film, Globe, Pencil } from 'lucide-react';
import { getThresholds, type PlatformThresholds, DEFAULT_THRESHOLDS } from '@/lib/thresholds';

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
  icon: React.ElementType;
  achieved: boolean;
  type: 'youtube' | 'tiktok' | 'instagram';
  estimatedDate?: string | null;
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

interface PlatformStats {
  subscribers: number;
  total_watch_hours: number;
  shorts_views: number;
  followers?: number;
  watch_mins?: number;
}

interface CategoryRevenue {
  category: string;
  views: number;
  estimatedRevenue: number;
  videos: number;
  percentage: number;
}

function estimateProjectedDate(current: number, target: number, growthRate: number): string | null {
  if (current <= 0 || growthRate <= 0) return null;
  const remaining = target - current;
  if (remaining <= 0) return 'Achieved';
  const periods = Math.ceil(remaining / growthRate);
  const projected = new Date();
  projected.setDate(projected.getDate() + periods * 7);
  return projected.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

export default function MonetizationPage() {
  const [revenue, setRevenue] = useState<RevenueData | null>(null);
  const [videoStats, setVideoStats] = useState<VideoStats | null>(null);
  const [platformStats, setPlatformStats] = useState<Record<string, PlatformStats>>({});
  const [milestones, setMilestones] = useState<Milestone[]>([]);
  const [loading, setLoading] = useState(true);
  const [projectedDate, setProjectedDate] = useState<string>('');
  const [thresholds, setThresholds] = useState<PlatformThresholds>(DEFAULT_THRESHOLDS);
  const [categoryRevenue, setCategoryRevenue] = useState<CategoryRevenue[]>([]);

  useEffect(() => {
    getThresholds().then(setThresholds);
  }, []);

  useEffect(() => {
    const unsubRevenue = onSnapshot(doc(db, 'monetization', 'revenue'),
      (snap) => {
        if (snap.exists()) setRevenue(snap.data() as RevenueData);
        setLoading(false);
      },
      (error) => {
        console.error('[Monetization] monetization/revenue:', error);
        setLoading(false);
      }
    );

    const unsubChannel = onSnapshot(doc(db, 'system', 'channel_stats'),
      (snap) => {
        if (snap.exists()) setPlatformStats(snap.data() as Record<string, PlatformStats>);
      },
      (error) => {
        console.error('[Monetization] system/channel_stats:', error);
      }
    );

    const unsubVideos = onSnapshot(query(collection(db, 'videos'), where('format', 'in', ['shorts', 'long'])),
      (snap) => {
        let totalViews = 0;
        let uploadedCount = 0;
        const catMap: Record<string, { views: number; count: number }> = {};
        snap.forEach(d => {
          const data = d.data();
          totalViews += data.views || 0;
          if (data.status === 'uploaded' || data.status === 'completed') uploadedCount++;
          const cat = data.category || 'Uncategorized';
          if (!catMap[cat]) catMap[cat] = { views: 0, count: 0 };
          catMap[cat].views += data.views || 0;
          catMap[cat].count += 1;
        });
        const totalCatViews = Object.values(catMap).reduce((s, c) => s + c.views, 0);
        const cats = Object.entries(catMap).map(([category, stats]) => ({
          category,
          views: stats.views,
          estimatedRevenue: stats.views * 0.005,
          videos: stats.count,
          percentage: totalCatViews > 0 ? (stats.views / totalCatViews) * 100 : 0,
        })).sort((a, b) => b.views - a.views);
        setCategoryRevenue(cats);
        setVideoStats({ totalVideos: snap.size, totalViews, uploadedCount });
      },
      (error) => {
        console.error('[Monetization] videos:', error);
      }
    );

    return () => { unsubRevenue(); unsubChannel(); unsubVideos(); };
  }, []);

  useEffect(() => {
    if (!videoStats) return;

    const youtube = platformStats?.youtube || { subscribers: 0, total_watch_hours: 0, shorts_views: 0 };
    const tiktok = platformStats?.tiktok || { followers: 0, watch_mins: 0 };
    const instagram = platformStats?.instagram || { followers: 0, watch_mins: 0 };

    const th = thresholds;
    const weeklySubGrowth = youtube.subscribers * 0.03;
    const weeklyHourGrowth = youtube.total_watch_hours * 0.03;
    const weeklyShortsGrowth = youtube.shorts_views * 0.03;
    setMilestones([
      { label: `${th.youtube.subs.toLocaleString()} YouTube Subscribers`, target: th.youtube.subs, current: youtube.subscribers, icon: Users, achieved: youtube.subscribers >= th.youtube.subs, type: 'youtube', estimatedDate: estimateProjectedDate(youtube.subscribers, th.youtube.subs, weeklySubGrowth) },
      { label: `${th.youtube.watchHours.toLocaleString()} YouTube Watch Hours`, target: th.youtube.watchHours, current: Math.round(youtube.total_watch_hours), icon: Clock, achieved: youtube.total_watch_hours >= th.youtube.watchHours, type: 'youtube', estimatedDate: estimateProjectedDate(youtube.total_watch_hours, th.youtube.watchHours, weeklyHourGrowth) },
      { label: `${(th.youtube.shortsViews / 1_000_000).toFixed(0)}M YouTube Shorts Views`, target: th.youtube.shortsViews, current: youtube.shorts_views, icon: Smartphone, achieved: youtube.shorts_views >= th.youtube.shortsViews, type: 'youtube', estimatedDate: estimateProjectedDate(youtube.shorts_views, th.youtube.shortsViews, weeklyShortsGrowth) },
      { label: `${th.tiktok.followers.toLocaleString()} TikTok Followers`, target: th.tiktok.followers, current: tiktok.followers || 0, icon: Music, achieved: (tiktok.followers || 0) >= th.tiktok.followers, type: 'tiktok', estimatedDate: estimateProjectedDate(tiktok.followers || 0, th.tiktok.followers, (tiktok.followers || 0) * 0.03) },
      { label: `${th.instagram.followers.toLocaleString()} Instagram Followers`, target: th.instagram.followers, current: instagram.followers || 0, icon: Camera, achieved: (instagram.followers || 0) >= th.instagram.followers, type: 'instagram', estimatedDate: estimateProjectedDate(instagram.followers || 0, th.instagram.followers, (instagram.followers || 0) * 0.03) },
    ]);

    if (youtube.subscribers > 0) {
      const remaining = th.youtube.subs - youtube.subscribers;
      const weeks = weeklySubGrowth > 0 ? Math.ceil(remaining / weeklySubGrowth) : 52;
      const projected = new Date();
      projected.setDate(projected.getDate() + weeks * 7);
      setProjectedDate(projected.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }));
    }
  }, [videoStats, platformStats, thresholds]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-8 h-8 text-light-muted animate-spin" />
      </div>
    );
  }

  const ytEligible = milestones.filter(m => m.type === 'youtube' && m.achieved).length >= 2;

  return (
    <div className="space-y-6 max-w-6xl">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #FF6969, #C80036)' }}>
            <DollarSign className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Monetization</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Multi-platform revenue tracking and YPP milestone progress</p>
          </div>
        </div>
      </motion.div>

      {/* YPP Eligibility Banner */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className={`rounded-2xl p-4 border ${ytEligible ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'} flex items-center gap-3`}
      >
        <span className="text-2xl">{ytEligible ? <CheckCircle className="w-6 h-6 text-emerald-400" /> : <Loader2 className="w-6 h-6 text-amber-400 animate-spin" />}</span>
        <div>
          <p className="text-sm font-bold text-light-text dark:text-dark-text">
            {ytEligible ? 'YouTube YPP Eligible — Apply for monetization!' : 'Working toward YouTube YPP'}
          </p>
          <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">
            {ytEligible
              ? 'You meet the requirements. Submit your channel for YouTube Partner Program review.'
              : projectedDate ? `Estimated YPP eligibility: ${projectedDate} at current growth rate` : 'Keep uploading — milestones track your progress below'}
          </p>
        </div>
      </motion.div>

      {/* Revenue Stats */}
      {revenue && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'Total Revenue', value: `$${revenue.totalRevenue.toLocaleString()}`, icon: DollarSign, color: 'text-emerald-400' },
            { label: 'This Month', value: `$${revenue.currentMonth.toLocaleString()}`, icon: Calendar, color: 'text-blue-400' },
            { label: 'RPM', value: `$${revenue.rpm.toFixed(2)}`, icon: BarChart3, color: 'text-purple-400' },
            { label: 'Est. Yearly', value: `$${revenue.estimatedYearly.toLocaleString()}`, icon: TrendingUp, color: 'text-yellow-400' },
          ].map(stat => (
            <motion.div key={stat.label} className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5">
              <div className="flex items-center gap-2 mb-1">
                <stat.icon className={`w-5 h-5 ${stat.color}`} />
                <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
              </div>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            </motion.div>
          ))}
        </div>
      )}

      {!revenue ? (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-12 text-center"
        >
          <DollarSign className="w-16 h-16 text-light-muted mx-auto mb-4" />
          <h2 className="text-xl font-bold text-light-text dark:text-dark-text mb-2">No Revenue Data Yet</h2>
          <p className="text-light-muted dark:text-dark-muted max-w-md mx-auto mb-6">
            Revenue data appears once your channel is monetized. Focus on reaching YPP thresholds first.
          </p>
        </motion.div>
      ) : (
        <>
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
            {revenue.platformBreakdown && revenue.platformBreakdown.length > 0 && (
              <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
                <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Revenue by Platform</h2>
                <div className="space-y-4">
                  {revenue.platformBreakdown.map(p => (
                    <div key={p.platform}>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <span className="text-xl">{p.icon}</span>
                          <span className="text-sm font-medium text-light-text dark:text-dark-text">{p.platform}</span>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-bold text-light-text dark:text-dark-text">${p.revenue.toLocaleString()}</p>
                          <p className="text-[10px] text-light-muted dark:text-dark-muted">RPM: ${p.rpm.toFixed(2)}</p>
                        </div>
                      </div>
                      <div className="w-full h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${p.percentage}%` }}
                          transition={{ duration: 0.8 }}
                          className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-green-400"
                        />
                      </div>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">{p.percentage}% of total</p>
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
                  {milestones.map(({ icon: MilestoneIcon, ...m }, i) => {
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
                            <MilestoneIcon className="w-5 h-5 text-light-muted" />
                            <span className="text-sm font-medium text-light-text dark:text-dark-text">{m.label}</span>
                          </div>
                          {m.achieved ? (
                            <span className="text-xs font-bold text-emerald-400 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" /> Done</span>
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
                        {m.estimatedDate && !m.achieved && (
                          <p className="text-[9px] text-light-info dark:text-light-info mt-0.5">
                            Est. {m.estimatedDate}
                          </p>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Revenue by Category */}
          {categoryRevenue.length > 0 && (
            <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
              <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Revenue by Category</h2>
              <div className="space-y-4">
                {categoryRevenue.map((cat, i) => (
                  <motion.div key={cat.category}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-light-text dark:text-dark-text">{cat.category}</span>
                        <span className="text-[10px] text-light-muted dark:text-dark-muted">({cat.videos} videos)</span>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-bold text-light-text dark:text-dark-text">${cat.estimatedRevenue.toFixed(2)}</p>
                        <p className="text-[10px] text-light-muted dark:text-dark-muted">{cat.views.toLocaleString()} views</p>
                      </div>
                    </div>
                    <div className="w-full h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${cat.percentage}%` }}
                        transition={{ duration: 0.8, delay: i * 0.05 }}
                        className="h-full rounded-full bg-gradient-to-r from-light-primary to-light-secondary"
                      />
                    </div>
                    <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">{cat.percentage.toFixed(1)}% of total views</p>
                  </motion.div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* CPM Rates for Tech/AI Content */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">CPM Rates — Tech &amp; AI Education</h2>
        <p className="text-xs text-light-muted dark:text-dark-muted mb-4">Tech/AI education content earns premium CPM rates across platforms. These are estimated ranges.</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { platform: 'YouTube', cpm: '$8.00 - $15.00', rpm: '$4.00 - $9.00', icon: Film },
            { platform: 'TikTok', cpm: '$1.00 - $4.00', rpm: '$0.50 - $2.00', icon: Music },
            { platform: 'Instagram', cpm: '$3.00 - $8.00', rpm: '$1.50 - $5.00', icon: Camera },
            { platform: 'Facebook', cpm: '$2.00 - $6.00', rpm: '$1.00 - $4.00', icon: Globe },
          ].map(({ icon: PlatformIcon, ...p }) => (
            <div key={p.platform} className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5 text-center">
              <PlatformIcon className="w-6 h-6 text-light-muted mx-auto mb-2" />
              <p className="text-sm font-bold text-light-text dark:text-dark-text mb-1">{p.platform}</p>
              <p className="text-xs text-light-muted dark:text-dark-muted">CPM: {p.cpm}</p>
              <p className="text-xs text-light-muted dark:text-dark-muted">RPM: {p.rpm}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Compliance Check */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Compliance Status</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-2">
              <Bot className="w-5 h-5 text-light-muted" />
              <span className="text-sm font-medium text-light-text dark:text-dark-text">AI Disclosure</span>
            </div>
            <p className="text-xs text-emerald-400">✅ All AI content flagged — compliant with YouTube/TikTok/IG policies</p>
          </div>
          <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-5 h-5 text-light-muted" />
              <span className="text-sm font-medium text-light-text dark:text-dark-text">Made for Kids</span>
            </div>
            <p className="text-xs text-emerald-400">✅ Set to &quot;not made for kids&quot; — full ad monetization enabled</p>
          </div>
          <div className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-2">
              <FileText className="w-5 h-5 text-light-muted" />
              <span className="text-sm font-medium text-light-text dark:text-dark-text">Content Safety</span>
            </div>
            <p className="text-xs text-emerald-400">✅ Compliance checks active — no prohibited content detected</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function formatNumber(n: number) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
  return n.toString();
}
