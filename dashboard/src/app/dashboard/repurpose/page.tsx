'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, getDocs, addDoc, serverTimestamp, query, orderBy, limit, onSnapshot, doc, updateDoc } from 'firebase/firestore';
import Image from 'next/image';

interface RepurposeJob {
  id: string;
  source_video_id: string;
  source_title: string;
  source_duration: number;
  clips_generated: number;
  clips: RepurposeClip[];
  status: 'processing' | 'completed' | 'failed';
  created_at?: any;
}

interface RepurposeClip {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  duration: number;
  hook_score: number;
  thumbnail_ready: boolean;
  status: 'ready' | 'processing' | 'failed';
}

const mockJobs: RepurposeJob[] = [
  {
    id: 'job-1', source_video_id: 'v-001', source_title: 'The Solar System Adventure - Full Episode',
    source_duration: 480, clips_generated: 5, status: 'completed',
    clips: [
      { id: 'c1', title: 'Why Planets Spin', start_time: 45, end_time: 98, duration: 53, hook_score: 88, thumbnail_ready: true, status: 'ready' },
      { id: 'c2', title: 'Jupiter is HUGE', start_time: 150, end_time: 200, duration: 50, hook_score: 92, thumbnail_ready: true, status: 'ready' },
      { id: 'c3', title: 'Saturn Rings Explained', start_time: 260, end_time: 315, duration: 55, hook_score: 85, thumbnail_ready: true, status: 'ready' },
      { id: 'c4', title: 'Mars Has the Tallest Mountain', start_time: 340, end_time: 395, duration: 55, hook_score: 90, thumbnail_ready: false, status: 'processing' },
      { id: 'c5', title: 'Can We Live on the Moon?', start_time: 410, end_time: 465, duration: 55, hook_score: 94, thumbnail_ready: false, status: 'processing' },
    ],
  },
  {
    id: 'job-2', source_video_id: 'v-002', source_title: 'Greek Myths: Hercules and the 12 Labors',
    source_duration: 600, clips_generated: 4, status: 'completed',
    clips: [
      { id: 'c6', title: 'Hercules vs the Lion', start_time: 60, end_time: 115, duration: 55, hook_score: 86, thumbnail_ready: true, status: 'ready' },
      { id: 'c7', title: 'The Hydra Battle', start_time: 180, end_time: 240, duration: 60, hook_score: 91, thumbnail_ready: true, status: 'ready' },
      { id: 'c8', title: 'Cleaning the Stables', start_time: 300, end_time: 350, duration: 50, hook_score: 72, thumbnail_ready: true, status: 'ready' },
      { id: 'c9', title: 'Hercules Becomes a God', start_time: 540, end_time: 595, duration: 55, hook_score: 95, thumbnail_ready: false, status: 'processing' },
    ],
  },
];

export default function RepurposePage() {
  const [jobs, setJobs] = useState<RepurposeJob[]>([]);
  const [selectedJob, setSelectedJob] = useState<RepurposeJob | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = onSnapshot(query(collection(db, 'repurpose_jobs'), orderBy('created_at', 'desc'), limit(20)), (snap) => {
      if (!snap.empty) {
        setJobs(snap.docs.map(d => ({ id: d.id, ...d.data() } as RepurposeJob)));
      } else {
        setJobs(mockJobs);
      }
      setLoading(false);
    });
    return () => unsub();
  }, []);

  const totalClips = jobs.reduce((s, j) => s + j.clips_generated, 0);
  const readyClips = jobs.reduce((s, j) => s + j.clips.filter(c => c.status === 'ready').length, 0);
  const processingClips = jobs.reduce((s, j) => s + j.clips.filter(c => c.status === 'processing').length, 0);

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
            <span className="text-2xl">✂️</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Content Repurposing</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Auto-split long-form videos into viral shorts</p>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Jobs Completed', value: jobs.filter(j => j.status === 'completed').length.toString(), icon: '✅', color: 'text-emerald-400' },
          { label: 'Total Clips', value: totalClips.toString(), icon: '🎬', color: 'text-blue-400' },
          { label: 'Ready to Publish', value: readyClips.toString(), icon: '🚀', color: 'text-purple-400' },
          { label: 'Processing', value: processingClips.toString(), icon: '⏳', color: 'text-yellow-400' },
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

      {/* Job List */}
      <div className="space-y-4">
        {jobs.map((job, i) => (
          <motion.div
            key={job.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 overflow-hidden"
          >
            <button
              onClick={() => setSelectedJob(selectedJob?.id === job.id ? null : job)}
              className="w-full p-5 flex items-center justify-between text-left hover:bg-light-bg/30 dark:hover:bg-dark-bg/30 transition-colors"
            >
              <div className="flex items-center gap-4">
                <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-cyan-500/20 to-blue-500/20 flex items-center justify-center">
                  <span className="text-2xl">🎬</span>
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">{job.source_title}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted mt-1">
                    {formatDuration(job.source_duration)} · {job.clips_generated} clips · {job.status}
                  </p>
                </div>
              </div>
              <motion.div animate={{ rotate: selectedJob?.id === job.id ? 180 : 0 }} className="text-light-muted dark:text-dark-muted">
                ▼
              </motion.div>
            </button>

            <AnimatePresence>
              {selectedJob?.id === job.id && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden"
                >
                  <div className="p-5 pt-0 border-t border-light-border/30 dark:border-white/5">
                    {/* Timeline */}
                    <div className="mb-4">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs text-light-muted dark:text-dark-muted">0:00</span>
                        <div className="flex-1 h-3 rounded-full bg-light-border/50 dark:bg-white/5 relative overflow-hidden">
                          {job.clips.map((clip, ci) => (
                            <motion.div
                              key={clip.id}
                              initial={{ scaleX: 0 }}
                              animate={{ scaleX: 1 }}
                              transition={{ delay: ci * 0.1, duration: 0.5 }}
                              className="absolute h-full bg-gradient-to-r from-cyan-500 to-blue-500 rounded-full"
                              style={{
                                left: `${(clip.start_time / job.source_duration) * 100}%`,
                                width: `${((clip.end_time - clip.start_time) / job.source_duration) * 100}%`,
                              }}
                            />
                          ))}
                        </div>
                        <span className="text-xs text-light-muted dark:text-dark-muted">{formatDuration(job.source_duration)}</span>
                      </div>
                    </div>

                    {/* Clips */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {job.clips.map((clip, ci) => (
                        <motion.div
                          key={clip.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          transition={{ delay: ci * 0.05 }}
                          className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5"
                        >
                          <div className="flex items-start justify-between mb-2">
                            <div>
                              <h4 className="text-sm font-semibold text-light-text dark:text-dark-text">{clip.title}</h4>
                              <p className="text-[10px] text-light-muted dark:text-dark-muted">
                                {formatTimestamp(clip.start_time)} - {formatTimestamp(clip.end_time)} · {clip.duration}s
                              </p>
                            </div>
                            <span className={`text-sm font-bold ${clip.hook_score >= 85 ? 'text-emerald-400' : clip.hook_score >= 70 ? 'text-yellow-400' : 'text-red-400'}`}>
                              {clip.hook_score}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 mb-3">
                            <div className="flex-1 h-1.5 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${clip.hook_score >= 85 ? 'bg-emerald-400' : clip.hook_score >= 70 ? 'bg-yellow-400' : 'bg-red-400'}`}
                                style={{ width: `${clip.hook_score}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-light-muted dark:text-dark-muted">hook score</span>
                          </div>

                          <div className="flex gap-2">
                            {clip.status === 'ready' ? (
                              <>
                                <button className="flex-1 py-2 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors">
                                  📤 Publish
                                </button>
                                <button className="py-2 px-3 rounded-lg text-xs font-medium bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted hover:bg-light-border/80 transition-colors">
                                  ✏️ Edit
                                </button>
                              </>
                            ) : (
                              <div className="flex-1 py-2 rounded-lg text-xs font-medium bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 flex items-center justify-center gap-2">
                                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity }} className="text-xs">⚙️</motion.div>
                                Processing...
                              </div>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>

      {/* How it works */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">How Repurposing Works</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { step: '1', title: 'Scan Long Videos', desc: 'AI analyzes your long-form videos for high-engagement moments', icon: '🔍' },
            { step: '2', title: 'Extract Clips', desc: 'Auto-extracts 30-60 second segments with strong hooks', icon: '✂️' },
            { step: '3', title: 'Score & Rank', desc: 'Each clip gets a hook score based on engagement potential', icon: '⭐' },
            { step: '4', title: 'Publish Shorts', desc: 'One-click publish to YouTube Shorts, TikTok, Reels', icon: '📤' },
          ].map(item => (
            <div key={item.step} className="relative">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center text-white font-bold text-sm mb-3">
                {item.step}
              </div>
              <span className="text-xl mb-2 block">{item.icon}</span>
              <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-1">{item.title}</h3>
              <p className="text-xs text-light-muted dark:text-dark-muted">{item.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function formatDuration(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

function formatTimestamp(seconds: number) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}
