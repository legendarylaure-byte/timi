'use client';

import { useEffect, useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, onSnapshot, Timestamp } from 'firebase/firestore';
import { AGENT_ROLES } from '@/lib/constants';

interface ActivityLog {
  id: string;
  agent_id: string;
  message: string;
  level: string;
  timestamp: Timestamp;
}

function getAgentColor(agentId: string): string {
  const agent = AGENT_ROLES.find(a => a.id === agentId);
  return agent?.color || '#6B7280';
}

function getAgentEmoji(agentId: string): string {
  const agent = AGENT_ROLES.find(a => a.id === agentId);
  return agent?.emoji || '🤖';
}

function getAgentName(agentId: string): string {
  const agent = AGENT_ROLES.find(a => a.id === agentId);
  return agent?.name || agentId;
}

function formatTime(timestamp: any): string {
  if (!timestamp) return '';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const now = new Date();
  const diff = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (diff < 10) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export function LiveActivityFeed() {
  const [logs, setLogs] = useState<ActivityLog[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const prevCountRef = useRef(0);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = query(collection(db, 'activity_logs'), orderBy('timestamp', 'desc'), limit(30));
    const unsub = onSnapshot(q, (snap) => {
      const items: ActivityLog[] = [];
      snap.docs.forEach(doc => {
        items.push({ id: doc.id, ...doc.data() } as ActivityLog);
      });
      items.reverse();
      setLogs(prev => {
        const merged = [...items];
        const ids = new Set(merged.map(l => l.id));
        prev.forEach(l => {
          if (!ids.has(l.id)) merged.push(l);
        });
        return merged.slice(-50);
      });
      setUnreadCount(prev => Math.min(prev + snap.docChanges().filter(c => c.type === 'added').length, 99));
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    if (unreadCount > 0 && prevCountRef.current !== unreadCount) {
      prevCountRef.current = unreadCount;
    }
  }, [unreadCount]);

  return (
    <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-light-border/50 dark:border-dark-border/50">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-bold text-light-text dark:text-dark-text" title="Live feed showing everything your AI agents are doing — from writing scripts to publishing videos. Updates in real time">Activity Feed</h3>
          {unreadCount > 0 && (
            <span className="px-1.5 py-0.5 rounded-full bg-light-primary text-white text-[10px] font-bold min-w-[18px] text-center">
              {unreadCount}
            </span>
          )}
        </div>
        <span className="text-[10px] text-light-muted dark:text-dark-muted">
          {logs.filter(l => {
            if (!l.timestamp) return false;
            const t: Date = typeof l.timestamp.toDate === 'function'
              ? l.timestamp.toDate()
              : new Date(l.timestamp as any);
            return Date.now() - t.getTime() < 60000;
          }).length} active in 1m
        </span>
      </div>

      <div ref={scrollRef} className="max-h-80 overflow-y-auto overscroll-contain p-3 space-y-1">
        {logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 text-light-muted dark:text-dark-muted">
            <p className="text-sm font-medium">No recent activity</p>
            <p className="text-xs mt-1 text-center max-w-[280px]">Agents have been quiet — the next scheduled run is at 11:45 AM Nepal time. Activity will appear here once agents start working</p>
          </div>
        ) : (
          <AnimatePresence initial={false}>
            {logs.map((log, i) => (
              <motion.div
                key={log.id}
                initial={{ opacity: 0, x: -12, height: 0 }}
                animate={{ opacity: 1, x: 0, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="flex items-start gap-2.5 py-1.5 px-2 rounded-lg hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
              >
                <span className="text-sm mt-0.5 shrink-0">{getAgentEmoji(log.agent_id)}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-light-text dark:text-dark-text leading-relaxed">
                    <span className="font-semibold" style={{ color: getAgentColor(log.agent_id) }}>
                      {getAgentName(log.agent_id)}
                    </span>
                    {' '}{log.message}
                  </p>
                </div>
                <span className="text-[9px] text-light-muted/60 dark:text-dark-muted/60 shrink-0 mt-0.5 font-mono">
                  {formatTime(log.timestamp)}
                </span>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
