'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import {
  collection, onSnapshot, doc, query, orderBy, limit,
  where,
} from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import { ActivePipeline } from '@/components/pipeline/ActivePipeline';
import { RenderingProgress } from '@/components/pipeline/RenderingProgress';
import { AgentGrid } from '@/components/agents/AgentGrid';
import { LiveActivityFeed } from '@/components/activity/LiveActivityFeed';
import { NextUploadTimer } from '@/components/schedule/NextUploadTimer';
import { DockerStatus, StorageStatus, FirebaseStatus } from '@/components/status/SystemStatusWidgets';
import { Rocket, Calendar, Lightbulb, TrendingUp, BarChart3 } from 'lucide-react';
import { AgentWorkflow } from '@/components/pipeline/AgentWorkflow';
import Image from 'next/image';

interface PipelineTrigger {
  id: string;
  topic: string;
  category: string;
  format: string;
  status: string;
  created_at: any;
}

function isToday(timestamp: any): boolean {
  if (!timestamp) return false;
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  return date.toDateString() === new Date().toDateString();
}

export default function DashboardPage() {
  const [currentTime, setCurrentTime] = useState(new Date());
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [videosToday, setVideosToday] = useState(0);
  const [totalVideos, setTotalVideos] = useState(0);
  const [totalViews, setTotalViews] = useState(0);
  const [shortsQuota, setShortsQuota] = useState(2);
  const [longQuota, setLongQuota] = useState(2);
  const [shortsTodayDone, setShortsTodayDone] = useState(0);
  const [longTodayDone, setLongTodayDone] = useState(0);
  const [triggers, setTriggers] = useState<PipelineTrigger[]>([]);
  const [triggerForm, setTriggerForm] = useState({
    topic: '', category: 'science', format: 'shorts', schedule: 'now' as 'now' | 'schedule', publishAt: '',
  });
  const [triggerSubmitting, setTriggerSubmitting] = useState(false);
  const [insights, setInsights] = useState<{
    best_category: string; best_format: string; recommendations: string[];
  } | null>(null);
  const [agentsExpanded, setAgentsExpanded] = useState(true);
  const [runPipelineExpanded, setRunPipelineExpanded] = useState(true);
  const [activityFeedExpanded, setActivityFeedExpanded] = useState(true);
  const [scheduleExpanded, setScheduleExpanded] = useState(true);
  const { addToast } = useToast();

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) setPipelineRunning(snap.data().running || false);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const q = query(collection(db, 'videos'), where('format', 'in', ['shorts', 'long']));
    const unsub = onSnapshot(q, (snap) => {
      const vids: any[] = [];
      snap.docs.forEach(d => vids.push({ id: d.id, ...d.data() }));
      setTotalVideos(vids.length);
      setTotalViews(vids.reduce((s, v) => s + (v.views || 0), 0));
      const today = vids.filter(v => isToday(v.created_at));
      setVideosToday(today.length);
      setShortsTodayDone(today.filter(v => v.format === 'shorts' && v.status === 'uploaded').length);
      setLongTodayDone(today.filter(v => v.format === 'long' && v.status === 'uploaded').length);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'settings', 'general'), (snap) => {
      if (!snap.exists()) return;
      const d = snap.data();
      if (d.shortsPerDay !== undefined) setShortsQuota(d.shortsPerDay);
      if (d.longPerDay !== undefined) setLongQuota(d.longPerDay);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const q = query(collection(db, 'pipeline_triggers'), orderBy('created_at', 'desc'), limit(5));
    const unsub = onSnapshot(q, (snap) => {
      const items: PipelineTrigger[] = [];
      snap.docs.forEach(d => items.push({ id: d.id, ...d.data() } as PipelineTrigger));
      setTriggers(items);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'analytics', 'insights'), (snap) => {
      if (!snap.exists()) return;
      const d = snap.data();
      setInsights({
        best_category: d.best_category || '',
        best_format: d.best_format || '',
        recommendations: d.recommendations || [],
      });
    }, () => {});
    return () => unsub();
  }, []);

  const submitTrigger = useCallback(async () => {
    if (!triggerForm.topic.trim()) {
      addToast('Please enter a topic', 'error');
      return;
    }
    setTriggerSubmitting(true);
    try {
      const publishAt = triggerForm.schedule === 'schedule' && triggerForm.publishAt
        ? new Date(triggerForm.publishAt).toISOString() : null;
      const res = await fetch('/api/pipeline-triggers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: triggerForm.topic.trim(),
          category: triggerForm.category,
          format: triggerForm.format,
          publish_at: publishAt,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      setPipelineRunning(true);
      addToast(
        publishAt
          ? `Scheduled ${triggerForm.format}: "${triggerForm.topic}"`
          : `Triggered ${triggerForm.format}: "${triggerForm.topic}"`,
        'success',
      );
      setTriggerForm({ topic: '', category: 'science', format: 'shorts', schedule: 'now', publishAt: '' });
    } catch {
      addToast('Failed to trigger pipeline', 'error');
    } finally {
      setTriggerSubmitting(false);
    }
  }, [triggerForm, addToast]);

  const greeting = currentTime.getHours() < 12 ? 'Morning'
    : currentTime.getHours() < 18 ? 'Afternoon' : 'Evening';

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
            <h1 className="text-2xl font-bold gradient-text">
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

      {/* Agent Workflow — live pipeline visualization */}
      <AgentWorkflow
        videosToday={videosToday}
        totalVideos={totalVideos}
        totalViews={totalViews}
        shortsQuota={shortsQuota}
        longQuota={longQuota}
        shortsTodayDone={shortsTodayDone}
        longTodayDone={longTodayDone}
      />

      {/* Pipeline Status + Timer row */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="lg:col-span-3">
          <ActivePipeline />
        </div>
        <div className="space-y-3">
          <NextUploadTimer />
        </div>
      </div>

      {/* Rendering Progress */}
      <RenderingProgress />

      {/* Agent Grid */}
      <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
        <button
          onClick={() => setAgentsExpanded(!agentsExpanded)}
          aria-expanded={agentsExpanded}
          className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
        >
          <h2 className="text-sm font-bold gradient-text" title="Live status of all 13 AI agents — shows who's working, idle, or paused">
            Agents
          </h2>
          <motion.svg
            animate={{ rotate: agentsExpanded ? 180 : 0 }}
            className="w-4 h-4 text-light-muted dark:text-dark-muted"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </motion.svg>
        </button>
        <AnimatePresence>
          {agentsExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="border-t border-light-border/50 dark:border-dark-border/50"
            >
              <div className="p-4">
                <AgentGrid />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Run Pipeline + Activity + Status Widgets row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Run Pipeline (span 2) */}
        <div className="lg:col-span-2 rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
          <button
            onClick={() => setRunPipelineExpanded(!runPipelineExpanded)}
            aria-expanded={runPipelineExpanded}
            className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
          >
            <h2 className="text-sm font-bold gradient-text flex items-center gap-2" title="Type a topic and click Run to start generating a video right away — choose Shorts (under 2 min) or Long format">
              <Rocket className="w-4 h-4" /> Run Pipeline
            </h2>
            <motion.svg
              animate={{ rotate: runPipelineExpanded ? 180 : 0 }}
              className="w-4 h-4 text-light-muted dark:text-dark-muted"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </motion.svg>
          </button>
          <AnimatePresence>
            {runPipelineExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-light-border/50 dark:border-dark-border/50"
              >
                <div className="p-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              placeholder="Enter video topic (e.g. Transformers Explained)"
              value={triggerForm.topic}
              onChange={e => setTriggerForm({ ...triggerForm, topic: e.target.value })}
              onKeyDown={e => e.key === 'Enter' && submitTrigger()}
              className="flex-1 px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text placeholder:text-light-muted focus:outline-none focus:ring-2 focus:ring-light-primary text-sm"
            />
            <select
              value={triggerForm.category}
              onChange={e => setTriggerForm({ ...triggerForm, category: e.target.value })}
              className="px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text focus:outline-none focus:ring-2 focus:ring-light-primary text-sm"
            >
              {CONTENT_CATEGORIES.map(cat => (
                <option key={cat.name} value={cat.name}>{cat.name}</option>
              ))}
            </select>
            <div className="flex gap-2">
              {(['shorts', 'long'] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setTriggerForm({ ...triggerForm, format: f })}
                  className={`px-4 py-2.5 rounded-xl font-medium text-sm transition-all capitalize ${
                    triggerForm.format === f
                      ? 'bg-light-primary text-white'
                      : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-muted'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mt-4">
            <div className="flex gap-2">
              {([{ key: 'now' as const, label: 'Publish Now' }, { key: 'schedule' as const, label: 'Schedule' }] as const).map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => setTriggerForm({ ...triggerForm, schedule: key })}
                  className={`px-4 py-2 rounded-xl text-xs font-medium transition-all ${
                    triggerForm.schedule === key
                      ? key === 'now' ? 'bg-light-success text-white' : 'bg-light-secondary text-white'
                      : 'bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-muted'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            {triggerForm.schedule === 'schedule' && (
              <input
                type="datetime-local"
                value={triggerForm.publishAt}
                min={new Date().toISOString().slice(0, 16)}
                onChange={e => setTriggerForm({ ...triggerForm, publishAt: e.target.value })}
                className="px-4 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-light-text dark:text-dark-text text-sm focus:outline-none focus:ring-2 focus:ring-light-secondary"
              />
            )}
            <div className="flex-1" />
            <button
              onClick={submitTrigger}
              disabled={triggerSubmitting || (triggerForm.schedule === 'schedule' && !triggerForm.publishAt)}
              className="px-6 py-2.5 rounded-xl bg-light-success hover:bg-light-success/90 text-white font-medium text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {triggerSubmitting ? 'Starting...' : triggerForm.schedule === 'schedule' ? 'Schedule' : 'Run Now'}
            </button>
          </div>

          {triggers.length > 0 && (
            <div className="mt-4 space-y-1.5">
              {triggers.map(t => (
                <div key={t.id} className="flex items-center gap-3 text-sm p-2.5 rounded-lg bg-light-bg/50 dark:bg-dark-bg/30">
                  <span className={`w-2 h-2 rounded-full ${
                    t.status === 'completed' ? 'bg-emerald-500' :
                    t.status === 'processing' ? 'bg-sky-500 animate-pulse' :
                    t.status === 'failed' ? 'bg-red-500' : 'bg-gray-400'
                  }`} />
                  <span className="flex-1 truncate text-light-text dark:text-dark-text">{t.topic}</span>
                  <span className="text-light-muted capitalize text-xs">{t.format}</span>
                  <span className={`capitalize font-medium text-xs ${
                    t.status === 'completed' ? 'text-emerald-500' :
                    t.status === 'processing' ? 'text-sky-500' :
                    t.status === 'failed' ? 'text-red-500' : 'text-gray-400'
                  }`}>{t.status}</span>
                </div>
              ))}
            </div>
          )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* System Status Widgets */}
        <div className="space-y-3">
          <DockerStatus />
          <StorageStatus />
          <FirebaseStatus />
        </div>
      </div>

      {/* Activity Feed + Insights row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
          <button
            onClick={() => setActivityFeedExpanded(!activityFeedExpanded)}
            aria-expanded={activityFeedExpanded}
            className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
          >
            <h3 className="text-sm font-bold gradient-text" title="Live activity log showing what each agent is doing — updated in real time">
              Activity Feed
            </h3>
            <motion.svg
              animate={{ rotate: activityFeedExpanded ? 180 : 0 }}
              className="w-4 h-4 text-light-muted dark:text-dark-muted"
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </motion.svg>
          </button>
          <AnimatePresence>
            {activityFeedExpanded && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="border-t border-light-border/50 dark:border-dark-border/50"
              >
                <LiveActivityFeed />
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div className="space-y-4">
          {/* Insights */}
          {insights?.best_category && (
            <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 glass-warm p-4 glow-red">
              <h3 className="text-sm font-bold gradient-text mb-3 flex items-center gap-2" title="AI-powered recommendations showing which content categories and formats perform best based on your channel analytics">
                <Lightbulb className="w-4 h-4" /> Insights
              </h3>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-light-muted dark:text-dark-muted flex items-center gap-1">
                    <TrendingUp className="w-3 h-3" /> Best Category
                  </span>
                  <span className="font-semibold text-light-text dark:text-dark-text">{insights.best_category}</span>
                </div>
                <div className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-light-muted dark:text-dark-muted flex items-center gap-1">
                    <BarChart3 className="w-3 h-3" /> Best Format
                  </span>
                  <span className="font-semibold text-light-text dark:text-dark-text capitalize">{insights.best_format}</span>
                </div>
              </div>
              {insights.recommendations.length > 0 && (
                <div className="mt-3 pt-3 border-t border-light-border/50 dark:border-dark-border/50 space-y-1">
                  {insights.recommendations.slice(0, 3).map((rec, i) => (
                    <p key={i} className="text-xs text-light-muted dark:text-dark-muted flex items-start gap-1.5">
                      <span className="text-light-primary mt-0.5">•</span>
                      <span>{rec}</span>
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Content Schedule */}
          <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
            <button
              onClick={() => setScheduleExpanded(!scheduleExpanded)}
              aria-expanded={scheduleExpanded}
              className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
            >
              <h3 className="text-sm font-bold gradient-text flex items-center gap-2" title="Daily content plan — shows how many shorts and long-form videos are scheduled vs how many have been completed so far today">
                <Calendar className="w-4 h-4" /> Today&apos;s Schedule
              </h3>
              <motion.svg
                animate={{ rotate: scheduleExpanded ? 180 : 0 }}
                className="w-4 h-4 text-light-muted dark:text-dark-muted"
                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </motion.svg>
            </button>
            <AnimatePresence>
              {scheduleExpanded && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="border-t border-light-border/50 dark:border-dark-border/50"
                >
                  <div className="p-4 space-y-3">
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-light-primary">Shorts (9:16)</span>
                        <span className="text-light-muted dark:text-dark-muted">{shortsTodayDone}/{shortsQuota}</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${shortsQuota > 0 ? (shortsTodayDone / shortsQuota) * 100 : 0}%` }}
                          className="h-full rounded-full bg-gradient-to-r from-light-primary to-rose-400"
                          transition={{ duration: 0.8 }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="font-medium text-sky-500">Long Form (16:9)</span>
                        <span className="text-light-muted dark:text-dark-muted">{longTodayDone}/{longQuota}</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${longQuota > 0 ? (longTodayDone / longQuota) * 100 : 0}%` }}
                          className="h-full rounded-full bg-gradient-to-r from-sky-400 to-blue-500"
                          transition={{ duration: 0.8 }}
                        />
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
