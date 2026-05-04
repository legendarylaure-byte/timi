'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, getDocs, addDoc, serverTimestamp, orderBy, query, limit, onSnapshot } from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import Image from 'next/image';

interface TrendItem {
  id: string;
  title: string;
  category: string;
  search_volume: number;
  growth: number;
  competition: 'low' | 'medium' | 'high';
  suggested_format: 'shorts' | 'long' | 'both';
  score: number;
  keywords: string[];
  created_at?: any;
}

const trendingIcons: Record<string, string> = {
  'Self-Learning': '🧠',
  'Bedtime Stories': '🌙',
  'Mythology Stories': '⚡',
  'Animated Fables': '🐾',
  'Science for Kids': '🔬',
  'Rhymes & Songs': '🎵',
  'Colors & Shapes': '🎨',
  'Tech & AI': '🤖',
  'Gaming': '🎮',
  'Cooking & Food': '🍳',
  'DIY & Crafts': '✂️',
  'Health & Wellness': '💪',
  'Travel & Adventure': '✈️',
  'Finance & Business': '💰',
  'Comedy & Entertainment': '😂',
  'Music & Dance': '💃',
};

export default function TrendsPage() {
  const [trends, setTrends] = useState<TrendItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [sortBy, setSortBy] = useState<'score' | 'growth' | 'volume'>('score');
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadTrends();
    const unsub = onSnapshot(collection(db, 'trends'), (snap) => {
      if (!snap.empty) {
        const items = snap.docs.map(d => ({ id: d.id, ...d.data() } as TrendItem));
        setTrends(items);
      }
      setLoading(false);
    });
    return () => unsub();
  }, []);

  const loadTrends = async () => {
    try {
      const q = query(collection(db, 'trends'), orderBy('created_at', 'desc'), limit(50));
      const snap = await getDocs(q);
      if (!snap.empty) {
        setTrends(snap.docs.map(d => ({ id: d.id, ...d.data() } as TrendItem)));
      }
    } catch {
      setTrends([]);
    }
  };

  const discoverTrends = async () => {
    setRefreshing(true);
    try {
      const response = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'discover_trends' }),
      });
      if (response.ok) {
        await loadTrends();
      }
    } catch (e) {
      console.error('Trend discovery failed:', e);
    }
    setRefreshing(false);
  };

  const filtered = trends
    .filter(t => selectedCategory === 'All' || t.category === selectedCategory)
    .sort((a, b) => {
      if (sortBy === 'score') return b.score - a.score;
      if (sortBy === 'growth') return b.growth - a.growth;
      return b.search_volume - a.search_volume;
    });

  const totalVolume = trends.reduce((s, t) => s + t.search_volume, 0);
  const avgGrowth = trends.length > 0 ? Math.round(trends.reduce((s, t) => s + t.growth, 0) / trends.length) : 0;
  const lowCompetition = trends.filter(t => t.competition === 'low').length;
  const topScore = trends.length > 0 ? Math.max(...trends.map(t => t.score)) : 0;

  const formatVolume = (n: number) => n >= 1000000 ? (n / 1000000).toFixed(1) + 'M' : n >= 1000 ? (n / 1000).toFixed(0) + 'K' : n.toString();

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500/20 to-pink-500/20 flex items-center justify-center">
              <span className="text-2xl">🔥</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Trend Discovery</h1>
              <p className="text-light-muted dark:text-dark-muted mt-1">AI-powered trending topic discovery for kids&apos; content</p>
            </div>
          </div>
          <button
            onClick={discoverTrends}
            disabled={refreshing}
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-2"
          >
            <motion.span animate={refreshing ? { rotate: 360 } : {}} transition={{ duration: 1, repeat: refreshing ? Infinity : 0 }}>
              🔍
            </motion.span>
            {refreshing ? 'Discovering...' : 'Discover Trends'}
          </button>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total Search Volume', value: formatVolume(totalVolume), icon: '📊', color: 'text-blue-400' },
          { label: 'Avg Growth', value: `+${avgGrowth}%`, icon: '📈', color: 'text-emerald-400' },
          { label: 'Low Competition', value: lowCompetition.toString(), icon: '🎯', color: 'text-purple-400' },
          { label: 'Top Opportunity', value: topScore.toString(), icon: '⭐', color: 'text-yellow-400' },
        ].map((stat) => (
          <motion.div key={stat.label} className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{stat.icon}</span>
              <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
            </div>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </motion.div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex gap-2 flex-wrap">
          {['All', ...CONTENT_CATEGORIES.map(c => c.name)].map(cat => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                selectedCategory === cat
                  ? 'bg-gradient-to-r from-orange-500 to-pink-500 text-white'
                  : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-muted dark:text-dark-muted'
              }`}
            >
              {trendingIcons[cat] || '🔥'} {cat}
            </button>
          ))}
        </div>
        <div className="ml-auto flex gap-2">
          {(['score', 'growth', 'volume'] as const).map(s => (
            <button
              key={s}
              onClick={() => setSortBy(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                sortBy === s
                  ? 'bg-light-primary/20 text-light-primary border border-light-primary/30'
                  : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-muted dark:text-dark-muted'
              }`}
            >
              {s === 'volume' ? 'Volume' : s}
            </button>
          ))}
        </div>
      </div>

      {/* Trend Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="text-3xl">🔍</motion.div>
        </div>
      ) : filtered.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-12 text-center">
          <div className="text-5xl mb-4">🔥</div>
          <h3 className="text-lg font-bold text-light-text dark:text-dark-text mb-2">No Trends Discovered Yet</h3>
          <p className="text-sm text-light-muted dark:text-dark-muted max-w-md mx-auto mb-4">
            Click &quot;Discover Trends&quot; to find trending topics for your content.
          </p>
          <button
            onClick={discoverTrends}
            disabled={refreshing}
            className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-orange-500 to-pink-500 text-white text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {refreshing ? 'Discovering...' : 'Discover Trends'}
          </button>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <AnimatePresence>
            {filtered.map((trend, i) => (
              <motion.div
                key={trend.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="p-5 rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 hover:border-orange-500/30 transition-all cursor-pointer group"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">{trendingIcons[trend.category] || '🔥'}</span>
                    <div>
                      <h3 className="text-sm font-semibold text-light-text dark:text-dark-text group-hover:text-orange-400 transition-colors">{trend.title}</h3>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted">{trend.category}</p>
                    </div>
                  </div>
                  <span className={`text-lg font-bold ${trend.score >= 85 ? 'text-emerald-400' : trend.score >= 70 ? 'text-yellow-400' : 'text-red-400'}`}>
                    {trend.score}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 mb-3">
                  <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                    <p className="text-[10px] text-light-muted dark:text-dark-muted">Volume</p>
                    <p className="text-sm font-bold text-light-text dark:text-dark-text">{formatVolume(trend.search_volume)}</p>
                  </div>
                  <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                    <p className="text-[10px] text-light-muted dark:text-dark-muted">Growth</p>
                    <p className="text-sm font-bold text-emerald-400">+{trend.growth}%</p>
                  </div>
                  <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                    <p className="text-[10px] text-light-muted dark:text-dark-muted">Competition</p>
                    <p className={`text-xs font-bold ${trend.competition === 'low' ? 'text-emerald-400' : trend.competition === 'medium' ? 'text-yellow-400' : 'text-red-400'}`}>
                      {trend.competition}
                    </p>
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 mb-3">
                  {trend.keywords.slice(0, 3).map(kw => (
                    <span key={kw} className="text-[10px] px-2 py-0.5 rounded-full bg-orange-500/10 text-orange-400 border border-orange-500/20">
                      #{kw}
                    </span>
                  ))}
                </div>

                <div className="flex items-center justify-between">
                  <span className={`text-[10px] px-2 py-1 rounded-full font-medium ${
                    trend.suggested_format === 'shorts' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                    trend.suggested_format === 'long' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                    'bg-gradient-to-r from-purple-500/10 to-blue-500/10 text-pink-400 border border-pink-500/20'
                  }`}>
                    {trend.suggested_format === 'both' ? 'Shorts + Long' : trend.suggested_format === 'shorts' ? 'Best for Shorts' : 'Best for Long'}
                  </span>
                  <button className="text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors">
                    Create →
                  </button>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
