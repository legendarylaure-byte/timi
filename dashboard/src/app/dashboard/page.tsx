'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, updateDoc, query, orderBy, limit } from 'firebase/firestore';
import { AGENT_ROLES } from '@/lib/constants';
import { GradientCard } from '@/components/ui/GradientCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { useToast } from '@/components/ui/Toast';
import { HappyScene } from '@/components/3d/HappyScene';
import Image from 'next/image';

interface AgentStatus {
  agent_id: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: any;
  error_message?: string;
}

interface ActivityLog {
  id: string;
  agent_id: string;
  message: string;
  level: string;
  timestamp: any;
}

interface VideoDoc {
  id: string;
  format: string;
  status: string;
  views: number;
  created_at: any;
}

const gradients: Record<string, string> = {
  primary: 'linear-gradient(135deg, #FF4D6D, #7C3AED)',
  warm: 'linear-gradient(135deg, #FF4D6D, #FBBF24)',
  cool: 'linear-gradient(135deg, #7C3AED, #3B82F6)',
  success: 'linear-gradient(135deg, #10B981, #3B82F6)',
};

function isToday(timestamp: any): boolean {
  if (!timestamp) return false;
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const now = new Date();
  return date.toDateString() === now.toDateString();
}

export default function DashboardPage() {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [agentStatuses, setAgentStatuses] = useState<Record<string, AgentStatus>>({});
  const [activityLogs, setActivityLogs] = useState<ActivityLog[]>([]);
  const [pipelineStatus, setPipelineStatus] = useState({ running: false, current_video: '' });
  const [videosToday, setVideosToday] = useState(0);
  const [totalVideos, setTotalVideos] = useState(0);
  const [totalViews, setTotalViews] = useState(0);
  const [shortsQuota, setShortsQuota] = useState(2);
  const [longQuota, setLongQuota] = useState(2);
  const [shortsTodayDone, setShortsTodayDone] = useState(0);
  const [longTodayDone, setLongTodayDone] = useState(0);
  const { addToast } = useToast();

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const q = query(collection(db, 'agent_status'));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const newStatuses: Record<string, AgentStatus> = {};
      snapshot.docs.forEach((doc) => {
        newStatuses[doc.id] = { agent_id: doc.id, ...doc.data() } as AgentStatus;
      });
      setAgentStatuses(newStatuses);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const q = query(collection(db, 'activity_logs'), orderBy('timestamp', 'desc'), limit(20));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const logs: ActivityLog[] = [];
      snapshot.docs.forEach((doc) => {
        logs.push({ id: doc.id, ...doc.data() } as ActivityLog);
      });
      setActivityLogs(logs);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const docRef = doc(db, 'system', 'pipeline');
    const unsubscribe = onSnapshot(docRef, (docSnap) => {
      if (docSnap.exists()) {
        setPipelineStatus(docSnap.data() as any);
      }
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const q = collection(db, 'videos');
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const vids: VideoDoc[] = [];
      snapshot.docs.forEach((d) => {
        vids.push({ id: d.id, ...d.data() } as VideoDoc);
      });

      setTotalVideos(vids.length);
      setTotalViews(vids.reduce((sum, v) => sum + (v.views || 0), 0));

      const todayVids = vids.filter((v) => isToday(v.created_at));
      setVideosToday(todayVids.length);

      const shortsDone = todayVids.filter((v) => v.format === 'shorts' && v.status === 'uploaded').length;
      const longDone = todayVids.filter((v) => v.format === 'long' && v.status === 'uploaded').length;
      setShortsTodayDone(shortsDone);
      setLongTodayDone(longDone);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'settings', 'general'), (snap) => {
      if (snap.exists()) {
        const data = snap.data();
        if (data.shortsPerDay !== undefined) setShortsQuota(data.shortsPerDay);
        if (data.longPerDay !== undefined) setLongQuota(data.longPerDay);
      }
    });
    return () => unsub();
  }, []);

  const toggleAgent = useCallback(async (agentId: string, currentEnabled: boolean) => {
    try {
      const docRef = doc(db, 'agent_status', agentId);
      await updateDoc(docRef, { enabled: !currentEnabled });
      addToast(
        `${AGENT_ROLES.find((a) => a.id === agentId)?.name || agentId} ${!currentEnabled ? 'resumed' : 'paused'}`,
        !currentEnabled ? 'success' : 'info'
      );
    } catch (error) {
      addToast('Failed to update agent status', 'error');
    }
  }, [addToast]);

  const getAgentColor = (agentId: string) => {
    return AGENT_ROLES.find((a) => a.id === agentId)?.color || '#6B7280';
  };

  const getAgentName = (agentId: string) => {
    return AGENT_ROLES.find((a) => a.id === agentId)?.name || agentId;
  };

  const formatTime = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  const greeting = currentTime.getHours() < 12 ? 'Morning' : currentTime.getHours() < 18 ? 'Afternoon' : 'Evening';

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
      >
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-light-text dark:text-dark-text">
              Good {greeting}!
            </h1>
            <p className="text-light-muted dark:text-dark-muted mt-0.5">
              Here&apos;s what your AI agents are working on
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-2xl font-mono font-bold gradient-text">
            {currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </p>
          <p className="text-sm text-light-muted dark:text-dark-muted">
            {currentTime.toLocaleDateString([], { weekday: 'long', month: 'long', day: 'numeric' })}
          </p>
        </div>
      </motion.div>

      {/* 3D Hero Scene */}
      <motion.div
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ delay: 0.1, duration: 0.5 }}
      >
        <HappyScene />
      </motion.div>

      {/* Pipeline Status Banner */}
      <AnimatePresence>
        {pipelineStatus.running && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="rounded-xl p-4 border border-light-success/30 bg-light-success/5 dark:bg-dark-success/5"
          >
            <div className="flex items-center gap-3">
              <motion.div
                className="w-3 h-3 rounded-full bg-light-success"
                animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                transition={{ duration: 2, repeat: Infinity }}
              />
              <p className="text-sm font-medium text-light-success">
                Pipeline running — Generating: <span className="font-bold">{pipelineStatus.current_video}</span>
              </p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: 'Videos Today', value: `${videosToday}`, suffix: `/${shortsQuota + longQuota}`, icon: '🎬', gradient: 'primary' as const },
          { label: 'Total Videos', value: `${totalVideos}`, icon: '📁', gradient: 'warm' as const },
          { label: 'Total Views', value: `${totalViews > 999 ? (totalViews / 1000).toFixed(1) + 'K' : totalViews}`, icon: '👁️', gradient: 'cool' as const },
          { label: 'Trending Topics', value: '10', icon: '🔥', gradient: 'warm' as const },
          { label: 'Clips Ready', value: '9', icon: '✂️', gradient: 'success' as const },
        ].map((stat, i) => (
          <GradientCard key={stat.label} gradient={stat.gradient} delay={0.1 + i * 0.1}>
            <div className="flex items-center justify-between mb-3">
              <motion.span
                className="text-2xl"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.2 + i * 0.1, type: 'spring' }}
              >
                {stat.icon}
              </motion.span>
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold"
                style={{ background: gradients[stat.gradient] }}
              >
                {stat.icon}
              </div>
            </div>
            <p className="text-2xl font-bold text-light-text dark:text-dark-text">
              {stat.value}
              {stat.suffix && <span className="text-light-muted dark:text-dark-muted text-lg font-normal">{stat.suffix}</span>}
            </p>
            <p className="text-sm text-light-muted dark:text-dark-muted">{stat.label}</p>
          </GradientCard>
        ))}
      </div>

      {/* Agent Status + Activity Feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Status with Controls */}
        <GradientCard gradient="cool" className="h-full">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Agent Status</h2>
          <div className="space-y-3">
            {AGENT_ROLES.map((agent, i) => {
              const status = agentStatuses[agent.id];
              const agentStatus = status?.status || 'idle';
              const isEnabled = status?.enabled ?? true;

              return (
                <motion.div
                  key={agent.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 p-3 rounded-xl hover:bg-light-primary/5 dark:hover:bg-white/5 transition-colors group"
                >
                  {/* Color bar */}
                  <div
                    className="w-1.5 h-10 rounded-full shrink-0"
                    style={{ backgroundColor: agent.color }}
                  />

                  {/* Agent info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-light-text dark:text-dark-text truncate">
                        {agent.name}
                      </p>
                      <StatusBadge status={agentStatus as any} size="sm" />
                    </div>
                    {status?.current_action && (
                      <p className="text-xs text-light-muted dark:text-dark-muted truncate mt-0.5">
                        {status.current_action}
                      </p>
                    )}
                  </div>

                  {/* Toggle control */}
                  <button
                    onClick={() => toggleAgent(agent.id, isEnabled)}
                    className={`shrink-0 w-10 h-6 rounded-full transition-all duration-200 ${
                      isEnabled
                        ? 'bg-light-success'
                        : 'bg-light-muted dark:bg-dark-muted'
                    }`}
                  >
                    <motion.div
                      className="w-5 h-5 rounded-full bg-white shadow-sm"
                      animate={{ x: isEnabled ? 20 : 2 }}
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                    />
                  </button>
                </motion.div>
              );
            })}
          </div>
        </GradientCard>

        {/* Activity Feed */}
        <GradientCard gradient="success" className="h-full">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Activity Feed</h2>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {activityLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-light-muted dark:text-dark-muted">
                <motion.div
                  animate={{ y: [0, -8, 0] }}
                  transition={{ duration: 2, repeat: Infinity }}
                  className="text-4xl mb-3"
                >
                  🤖
                </motion.div>
                <p className="text-sm font-medium">Agents are warming up...</p>
                <p className="text-xs mt-1">Activity will appear here when agents start working</p>
              </div>
            ) : (
              activityLogs.map((log, i) => (
                <motion.div
                  key={log.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * 0.05, 0.5) }}
                  className="flex items-start gap-3 p-3 rounded-xl bg-light-bg dark:bg-dark-bg/50"
                >
                  <div
                    className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${
                      log.level === 'success' ? 'bg-light-success animate-pulse' :
                      log.level === 'error' ? 'bg-light-primary animate-pulse' :
                      'bg-light-info'
                    }`}
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-light-text dark:text-dark-text">
                      <span className="font-medium" style={{ color: getAgentColor(log.agent_id) }}>
                        {getAgentName(log.agent_id)}
                      </span>
                      {' '}
                      {log.message}
                    </p>
                    <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">
                      {formatTime(log.timestamp)}
                    </p>
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </GradientCard>
      </div>

      {/* Content Schedule */}
      <GradientCard gradient="warm">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Today&apos;s Content Schedule</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="p-4 rounded-xl border border-light-primary/20 bg-light-primary/5 dark:bg-light-primary/5">
            <h3 className="font-semibold text-light-primary mb-2">Shorts (9:16)</h3>
            <p className="text-sm text-light-muted dark:text-dark-muted">{shortsQuota} videos planned</p>
            <div className="mt-3 h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${shortsQuota > 0 ? (shortsTodayDone / shortsQuota) * 100 : 0}%` }}
                transition={{ duration: 1, delay: 0.5 }}
                className="h-full rounded-full"
                style={{ background: gradients.primary }}
              />
            </div>
            <p className="text-xs text-light-muted dark:text-dark-muted mt-1.5">{shortsTodayDone} of {shortsQuota} completed</p>
          </div>
          <div className="p-4 rounded-xl border border-light-secondary/20 bg-light-secondary/5 dark:bg-light-secondary/5">
            <h3 className="font-semibold text-light-secondary mb-2">Long Form (16:9)</h3>
            <p className="text-sm text-light-muted dark:text-dark-muted">{longQuota} videos planned</p>
            <div className="mt-3 h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${longQuota > 0 ? (longTodayDone / longQuota) * 100 : 0}%` }}
                transition={{ duration: 1, delay: 0.7 }}
                className="h-full rounded-full"
                style={{ background: gradients.cool }}
              />
            </div>
            <p className="text-xs text-light-muted dark:text-dark-muted mt-1.5">{longTodayDone} of {longQuota} completed</p>
          </div>
        </div>
      </GradientCard>
    </div>
  );
}
