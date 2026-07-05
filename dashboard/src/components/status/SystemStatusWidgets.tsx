'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';

interface DockerData {
  available: boolean;
  container_count: number;
  all_running: boolean;
  pipeline?: { status: string; state: string; uptime: string };
  containers?: Array<{ name: string; status: string; state: string; uptime: string }>;
  reason?: string;
  error?: string;
}

interface StorageData {
  connected: boolean;
  configured?: boolean;
  total_size_gb: number;
  limit_gb: number;
  objects: number;
  free_percent: number;
  pending_deletion: number;
  error?: string;
}

interface FirebaseData {
  connected: boolean;
  latency_ms: number;
  heartbeat?: { status: string; last_beat: string };
  error?: string;
}

async function fetchJson(url: string): Promise<any> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function StatusDot({ status }: { status: 'ok' | 'warn' | 'error' | 'unknown' }) {
  const colors = {
    ok: 'bg-emerald-500',
    warn: 'bg-amber-400',
    error: 'bg-red-500',
    unknown: 'bg-gray-400',
  };
  return (
    <span className={`w-2 h-2 rounded-full ${colors[status]} ${status !== 'ok' ? 'animate-pulse' : ''}`} />
  );
}

export function DockerStatus() {
  const [data, setData] = useState<DockerData | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const poll = async () => {
      const d = await fetchJson('/api/docker');
      setData(d);
    };
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, []);

  const isCloud = data?.reason === 'vercel_serverless';
  const status: 'ok' | 'warn' | 'error' | 'unknown' = !data ? 'unknown'
    : isCloud ? 'warn'
    : data.available && data.all_running ? 'ok'
    : data.available ? 'warn'
    : 'error';

  return (
    <div className="rounded-xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card p-3">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between" title="Docker runs your pipeline container in the background — click to see container details">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-[#2496ED]" viewBox="0 0 24 24" fill="currentColor">
            <path d="M22.5 10.5c-1.5-1.5-4.5-2-7.5-1-1.5-4.5-6-7-10-6.5-1.5 0-3 .5-4 1.5-1 1-1.5 2.5-1.5 4 0 3.5 2.5 6.5 6 7 1 1.5 2.5 2.5 4 3 .5 1.5 1.5 3 3 4 1.5 1 3 1.5 4.5 1 2.5-1 4-3.5 4-6s-1-4.5-2.5-6zM8 7h1v1H8V7zm2-2h1v1h-1V5zm0 4h1v1h-1V9zm-2-1h1v1H8V8zm0 3h1v1H8v-1zm2 4h1v1h-1v-1zm2-3h1v1h-1v-1zm-2 1h1v1h-1v-1zm-2 0h1v1H8v-1zm0-6h1v1H8V6z"/>
          </svg>
          <div className="text-left">
            <h4 className="text-xs font-semibold text-light-text dark:text-dark-text">Docker</h4>
            <p className="text-[10px] text-light-muted dark:text-dark-muted">
              {isCloud ? 'N/A (cloud)' : data ? `${data.container_count} container${data.container_count !== 1 ? 's' : ''}` : '...'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-light-muted dark:text-dark-muted">{status}</span>
          <StatusDot status={status} />
        </div>
      </button>

      {expanded && data && !isCloud && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="mt-2 pt-2 border-t border-light-border/50 dark:border-dark-border/50 space-y-1"
        >
          {data.containers?.map((c, i) => (
            <div key={i} className="flex items-center justify-between text-[10px] py-0.5">
              <span className="text-light-text dark:text-dark-text font-mono truncate max-w-[120px]">{c.name}</span>
              <span className={`${c.state === 'running' ? 'text-emerald-500' : 'text-red-500'} font-medium`}>
                {c.state} {c.uptime ? `(${c.uptime})` : ''}
              </span>
            </div>
          ))}
          {data.pipeline && (
            <div className="text-[10px] text-light-muted dark:text-dark-muted pt-1 border-t border-light-border/30">
              timi-pipeline: {data.pipeline.status} · {data.pipeline.uptime}
            </div>
          )}
        </motion.div>
      )}
      {expanded && isCloud && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="mt-2 pt-2 border-t border-light-border/50 dark:border-dark-border/50 text-[10px] text-light-muted dark:text-dark-muted"
        >
          Docker is not available in this cloud environment. The pipeline runs on your local machine instead.
        </motion.div>
      )}
    </div>
  );
}

export function StorageStatus() {
  const [data, setData] = useState<StorageData | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const poll = async () => {
      const d = await fetchJson('/api/storage');
      setData(d);
    };
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, []);

  const status: 'ok' | 'warn' | 'error' | 'unknown' = !data ? 'unknown'
    : data.connected && data.free_percent > 20 ? 'ok'
    : data.connected && data.free_percent > 10 ? 'warn'
    : data.connected ? 'error'
    : 'error';

  const usagePercent = data ? Math.round((1 - data.free_percent / 100) * 100) : 0;

  return (
    <div className="rounded-xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card p-3">
      <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center justify-between" title="Cloudflare R2 stores your video files in the cloud — click to see storage usage details">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <div className="text-left">
            <h4 className="text-xs font-semibold text-light-text dark:text-dark-text">Cloudflare R2</h4>
            <p className="text-[10px] text-light-muted dark:text-dark-muted">
              {data?.connected ? `${data.total_size_gb}GB / ${data.limit_gb}GB` : data?.configured === false ? 'Not configured' : 'Connecting...'}
            </p>
          </div>
        </div>
        <StatusDot status={status} />
      </button>

      {expanded && data && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: 'auto', opacity: 1 }}
          className="mt-2 pt-2 border-t border-light-border/50 dark:border-dark-border/50 space-y-2"
        >
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-light-muted dark:text-dark-muted">Usage</span>
              <span className="text-light-text dark:text-dark-text font-medium">{usagePercent}%</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-light-border dark:bg-dark-border overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-sky-400 to-blue-500"
                style={{ width: `${usagePercent}%` }}
              />
            </div>
          </div>
          <div className="flex justify-between text-[10px]">
            <span className="text-light-muted dark:text-dark-muted">Objects</span>
            <span className="text-light-text dark:text-dark-text">{data.objects?.toLocaleString() || 0}</span>
          </div>
          {data.pending_deletion > 0 && (
            <div className="flex justify-between text-[10px]">
              <span className="text-amber-500">Pending deletion</span>
              <span className="text-amber-500">{data.pending_deletion}</span>
            </div>
          )}
        </motion.div>
      )}
    </div>
  );
}

export function FirebaseStatus() {
  const [data, setData] = useState<FirebaseData | null>(null);

  useEffect(() => {
    const poll = async () => {
      const d = await fetchJson('/api/firebase');
      setData(d);
    };
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, []);

  const status: 'ok' | 'warn' | 'error' | 'unknown' = !data ? 'unknown'
    : data.connected && data.latency_ms < 500 ? 'ok'
    : data.connected && data.latency_ms < 1000 ? 'warn'
    : data.connected ? 'error'
    : 'error';

  return (
    <div className="rounded-xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card p-3" title="Firebase is your database — it stores all video info, agent status, and activity logs. Response time under 1 second from Nepal is normal">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <div className="text-left">
            <h4 className="text-xs font-semibold text-light-text dark:text-dark-text">Firebase</h4>
            <p className="text-[10px] text-light-muted dark:text-dark-muted">
              {data ? `${data.latency_ms}ms latency` : '...'}
            </p>
          </div>
        </div>
        <StatusDot status={status} />
      </div>

      {data?.heartbeat && (
        <div className="mt-2 pt-2 border-t border-light-border/50 dark:border-dark-border/50">
          <div className="flex justify-between text-[10px]">
            <span className="text-light-muted dark:text-dark-muted">Heartbeat</span>
            <span className={`font-medium ${
              data.heartbeat.status === 'ok' ? 'text-emerald-500' : 'text-amber-500'
            }`}>
              {data.heartbeat.status}
            </span>
          </div>
          {data.heartbeat.last_beat && (
            <div className="flex justify-between text-[10px] mt-0.5">
              <span className="text-light-muted dark:text-dark-muted">Last beat</span>
              <span className="text-light-text dark:text-dark-text">{data.heartbeat.last_beat}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
