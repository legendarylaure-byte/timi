'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, startAfter, onSnapshot, DocumentSnapshot } from 'firebase/firestore';
import { AGENT_ROLES } from '@/lib/constants';
import Image from 'next/image';

interface ActivityLog {
  id: string;
  agent_id: string;
  message: string;
  level: string;
  timestamp: any;
}

const PAGE_SIZE = 25;

export default function LogsPage() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [filter, setFilter] = useState<string>('all');
  const [lastVisible, setLastVisible] = useState<DocumentSnapshot | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const q = query(collection(db, 'activity_logs'), orderBy('timestamp', 'desc'), limit(PAGE_SIZE));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const items: ActivityLog[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as ActivityLog);
      });
      setLogs(items);
      setHasMore(snapshot.docs.length === PAGE_SIZE);
      setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
      setLoading(false);
    });
    return () => unsubscribe();
  }, []);

  const loadMore = () => {
    if (!lastVisible || !hasMore) return;
    const q = query(collection(db, 'activity_logs'), orderBy('timestamp', 'desc'), startAfter(lastVisible), limit(PAGE_SIZE));
    onSnapshot(q, (snapshot) => {
      const items: ActivityLog[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as ActivityLog);
      });
      setLogs((prev) => [...prev, ...items]);
      setHasMore(snapshot.docs.length === PAGE_SIZE);
      setLastVisible(snapshot.docs[snapshot.docs.length - 1] || null);
    });
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter((log) => log.level === filter);

  const dotColors: Record<string, string> = {
    info: 'bg-blue-400',
    success: 'bg-emerald-400',
    warning: 'bg-yellow-400',
    error: 'bg-red-400',
  };

  const bgColors: Record<string, string> = {
    info: 'bg-blue-500/5 dark:bg-blue-500/10',
    success: 'bg-emerald-500/5 dark:bg-emerald-500/10',
    warning: 'bg-yellow-500/5 dark:bg-yellow-500/10',
    error: 'bg-red-500/5 dark:bg-red-500/10',
  };

  const getAgentColor = (agentId: string) => AGENT_ROLES.find((a) => a.id === agentId)?.color || '#6B7280';
  const getAgentName = (agentId: string) => AGENT_ROLES.find((a) => a.id === agentId)?.name || agentId;

  const formatTime = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    return date.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Activity Logs</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">
              Real-time log of all agent activities
            </p>
          </div>
        </div>
      </motion.div>

      <div className="flex gap-2 flex-wrap">
        {['all', 'info', 'success', 'warning', 'error'].map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all capitalize ${
              filter === level
                ? 'bg-gradient-to-r from-light-primary to-light-secondary text-white'
                : 'bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted hover:bg-light-border dark:hover:bg-dark-border'
            }`}
          >
            {level}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-light-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-light-muted dark:text-dark-muted">
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 2, repeat: Infinity }}
            className="text-4xl mb-3"
          >
            📝
          </motion.div>
          <p className="text-sm font-medium">No activity logs yet</p>
          <p className="text-xs mt-1">Logs will appear here when agents start running</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredLogs.map((log, i) => (
            <motion.div
              key={log.id}
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: Math.min(i * 0.02, 0.3) }}
              className={`flex items-start gap-4 p-4 rounded-xl border border-light-border/30 dark:border-white/5 ${bgColors[log.level] || bgColors.info}`}
            >
              <div className={`w-2.5 h-2.5 rounded-full mt-1.5 shrink-0 ${dotColors[log.level] || dotColors.info} ${log.level === 'error' ? 'animate-pulse' : ''}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold truncate" style={{ color: getAgentColor(log.agent_id) }}>
                    {getAgentName(log.agent_id)}
                  </span>
                  <span className="text-[10px] text-light-muted dark:text-gray-500 shrink-0">
                    {formatTime(log.timestamp)}
                  </span>
                </div>
                <p className="text-sm text-light-text/80 dark:text-dark-text/80">{log.message}</p>
              </div>
            </motion.div>
          ))}
        </div>
      )}

      {hasMore && filteredLogs.length > 0 && (
        <div className="flex justify-center pt-4">
          <button
            onClick={loadMore}
            className="px-6 py-2 rounded-xl text-sm font-medium bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted hover:bg-light-border dark:hover:bg-dark-border transition-colors"
          >
            Load More
          </button>
        </div>
      )}
    </div>
  );
}
