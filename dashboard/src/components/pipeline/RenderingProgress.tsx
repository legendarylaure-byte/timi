'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, query, limit, Timestamp } from 'firebase/firestore';
import { doc } from 'firebase/firestore';
import { RENDERING_STEPS } from '@/lib/constants';

interface VideoProgress {
  videoId: string;
  step: string;
  updated_at: number;
  state: any;
}

interface PipelineDoc {
  running: boolean;
  current_video: string;
  last_updated: Timestamp;
}



export function RenderingProgress() {
  const [pipeline, setPipeline] = useState<PipelineDoc | null>(null);
  const [videos, setVideos] = useState<VideoProgress[]>([]);

  useEffect(() => {
    const unsubPipeline = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) setPipeline(snap.data() as PipelineDoc);
    }, () => {});

    const unsubCheckpoints = onSnapshot(
      query(collection(db, 'pipeline_checkpoints'), limit(20)),
      (snap) => {
        const items: VideoProgress[] = [];
        snap.docs.forEach(doc => {
          const data = doc.data();
          const existing = items.findIndex(i => i.videoId === doc.id);
          if (existing >= 0) {
            const existingTime = items[existing].updated_at || 0;
            if ((data.updated_at || 0) > existingTime) {
              items[existing] = {
                videoId: doc.id,
                step: data.step,
                updated_at: data.updated_at,
                state: data.state,
              };
            }
          } else {
            items.push({
              videoId: doc.id,
              step: data.step,
              updated_at: data.updated_at,
              state: data.state,
            });
          }
        });
        setVideos(items);
      },
      () => {}
    );

    return () => {
      unsubPipeline();
      unsubCheckpoints();
    };
  }, []);

  if (!pipeline?.running || videos.length === 0) return null;

  return (
    <div className="space-y-2">
      {videos.map(video => {
        const stepIndex = RENDERING_STEPS.indexOf(video.step);
        const progress = stepIndex >= 0 ? ((stepIndex + 1) / RENDERING_STEPS.length) * 100 : 50;

        return (
          <motion.div
            key={video.videoId}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="p-3 rounded-xl border border-light-border/60 dark:border-dark-border/60 bg-light-bg/50 dark:bg-dark-bg/50"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-medium text-light-text dark:text-dark-text truncate max-w-[200px]">
                {video.videoId.slice(0, 20)}...
              </p>
              <span className="text-[10px] text-light-muted dark:text-dark-muted font-mono">
                {Math.round(progress)}%
              </span>
            </div>

            <div className="w-full h-1.5 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-light-primary to-emerald-400 dark:from-dark-primary dark:to-emerald-400"
                initial={{ width: 0 }}
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
            </div>

            <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1.5 capitalize">
              {video.step.replace(/_/g, ' ')}
            </p>

            {video.state && Object.keys(video.state).length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {Object.entries(video.state).map(([key, value]) => (
                  <span key={key} className="px-1.5 py-0.5 rounded-md bg-light-primary/10 dark:bg-dark-primary/10 text-[9px] text-light-muted dark:text-dark-muted">
                    {key}: {String(value).slice(0, 20)}
                  </span>
                ))}
              </div>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
