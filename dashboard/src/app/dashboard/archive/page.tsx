'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, startAfter, onSnapshot, getDocs } from 'firebase/firestore';
import { DocumentSnapshot } from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import Image from 'next/image';
import PlatformBadge from '@/components/platforms/PlatformBadge';
import VideoPreview from '@/components/ui/VideoPreview';
import { LayoutGrid, List, Trash2 } from 'lucide-react';

interface VideoDoc {
  id: string;
  title: string;
  format: string;
  status: string;
  category?: string;
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
  published_platforms?: string[];
  publish_urls?: Record<string, string>;
  youtube_id?: string;
  error?: string;
  failed_step?: string;
}

const PAGE_SIZE = 48;

export default function ArchivePage() {
  const [videos, setVideos] = useState<VideoDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastVisible, setLastVisible] = useState<DocumentSnapshot | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [search, setSearch] = useState('');
  const [formatFilter, setFormatFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [platformFilter, setPlatformFilter] = useState('all');
  const [selectedVideo, setSelectedVideo] = useState<VideoDoc | null>(null);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [showBatchConfirm, setShowBatchConfirm] = useState(false);
  const [batchDeleting, setBatchDeleting] = useState(false);

  useEffect(() => {
    const q = query(collection(db, 'videos'), orderBy('created_at', 'desc'), limit(PAGE_SIZE));
    const unsub = onSnapshot(q,
      (snapshot) => {
        const items: VideoDoc[] = [];
        snapshot.docs.forEach((d) => {
          items.push({ id: d.id, ...d.data() } as VideoDoc);
        });
        setVideos(items);
        setHasMore(snapshot.docs.length === PAGE_SIZE);
        setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
        setLoading(false);
      },
      (error) => {
        console.error('[Archive] videos:', error);
        setLoading(false);
      }
    );
    return () => unsub();
  }, []);

  const loadMore = useCallback(async () => {
    if (!lastVisible || !hasMore) return;
    try {
      const q = query(collection(db, 'videos'), orderBy('created_at', 'desc'), startAfter(lastVisible), limit(PAGE_SIZE));
      const snapshot = await getDocs(q);
      const items: VideoDoc[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as VideoDoc);
      });
      setVideos((prev) => [...prev, ...items]);
      setHasMore(snapshot.docs.length === PAGE_SIZE);
      setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
    } catch (error) {
      console.error('[Archive] loadMore:', error);
    }
  }, [lastVisible, hasMore]);

  const formatVideo = (v: VideoDoc) => v.format === 'shorts' ? 'Shorts' : 'Long Form';

  const statusColors: Record<string, string> = {
    generating: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    uploaded: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
    blocked: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    blocked_virality: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    blocked_compliance: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
    testing: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  };

  const baseFiltered = videos.filter((v) => {
    return !v.category || CONTENT_CATEGORIES.some(c => c.name === v.category);
  });

  const filtered = baseFiltered.filter((v) => {
    const matchSearch = search === '' || v.title?.toLowerCase().includes(search.toLowerCase());
    const matchFormat = formatFilter === 'all' || v.format === formatFilter;
    const matchStatus = statusFilter === 'all' || v.status === statusFilter;
    const matchCategory = categoryFilter === 'all' || v.category === categoryFilter;
    const matchPlatform = platformFilter === 'all' || (v.published_platforms || []).includes(platformFilter);
    return matchSearch && matchFormat && matchStatus && matchCategory && matchPlatform;
  });

  const totalVideos = baseFiltered.length;
  const totalViews = baseFiltered.reduce((sum, v) => sum + (v.views || 0), 0);
  const uploadedCount = baseFiltered.filter((v) => v.status === 'uploaded').length;
  const generatingCount = baseFiltered.filter((v) => v.status === 'generating').length;
  const totalPlatformPublishes = baseFiltered.reduce((sum, v) => sum + (v.published_platforms?.length || 0), 0);

  const allFilteredSelected = filtered.length > 0 && filtered.every(v => selectedIds.has(v.id));

  const toggleSelect = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allFilteredSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filtered.map(v => v.id)));
    }
  };

  const handleBatchDelete = async () => {
    setBatchDeleting(true);
    try {
      const res = await fetch('/api/videos/batch-delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: Array.from(selectedIds) }),
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || 'Batch delete failed');
      setVideos((prev) => prev.filter((v) => !selectedIds.has(v.id)));
      setSelectedIds(new Set());
      setShowBatchConfirm(false);
    } catch (err: any) {
      console.error('[Archive] batch delete:', err);
      alert('Failed to delete videos: ' + err.message);
    } finally {
      setBatchDeleting(false);
    }
  };

  const getYouTubeId = (v: VideoDoc): string | undefined => {
    if (v.youtube_id) return v.youtube_id;
    const url = v.publish_urls?.youtube || v.publish_urls?.YouTube;
    if (url) {
      const m = url.match(/(?:v=|youtu\.be\/)([\w-]+)/);
      if (m) return m[1];
    }
    return undefined;
  };

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

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[
          { label: 'Total Videos', value: totalVideos.toString(), icon: '📁' },
          { label: 'Total Views', value: formatViews(totalViews), icon: '👁️' },
          { label: 'Uploaded', value: uploadedCount.toString(), icon: '✅' },
          { label: 'Generating', value: generatingCount.toString(), icon: '⏳' },
          { label: 'Platform Publishes', value: totalPlatformPublishes.toString(), icon: '📡' },
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

      <div className="flex gap-3 flex-wrap items-center">
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
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
        >
          <option value="all">All Categories</option>
          {CONTENT_CATEGORIES.map(cat => (
            <option key={cat.name} value={cat.name}>{cat.name}</option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
        >
          <option value="all">All Platforms</option>
          <option value="youtube">🔴 YouTube</option>
          <option value="tiktok">🎵 TikTok</option>
          <option value="instagram">📸 Instagram</option>
          <option value="facebook">👥 Facebook</option>
        </select>
        <div className="flex rounded-xl overflow-hidden border border-light-border/50 dark:border-white/10">
          <button
            onClick={() => setViewMode('grid')}
            className={`p-2.5 transition-colors ${viewMode === 'grid' ? 'bg-light-primary/10 text-light-primary' : 'bg-light-bg dark:bg-dark-bg text-light-muted dark:text-dark-muted hover:text-light-text'}`}
            title="Grid view"
          >
            <LayoutGrid size={18} />
          </button>
          <button
            onClick={() => setViewMode('list')}
            className={`p-2.5 transition-colors ${viewMode === 'list' ? 'bg-light-primary/10 text-light-primary' : 'bg-light-bg dark:bg-dark-bg text-light-muted dark:text-dark-muted hover:text-light-text'}`}
            title="List view"
          >
            <List size={18} />
          </button>
        </div>
      </div>

      {filtered.length > 0 && (
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={allFilteredSelected}
              onChange={toggleSelectAll}
              className="w-4 h-4 rounded border-light-border/50 dark:border-white/10 accent-light-primary"
            />
            <span className="text-xs text-light-muted dark:text-dark-muted">
              {allFilteredSelected ? 'Deselect all' : 'Select all'} ({filtered.length} videos)
            </span>
          </label>
          {selectedIds.size > 0 && (
            <button
              onClick={() => setShowBatchConfirm(true)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20 hover:bg-red-500/20 transition-colors"
            >
              <Trash2 size={14} />
              Delete {selectedIds.size} selected
            </button>
          )}
        </div>
      )}

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
      ) : viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((video, i) => {
            const ytId = getYouTubeId(video);
            const isSelected = selectedIds.has(video.id);
            return (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.03, 0.3) }}
                className={`relative p-3 rounded-2xl glass-strong border transition-all cursor-pointer ${
                  isSelected
                    ? 'border-light-primary/50 dark:border-light-primary/50 ring-1 ring-light-primary/30'
                    : 'border-light-border/30 dark:border-white/5 hover:border-light-primary/30 dark:hover:border-light-primary/30'
                }`}
                onClick={() => setSelectedVideo(video)}
              >
                <div
                  className="absolute top-2 left-2 z-10"
                  onClick={(e) => { e.stopPropagation(); toggleSelect(video.id); }}
                >
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => {}}
                    className="w-4 h-4 rounded border-light-border/50 dark:border-white/10 accent-light-primary cursor-pointer"
                  />
                </div>
                {ytId ? (
                  <div className="relative w-full aspect-video rounded-lg overflow-hidden mb-3 bg-black">
                    <img
                      src={`https://img.youtube.com/vi/${ytId}/mqdefault.jpg`}
                      alt={video.title}
                      className="w-full h-full object-cover"
                      loading="lazy"
                    />
                    <div className="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                      <div className="w-10 h-10 rounded-full bg-black/60 flex items-center justify-center">
                        <svg className="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                          <path d="M8 5v14l11-7z" />
                        </svg>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="w-full aspect-video rounded-lg mb-3 bg-gradient-to-br from-light-primary/10 to-light-secondary/10 flex items-center justify-center">
                    <span className="text-3xl">{video.format === 'shorts' ? '🎬' : '🎥'}</span>
                  </div>
                )}
                <div className="flex items-start justify-between mb-2">
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
                  <div className="flex items-center gap-1.5">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${statusColors[video.status] || statusColors.generating}`}>
                      {video.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {video.published_platforms?.map(p => (
                      <PlatformBadge key={p} platform={p} />
                    ))}
                    <span className="text-xs text-light-muted dark:text-dark-muted ml-1">
                      👁️ {formatViews(video.views || 0)}
                    </span>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-light-border/30 dark:border-white/5 text-xs text-light-muted dark:text-dark-muted">
                <th className="p-3 text-left w-10">
                  <input
                    type="checkbox"
                    checked={allFilteredSelected}
                    onChange={toggleSelectAll}
                    className="w-4 h-4 rounded accent-light-primary"
                  />
                </th>
                <th className="p-3 text-left w-12"></th>
                <th className="p-3 text-left">Title</th>
                <th className="p-3 text-left w-20">Format</th>
                <th className="p-3 text-left w-24">Status</th>
                <th className="p-3 text-left w-28">Platforms</th>
                <th className="p-3 text-right w-16">Views</th>
                <th className="p-3 text-right w-24">Date</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((video, i) => {
                const ytId = getYouTubeId(video);
                const isSelected = selectedIds.has(video.id);
                return (
                  <tr
                    key={video.id}
                    className={`border-b border-light-border/20 dark:border-white/5 transition-colors cursor-pointer ${
                      isSelected ? 'bg-light-primary/5 dark:bg-light-primary/10' : 'hover:bg-light-bg/50 dark:hover:bg-dark-bg/50'
                    }`}
                    onClick={() => setSelectedVideo(video)}
                  >
                    <td className="p-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelect(video.id)}
                        className="w-4 h-4 rounded accent-light-primary cursor-pointer"
                      />
                    </td>
                    <td className="p-3">
                      {ytId ? (
                        <img
                          src={`https://img.youtube.com/vi/${ytId}/default.jpg`}
                          alt=""
                          className="w-10 h-7 rounded object-cover"
                        />
                      ) : (
                        <div className="w-10 h-7 rounded bg-gradient-to-br from-light-primary/10 to-light-secondary/10 flex items-center justify-center text-xs">
                          {video.format === 'shorts' ? '🎬' : '🎥'}
                        </div>
                      )}
                    </td>
                    <td className="p-3">
                      <p className="font-medium text-light-text dark:text-dark-text line-clamp-1 max-w-[300px]">
                        {video.title}
                      </p>
                    </td>
                    <td className="p-3">
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                        {formatVideo(video)}
                      </span>
                    </td>
                    <td className="p-3">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full border ${statusColors[video.status] || statusColors.generating}`}>
                        {video.status}
                      </span>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-1">
                        {video.published_platforms?.map(p => (
                          <PlatformBadge key={p} platform={p} size="sm" />
                        ))}
                      </div>
                    </td>
                    <td className="p-3 text-right text-light-text dark:text-dark-text">
                      {formatViews(video.views || 0)}
                    </td>
                    <td className="p-3 text-right text-xs text-light-muted dark:text-dark-muted">
                      {formatDate(video.created_at)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
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
        {showBatchConfirm && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
            onClick={() => setShowBatchConfirm(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-sm rounded-2xl glass-strong border border-red-500/20 p-6"
            >
              <h3 className="text-lg font-bold text-light-text dark:text-dark-text mb-2">Delete {selectedIds.size} videos?</h3>
              <p className="text-sm text-light-muted dark:text-dark-muted mb-4">
                This will permanently delete the video files from cloud storage and remove them from the database. This cannot be undone.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleBatchDelete}
                  disabled={batchDeleting}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50 transition-colors"
                >
                  {batchDeleting ? 'Deleting...' : `Yes, Delete ${selectedIds.size}`}
                </button>
                <button
                  onClick={() => setShowBatchConfirm(false)}
                  disabled={batchDeleting}
                  className="flex-1 px-4 py-2 rounded-lg text-sm font-medium bg-light-border/50 dark:bg-dark-border/50 text-light-text dark:text-dark-text hover:bg-light-border dark:hover:bg-dark-border disabled:opacity-50 transition-colors"
                >
                  Cancel
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {selectedVideo && (
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
            onClick={() => setSelectedVideo(null)}
          >
            <motion.div
              key="modal"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-lg rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6 max-h-[80vh] overflow-y-auto"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{selectedVideo.title}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">{selectedVideo.id}</p>
                </div>
                <button onClick={() => setSelectedVideo(null)} className="text-light-muted text-xl hover:text-light-text dark:hover:text-dark-text" aria-label="Close">✕</button>
              </div>

              <div className="space-y-3">
                {getYouTubeId(selectedVideo) && (
                  <VideoPreview
                    youtubeId={getYouTubeId(selectedVideo)!}
                    title={selectedVideo.title}
                  />
                )}

                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[selectedVideo.status] || ''}`}>
                    {selectedVideo.status}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                    {formatVideo(selectedVideo)}
                  </span>
                </div>

                {selectedVideo.published_platforms && selectedVideo.published_platforms.length > 0 && (
                  <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                    <p className="text-xs text-light-muted dark:text-dark-muted mb-2">Published On</p>
                    <div className="flex flex-col gap-1.5">
                      {selectedVideo.published_platforms.map(platform => (
                        <a
                          key={platform}
                          href={selectedVideo.publish_urls?.[platform] || selectedVideo.publish_urls?.[platform.charAt(0).toUpperCase() + platform.slice(1)] || '#'}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                        >
                          <PlatformBadge platform={platform} size="md" />
                          <span className="text-sm font-medium text-light-text dark:text-dark-text capitalize">{platform}</span>
                          <span className="ml-auto text-xs text-light-muted">Watch →</span>
                        </a>
                      ))}
                    </div>
                  </div>
                )}

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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
