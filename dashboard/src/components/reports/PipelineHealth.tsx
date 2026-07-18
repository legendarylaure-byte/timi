'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Activity, CheckCircle, XCircle, Clock, DollarSign, TrendingUp, Loader2, AlertTriangle, Video, Music2, Camera, Globe } from 'lucide-react';
import { auth } from '@/lib/firebase';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts';

interface PipelineData {
  successRate: number;
  totalRuns: number;
  avgDurationSec: number;
  isRunning: boolean;
  stepBreakdown: Array<{
    step: string; label: string; avgDurationSec: number;
    failureCount: number; successRate: number; totalRuns: number;
  }>;
  recentErrors: Array<{ time: string; step: string; error: string; agentId: string }>;
  estimatedCostMTD: number;
  revenueMTD: number;
  roi: number;
  publishErrors: Array<{ time: string; platform: string; error: string }>;
  platformFailCount: Record<string, number>;
  freshness: string;
}

export function PipelineHealth() {
  const [data, setData] = useState<PipelineData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const user = auth.currentUser;
        if (!user) return;
        const token = await user.getIdToken();
        const res = await fetch('/api/reports/pipeline-health', {
          headers: { authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-sm text-red-400">Failed to load pipeline health: {error}</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="glass rounded-xl p-12 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-light-muted" />
      </div>
    );
  }

  const successColor = data.successRate >= 80 ? 'text-emerald-400' : data.successRate >= 50 ? 'text-yellow-400' : 'text-red-400';
  const successBg = data.successRate >= 80 ? 'from-emerald-500/20' : data.successRate >= 50 ? 'from-yellow-500/20' : 'from-red-500/20';

  const formatDuration = (sec: number) => {
    if (sec < 60) return `${sec}s`;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return s > 0 ? `${m}m ${s}s` : `${m}m`;
  };

  const formatTime = (iso: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className={`glass rounded-xl p-4 border bg-gradient-to-br ${successBg} border-emerald-500/20`}
        >
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-light-muted dark:text-dark-muted uppercase tracking-wider">Success Rate</span>
            {data.isRunning ? (
              <span className="flex items-center gap-1 text-xs text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" /> Running
              </span>
            ) : (
              <span className="text-xs text-light-muted">Idle</span>
            )}
          </div>
          <div className={`text-2xl font-bold ${successColor}`}>{data.successRate}%</div>
          <div className="text-xs text-light-muted mt-1">{data.totalRuns} total runs</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="glass rounded-xl p-4 border border-blue-500/20"
        >
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-light-muted uppercase tracking-wider">Avg Duration</span>
          </div>
          <div className="text-2xl font-bold text-blue-400">{formatDuration(data.avgDurationSec)}</div>
          <div className="text-xs text-light-muted mt-1">Per pipeline run</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="glass rounded-xl p-4 border border-purple-500/20"
        >
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-light-muted uppercase tracking-wider">Est. Cost (MTD)</span>
          </div>
          <div className="text-2xl font-bold text-purple-400">${data.estimatedCostMTD.toFixed(2)}</div>
          <div className="text-xs text-light-muted mt-1">Compute + API costs</div>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
          className="glass rounded-xl p-4 border border-orange-500/20"
        >
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-orange-400" />
            <span className="text-xs text-light-muted uppercase tracking-wider">ROI</span>
          </div>
          <div className="text-2xl font-bold text-orange-400">{data.roi.toFixed(1)}x</div>
          <div className="text-xs text-light-muted mt-1">${data.revenueMTD.toFixed(2)} revenue vs ${data.estimatedCostMTD.toFixed(2)} cost</div>
        </motion.div>
      </div>

      {data.stepBreakdown.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4">Step Duration Breakdown</h3>
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.stepBreakdown} layout="vertical" margin={{ top: 5, right: 30, left: 80, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#6B7280' }} tickFormatter={(v: number) => `${Math.round(v / 60)}m`} />
                <YAxis type="category" dataKey="label" tick={{ fontSize: 11, fill: '#6B7280' }} width={90} />
                <Tooltip
                  contentStyle={{
                    background: 'rgba(0,0,0,0.8)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '12px',
                    fontSize: '12px',
                  }}
                  formatter={(value: any) => [formatDuration(Number(value) || 0), 'Avg Duration']}
                />
                <Bar dataKey="avgDurationSec" radius={[0, 6, 6, 0]} maxBarSize={20}>
                  {data.stepBreakdown.map((_, idx) => {
                    const colors = ['#8a50e8', '#c060d0', '#e07040', '#8a50e8', '#c060d0', '#e07040', '#8a50e8', '#c060d0', '#e07040', '#ffffff'];
                    return <Cell key={idx} fill={colors[idx % colors.length]} fillOpacity={0.8} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {data.recentErrors.length > 0 && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            Recent Errors
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {data.recentErrors.map((err, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10">
                <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-red-400">{err.step}</span>
                    <span className="text-[10px] text-light-muted">{formatTime(err.time)}</span>
                  </div>
                  <p className="text-xs text-light-muted truncate">{err.error}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.recentErrors.length === 0 && (
        <div className="glass rounded-xl p-6 text-center">
          <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
          <p className="text-sm text-light-muted">No recent errors — pipeline is running smoothly</p>
        </div>
      )}

      {/* Platform Publish Status */}
      <div className="glass rounded-xl p-6">
        <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
          <Globe className="w-4 h-4 text-blue-400" />
          Platform Publish Status
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          {[
            { id: 'youtube', label: 'YouTube', icon: Video, color: 'text-red-400' },
            { id: 'tiktok', label: 'TikTok', icon: Music2, color: 'text-purple-400' },
            { id: 'instagram', label: 'Instagram', icon: Camera, color: 'text-pink-400' },
            { id: 'facebook', label: 'Facebook', icon: Globe, color: 'text-blue-400' },
          ].map((p) => {
            const failCount = data.platformFailCount?.[p.id] || 0;
            const status = failCount === 0 ? 'healthy' : failCount <= 2 ? 'degraded' : 'failing';
            const statusColor = status === 'healthy' ? 'text-emerald-400' : status === 'degraded' ? 'text-yellow-400' : 'text-red-400';
            const bgColor = status === 'healthy' ? 'border-emerald-500/20' : status === 'degraded' ? 'border-yellow-500/20' : 'border-red-500/20';
            return (
              <div key={p.id} className={`glass rounded-xl p-3 border ${bgColor} text-center`}>
                <p.icon className={`w-5 h-5 ${p.color} mx-auto mb-1`} />
                <div className="text-xs font-medium text-light-text dark:text-dark-text truncate">{p.label}</div>
                <div className={`text-lg font-bold ${statusColor}`}>
                  {failCount === 0 ? '✓' : failCount}
                </div>
                <div className="text-[10px] text-light-muted">{status === 'healthy' ? 'OK' : status === 'degraded' ? `${failCount} issues` : 'Failing'}</div>
              </div>
            );
          })}
        </div>

        {data.publishErrors.length > 0 && (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {data.publishErrors.map((err, i) => {
              const plat = err.platform;
              const pColor = plat === 'tiktok' ? 'text-purple-400' : plat === 'instagram' ? 'text-pink-400' : plat === 'facebook' ? 'text-blue-400' : 'text-red-400';
              return (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/10">
                  <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs font-medium ${pColor}`}>{err.platform}</span>
                      <span className="text-[10px] text-light-muted">{formatTime(err.time)}</span>
                    </div>
                    <p className="text-xs text-light-muted truncate">{err.error}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {data.publishErrors.length === 0 && (
          <p className="text-xs text-light-muted text-center">All platforms publishing normally</p>
        )}
      </div>
    </div>
  );
}
