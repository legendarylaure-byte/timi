'use client';

import { useState, useEffect } from 'react';
import { Film, Eye, Users, DollarSign, BarChart3, TrendingUp, Target, Activity } from 'lucide-react';
import { KpiCard } from './KpiCard';
import { auth } from '@/lib/firebase';

interface SummaryData {
  totalVideos: number;
  publishedVideos: number;
  totalViews: number;
  totalSubs: number;
  monthlyRevenue: number;
  estimatedYearly: number;
  pipelineSuccessRate: number;
  bestCategory: { name: string; avgViews: number } | null;
  bestFormat: 'shorts' | 'long' | null;
  periodComparison: {
    viewsChange: number;
    subsChange: number;
    revenueChange: number;
  };
  freshness: {
    views: string;
    subs: string;
    revenue: string;
    pipeline: string;
  };
  todayCount: { shorts: number; long: number };
  formatBreakdown: { shorts: number; long: number };
}

export function ExecutiveSummary() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const user = auth.currentUser;
        if (!user) return;
        const token = await user.getIdToken();
        const res = await fetch('/api/reports/summary', {
          headers: { authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        if (!cancelled) setData(json);
      } catch (e: any) {
        if (!cancelled) setError(e.message);
      }
    };
    fetchData();
    return () => { cancelled = true; };
  }, []);

  if (error) {
    return (
      <div className="glass rounded-xl p-6 text-center">
        <p className="text-sm text-red-400">Failed to load summary: {error}</p>
        <button onClick={() => window.location.reload()} className="text-xs text-light-primary mt-2 hover:underline">
          Retry
        </button>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-28 glass rounded-xl p-4">
            <div className="h-4 w-20 bg-light-border dark:bg-dark-border rounded mb-3" />
            <div className="h-8 w-24 bg-light-border dark:bg-dark-border rounded mb-2" />
            <div className="h-3 w-16 bg-light-border dark:bg-dark-border rounded" />
          </div>
        ))}
      </div>
    );
  }

  const f = data.formatBreakdown;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          title="Total Videos"
          value={String(data.totalVideos)}
          subtitle={`${data.publishedVideos} published · ${f.shorts} shorts / ${f.long} long`}
          icon={<Film className="w-4 h-4" />}
          freshness={data.freshness.pipeline}
          color="purple"
        />
        <KpiCard
          title="Total Views"
          value={formatNum(data.totalViews)}
          subtitle={`${data.todayCount.shorts + data.todayCount.long} videos today`}
          change={data.periodComparison.viewsChange}
          icon={<Eye className="w-4 h-4" />}
          freshness={data.freshness.views}
          color="blue"
        />
        <KpiCard
          title="Subscribers"
          value={formatNum(data.totalSubs)}
          change={data.periodComparison.subsChange}
          icon={<Users className="w-4 h-4" />}
          freshness={data.freshness.subs}
          color="green"
        />
        <KpiCard
          title="Revenue (MTD)"
          value={`$${data.monthlyRevenue.toFixed(2)}`}
          subtitle={`$${data.estimatedYearly.toFixed(0)}/yr estimated`}
          change={data.periodComparison.revenueChange}
          icon={<DollarSign className="w-4 h-4" />}
          freshness={data.freshness.revenue}
          color="red"
        />
        <KpiCard
          title="Pipeline Success"
          value={`${data.pipelineSuccessRate}%`}
          subtitle={`${data.totalVideos} total runs`}
          icon={<Activity className="w-4 h-4" />}
          freshness={data.freshness.pipeline}
          color="teal"
        />
        <KpiCard
          title="Best Category"
          value={data.bestCategory?.name || 'N/A'}
          subtitle={data.bestCategory ? `${formatNum(data.bestCategory.avgViews)} avg views` : 'Insufficient data'}
          icon={<BarChart3 className="w-4 h-4" />}
          color="orange"
        />
        <KpiCard
          title="Best Format"
          value={data.bestFormat === 'shorts' ? 'Shorts' : data.bestFormat === 'long' ? 'Long Form' : 'N/A'}
          subtitle={data.bestFormat ? 'Highest avg views' : 'Insufficient data'}
          icon={<TrendingUp className="w-4 h-4" />}
          color="green"
        />
        <KpiCard
          title="Today's Production"
          value={`${data.todayCount.shorts + data.todayCount.long}`}
          subtitle={`${data.todayCount.shorts} shorts · ${data.todayCount.long} long`}
          icon={<Target className="w-4 h-4" />}
          color="purple"
        />
      </div>
    </div>
  );
}

function formatNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}
