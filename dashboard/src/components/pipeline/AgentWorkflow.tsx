'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { doc, collection, onSnapshot, Timestamp } from 'firebase/firestore';
import { Play, FolderOpen, Eye } from 'lucide-react';

interface PipelineDoc {
  running: boolean;
  current_video: string;
  paused_by_user: boolean;
  last_updated: Timestamp;
}

interface AgentStatus {
  agent_id: string;
  name: string;
  color: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: Timestamp;
}

const WORKFLOW_STEPS = [
  { key: 'scriptwriter', label: 'Script', icon: '📝', color: '#FF6B6B' },
  { key: 'storyboard', label: 'Storyboard', icon: '🎨', color: '#4ECDC4' },
  { key: 'voice', label: 'Voice', icon: '🎙️', color: '#FFD93D' },
  { key: 'composer', label: 'Music', icon: '🎵', color: '#A29BFE' },
  { key: 'animator', label: 'Animate', icon: '🎬', color: '#00D2FF' },
  { key: 'editor', label: 'Edit', icon: '✂️', color: '#F39C12' },
  { key: 'thumbnail', label: 'Thumbnail', icon: '🖼️', color: '#E056FD' },
  { key: 'publisher', label: 'Publish', icon: '🚀', color: '#7ED6DF' },
];

export function AgentWorkflow({
  videosToday,
  totalVideos,
  totalViews,
  shortsQuota,
  longQuota,
  shortsTodayDone,
  longTodayDone,
}: {
  videosToday: number;
  totalVideos: number;
  totalViews: number;
  shortsQuota: number;
  longQuota: number;
  shortsTodayDone: number;
  longTodayDone: number;
}) {
  const [pipeline, setPipeline] = useState<PipelineDoc | null>(null);
  const [agentStatuses, setAgentStatuses] = useState<Map<string, AgentStatus>>(new Map());

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) setPipeline(snap.data() as PipelineDoc);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'agent_status'), (snap) => {
      const map = new Map<string, AgentStatus>();
      snap.docs.forEach(d => {
        const data = d.data() as AgentStatus;
        map.set(data.agent_id, data);
      });
      setAgentStatuses(map);
    }, () => {});
    return () => unsub();
  }, []);

  const workingCount = Array.from(agentStatuses.values()).filter(
    a => a.status === 'working'
  ).length;

  return (
    <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 glass-warm p-4 glow-red">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <motion.div
            animate={pipeline?.running ? { scale: [1, 1.15, 1], boxShadow: ['0 0 4px rgba(16,185,129,0.4)', '0 0 16px rgba(16,185,129,0.8)', '0 0 4px rgba(16,185,129,0.4)'] } : {}}
            transition={{ repeat: Infinity, duration: 2 }}
            className={`w-3 h-3 rounded-full ${pipeline?.running ? 'bg-emerald-500' : workingCount > 0 ? 'bg-amber-400' : 'bg-gray-400'}`}
          />
          <div>
            <h3 className="text-sm font-bold gradient-text">Agent Pipeline</h3>
            <p className="text-[11px] text-light-muted dark:text-dark-muted">
              {pipeline?.running
                ? (workingCount > 0 ? `${workingCount} agent${workingCount > 1 ? 's' : ''} working` : 'Pipeline active — waiting for agent dispatch')
                : workingCount > 0
                  ? `${workingCount} agent${workingCount > 1 ? 's' : ''} running background tasks`
                  : 'Waiting for next daily run at 11:45 AM NPT'}
            </p>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-3">
          <div className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-light-bg/60 dark:bg-dark-bg/60">
            <Play className="w-3 h-3 text-light-primary" />
            <span className="text-light-muted dark:text-dark-muted">Today</span>
            <span className="font-bold text-light-text dark:text-dark-text">{videosToday}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-light-bg/60 dark:bg-dark-bg/60">
            <FolderOpen className="w-3 h-3 text-sky-500" />
            <span className="text-light-muted dark:text-dark-muted">Total</span>
            <span className="font-bold text-light-text dark:text-dark-text">{totalVideos}</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg bg-light-bg/60 dark:bg-dark-bg/60">
            <Eye className="w-3 h-3 text-emerald-500" />
            <span className="text-light-muted dark:text-dark-muted">Views</span>
            <span className="font-bold text-light-text dark:text-dark-text">{totalViews > 999 ? `${(totalViews / 1000).toFixed(1)}K` : totalViews}</span>
          </div>
          <div className="w-px h-6 bg-light-border/50 dark:bg-dark-border/50" />
          <div className="flex items-center gap-2 text-xs">
            <div className="flex flex-col items-center">
              <span className="text-[10px] text-light-muted dark:text-dark-muted">Shorts</span>
              <span className="font-bold text-light-primary">{shortsTodayDone}/{shortsQuota}</span>
            </div>
            <span className="text-light-muted/40">·</span>
            <div className="flex flex-col items-center">
              <span className="text-[10px] text-light-muted dark:text-dark-muted">Long</span>
              <span className="font-bold text-sky-500">{longTodayDone}/{longQuota}</span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-1 sm:gap-2 overflow-x-auto pb-1 scrollbar-thin">
        {WORKFLOW_STEPS.map((step, i) => {
          const agent = agentStatuses.get(step.key);
          const isWorking = agent?.status === 'working';
          const isCompleted = agent?.status === 'completed';
          const isIdle = agent?.status === 'idle' || !agent;

          return (
            <div key={step.key} className="flex items-center gap-1 sm:gap-2 shrink-0">
              <motion.div className="group relative">
                <motion.div
                  animate={
                    isWorking
                      ? {
                          y: [0, -4, 0],
                          transition: { repeat: Infinity, duration: 1.2 },
                        }
                      : isCompleted
                        ? {
                            scale: [1, 1.06, 1],
                            transition: { repeat: Infinity, duration: 2.5 },
                          }
                        : {}
                  }
                >
                  <div className={`
                    flex flex-col items-center gap-1 w-14 sm:w-16 p-2 rounded-xl transition-all duration-300 relative
                    ${isWorking ? 'bg-cyan-500/10 ring-2 ring-cyan-400/40 shadow-[0_0_12px_rgba(6,182,212,0.2)]' : ''}
                    ${isCompleted ? 'bg-emerald-500/10 ring-1 ring-emerald-500/30' : ''}
                    ${isIdle ? 'bg-light-bg/40 dark:bg-dark-bg/40' : ''}
                  `}>
                    {/* Neon glow on active */}
                    {isWorking && (
                      <motion.div
                        animate={{ opacity: [0.3, 0.7, 0.3] }}
                        transition={{ repeat: Infinity, duration: 2 }}
                        className="absolute inset-0 rounded-xl bg-gradient-to-br from-cyan-400/10 to-transparent pointer-events-none"
                      />
                    )}

                    <div className={`
                      w-7 h-7 rounded-lg flex items-center justify-center text-sm transition-all duration-300 relative
                      ${isWorking ? 'scale-110' : ''}
                      ${isCompleted ? 'bg-emerald-500 text-white' : ''}
                      ${!isCompleted && isWorking ? 'shadow-[0_0_6px_rgba(0,0,0,0.1)]' : ''}
                      ${!isCompleted && !isWorking ? 'bg-light-border/50 dark:bg-dark-border/50' : ''}
                    `}
                      style={!isCompleted && isWorking ? { background: `${step.color}25`, boxShadow: `0 0 8px ${step.color}40` } : {}}
                    >
                      {isCompleted ? (
                        <motion.span
                          initial={{ scale: 0 }}
                          animate={{ scale: 1 }}
                          className="text-white text-xs"
                        >
                          ✓
                        </motion.span>
                      ) : (
                        <span>{step.icon}</span>
                      )}
                    </div>

                    <span className={`
                      text-[9px] font-medium leading-tight text-center
                      ${isWorking ? 'text-cyan-500 dark:text-cyan-400' : ''}
                      ${isCompleted ? 'text-emerald-600 dark:text-emerald-400' : ''}
                      ${isIdle ? 'text-light-muted/60 dark:text-dark-muted/60' : ''}
                    `}>{step.label}</span>
                  </div>
                </motion.div>

                {/* Working dots indicator */}
                <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 flex gap-0.5">
                  {isWorking && (
                    <>
                      <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1, delay: 0 }} className="w-1 h-1 rounded-full bg-cyan-400" />
                      <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1, delay: 0.3 }} className="w-1 h-1 rounded-full bg-cyan-400" />
                      <motion.span animate={{ opacity: [0, 1, 0] }} transition={{ repeat: Infinity, duration: 1, delay: 0.6 }} className="w-1 h-1 rounded-full bg-cyan-400" />
                    </>
                  )}
                </div>

                {/* Tooltip with agent action */}
                <AnimatePresence>
                  {isWorking && agent?.current_action && (
                    <motion.div
                      initial={{ opacity: 0, y: 4, scale: 0.95 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4, scale: 0.95 }}
                      className="absolute -top-1 left-1/2 -translate-x-1/2 -translate-y-full z-50"
                    >
                      <div className={`
                        px-2.5 py-1.5 rounded-lg text-[10px] whitespace-nowrap
                        backdrop-blur-lg border shadow-xl
                        bg-dark-bg dark:bg-dark-card border-dark-border text-dark-text
                      `}>
                        <div className="flex items-center gap-1.5">
                          <span className="animate-pulse text-emerald-400">●</span>
                          <span className="font-medium">{agent.name}</span>
                          <span className="text-dark-muted">—</span>
                          <span className="text-dark-muted max-w-[140px] truncate">{agent.current_action}</span>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>

              {i < WORKFLOW_STEPS.length - 1 && (
                <div className="flex items-center">
                  <motion.div
                    animate={pipeline?.running ? { x: [0, 2, 0], opacity: [0.3, 0.8, 0.3] } : {}}
                    transition={{ repeat: Infinity, duration: 2, delay: i * 0.15 }}
                    className="w-3 sm:w-4 h-0.5 rounded-full"
                    style={{
                      background: pipeline?.running
                        ? 'linear-gradient(90deg, #ec133e, #f4718b)'
                        : undefined,
                      backgroundColor: !pipeline?.running ? 'var(--border-color, #e2e8f0)' : undefined,
                    }}
                  />
                  <svg className="w-2 h-2 text-light-muted/30 dark:text-dark-muted/30 -ml-0.5" fill="currentColor" viewBox="0 0 8 8">
                    <path d="M0 0l4 4-4 4z" />
                  </svg>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex sm:hidden items-center justify-between mt-3 pt-3 border-t border-light-border/50 dark:border-dark-border/50">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-light-muted dark:text-dark-muted">Today</span>
          <span className="font-bold text-light-text dark:text-dark-text">{videosToday}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-light-muted dark:text-dark-muted">Total</span>
          <span className="font-bold text-light-text dark:text-dark-text">{totalVideos}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-light-muted dark:text-dark-muted">Views</span>
          <span className="font-bold text-light-text dark:text-dark-text">{totalViews > 999 ? `${(totalViews / 1000).toFixed(1)}K` : totalViews}</span>
        </div>
        <div className="flex items-center gap-1 text-xs">
          <span className="font-bold text-light-primary">{shortsTodayDone}/{shortsQuota}</span>
          <span className="text-light-muted/40">·</span>
          <span className="font-bold text-sky-500">{longTodayDone}/{longQuota}</span>
        </div>
      </div>
    </div>
  );
}
