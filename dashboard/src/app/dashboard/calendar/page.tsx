'use client';

import { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, query, where, orderBy } from 'firebase/firestore';
import Image from 'next/image';

interface VideoDoc {
  id: string;
  title?: string;
  format?: string;
  status?: string;
  category?: string;
  created_at?: any;
  scheduled_date?: string;
  publish_at?: string;
  character?: string;
  priority?: number;
  reasoning?: string;
  topic?: string;
  _source?: string;
}

interface CalendarDay {
  date: Date;
  items: VideoDoc[];
}

const statusColors: Record<string, string> = {
  planned: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  scripted: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  generating: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse',
  ready: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  uploaded: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  published: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  pending: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  processing: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30 animate-pulse',
  scheduled: 'bg-cyan-500/20 text-cyan-400 border-cyan-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const formatColors: Record<string, string> = {
  shorts: 'from-light-primary/20 to-light-secondary/20',
  long: 'from-light-secondary/20 to-light-info/20',
};

function getWeekStart(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay() + 1);
  d.setHours(0, 0, 0, 0);
  return d;
}

function getWeekEnd(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay() + 7);
  d.setHours(23, 59, 59, 999);
  return d;
}

function extractDateStr(item: VideoDoc): string | null {
  const d = item.publish_at || item.scheduled_date;
  if (d) return d.slice(0, 10);
  if (item.created_at) {
    if (typeof item.created_at === 'string') return item.created_at.slice(0, 10);
    if (item.created_at.toDate) return item.created_at.toDate().toISOString().slice(0, 10);
  }
  return null;
}

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState(() => getWeekStart(new Date()));
  const [calendarData, setCalendarData] = useState<CalendarDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedItem, setSelectedItem] = useState<VideoDoc | null>(null);

  const [videos, setVideos] = useState<VideoDoc[]>([]);
  const [triggers, setTriggers] = useState<VideoDoc[]>([]);
  const [planVideos, setPlanVideos] = useState<VideoDoc[]>([]);

  const weekEnd = useMemo(() => getWeekEnd(weekStart), [weekStart]);

  useEffect(() => {
    const unsubVideo = onSnapshot(
      query(
        collection(db, 'videos'),
        where('created_at', '>=', weekStart.toISOString()),
        where('created_at', '<=', weekEnd.toISOString()),
        orderBy('created_at', 'asc'),
      ),
      (snapshot) => {
        setVideos(snapshot.docs.map((d) => ({ id: d.id, ...d.data(), _source: 'video' } as VideoDoc)));
        setLoading(false);
      },
      (err) => {
        console.error('Videos snapshot error:', err);
        setLoading(false);
      },
    );

    const unsubTrigger = onSnapshot(
      query(
        collection(db, 'pipeline_triggers'),
        where('created_at', '>=', weekStart.toISOString()),
        where('created_at', '<=', weekEnd.toISOString()),
        orderBy('created_at', 'asc'),
      ),
      (snapshot) => {
        setTriggers(snapshot.docs.map((d) => {
          const data = d.data() as any;
          return {
            id: d.id,
            title: data.topic || data.title || 'Untitled',
            format: data.format || 'shorts',
            status: data.status || 'pending',
            category: data.category || 'General',
            publish_at: data.publish_at || (data.created_at?.toDate?.()?.toISOString() || ''),
            created_at: data.created_at,
            _source: 'trigger',
            priority: 80,
          } as VideoDoc;
        }));
      },
      (err) => console.error('Triggers snapshot error:', err),
    );

    const unsubPlan = onSnapshot(
      doc(db, 'system', 'content_plan'),
      (docSnap) => {
        if (!docSnap.exists()) {
          setPlanVideos([]);
          return;
        }
        const planData = docSnap.data();
        if (!planData?.videos?.length) {
          setPlanVideos([]);
          return;
        }
        const items: VideoDoc[] = (planData.videos || [])
          .filter((v: any) => {
            const pd = planData.plan_date;
            if (!pd) return true;
            const d = new Date(pd + 'T00:00:00');
            const now = new Date();
            const weekAgo = new Date(now.getTime() - 7 * 86400000);
            const planEnd = new Date(now.getTime() + 7 * 86400000);
            return d >= weekAgo && d <= planEnd;
          })
          .map((v: any, i: number) => ({
            id: `plan-${i}`,
            title: v.title,
            format: v.format || 'shorts',
            status: 'planned',
            category: v.category,
            character: v.character,
            priority: v.priority || 50,
            reasoning: v.reasoning || '',
            publish_at: planData.plan_date || new Date().toISOString(),
            _source: 'plan',
          }));
        setPlanVideos(items);
      },
      (err) => console.error('Content plan snapshot error:', err),
    );

    return () => {
      unsubVideo();
      unsubTrigger();
      unsubPlan();
    };
  }, [weekStart, weekEnd]);

  useEffect(() => {
    const days: CalendarDay[] = [];
    for (let i = 0; i < 7; i++) {
      const date = new Date(weekStart);
      date.setDate(date.getDate() + i);
      days.push({ date, items: [] });
    }

    const seen = new Set<string>();

    const addItem = (item: VideoDoc) => {
      const key = `${item._source}-${item.id}`;
      if (seen.has(key)) return;
      seen.add(key);
      const dateStr = extractDateStr(item);
      if (!dateStr) return;
      const day = days.find((d) => d.date.toISOString().slice(0, 10) === dateStr);
      if (day) day.items.push(item);
    };

    videos.forEach(addItem);
    triggers.forEach(addItem);
    planVideos.forEach(addItem);

    days.forEach((d) => d.items.sort((a, b) => (b.priority || 50) - (a.priority || 50)));
    setCalendarData(days);
  }, [weekStart, videos, triggers, planVideos]);

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

  const totalItems = calendarData.reduce((sum, day) => sum + day.items.length, 0);

  const weekLabel = `${weekStart.toLocaleDateString([], { month: 'short', day: 'numeric' })} \u2014 ${new Date(weekStart.getTime() + 6 * 86400000).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}`;

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
          <button onClick={prevWeek} className="px-4 py-2 rounded-xl bg-light-border/50 dark:bg-dark-border/50 text-light-text dark:text-dark-text hover:bg-light-border dark:hover:bg-dark-border transition-colors text-sm">&larr; Prev</button>
          <span className="text-sm font-semibold text-light-text dark:text-dark-text">{weekLabel}</span>
          <button onClick={nextWeek} className="px-4 py-2 rounded-xl bg-light-border/50 dark:bg-dark-border/50 text-light-text dark:text-dark-text hover:bg-light-border dark:hover:bg-dark-border transition-colors text-sm">Next &rarr;</button>
        </div>
        {loading && (
          <span className="text-xs text-light-muted dark:text-dark-muted animate-pulse">Loading...</span>
        )}
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-3 h-3 rounded-full bg-gradient-to-r from-light-primary to-light-secondary" />
            <span className="text-light-muted dark:text-dark-muted">{totalItems} items this week</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-gray-500" />
            <span className="text-light-muted dark:text-dark-muted">Planned</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-cyan-500" />
            <span className="text-light-muted dark:text-dark-muted">Scheduled</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-2 h-2 rounded-full bg-purple-500" />
            <span className="text-light-muted dark:text-dark-muted">Published</span>
          </div>
        </div>
      </div>

      {calendarData.length === 0 && !loading ? (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-16 text-light-muted dark:text-dark-muted"
        >
          <p className="text-lg mb-2">No data available</p>
          <p className="text-sm opacity-60">Check browser console for Firestore errors, or ensure the planner has generated content.</p>
        </motion.div>
      ) : (
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
                      const fmt = (item.format || 'shorts') as string;
                      const displayStatus = item.status || 'planned';

                      return (
                        <motion.button
                          key={`${item._source}-${item.id}`}
                          onClick={() => setSelectedItem(item)}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          className={`w-full text-left p-2.5 rounded-xl border bg-gradient-to-br ${formatColors[fmt]} transition-all ${statusColors[displayStatus]}`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-semibold text-light-text dark:text-dark-text truncate pr-1">
                              {fmt === 'shorts' ? '\uD83D\uDCF1' : '\uD83C\uDFAC'} {item.title || 'Untitled'}
                            </span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${statusColors[displayStatus]}`}>
                              {displayStatus}
                            </span>
                            {item.character && (
                              <span className="text-[10px] text-light-muted dark:text-dark-muted">{item.character}</span>
                            )}
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
      )}

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
                  <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{selectedItem.title || 'Untitled'}</h3>
                  <p className="text-xs text-light-muted dark:text-dark-muted mt-0.5">{selectedItem.category || 'General'} {selectedItem.character ? ` - ${selectedItem.character}` : ''}</p>
                </div>
                <button onClick={() => setSelectedItem(null)} className="text-light-muted text-xl hover:text-light-text dark:hover:text-dark-text" aria-label="Close video details">&times;</button>
              </div>

              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Format</span>
                  <span className="text-xs font-semibold text-light-text dark:text-dark-text">{(selectedItem.format || 'shorts') === 'shorts' ? 'Shorts (9:16)' : 'Long Form (16:9)'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Publish Time</span>
                  <span className="text-xs font-semibold text-light-text dark:text-dark-text">{selectedItem.publish_at ? new Date(selectedItem.publish_at).toLocaleString() : 'Not scheduled'}</span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Status</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[selectedItem.status || 'planned']}`}>
                    {selectedItem.status || 'planned'}
                  </span>
                </div>
                <div className="flex items-center justify-between p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                  <span className="text-xs text-light-muted dark:text-dark-muted">Source</span>
                  <span className="text-xs font-semibold text-light-text dark:text-dark-text">{selectedItem._source || 'video'}</span>
                </div>
                {selectedItem.reasoning && (
                  <div className="p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50">
                    <span className="text-xs text-light-muted dark:text-dark-muted block mb-1">Planning Note</span>
                    <span className="text-xs text-light-text dark:text-dark-text">{selectedItem.reasoning}</span>
                  </div>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
