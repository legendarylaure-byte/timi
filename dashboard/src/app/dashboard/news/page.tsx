'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import { NEWS_CATEGORIES, PUBLISH_SLOTS, DAILY_SCHEDULE } from '@/lib/constants';
import Image from 'next/image';
import { Newspaper, Globe, Flag, Loader2, ExternalLink, CalendarClock } from 'lucide-react';

interface NewsVideo {
  id: string;
  title: string;
  format: string;
  status: string;
  category: string;
  youtube_url: string;
  news_source: string;
  created_at: any;
}

const categoryEmoji: Record<string, string> = {
  'World News (24hr)': '🌍',
  'Nepal News': '🇳🇵',
};

export default function NewsPage() {
  const [videos, setVideos] = useState<NewsVideo[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'shorts' | 'long'>('all');

  useEffect(() => {
    const q = query(collection(db, 'videos'), orderBy('created_at', 'desc'), limit(100));
    const unsub = onSnapshot(q,
      (snap) => {
        const items: NewsVideo[] = [];
        snap.docs.forEach((d) => {
          const data = d.data() as NewsVideo;
          if (NEWS_CATEGORIES.some((c) => c.name === data.category)) {
            items.push({ ...data, id: d.id });
          }
        });
        setVideos(items);
        setLoading(false);
      },
      (error) => {
        console.error('[News]', error);
        setLoading(false);
      }
    );
    return () => unsub();
  }, []);

  const newsSlots = PUBLISH_SLOTS.filter((s) => s.category.includes('News') || s.category.includes('World / Nepal'));

  const worldShorts = videos.filter((v) => v.category === 'World News (24hr)' && v.format === 'shorts');
  const nepalShorts = videos.filter((v) => v.category === 'Nepal News' && v.format === 'shorts');
  const newsLongs = videos.filter((v) => v.format === 'long');
  const published = videos.filter((v) => v.status === 'uploaded');

  const filtered = videos.filter((v) => filter === 'all' || v.format === filter);

  const formatDate = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const getYoutubeUrl = (v: NewsVideo): string | undefined => {
    if (v.youtube_url) return v.youtube_url;
    return undefined;
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text flex items-center gap-2">
              <Newspaper className="w-7 h-7 text-light-primary" /> News Desk
            </h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">
              Verified World &amp; Nepal news — scraped from reputable publishers, narrated accurately. 2 shorts + 1 long every day.
            </p>
          </div>
        </div>
      </motion.div>

      {/* Schedule banner */}
      <motion.div
        className="rounded-2xl p-5 border border-light-primary/20 dark:border-light-primary/30"
        style={{ background: 'linear-gradient(135deg, rgba(0,204,204,0.08), rgba(26,26,26,0.4))' }}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      >
        <div className="flex items-center gap-2 mb-3">
          <CalendarClock className="w-4 h-4 text-light-primary" />
          <h2 className="text-sm font-semibold text-light-text dark:text-dark-text">Daily News Schedule</h2>
          <span className="ml-2 text-xs px-2 py-0.5 rounded-full bg-light-primary/15 text-light-primary">{DAILY_SCHEDULE.label}</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {newsSlots.map((slot) => (
            <div key={slot.id} className="p-3 rounded-xl bg-light-bg/60 dark:bg-dark-bg/60 border border-light-border/30 dark:border-white/5">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-light-text dark:text-dark-text">{slot.label}</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-light-primary/10 text-light-primary">{slot.format}</span>
              </div>
              <p className="text-lg font-bold text-light-text dark:text-dark-text">{slot.npt} <span className="text-xs font-normal text-light-muted dark:text-dark-muted">{slot.utc}</span></p>
              <p className="text-[10px] text-light-muted dark:text-dark-muted">{slot.category}</p>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'World News Shorts', value: worldShorts.length, icon: Globe, color: 'text-blue-400' },
          { label: 'Nepal News Shorts', value: nepalShorts.length, icon: Flag, color: 'text-purple-400' },
          { label: 'News Longs', value: newsLongs.length, icon: Newspaper, color: 'text-emerald-400' },
          { label: 'Published', value: published.length, icon: ExternalLink, color: 'text-yellow-400' },
        ].map((stat) => {
          const StatIcon = stat.icon;
          return (
            <motion.div key={stat.label} className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5">
              <div className="flex items-center gap-2 mb-1">
                <StatIcon className={`w-5 h-5 ${stat.color}`} />
                <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
              </div>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            </motion.div>
          );
        })}
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {(['all', 'shorts', 'long'] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
              filter === f
                ? 'bg-light-primary text-white'
                : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-muted dark:text-dark-muted'
            }`}
          >
            {f === 'all' ? `All (${videos.length})` : f}
          </button>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 text-light-muted animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-12 text-center">
          <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 2, repeat: Infinity }} className="text-4xl mb-3">🗞️</motion.div>
          <p className="text-sm font-medium text-light-text dark:text-dark-text">No news videos yet</p>
          <p className="text-xs mt-1 text-light-muted dark:text-dark-muted">Verified World &amp; Nepal news goes live every morning during the overnight idle window.</p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((video, i) => {
            const ytUrl = getYoutubeUrl(video);
            return (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.03, 0.3) }}
                className={`p-3 rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 ${
                  ytUrl ? 'hover:border-light-primary/40' : ''
                } transition-all`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xl">{categoryEmoji[video.category] || '🗞️'}</span>
                  <span className="text-[10px] text-light-muted dark:text-dark-muted">{formatDate(video.created_at)}</span>
                </div>
                <p className="text-sm font-semibold text-light-text dark:text-dark-text line-clamp-3 mb-2">{video.title}</p>
                {video.news_source && (
                  <p className="text-[10px] text-light-muted dark:text-dark-muted mb-2 truncate">Source: {video.news_source}</p>
                )}
                <div className="flex items-center justify-between">
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                    {video.format === 'shorts' ? 'Shorts' : 'Long Form'}
                  </span>
                  {ytUrl ? (
                    <a
                      href={ytUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-[11px] font-medium text-light-primary hover:underline"
                    >
                      <ExternalLink size={12} /> Watch
                    </a>
                  ) : (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-yellow-500/15 text-yellow-500">{video.status}</span>
                  )}
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
