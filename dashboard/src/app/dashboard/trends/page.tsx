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
};

const mockTrends: TrendItem[] = [
  { id: '1', title: 'ABC Phonics with Animals', category: 'Self-Learning', search_volume: 245000, growth: 34, competition: 'low', suggested_format: 'shorts', score: 92, keywords: ['abc', 'phonics', 'animals', 'learn'] },
  { id: '2', title: 'Sleepy Cloud Bedtime Story', category: 'Bedtime Stories', search_volume: 180000, growth: 28, competition: 'medium', suggested_format: 'long', score: 88, keywords: ['bedtime', 'sleep', 'cloud', 'calm'] },
  { id: '3', title: 'Norse Gods for Kids', category: 'Mythology Stories', search_volume: 95000, growth: 67, competition: 'low', suggested_format: 'both', score: 85, keywords: ['thor', 'odin', 'norse', 'myths'] },
  { id: '4', title: 'The Tortoise and the Hare 3D', category: 'Animated Fables', search_volume: 320000, growth: 12, competition: 'high', suggested_format: 'shorts', score: 78, keywords: ['fable', 'tortoise', 'hare', 'moral'] },
  { id: '5', title: 'Why is the Sky Blue?', category: 'Science for Kids', search_volume: 410000, growth: 45, competition: 'medium', suggested_format: 'shorts', score: 94, keywords: ['sky', 'blue', 'science', 'why'] },
  { id: '6', title: 'Counting to 10 with Dinosaurs', category: 'Rhymes & Songs', search_volume: 290000, growth: 52, competition: 'low', suggested_format: 'shorts', score: 91, keywords: ['count', 'dinosaurs', 'numbers', 'song'] },
  { id: '7', title: 'Learning Shapes with Robots', category: 'Colors & Shapes', search_volume: 175000, growth: 38, competition: 'medium', suggested_format: 'shorts', score: 82, keywords: ['shapes', 'robots', 'circle', 'square'] },
  { id: '8', title: 'Greek Mythology: Hercules', category: 'Mythology Stories', search_volume: 130000, growth: 71, competition: 'low', suggested_format: 'long', score: 87, keywords: ['hercules', 'greek', 'hero', 'myth'] },
  { id: '9', title: 'Solar System Adventure', category: 'Science for Kids', search_volume: 380000, growth: 29, competition: 'medium', suggested_format: 'both', score: 86, keywords: ['solar system', 'planets', 'space', 'adventure'] },
  { id: '10', title: 'Twinkle Twinkle Remix', category: 'Rhymes & Songs', search_volume: 520000, growth: 18, competition: 'high', suggested_format: 'shorts', score: 74, keywords: ['twinkle', 'lullaby', 'remix', 'nursery'] },
];

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
      } else {
        setTrends(mockTrends);
        // Seed Firestore with mock trends
        for (const t of mockTrends) {
          await addDoc(collection(db, 'trends'), { ...t, created_at: serverTimestamp() });
        }
      }
    } catch {
      setTrends(mockTrends);
    }
  };

  const discoverTrends = async () => {
    setRefreshing(true);
    // Simulate trend discovery
    await new Promise(r => setTimeout(r, 2000));
    const newTrends = mockTrends.map(t => ({
      ...t,
      growth: Math.min(100, t.growth + Math.floor(Math.random() * 20 - 5)),
      search_volume: Math.floor(t.search_volume * (0.9 + Math.random() * 0.2)),
      score: Math.min(100, Math.max(50, t.score + Math.floor(Math.random() * 10 - 5))),
    }));
    setTrends(newTrends);
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
              <p className="text-light-muted dark:text-dark-muted mt-1">AI-powered trending topic discovery for kids' content</p>
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
