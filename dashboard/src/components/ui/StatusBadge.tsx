'use client';

import { motion } from 'framer-motion';

interface StatusBadgeProps {
  status: 'idle' | 'working' | 'completed' | 'error';
  label?: string;
  size?: 'sm' | 'md';
}

const statusConfig: Record<string, { color: string; bg: string; dotColor: string; label: string }> = {
  idle: { color: 'text-light-muted dark:text-dark-muted', bg: 'bg-light-muted/10 dark:bg-dark-muted/10', dotColor: 'bg-light-muted dark:bg-dark-muted', label: 'Idle' },
  working: { color: 'text-light-success dark:text-dark-success', bg: 'bg-light-success/10 dark:bg-dark-success/10', dotColor: 'bg-light-success dark:bg-dark-success', label: 'Working' },
  completed: { color: 'text-light-info dark:text-dark-info', bg: 'bg-light-info/10 dark:bg-dark-info/10', dotColor: 'bg-light-info dark:bg-dark-info', label: 'Done' },
  // error was `primary` here too. Same bug as Toast: a red state painted in
  // the brand purple, so "this failed" looked like ordinary UI chrome.
  error: { color: 'text-light-error dark:text-dark-error', bg: 'bg-light-error/10 dark:bg-dark-error/10', dotColor: 'bg-light-error dark:bg-dark-error', label: 'Error' },
};

export function StatusBadge({ status, label, size = 'sm' }: StatusBadgeProps) {
  const config = statusConfig[status];
  const sizeClasses = size === 'sm' ? 'px-2.5 py-1 text-xs' : 'px-3 py-1.5 text-sm';

  return (
    <span className={`inline-flex items-center gap-1.5 ${sizeClasses} rounded-full font-medium ${config.color} ${config.bg}`}>
      <span className="relative flex h-2 w-2">
        {status === 'working' && (
          <motion.span
            className="absolute inline-flex h-full w-full rounded-full opacity-75"
            style={{ backgroundColor: config.dotColor.replace('bg-', '') }}
            animate={{ scale: [1, 1.5, 1], opacity: [0.75, 0, 0.75] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${config.dotColor}`} />
      </span>
      {label || config.label}
    </span>
  );
}
