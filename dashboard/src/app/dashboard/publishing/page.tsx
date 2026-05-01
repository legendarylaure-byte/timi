'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, getDocs, addDoc, serverTimestamp, query, orderBy, limit, onSnapshot, doc, updateDoc, getDoc, setDoc } from 'firebase/firestore';
import Image from 'next/image';

interface PlatformConfig {
  id: string;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  followers: number;
  videosPublished: number;
  lastPublished?: any;
  autoPublish: boolean;
  bestTime: string;
  scheduleEnabled: boolean;
  maxShortsPerDay: number;
  maxLongPerDay: number;
}

interface UploadQueueItem {
  id: string;
  title: string;
  format: 'shorts' | 'long';
  platforms: string[];
  status: 'queued' | 'uploading' | 'published' | 'failed';
  created_at?: any;
  progress: Record<string, number>;
}

const mockPlatforms: PlatformConfig[] = [
  { id: 'youtube', name: 'YouTube', icon: '🔴', color: '#FF0000', connected: true, followers: 12400, videosPublished: 156, autoPublish: true, bestTime: '18:00', scheduleEnabled: true, maxShortsPerDay: 2, maxLongPerDay: 2 },
  { id: 'tiktok', name: 'TikTok', icon: '🎵', color: '#000000', connected: true, followers: 28900, videosPublished: 203, autoPublish: true, bestTime: '19:00', scheduleEnabled: true, maxShortsPerDay: 3, maxLongPerDay: 0 },
  { id: 'instagram', name: 'Instagram', icon: '📸', color: '#E4405F', connected: true, followers: 8700, videosPublished: 98, autoPublish: false, bestTime: '20:00', scheduleEnabled: false, maxShortsPerDay: 2, maxLongPerDay: 1 },
  { id: 'facebook', name: 'Facebook', icon: '👤', color: '#1877F2', connected: false, followers: 0, videosPublished: 0, autoPublish: false, bestTime: '17:00', scheduleEnabled: false, maxShortsPerDay: 0, maxLongPerDay: 0 },
];

const mockQueue: UploadQueueItem[] = [
  { id: 'q1', title: 'ABC Phonics with Animals', format: 'shorts', platforms: ['youtube', 'tiktok', 'instagram'], status: 'published', progress: { youtube: 100, tiktok: 100, instagram: 100 } },
  { id: 'q2', title: 'Why is the Sky Blue?', format: 'shorts', platforms: ['youtube', 'tiktok'], status: 'uploading', progress: { youtube: 78, tiktok: 45 } },
  { id: 'q3', title: 'The Solar System Adventure', format: 'long', platforms: ['youtube', 'facebook'], status: 'queued', progress: { youtube: 0, facebook: 0 } },
  { id: 'q4', title: 'Sleepy Cloud Bedtime Story', format: 'long', platforms: ['youtube'], status: 'queued', progress: { youtube: 0 } },
];

export default function PublishingPage() {
  const [platforms, setPlatforms] = useState<PlatformConfig[]>([]);
  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'platform_settings'), (snap) => {
      if (!snap.empty) {
        setPlatforms(snap.docs.map(d => ({ id: d.id, ...d.data() } as PlatformConfig)));
      } else {
        setPlatforms(mockPlatforms);
      }
      setLoading(false);
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(query(collection(db, 'upload_queue'), orderBy('created_at', 'desc'), limit(20)), (snap) => {
      if (!snap.empty) {
        setQueue(snap.docs.map(d => ({ id: d.id, ...d.data() } as UploadQueueItem)));
      } else {
        setQueue(mockQueue);
      }
    });
    return () => unsub();
  }, []);

  const totalFollowers = platforms.reduce((s, p) => s + p.followers, 0);
  const totalPublished = platforms.reduce((s, p) => s + p.videosPublished, 0);
  const connectedCount = platforms.filter(p => p.connected).length;
  const queuedCount = queue.filter(q => q.status === 'queued').length;

  const formatFollowers = (n: number) => n >= 1000000 ? (n / 1000000).toFixed(1) + 'M' : n >= 1000 ? (n / 1000).toFixed(1) + 'K' : n.toString();

  const toggleConnection = async (platformId: string) => {
    const platform = platforms.find(p => p.id === platformId);
    if (!platform) return;
    const updated = { ...platform, connected: !platform.connected };
    await setDoc(doc(db, 'platform_settings', platformId), updated, { merge: true });
  };

  const toggleAutoPublish = async (platformId: string) => {
    const platform = platforms.find(p => p.id === platformId);
    if (!platform) return;
    const updated = { ...platform, autoPublish: !platform.autoPublish };
    await setDoc(doc(db, 'platform_settings', platformId), updated, { merge: true });
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
            <span className="text-2xl">📤</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Multi-Platform Publishing</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Manage uploads across YouTube, TikTok, Instagram & Facebook</p>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Connected Platforms', value: `${connectedCount}/${platforms.length}`, icon: '🔗', color: 'text-emerald-400' },
          { label: 'Total Followers', value: formatFollowers(totalFollowers), icon: '👥', color: 'text-blue-400' },
          { label: 'Videos Published', value: totalPublished.toString(), icon: '🎬', color: 'text-purple-400' },
          { label: 'In Queue', value: queuedCount.toString(), icon: '⏳', color: 'text-yellow-400' },
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

      {/* Platform Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {platforms.map((platform, i) => (
          <motion.div
            key={platform.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`rounded-2xl glass-strong border overflow-hidden transition-all cursor-pointer ${
              selectedPlatform === platform.id ? 'border-2' : 'border-light-border/30 dark:border-white/5'
            }`}
            style={selectedPlatform === platform.id ? { borderColor: platform.color } : {}}
            onClick={() => setSelectedPlatform(selectedPlatform === platform.id ? null : platform.id)}
          >
            {/* Platform Header */}
            <div className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl" style={{ background: `${platform.color}20` }}>
                    {platform.icon}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{platform.name}</h3>
                    <p className="text-xs text-light-muted dark:text-dark-muted">{formatFollowers(platform.followers)} followers</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusPill connected={platform.connected} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Published</p>
                  <p className="text-lg font-bold text-light-text dark:text-dark-text">{platform.videosPublished}</p>
                </div>
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Shorts/Day</p>
                  <p className="text-lg font-bold text-light-text dark:text-dark-text">{platform.maxShortsPerDay}</p>
                </div>
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Best Time</p>
                  <p className="text-sm font-bold text-light-text dark:text-dark-text">{platform.bestTime}</p>
                </div>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={(e) => { e.stopPropagation(); toggleConnection(platform.id); }}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    platform.connected
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
                  }`}
                >
                  {platform.connected ? 'Disconnect' : 'Connect'}
                </button>
                {platform.connected && (
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleAutoPublish(platform.id); }}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                      platform.autoPublish
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : 'bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted'
                    }`}
                  >
                    Auto: {platform.autoPublish ? 'ON' : 'OFF'}
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Details */}
            <AnimatePresence>
              {selectedPlatform === platform.id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="px-5 pb-5 pt-0 border-t border-light-border/30 dark:border-white/5">
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Schedule enabled</span>
                        <span className={`text-xs font-bold ${platform.scheduleEnabled ? 'text-emerald-400' : 'text-light-muted dark:text-dark-muted'}`}>
                          {platform.scheduleEnabled ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Long form per day</span>
                        <span className="text-sm font-bold text-light-text dark:text-dark-text">{platform.maxLongPerDay}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Last published</span>
                        <span className="text-sm font-bold text-light-text dark:text-dark-text">
                          {platform.lastPublished ? formatTimeAgo(platform.lastPublished) : 'Never'}
                        </span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>

      {/* Upload Queue */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Upload Queue</h2>
        <div className="space-y-3">
          {queue.map((item, i) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">{item.title}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted">{item.format === 'shorts' ? 'Shorts (9:16)' : 'Long Form (16:9)'}</p>
                </div>
                <StatusBadge status={item.status} />
              </div>

              <div className="flex gap-3">
                {item.platforms.map(platformId => {
                  const platform = platforms.find(p => p.id === platformId);
                  const progress = item.progress[platformId] || 0;
                  return (
                    <div key={platformId} className="flex-1">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-light-muted dark:text-dark-muted">{platform?.icon} {platform?.name}</span>
                        <span className="text-xs font-bold text-light-text dark:text-dark-text">{progress}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${progress}%` }}
                          transition={{ duration: 0.5 }}
                          className="h-full rounded-full"
                          style={{ backgroundColor: platform?.color || '#6B7280' }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatusPill({ connected }: { connected: boolean }) {
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
      connected ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'
    }`}>
      {connected ? '● Connected' : '○ Disconnected'}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    queued: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    uploading: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    published: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  return (
    <span className={`px-2 py-1 rounded-full text-[10px] font-bold border ${colors[status] || colors.queued}`}>
      {status.toUpperCase()}
    </span>
  );
}

function formatTimeAgo(timestamp: any) {
  if (!timestamp) return 'Never';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
