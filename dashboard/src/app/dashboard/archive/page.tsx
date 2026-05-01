'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, startAfter, onSnapshot, doc, getDoc, deleteDoc } from 'firebase/firestore';
import { DocumentSnapshot } from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import Image from 'next/image';

interface VideoDoc {
  id: string;
  title: string;
  format: string;
  status: string;
  views: number;
  created_at: any;
  updated_at: any;
  r2_key?: string;
  script?: string;
  metadata?: {
    title: string;
    description: string;
    tags: string[];
    hashtags: string[];
  };
}

const PAGE_SIZE = 12;

export default function ArchivePage() {
  const [videos, setVideos] = useState<VideoDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastVisible, setLastVisible] = useState<DocumentSnapshot | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState('');
  const [formatFilter, setFormatFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [selectedVideo, setSelectedVideo] = useState<VideoDoc | null>(null);

  useEffect(() => {
    const q = query(collection(db, 'videos'), orderBy('created_at', 'desc'), limit(PAGE_SIZE));
    const unsub = onSnapshot(q, (snapshot) => {
      const items: VideoDoc[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as VideoDoc);
      });
      setVideos(items);
      setHasMore(snapshot.docs.length === PAGE_SIZE);
      setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
      setLoading(false);
    });
    return () => unsub();
  }, []);

  const loadMore = useCallback(() => {
    if (!lastVisible || !hasMore) return;
    const q = query(collection(db, 'videos'), orderBy('created_at', 'desc'), startAfter(lastVisible), limit(PAGE_SIZE));
    onSnapshot(q, (snapshot) => {
      const items: VideoDoc[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as VideoDoc);
      });
      setVideos((prev) => [...prev, ...items]);
      setHasMore(snapshot.docs.length === PAGE_SIZE);
      setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
    });
  }, [lastVisible, hasMore]);

  const formatVideo = (v: VideoDoc) => v.format === 'shorts' ? 'Shorts' : 'Long Form';

  const statusColors: Record<string, string> = {
    generating: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    uploaded: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  };

  const filtered = videos.filter((v) => {
    const matchSearch = search === '' || v.title.toLowerCase().includes(search.toLowerCase());
    const matchFormat = formatFilter === 'all' || v.format === formatFilter;
    const matchStatus = statusFilter === 'all' || v.status === statusFilter;
    return matchSearch && matchFormat && matchStatus;
  });

  const totalVideos = videos.length;
  const totalViews = videos.reduce((sum, v) => sum + (v.views || 0), 0);
  const uploadedCount = videos.filter((v) => v.status === 'uploaded').length;
  const generatingCount = videos.filter((v) => v.status === 'generating').length;

  const formatDate = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const formatViews = (count: number) => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
    return count.toString();
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Content Archive</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Search and browse all generated videos</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Total Videos', value: totalVideos.toString(), icon: '📁', color: 'from-light-primary to-light-secondary' },
          { label: 'Total Views', value: formatViews(totalViews), icon: '👁️', color: 'from-light-secondary to-light-info' },
          { label: 'Uploaded', value: uploadedCount.toString(), icon: '✅', color: 'from-light-success to-light-info' },
          { label: 'Generating', value: generatingCount.toString(), icon: '⏳', color: 'from-light-accent to-light-primary' },
        ].map((stat) => (
          <motion.div
            key={stat.label}
            className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{stat.icon}</span>
              <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
            </div>
            <p className="text-2xl font-bold text-light-text dark:text-dark-text">{stat.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="flex gap-3 flex-wrap">
        <div className="flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="Search videos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text placeholder:text-light-muted dark:placeholder:text-dark-muted text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
          />
        </div>
        <select
          value={formatFilter}
          onChange={(e) => setFormatFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
        >
          <option value="all">All Formats</option>
          <option value="shorts">Shorts</option>
          <option value="long">Long Form</option>
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
        >
          <option value="all">All Status</option>
          <option value="uploaded">Uploaded</option>
          <option value="generating">Generating</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-light-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-light-muted dark:text-dark-muted">
          <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 2, repeat: Infinity }} className="text-4xl mb-3">
            📁
          </motion.div>
          <p className="text-sm font-medium">No videos found</p>
          <p className="text-xs mt-1">Videos will appear here once the agents start generating content</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((video, i) => (
            <motion.button
              key={video.id}
              onClick={() => setSelectedVideo(video)}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: Math.min(i * 0.03, 0.3) }}
              whileHover={{ scale: 1.02, y: -2 }}
              whileTap={{ scale: 0.98 }}
              className="text-left p-4 rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 hover:border-light-primary/30 dark:hover:border-light-primary/30 transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                  {formatVideo(video)}
                </span>
                <span className="text-[10px] text-light-muted dark:text-dark-muted">
                  {formatDate(video.created_at)}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-light-text dark:text-dark-text line-clamp-2 mb-2">
                {video.title}
              </h3>
              <div className="flex items-center justify-between">
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${statusColors[video.status] || statusColors.generating}`}>
                  {video.status}
                </span>
                <span className="text-xs text-light-muted dark:text-dark-muted">
                  👁️ {formatViews(video.views || 0)}
                </span>
              </div>
            </motion.button>
          ))}
        </div>
      )}

      {hasMore && filtered.length > 0 && (
        <div className="flex justify-center pt-4">
          <button
            onClick={loadMore}
            className="px-6 py-2 rounded-xl text-sm font-medium bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted hover:bg-light-border dark:hover:bg-dark-border transition-colors"
          >
            Load More
          </button>
        </div>
      )}

      <AnimatePresence>
        {selectedVideo && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 z-40"
              onClick={() => setSelectedVideo(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-x-4 top-1/2 -translate-y-1/2 max-w-lg mx-auto z-50 rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6 max-h-[80vh] overflow-y-auto"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{selectedVideo.title}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">{selectedVideo.id}</p>
                </div>
                <button onClick={() => setSelectedVideo(null)} className="text-light-muted text-xl hover:text-light-text dark:hover:text-dark-text">✕</button>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[selectedVideo.status] || ''}`}>
                    {selectedVideo.status}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                    {formatVideo(selectedVideo)}
                  </span>
                </div>

                <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Views</p>
                  <p className="text-lg font-bold text-light-text dark:text-dark-text">{formatViews(selectedVideo.views || 0)}</p>
                </div>

                {selectedVideo.r2_key && (
                  <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                    <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Storage Key</p>
                    <p className="text-xs font-mono text-light-text dark:text-dark-text truncate">{selectedVideo.r2_key}</p>
                  </div>
                )}

                {selectedVideo.metadata && (
                  <>
                    <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                      <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Description</p>
                      <p className="text-xs text-light-text dark:text-dark-text">{selectedVideo.metadata.description}</p>
                    </div>
                    <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                      <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Tags</p>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedVideo.metadata.tags.map((tag, i) => (
                          <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-light-secondary/10 dark:bg-light-secondary/20 text-light-secondary">
                            #{tag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                {selectedVideo.script && (
                  <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                    <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Script</p>
                    <p className="text-xs text-light-text dark:text-dark-text whitespace-pre-wrap line-clamp-6">
                      {selectedVideo.script}
                    </p>
                  </div>
                )}

                <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <p className="text-xs text-light-muted dark:text-dark-muted mb-1">Created</p>
                  <p className="text-sm text-light-text dark:text-dark-text">{formatDate(selectedVideo.created_at)}</p>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
