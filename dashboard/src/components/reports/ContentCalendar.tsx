'use client';

import { useState, useEffect } from 'react';
import { Calendar as CalendarIcon, Clock, Film, Video, BookOpen, Loader2, ChevronLeft, ChevronRight } from 'lucide-react';

interface CalendarEvent {
  id: string;
  title: string;
  scheduledTime: string;
  status: string;
  format: string;
  thumbnailUrl?: string;
}

const statusColors: Record<string, string> = {
  scheduled: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  pending: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  processing: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  published: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  failed: 'bg-red-500/20 text-red-400 border-red-500/30',
};

const formatIcons: Record<string, React.ReactNode> = {
  shorts: <Film className="w-3.5 h-3.5" />,
  long: <Video className="w-3.5 h-3.5" />,
  documentary: <BookOpen className="w-3.5 h-3.5" />,
};

export function ContentCalendar() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [weekOffset, setWeekOffset] = useState(0);

  useEffect(() => {
    setLoading(true);
    fetch('/api/reports/content-calendar')
      .then(r => r.json())
      .then(data => {
        setEvents(data.events || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const today = new Date();
  const startOfWeek = new Date(today);
  startOfWeek.setDate(today.getDate() + weekOffset * 7 - today.getDay());
  startOfWeek.setHours(0, 0, 0, 0);

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(startOfWeek);
    d.setDate(startOfWeek.getDate() + i);
    return d;
  });

  const getEventsForDay = (date: Date) => {
    const dateStr = date.toISOString().slice(0, 10);
    return events.filter(e => e.scheduledTime?.startsWith(dateStr));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-light-text dark:text-dark-text flex items-center gap-2">
          <CalendarIcon className="w-5 h-5 text-brand-red" />
          Content Calendar
        </h2>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setWeekOffset(w => w - 1)}
            className="p-1.5 rounded-lg hover:bg-light-border/50 dark:hover:bg-dark-border/50 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="text-sm text-light-muted dark:text-dark-muted min-w-[180px] text-center">
            {days[0].toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} – {days[6].toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
          </span>
          <button
            onClick={() => setWeekOffset(w => w + 1)}
            className="p-1.5 rounded-lg hover:bg-light-border/50 dark:hover:bg-dark-border/50 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-light-muted" />
        </div>
      ) : (
        <div className="grid grid-cols-7 gap-2">
          {days.map((day, i) => {
            const dayEvents = getEventsForDay(day);
            const isToday = day.toISOString().slice(0, 10) === today.toISOString().slice(0, 10);
            return (
              <div
                key={i}
                className={`rounded-xl border p-2 min-h-[140px] ${
                  isToday
                    ? 'border-brand-red/30 bg-brand-red/5'
                    : 'border-light-border dark:border-dark-border bg-light-card dark:bg-dark-card'
                }`}
              >
                <div className={`text-xs font-semibold mb-1.5 text-center ${
                  isToday ? 'text-brand-red' : 'text-light-muted dark:text-dark-muted'
                }`}>
                  {day.toLocaleDateString('en-US', { weekday: 'short' })}
                  <br />
                  <span className="text-sm">{day.getDate()}</span>
                </div>
                <div className="space-y-1">
                  {dayEvents.length === 0 && (
                    <p className="text-[10px] text-light-muted/50 dark:text-dark-muted/50 text-center pt-2">—</p>
                  )}
                  {dayEvents.slice(0, 3).map(event => (
                    <div
                      key={event.id}
                      className={`text-[10px] p-1.5 rounded-lg border ${statusColors[event.status] || 'border-light-border/50'} cursor-pointer hover:opacity-80 transition-opacity`}
                      title={`${event.title} [${event.status}]`}
                    >
                      <div className="flex items-center gap-1 mb-0.5">
                        {formatIcons[event.format] || <Film className="w-3 h-3" />}
                        <span className="truncate font-medium">{event.title?.slice(0, 20)}</span>
                      </div>
                      <div className="flex items-center gap-1 text-[8px] opacity-60">
                        <Clock className="w-2.5 h-2.5" />
                        {event.scheduledTime ? new Date(event.scheduledTime).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '—'}
                      </div>
                    </div>
                  ))}
                  {dayEvents.length > 3 && (
                    <p className="text-[9px] text-center text-light-muted dark:text-dark-muted">+{dayEvents.length - 3} more</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!loading && events.length === 0 && (
        <p className="text-center text-sm text-light-muted dark:text-dark-muted py-4">
          No scheduled content. The pipeline will auto-generate content based on the daily schedule.
        </p>
      )}
    </div>
  );
}
