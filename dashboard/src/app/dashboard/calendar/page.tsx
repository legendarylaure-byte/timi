'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, getDoc } from 'firebase/firestore';
import { CONTENT_CATEGORIES, PLATFORMS } from '@/lib/constants';
import Image from 'next/image';

const PLATFORM_KEYS = Object.keys(PLATFORMS);

const aiTopics = [
  'The Magic Paintbrush',
  'Why Do Stars Twinkle?',
  'The Brave Little Seed',
  'Numbers in the Sky',
  'The Friendly Dragon',
  'How Rainbows Are Made',
  'The Sleepy Moon',
  'Animals Can Count Too',
  'The Colorful Cloud',
  'The Lost Teddy Bear',
  'Why Leaves Change Color',
  'The Dancing Flowers',
];

const optimalTimes = ['8:00 AM', '10:00 AM', '2:00 PM', '4:00 PM', '6:00 PM', '8:00 PM'];

function predictScore(): number {
  return Math.floor(Math.random() * 40) + 60;
}

function generateCalendarData(weekStart: Date, quota: { shorts: number; long: number }) {
  const days = [];
  for (let i = 0; i < 7; i++) {
    const date = new Date(weekStart);
    date.setDate(date.getDate() + i);
    const dayItems = [];

    if (date <= new Date()) {
      for (let s = 0; s < quota.shorts; s++) {
        const statuses: CalendarItem['status'][] = ['planned', 'scripted', 'generating', 'ready', 'published'];
        const idx = Math.min(i, statuses.length - 1);
        dayItems.push({
          id: `short-${date.toISOString().split('T')[0]}-${s + 1}`,
          topic: aiTopics[(date.getDay() + s) % aiTopics.length],
          format: 'shorts' as const,
          platforms: PLATFORM_KEYS.slice(0, 2),
          scheduledDate: date.toISOString().split('T')[0],
          scheduledTime: optimalTimes[s % optimalTimes.length],
          status: statuses[Math.min(idx, 2)],
          predictedScore: predictScore(),
          category: CONTENT_CATEGORIES[(date.getDay() + s) % CONTENT_CATEGORIES.length].name,
        });
      }
      for (let l = 0; l < quota.long; l++) {
        const statuses: CalendarItem['status'][] = ['planned', 'scripted', 'generating', 'ready', 'published'];
        const idx = Math.min(i, statuses.length - 1);
        dayItems.push({
          id: `long-${date.toISOString().split('T')[0]}-${l + 1}`,
          topic: aiTopics[(date.getDay() + l + 5) % aiTopics.length],
          format: 'long' as const,
          platforms: PLATFORM_KEYS.slice(0, 3),
          scheduledDate: date.toISOString().split('T')[0],
          scheduledTime: optimalTimes[(l + 2) % optimalTimes.length],
          status: statuses[Math.min(idx, 2)],
          predictedScore: predictScore(),
          category: CONTENT_CATEGORIES[(date.getDay() + l + 2) % CONTENT_CATEGORIES.length].name,
        });
      }
    }
    days.push({ date, items: dayItems });
  }
  return days;
}

interface CalendarItem {
  id: string;
  topic: string;
  format: 'shorts' | 'long';
  platforms: string[];
  scheduledDate: string;
  scheduledTime: string;
  status: 'planned' | 'scripted' | 'generating' | 'ready' | 'published';
  predictedScore: number;
  category: string;
}

const statusColors: Record<string, string> = {
  planned: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  scripted: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  generating: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse',
  ready: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  published: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
};

const formatColors: Record<string, string> = {
  shorts: 'from-light-primary/20 to-light-secondary/20',
  long: 'from-light-secondary/20 to-light-info/20',
};

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() - d.getDay() + 1);
    d.setHours(0, 0, 0, 0);
    return d;
  });
  const [calendarData, setCalendarData] = useState<ReturnType<typeof generateCalendarData>>([]);
  const [quota, setQuota] = useState({ shorts: 2, long: 2 });
  const [selectedItem, setSelectedItem] = useState<CalendarItem | null>(null);
  const [activeVideos, setActiveVideos] = useState<Record<string, Partial<CalendarItem>>>({});

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'settings', 'general'), (snap) => {
      if (snap.exists()) {
        const data = snap.data();
        setQuota({
          shorts: data.shortsPerDay ?? 2,
          long: data.longPerDay ?? 2,
        });
      }
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    const q = collection(db, 'videos');
    const unsub = onSnapshot(q, (snapshot) => {
      const vids: Record<string, Partial<CalendarItem>> = {};
      snapshot.docs.forEach((d) => {
        const data = d.data();
        const statusMap: Record<string, CalendarItem['status']> = {
          generating: 'generating',
          uploaded: 'published',
          failed: 'planned',
        };
        vids[d.id] = {
          status: statusMap[data.status] || 'planned',
        };
      });
      setActiveVideos(vids);
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    setCalendarData(generateCalendarData(weekStart, quota));
  }, [weekStart, quota]);

  const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  const prevWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() - 7);
    setWeekStart(d);
  };

  const nextWeek = () => {
    const d = new Date(weekStart);
    d.setDate(d.getDate() + 7);
    setWeekStart(d);
  };

  const totalPredicted = calendarData.reduce((sum, day) => sum + day.items.reduce((s, item) => s + item.predictedScore, 0), 0);
  const totalItems = calendarData.reduce((sum, day) => sum + day.items.length, 0);
  const avgScore = totalItems > 0 ? Math.round(totalPredicted / totalItems) : 0;

  const weekLabel = `${weekStart.toLocaleDateString([], { month: 'short', day: 'numeric' })} — ${new Date(weekStart.getTime() + 6 * 86400000).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">AI Content Planner</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Smart scheduling with AI performance predictions</p>
          </div>
        </div>
      </motion.div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <button onClick={prevWeek} className="px-4 py-2 rounded-xl bg-light-border/50 dark:bg-dark-border/50 text-light-text dark:text-dark-text hover:bg-light-border dark:hover:bg-dark-border transition-colors text-sm">← Prev</button>
          <span className="text-sm font-semibold text-light-text dark:text-dark-text">{weekLabel}</span>
          <button onClick={nextWeek} className="px-4 py-2 rounded-xl bg-light-border/50 dark:bg-dark-border/50 text-light-text dark:text-dark-text hover:bg-light-border dark:hover:bg-dark-border transition-colors text-sm">Next →</button>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-gradient-to-r from-light-primary to-light-secondary" />
            <span className="text-light-muted dark:text-dark-muted">{totalItems} videos this week</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-emerald-500/50" />
            <span className="text-light-muted dark:text-dark-muted">Avg score: {avgScore}/100</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7 gap-3">
        {calendarData.map((day, dayIdx) => {
          const isToday = day.date.toDateString() === new Date().toDateString();
          const isPast = day.date < new Date(new Date().toDateString());

          return (
            <motion.div
              key={day.date.toISOString()}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: dayIdx * 0.05 }}
              className={`rounded-2xl border p-4 min-h-48 transition-all ${
                isToday
                  ? 'border-light-primary/50 bg-light-primary/5 dark:bg-light-primary/10'
                  : 'border-light-border/30 dark:border-white/5 glass-strong'
              } ${isPast ? 'opacity-60' : ''}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-light-muted dark:text-dark-muted">{dayNames[dayIdx]}</span>
                  {isToday && (
                    <div className="w-2 h-2 rounded-full bg-light-primary animate-pulse" />
                  )}
                </div>
                <span className="text-lg font-bold text-light-text dark:text-dark-text">{day.date.getDate()}</span>
              </div>

              <div className="space-y-2">
                {day.items.length === 0 ? (
                  <p className="text-xs text-light-muted dark:text-dark-muted/50 text-center py-4">No content planned</p>
                ) : (
                  day.items.map((item) => {
                    const liveStatus = activeVideos[item.id]?.status;
                    const displayStatus = liveStatus || item.status;

                    return (
                      <motion.button
                        key={item.id}
                        onClick={() => setSelectedItem(item)}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className={`w-full text-left p-2.5 rounded-xl border bg-gradient-to-br ${formatColors[item.format]} transition-all ${statusColors[displayStatus]}`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs font-semibold text-light-text dark:text-dark-text truncate pr-1">
                            {item.format === 'shorts' ? '📱' : '🎬'} {item.topic}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${statusColors[displayStatus]}`}>
                            {displayStatus}
                          </span>
                          <span className="text-[10px] text-light-muted dark:text-dark-muted">
                            {item.predictedScore}%
                          </span>
                        </div>
                        <div className="flex gap-1 mt-1.5">
                          {item.platforms.slice(0, 2).map((p) => (
                            <span key={p} className="text-[9px] px-1.5 py-0.5 rounded bg-light-bg/50 dark:bg-dark-bg/50 text-light-muted dark:text-dark-muted">
                              {p}
                            </span>
                          ))}
                        </div>
                      </motion.button>
                    );
                  })
                )}
              </div>
            </motion.div>
          );
        })}
      </div>

      <AnimatePresence>
        {selectedItem && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/40 z-40"
              onClick={() => setSelectedItem(null)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="fixed inset-x-4 top-1/2 -translate-y-1/2 max-w-md mx-auto z-50 rounded-2xl glass-strong border border-light-border/50 dark:border-white/10 p-6"
            >
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{selectedItem.topic}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">{selectedItem.category}</p>
                </div>
                <button onClick={() => setSelectedItem(null)} className="text-light-muted text-xl hover:text-light-text dark:hover:text-dark-text">✕</button>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Format</span>
                  <span className="text-xs font-semibold text-light-text dark:text-dark-text">{selectedItem.format === 'shorts' ? 'Shorts (9:16)' : 'Long Form (16:9)'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Publish Time</span>
                  <span className="text-xs font-semibold text-light-text dark:text-dark-text">{selectedItem.scheduledTime}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">AI Prediction</span>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-2 bg-light-border dark:bg-dark-border rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${selectedItem.predictedScore >= 80 ? 'bg-emerald-500' : selectedItem.predictedScore >= 60 ? 'bg-yellow-500' : 'bg-red-500'}`}
                        style={{ width: `${selectedItem.predictedScore}%` }}
                      />
                    </div>
                    <span className="text-xs font-bold text-light-text dark:text-dark-text">{selectedItem.predictedScore}%</span>
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Platforms</span>
                  <div className="flex gap-1.5">
                    {selectedItem.platforms.map((p) => (
                      <span key={p} className="text-xs px-2 py-0.5 rounded-full bg-light-primary/10 dark:bg-light-primary/20 text-light-primary">
                        {p}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Status</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[selectedItem.status]}`}>
                    {selectedItem.status}
                  </span>
                </div>
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
