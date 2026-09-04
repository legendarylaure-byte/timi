'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Activity, BarChart3, Gauge, Sparkles } from 'lucide-react';
import { auth } from '@/lib/firebase';
import { LivePayload, ReviewPayload } from '@/lib/monitor';
import { LivePipeline } from '@/components/monitor/LivePipeline';
import { ResourceHealth } from '@/components/monitor/ResourceHealth';
import { HealthScore } from '@/components/monitor/HealthScore';
import { ActivityReview } from '@/components/monitor/ActivityReview';
import { GrowthView } from '@/components/monitor/GrowthView';
import { ForecastRisks } from '@/components/monitor/ForecastRisks';
import { AdvisorPanel } from '@/components/monitor/AdvisorPanel';
import { ToastProvider } from '@/components/ui/Toast';

const tabs = [
  { id: 'live', label: 'Live', icon: Activity },
  { id: 'review', label: 'Review', icon: BarChart3 },
  { id: 'advisor', label: 'Advisor', icon: Sparkles },
] as const;

type TabId = typeof tabs[number]['id'];

async function authHeaders(): Promise<Record<string, string>> {
  const u = auth.currentUser;
  const token = u ? await u.getIdToken() : '';
  const h: Record<string, string> = {};
  if (token) h['Authorization'] = `Bearer ${token}`;
  return h;
}

export default function MonitorPage() {
  const [activeTab, setActiveTab] = useState<TabId>('live');
  const [live, setLive] = useState<LivePayload | null>(null);
  const [review, setReview] = useState<ReviewPayload | null>(null);
  const [reviewLoading, setReviewLoading] = useState(true);

  const loadLive = useCallback(async () => {
    try {
      const res = await fetch('/api/monitor/live', { headers: await authHeaders() });
      if (res.ok) setLive((await res.json()) as LivePayload);
    } catch { /* transient */ }
  }, []);

  const loadReview = useCallback(async () => {
    try {
      const res = await fetch('/api/monitor/review', { headers: await authHeaders() });
      if (res.ok) setReview((await res.json()) as ReviewPayload);
    } finally {
      setReviewLoading(false);
    }
  }, []);

  useEffect(() => {
    loadReview();
    loadLive();
    const id = setInterval(loadLive, 5000);
    return () => clearInterval(id);
  }, [loadLive, loadReview]);

  const successRate = review?.pipeline.success_rate ?? 0;
  const heartbeatLive = live?.heartbeat.status === 'fresh';
  const viewsTrend = (review?.videos.slice().reverse() || []).map((v) => v.views);
  const videoTrendGood =
    viewsTrend.length >= 3 &&
    viewsTrend[viewsTrend.length - 1] >= (viewsTrend[0] || 1);

  return (
    <ToastProvider>
      <div className="space-y-5">
        <Header />

        {/* Tabs */}
        <div className="flex gap-1.5 rounded-2xl glass-panel p-1 w-fit">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = activeTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`relative inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${active ? 'text-white' : 'text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text'}`}
              >
                {active && (
                  <motion.span
                    layoutId="monitor-tab"
                    className="absolute inset-0 rounded-xl"
                    style={{ background: 'linear-gradient(135deg, #ec133e, #bd0f32)' }}
                    transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                  />
                )}
                <Icon className="relative z-10 w-4 h-4" />
                <span className="relative z-10">{t.label}</span>
              </button>
            );
          })}
        </div>

        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {activeTab === 'live' && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2">
                  <LivePipeline live={live} />
                </div>
                <div className="lg:col-span-1 space-y-4">
                  <ResourceHealth live={live} />
                </div>
              </div>
            )}

            {activeTab === 'review' && (
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <HealthScore successRate={successRate} heartbeatLive={heartbeatLive} videoTrendGood={videoTrendGood} />
                <GrowthView data={review} />
                <ForecastRisks live={live} review={review} />
                <div className="lg:col-span-3">
                  <ActivityReview data={review} />
                </div>
              </div>
            )}

            {activeTab === 'advisor' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <AdvisorPanel review={review} />
                <HowToCard />
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </ToastProvider>
  );
}

function Header() {
  return (
    <div>
      <h1 className="text-2xl md:text-3xl font-bold gradient-text flex items-center gap-3">
        <Activity className="w-7 h-7" /> Mission Control
      </h1>
      <p className="text-sm text-light-muted dark:text-dark-muted mt-1">
        One command center for everything your video pipeline is doing, how it&apos;s trending, and how to make it go viral.
      </p>
    </div>
  );
}

function HowToCard() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="glass-panel p-6 rounded-2xl"
    >
      <h3 className="text-sm font-bold text-light-text dark:text-dark-text mb-3">How to use the Advisor</h3>
      <ol className="space-y-3 text-sm text-light-muted dark:text-dark-muted">
        {[
          'Click "Generate & copy command".',
          'Open your Mac terminal in the timi folder.',
          'Paste and run the command — it uses your local AI (no cloud).',
          'It prints a ready-to-paste improvement prompt.',
          'Paste that prompt into your favorite AI coding assistant to upgrade the pipeline.',
        ].map((step, i) => (
          <li key={i} className="flex items-start gap-3">
            <span className="w-6 h-6 rounded-full bg-light-primary/10 dark:bg-dark-primary/10 text-light-primary dark:text-dark-primary text-xs font-bold flex items-center justify-center shrink-0">
              {i + 1}
            </span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      <div className="mt-4 p-3 rounded-xl bg-light-bg/60 dark:bg-dark-bg/60 border border-light-border/30 dark:border-dark-border/30">
        <p className="text-[11px] text-light-muted dark:text-dark-muted flex items-center gap-1.5">
          <Gauge className="w-3.5 h-3.5" />
          The improvement prompt comes straight from your own production data — failures, bottlenecks, and what&apos;s trending.
        </p>
      </div>
    </motion.div>
  );
}