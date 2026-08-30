import { motion } from 'framer-motion';
import type { ComponentType } from 'react';

interface EmptyStateProps {
  icon: ComponentType<{ className?: string }>;
  title: string;
  hint?: string;
  actionLabel?: string;
  onAction?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  hint,
  actionLabel,
  onAction,
  className = '',
}: EmptyStateProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={`glass-panel glass-noise flex flex-col items-center justify-center text-center p-10 ${className}`}
    >
      <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-light-primary/15 to-light-secondary/15 dark:from-dark-primary/15 dark:to-dark-accent/15 flex items-center justify-center mb-4">
        <Icon className="w-7 h-7 text-light-primary/70 dark:text-dark-primary/70" />
      </div>
      <h3 className="text-base font-bold text-light-text dark:text-dark-text">{title}</h3>
      {hint && <p className="text-sm text-light-muted dark:text-dark-muted mt-1.5 max-w-sm">{hint}</p>}
      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="mt-5 px-5 py-2.5 rounded-xl font-semibold text-sm text-white transition-all duration-300 hover:scale-105 active:scale-95"
          style={{
            background: 'linear-gradient(135deg, #ec133e, #bd0f32)',
            boxShadow: '0 6px 18px rgba(236, 19, 62, 0.28)',
          }}
        >
          {actionLabel}
        </button>
      )}
    </motion.div>
  );
}
