'use client';

import { motion } from 'framer-motion';

interface SkeletonProps {
  className?: string;
  lines?: number;
  variant?: 'card' | 'text' | 'circle';
}

export function LoadingSkeleton({ className = '', lines = 1, variant = 'text' }: SkeletonProps) {
  if (variant === 'circle') {
    return (
      <motion.div
        className={`rounded-full bg-light-border dark:bg-dark-border ${className}`}
        animate={{ opacity: [0.3, 1, 0.3] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      />
    );
  }

  if (variant === 'card') {
    return (
      <motion.div
        className={`rounded-xl bg-light-bg dark:bg-dark-bg/50 border border-light-border dark:border-dark-border p-4 ${className}`}
        animate={{ opacity: [0.5, 1, 0.5] }}
        transition={{ duration: 1.5, repeat: Infinity }}
      >
        <div className="h-4 w-1/3 bg-light-border dark:bg-dark-border rounded mb-3" />
        <div className="h-8 w-1/2 bg-light-border dark:bg-dark-border rounded mb-2" />
        <div className="h-3 w-2/3 bg-light-border dark:bg-dark-border rounded" />
      </motion.div>
    );
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <motion.div
          key={i}
          className="h-4 bg-light-border dark:bg-dark-border rounded"
          style={{ width: `${80 - i * 15}%` }}
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.1 }}
        />
      ))}
    </div>
  );
}

export function SkeletonGrid({ cols = 3, cards = 3 }: { cols?: number; cards?: number }) {
  return (
    <div className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-${cols} gap-4`}>
      {Array.from({ length: cards }).map((_, i) => (
        <LoadingSkeleton key={i} variant="card" />
      ))}
    </div>
  );
}
