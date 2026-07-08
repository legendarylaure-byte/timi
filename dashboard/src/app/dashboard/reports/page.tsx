'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  BarChart3, TrendingUp, Sparkles, Activity, Target, Bot,
  RefreshCw, Download, Calendar,
} from 'lucide-react';
import { ExecutiveSummary } from '@/components/reports/ExecutiveSummary';
import { PerformanceTrends } from '@/components/reports/PerformanceTrends';
import { PipelineHealth } from '@/components/reports/PipelineHealth';
import { QualityInsights } from '@/components/reports/QualityInsights';
import { GoalsPanel } from '@/components/reports/GoalsPanel';
import { ChatPanel } from '@/components/reports/ChatPanel';

const tabs = [
  { id: 'summary', label: 'Executive Summary', icon: BarChart3 },
  { id: 'trends', label: 'Performance Trends', icon: TrendingUp },
  { id: 'quality', label: 'Quality & Insights', icon: Sparkles },
  { id: 'pipeline', label: 'Pipeline Health', icon: Activity },
  { id: 'goals', label: 'Goals & Forecast', icon: Target },
  { id: 'chat', label: 'AI Analyst', icon: Bot },
] as const;

type TabId = typeof tabs[number]['id'];

export default function ReportsPage() {
  const [activeTab, setActiveTab] = useState<TabId>('summary');
  const [refreshKey, setRefreshKey] = useState(0);
  const [days, setDays] = useState(30);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  useEffect(() => {
    const interval = setInterval(handleRefresh, 120000);
    return () => clearInterval(interval);
  }, [handleRefresh]);

  const handleExport = async () => {
    let data: any[] = [];
    let filename = 'report';

    try {
      const res = await fetch('/api/reports/summary');
      if (res.ok) {
        const json = await res.json();
        data = [json];
        filename = 'timi_report_summary';
      }
    } catch { /* ignore */ }

    if (data.length === 0) return;

    const headers = Object.keys(data[0]);
    const csv = [
      headers.join(','),
      ...data.map(row => headers.map(h => {
        const val = row[h];
        const str = typeof val === 'object' ? JSON.stringify(val) : String(val ?? '');
        return `"${str.replace(/"/g, '""')}"`;
      }).join(',')),
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${filename}_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold gradient-text">Reports</h1>
          <p className="text-sm text-light-muted dark:text-dark-muted mt-1">
            Intelligence hub — analytics, trends, and AI-powered insights
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 px-2 py-1 rounded-lg bg-light-border/30 dark:bg-dark-border/30">
            <Calendar className="w-3.5 h-3.5 text-light-muted" />
            <select
              value={days}
              onChange={e => setDays(Number(e.target.value))}
              className="bg-transparent text-xs text-light-text dark:text-dark-text border-none outline-none cursor-pointer"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
            </select>
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-light-muted hover:text-light-text hover:bg-light-border/50 transition-all"
            title="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            Export
          </button>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-light-muted hover:text-light-text hover:bg-light-border/50 transition-all"
            title="Refresh data"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        </div>
      </div>

      <div className="flex gap-1 overflow-x-auto pb-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${
                isActive
                  ? 'text-white'
                  : 'text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text hover:bg-light-border/50 dark:hover:bg-dark-border/50'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="reportTab"
                  className="absolute inset-0 rounded-xl"
                  style={{ background: 'linear-gradient(135deg, #ec133e, #bd0f32)' }}
                  transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                />
              )}
              <Icon className="relative z-10 w-4 h-4" />
              <span className="relative z-10">{tab.label}</span>
            </button>
          );
        })}
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={`${activeTab}_${refreshKey}`}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'summary' && <ExecutiveSummary key={refreshKey} />}
          {activeTab === 'trends' && <PerformanceTrends key={refreshKey} />}
          {activeTab === 'quality' && <QualityInsights key={refreshKey} />}
          {activeTab === 'pipeline' && <PipelineHealth key={refreshKey} />}
          {activeTab === 'goals' && <GoalsPanel key={refreshKey} />}
          {activeTab === 'chat' && <ChatPanel />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
