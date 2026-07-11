'use client';

import { useState, useEffect } from 'react';
import { auth } from '@/lib/firebase';
import { motion } from 'framer-motion';
import {
  FlaskConical, Play, Square, RefreshCw, CheckCircle2,
  XCircle, Clock, ChevronRight, BarChart3,
} from 'lucide-react';

interface TitleVariant {
  title: string;
  formula?: string;
  ctr_prediction?: string;
}

interface TitleTest {
  videoId: string;
  youtubeId: string;
  title: string;
  variants: TitleVariant[];
  currentIndex: number;
  status: string;
  startedAt: string;
  stageEnd: string;
  results: Record<string, number | null>;
  winner: { title: string; ctr: number; method: string } | null;
  format: string;
  category: string;
  publishedAt: string;
}

export function TitleTesting() {
  const [tests, setTests] = useState<TitleTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [advancing, setAdvancing] = useState<string | null>(null);

  const getToken = async (): Promise<string | null> => {
    const user = auth.currentUser;
    if (!user) return null;
    try {
      return await user.getIdToken();
    } catch {
      return null;
    }
  };

  const fetchTests = async () => {
    const token = await getToken();
    if (!token) return;
    try {
      setLoading(true);
      const res = await fetch('/api/reports/title-tests', {
        headers: { authorization: `Bearer ${token}` },
      });
      const json = await res.json();
      if (json.success) {
        setTests(json.tests || []);
      } else {
        setError(json.error || 'Failed to load');
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    const init = async () => {
      const token = await getToken();
      if (token && !cancelled) fetchTests();
    };
    init();
    return () => { cancelled = true; };
  }, []);

  const authHeaders = async (): Promise<Record<string, string>> => {
    const token = await getToken();
    const headers: Record<string, string> = {};
    if (token) headers['authorization'] = `Bearer ${token}`;
    return headers;
  };

  const handleAdvance = async (videoId: string) => {
    setAdvancing(videoId);
    try {
      const headers = await authHeaders();
      await fetch('/api/reports/title-tests', {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ videoId, action: 'advance' }),
      });
      await fetchTests();
    } catch { /* ignore */ }
    setAdvancing(null);
  };

  const handleStop = async (videoId: string) => {
    try {
      const headers = await authHeaders();
      await fetch('/api/reports/title-tests', {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
        body: JSON.stringify({ videoId, action: 'stop' }),
      });
      await fetchTests();
    } catch { /* ignore */ }
  };

  const statusBadge = (status: string) => {
    const styles: Record<string, string> = {
      testing: 'bg-blue-500/20 text-blue-400',
      completed: 'bg-green-500/20 text-green-400',
      waiting: 'bg-yellow-500/20 text-yellow-400',
      stopped: 'bg-gray-500/20 text-gray-400',
      failed: 'bg-red-500/20 text-red-400',
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[status] || 'bg-gray-500/20 text-gray-400'}`}>
        {status}
      </span>
    );
  };

  if (loading && tests.length === 0) {
    return (
      <div className="p-6 text-center text-light-muted dark:text-dark-muted">
        <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2" />
        Loading title tests...
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FlaskConical className="w-5 h-5 text-blue-400" />
            A/B Title Testing
          </h2>
          <p className="text-sm text-light-muted dark:text-dark-muted mt-1">
            {tests.length} test{tests.length !== 1 ? 's' : ''} found — sequential 24h variant rotation
          </p>
        </div>
        <button
          onClick={fetchTests}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-light-border/50 dark:hover:bg-dark-border/50 transition-all"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 text-red-400 text-sm">{error}</div>
      )}

      {tests.length === 0 ? (
        <div className="p-8 text-center text-light-muted dark:text-dark-muted border border-dashed border-light-border dark:border-dark-border rounded-xl">
          <FlaskConical className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p>No A/B title tests found</p>
          <p className="text-xs mt-1">Tests are created automatically when a video is published with multiple title variants</p>
        </div>
      ) : (
        <div className="space-y-4">
          {tests.map((test) => {
            const currentVariant = test.variants[test.currentIndex];
            const progress = test.variants.length > 0
              ? Math.round((test.currentIndex / test.variants.length) * 100)
              : 0;

            return (
              <div
                key={test.videoId}
                className="p-4 rounded-xl bg-light-card dark:bg-dark-card border border-light-border dark:border-dark-border"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-medium text-sm truncate">{test.title}</h3>
                      {statusBadge(test.status)}
                    </div>
                    <p className="text-xs text-light-muted dark:text-dark-muted">
                      {test.format} &middot; {test.category} &middot; {test.variants.length} variants
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {test.status === 'testing' && (
                      <>
                        <button
                          onClick={() => handleAdvance(test.videoId)}
                          disabled={advancing === test.videoId}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-all disabled:opacity-50"
                        >
                          {advancing === test.videoId ? (
                            <RefreshCw className="w-3 h-3 animate-spin" />
                          ) : (
                            <Play className="w-3 h-3" />
                          )}
                          Advance
                        </button>
                        <button
                          onClick={() => handleStop(test.videoId)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 hover:bg-red-500/30 transition-all"
                        >
                          <Square className="w-3 h-3" />
                          Stop
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="mt-3 h-1.5 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
                  <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-blue-500 to-purple-500"
                    initial={{ width: 0 }}
                    animate={{ width: `${progress}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>

                {/* Variants */}
                <div className="mt-3 space-y-2">
                  {test.variants.map((v, i) => {
                    const isCurrent = i === test.currentIndex;
                    const isPast = i < test.currentIndex;
                    const isWinner = test.winner?.title === v.title;
                    const ctr = test.results?.[v.title];

                    return (
                      <div
                        key={i}
                        className={`flex items-center gap-3 p-2 rounded-lg text-xs ${
                          isCurrent
                            ? 'bg-blue-500/10 border border-blue-500/30'
                            : isPast
                            ? 'bg-green-500/5 border border-green-500/20'
                            : 'bg-light-border/20 dark:bg-dark-border/20 border border-transparent'
                        }`}
                      >
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                          isCurrent ? 'bg-blue-500 text-white' :
                          isPast ? 'bg-green-500 text-white' :
                          'bg-light-border dark:bg-dark-border text-light-muted'
                        }`}>
                          {isWinner ? <CheckCircle2 className="w-3 h-3" /> : i + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className={`block truncate ${isCurrent ? 'font-medium' : ''}`}>
                            {v.title}
                          </span>
                          {v.formula && (
                            <span className="text-light-muted dark:text-dark-muted">{v.formula}</span>
                          )}
                        </div>
                        <div className="text-right shrink-0">
                          {ctr !== undefined && ctr !== null ? (
                            <span className="font-mono text-green-400">{(ctr * 100).toFixed(1)}%</span>
                          ) : isPast ? (
                            <span className="text-light-muted dark:text-dark-muted">no CTR data</span>
                          ) : isCurrent ? (
                            <span className="flex items-center gap-1 text-blue-400">
                              <Clock className="w-3 h-3" /> live
                            </span>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Winner */}
                {test.winner && (
                  <div className="mt-3 p-2 rounded-lg bg-green-500/10 border border-green-500/30 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                    <span className="text-xs font-medium">Winner: </span>
                    <span className="text-xs truncate flex-1">{test.winner.title}</span>
                    <span className="text-xs font-mono text-green-400">
                      {(test.winner.ctr * 100).toFixed(1)}% CTR
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
