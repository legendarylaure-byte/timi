'use client';

import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface KpiCardProps {
  title: string;
  value: string;
  subtitle?: string;
  change?: number;
  icon: React.ReactNode;
  freshness?: string;
  color?: 'red' | 'blue' | 'green' | 'purple' | 'orange' | 'teal';
}

const colorMap = {
  red: 'from-red-500/20 to-red-600/5 border-red-500/20',
  blue: 'from-blue-500/20 to-blue-600/5 border-blue-500/20',
  green: 'from-emerald-500/20 to-emerald-600/5 border-emerald-500/20',
  purple: 'from-purple-500/20 to-purple-600/5 border-purple-500/20',
  orange: 'from-orange-500/20 to-orange-600/5 border-orange-500/20',
  teal: 'from-teal-500/20 to-teal-600/5 border-teal-500/20',
};

const iconColorMap = {
  red: 'text-red-400',
  blue: 'text-blue-400',
  green: 'text-emerald-400',
  purple: 'text-purple-400',
  orange: 'text-orange-400',
  teal: 'text-teal-400',
};

export function KpiCard({ title, value, subtitle, change, icon, freshness, color = 'blue' }: KpiCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`glass rounded-xl p-4 border bg-gradient-to-br ${colorMap[color]} relative overflow-hidden`}
    >
      <div className="flex items-start justify-between mb-2">
        <span className="text-xs font-medium text-light-muted dark:text-dark-muted uppercase tracking-wider">
          {title}
        </span>
        <span className={iconColorMap[color]}>{icon}</span>
      </div>
      <div className="text-2xl font-bold text-light-text dark:text-dark-text mb-1">{value}</div>
      {subtitle && (
        <div className="text-xs text-light-muted dark:text-dark-muted">{subtitle}</div>
      )}
      {change !== undefined && (
        <div className={`flex items-center gap-1 mt-1 text-xs font-medium ${change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
          {change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          <span>{Math.abs(change)}% vs last period</span>
        </div>
      )}
      {freshness && (
        <div className="absolute top-2 right-2">
          <span className="text-[10px] text-light-muted/50 dark:text-dark-muted/50">{freshness}</span>
        </div>
      )}
    </motion.div>
  );
}
