'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, onSnapshot, doc, getDoc, setDoc } from 'firebase/firestore';
import { AGENT_ROLES } from '@/lib/constants';

interface Notification {
  id: string;
  agent_id: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
  timestamp: any;
}

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [readIds, setReadIds] = useState<Set<string>>(new Set());
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const q = query(collection(db, 'activity_logs'), orderBy('timestamp', 'desc'), limit(30));
    const unsub = onSnapshot(q, (snapshot) => {
      const items: Notification[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as Notification);
      });
      setNotifications(items);
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    const loadRead = async () => {
      try {
        const snap = await getDoc(doc(db, 'notifications', 'user'));
        if (snap.exists()) {
          setReadIds(new Set(snap.data().read_ids || []));
        }
      } catch {}
    };
    loadRead();
  }, []);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    if (open) document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const unread = notifications.filter((n) => !readIds.has(n.id));
  const unreadCount = unread.length;

  const markRead = async (id: string) => {
    const newRead = new Set(readIds);
    newRead.add(id);
    setReadIds(newRead);
    try {
      await setDoc(doc(db, 'notifications', 'user'), { read_ids: Array.from(newRead) }, { merge: true });
    } catch {}
  };

  const markAllRead = async () => {
    const allIds = notifications.map((n) => n.id);
    setReadIds(new Set(allIds));
    try {
      await setDoc(doc(db, 'notifications', 'user'), { read_ids: allIds }, { merge: true });
    } catch {}
  };

  const getAgentColor = (agentId: string) => AGENT_ROLES.find((a) => a.id === agentId)?.color || '#6B7280';
  const getAgentName = (agentId: string) => AGENT_ROLES.find((a) => a.id === agentId)?.name || agentId;

  const levelIcons: Record<string, string> = {
    success: '✅',
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
  };

  const formatTime = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="relative w-10 h-10 rounded-xl flex items-center justify-center shadow-sm hover:shadow-md transition-all text-lg border border-light-border/50 dark:border-white/10 bg-light-card dark:bg-dark-card"
      >
        🔔
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center animate-pulse">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.95 }}
            className="absolute right-0 top-12 w-80 sm:w-96 max-h-[70vh] rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 shadow-2xl overflow-hidden z-50"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-light-border/50 dark:border-white/10">
              <h3 className="text-sm font-bold text-light-text dark:text-dark-text">
                Notifications
              </h3>
              {unreadCount > 0 && (
                <button
                  onClick={markAllRead}
                  className="text-xs text-light-primary hover:underline"
                >
                  Mark all read
                </button>
              )}
            </div>

            <div className="overflow-y-auto max-h-[55vh]">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-light-muted dark:text-dark-muted">
                  <span className="text-3xl mb-2">🔔</span>
                  <p className="text-sm font-medium">No notifications</p>
                  <p className="text-xs mt-1">Alerts will appear here</p>
                </div>
              ) : (
                notifications.map((notif, i) => (
                  <button
                    key={notif.id}
                    onClick={() => markRead(notif.id)}
                    className={`w-full text-left px-4 py-3 border-b border-light-border/30 dark:border-white/5 transition-colors hover:bg-light-primary/5 dark:hover:bg-white/5 ${
                      !readIds.has(notif.id) ? 'bg-light-primary/5 dark:bg-white/5' : ''
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-sm mt-0.5 shrink-0">{levelIcons[notif.level]}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold truncate" style={{ color: getAgentColor(notif.agent_id) }}>
                          {getAgentName(notif.agent_id)}
                        </p>
                        <p className="text-xs text-light-text/70 dark:text-dark-text/70 mt-0.5 line-clamp-2">
                          {notif.message}
                        </p>
                        <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">
                          {formatTime(notif.timestamp)}
                        </p>
                      </div>
                    </div>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
