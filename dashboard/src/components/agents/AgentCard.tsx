'use client';

import { motion } from 'framer-motion';
import { AGENT_ROLES } from '@/lib/constants';
import { StatusBadge } from '@/components/ui/StatusBadge';

interface AgentStatus {
  agent_id: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: any;
  error_message?: string;
}

interface ActivityEntry {
  timestamp: any;
  level: string;
}

interface AgentCardProps {
  agentId: string;
  status: AgentStatus | undefined;
  recentActivity: ActivityEntry[];
  onToggle: (agentId: string, enabled: boolean) => void;
  onShowIdleInfo: (agentId: string) => void;
}

function formatRelativeTime(timestamp: any): string {
  if (!timestamp) return '';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

function formatRelativeTimeFull(timestamp: any): string {
  if (!timestamp) return '';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

function AgentTimeline({ activities, lastUpdated }: { activities: ActivityEntry[]; lastUpdated: any }) {
  const recent = activities.slice(0, 5).reverse();

  const allPoints = [
    ...recent.map(a => ({
      time: a.timestamp,
      label: formatRelativeTime(a.timestamp),
      type: a.level === 'error' ? 'error' : 'activity' as const,
    })),
  ];

  if (lastUpdated) {
    allPoints.push({
      time: lastUpdated,
      label: formatRelativeTime(lastUpdated),
      type: 'activity',
    });
  }

  allPoints.sort((a, b) => {
    const ta = a.time?.toDate ? a.time.toDate().getTime() : new Date(a.time || 0).getTime();
    const tb = b.time?.toDate ? b.time.toDate().getTime() : new Date(b.time || 0).getTime();
    return ta - tb;
  });

  const latest = allPoints.slice(-5);

  if (latest.length === 0) return null;

  return (
    <div className="flex items-center gap-1 mt-2">
      {latest.map((point, i) => {
        const isLast = i === latest.length - 1;
        return (
          <div key={i} className="flex items-center gap-0.5 group/timeline relative">
            <div className={`w-1.5 h-1.5 rounded-full ${
              point.type === 'error' ? 'bg-red-400' :
              isLast ? 'bg-light-primary dark:bg-dark-primary' :
              'bg-light-muted/50 dark:bg-dark-muted/50'
            }`} />
            {!isLast && <div className="w-2 h-px bg-light-border dark:bg-dark-border" />}
            <div className="absolute -top-6 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-md bg-dark-bg text-dark-text text-[10px] whitespace-nowrap opacity-0 group-hover/timeline:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
              {formatRelativeTimeFull(point.time)}
            </div>
          </div>
        );
      })}
      <span className="text-[9px] text-light-muted dark:text-dark-muted ml-0.5 font-medium">
        {formatRelativeTime(lastUpdated || latest[latest.length - 1]?.time)}
      </span>
    </div>
  );
}

export function AgentCard({ agentId, status, recentActivity, onToggle, onShowIdleInfo }: AgentCardProps) {
  const agent = AGENT_ROLES.find(a => a.id === agentId);
  if (!agent) return null;

  const agentStatus = status?.status || 'idle';
  const isEnabled = status?.enabled ?? true;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={`relative rounded-xl border transition-all duration-200 ${
        agentStatus === 'working'
          ? 'border-light-primary/40 dark:border-dark-primary/40 ring-2 ring-light-primary/20 dark:ring-dark-primary/20 animate-pulse bg-light-primary/5 dark:bg-dark-primary/5'
          : agentStatus === 'error'
          ? 'border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/20'
          : 'border-light-border/50 dark:border-dark-border/50 bg-light-card dark:bg-dark-card hover:shadow-md'
      }`}
    >
      {/* Color bar */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${
          agentStatus === 'working' ? 'animate-pulse' : ''
        }`}
        style={{ backgroundColor: agent.color }}
      />

      <div className="pl-4 pr-3 py-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-base">{agent.emoji}</span>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="text-sm font-semibold text-light-text dark:text-dark-text truncate">
                  {agent.name}
                </p>
                <StatusBadge status={agentStatus as any} size="sm" />
                {agentStatus === 'working' && (
                  <motion.span
                    animate={{ y: [0, -2, 0], opacity: [1, 0.4, 1] }}
                    transition={{ repeat: Infinity, duration: 1.2 }}
                    className="w-1.5 h-1.5 rounded-full bg-light-primary"
                  />
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 shrink-0">
              <button
                onClick={() => onShowIdleInfo(agentId)}
                className="w-6 h-6 rounded-md flex items-center justify-center text-light-muted hover:text-light-text dark:hover:text-dark-text hover:bg-light-primary/10 transition-colors"
                title="Click to learn what this agent does"
              >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M12 18h.01" />
              </svg>
            </button>
            <button
              onClick={() => onToggle(agentId, isEnabled)}
              className={`shrink-0 w-8 h-5 rounded-full transition-all duration-200 ${
                isEnabled ? 'bg-light-success' : 'bg-light-muted dark:bg-dark-muted'
              }`}
            >
              <motion.div
                className="w-3.5 h-3.5 rounded-full bg-white shadow-sm"
                animate={{ x: isEnabled ? 16 : 2 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
          </div>
        </div>

        {status?.current_action && (
          <p className="text-xs text-light-muted dark:text-dark-muted mt-1 ml-7 truncate">
            {status.current_action}
          </p>
        )}

        <AgentTimeline
          activities={recentActivity}
          lastUpdated={status?.last_updated}
        />

        {status?.error_message && (
          <p className="text-xs text-red-500 mt-1 ml-7 truncate" title={status.error_message}>
            {status.error_message}
          </p>
        )}
      </div>
    </motion.div>
  );
}
