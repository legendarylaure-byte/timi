'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Sparkles, TrendingUp, TrendingDown, Loader2, AlertTriangle, CheckCircle, Eye } from 'lucide-react';
import { auth } from '@/lib/firebase';
import {
  ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
  BarChart, Bar,
} from 'recharts';

interface CorrelationData {
  correlations: Array<{
    factor: string; metric: string; pearsonR: number;
    sampleSize: number; interpretation: string;
    scatterData: Array<{ x: number; y: number; label: string }>;
  }>;
  formatBreakdown: Array<{ name: string; avgViews: number; count: number }>;
  categoryBreakdown: Array<{ name: string; avgViews: number; count: number }>;
  totalVideosAnalyzed: number;
  insight: string;
}

interface QualityTrendsData {
  trends: Array<{ date: string; avgQualityScore: number; avgViralityScore: number; avgViews: number; videoCount: number }>;
  anomalies: Array<{ videoId: string; title: string; format: string; predictedViews: number; actualViews: number; deviation: number; type: string }>;
  correlationSummary: string;
  freshness: string;
  averageViewsOverall: number;
}

export function QualityInsights() {
  const [corr, setCorr] = useState<CorrelationData | null>(null);
  const [quality, setQuality] = useState<QualityTrendsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [corrIndex, setCorrIndex] = useState(0);
  const [viewMode, setViewMode] = useState<'correlations' | 'anomalies' | 'breakdown'>('correlations');

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      try {
        const user = auth.currentUser;
        if (!user) return;
        const token = await user.getIdToken();
        const headers = { authorization: `Bearer ${token}` };

        const [corrRes, qualRes] = await Promise.all([
          fetch('/api/reports/correlations', { headers }),
          fetch('/api/reports/quality-trends', { headers }),
        ]);

        if (!cancelled) {
          if (corrRes.ok) setCorr(await corrRes.json());
          if (qualRes.ok) setQuality(await qualRes.json());
        }
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
        <p className="text-sm text-red-400">Failed to load insights: {error}</p>
      </div>
    );
  }

  if (!corr) {
    return (
      <div className="glass rounded-xl p-12 flex items-center justify-center">
        <Loader2 className="w-6 h-6 animate-spin text-light-muted" />
      </div>
    );
  }

  const formatNum = (v: number) => {
    if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
    if (v >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
    return String(v);
  };

  const selectedCorr = corr.correlations[corrIndex];
  const anomalies = quality?.anomalies || [];

  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        {(['correlations', 'anomalies', 'breakdown'] as const).map((mode) => (
          <button
            key={mode}
            onClick={() => setViewMode(mode)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              viewMode === mode
                ? 'bg-light-primary text-white'
                : 'text-light-muted dark:text-dark-muted hover:bg-light-border/50'
            }`}
          >
            {mode === 'correlations' ? 'Correlations' : mode === 'anomalies' ? 'Anomalies' : 'Breakdown'}
          </button>
        ))}
      </div>

      {viewMode === 'correlations' && (
        <>
          <div className="glass rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">
                Factor vs Views Correlation
              </h3>
              <span className="text-xs text-light-muted">
                {corr.totalVideosAnalyzed} videos analyzed
              </span>
            </div>
            <div className="flex gap-2 mb-4 overflow-x-auto">
              {corr.correlations.map((c, i) => (
                <button
                  key={c.factor}
                  onClick={() => setCorrIndex(i)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-all ${
                    corrIndex === i
                      ? 'bg-light-primary text-white'
                      : 'text-light-muted dark:text-dark-muted hover:bg-light-border/50'
                  }`}
                >
                  {c.factor} vs {c.metric}
                  <span className={`ml-1.5 inline-block ${
                    Math.abs(c.pearsonR) >= 0.4 ? 'text-emerald-400' : Math.abs(c.pearsonR) >= 0.2 ? 'text-yellow-400' : 'text-gray-400'
                  }`}>
                    r={c.pearsonR.toFixed(2)}
                  </span>
                </button>
              ))}
            </div>
            {selectedCorr && selectedCorr.scatterData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <ScatterChart margin={{ top: 10, right: 20, bottom: 10, left: 10 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis
                      dataKey="x"
                      name={selectedCorr.factor}
                      tick={{ fontSize: 11, fill: '#6B7280' }}
                      label={{ value: selectedCorr.factor, position: 'bottom', style: { fill: '#6B7280', fontSize: 11 } }}
                    />
                    <YAxis
                      dataKey="y"
                      name="Views"
                      tick={{ fontSize: 11, fill: '#6B7280' }}
                      tickFormatter={formatNum}
                      label={{ value: 'Views', angle: -90, position: 'left', style: { fill: '#6B7280', fontSize: 11 } }}
                    />
                    <Tooltip
                      contentStyle={{
                        background: 'rgba(0,0,0,0.8)',
                        border: '1px solid rgba(255,255,255,0.1)',
                        borderRadius: '12px',
                        fontSize: '12px',
                      }}
                  formatter={(value: any) => [typeof value === 'number' ? formatNum(value) : value, '']}
                  labelFormatter={(label: any) => String(selectedCorr.scatterData.find(d => d.label === label)?.label || label || '')}
                    />
                    <Scatter data={selectedCorr.scatterData} fill="#ec133e" fillOpacity={0.6}>
                      {selectedCorr.scatterData.map((_, idx) => (
                        <Cell key={idx} fill="#ec133e" fillOpacity={0.5} />
                      ))}
                    </Scatter>
                  </ScatterChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-sm text-light-muted">
                Not enough data for scatter plot. Need more videos with both metrics recorded.
              </div>
            )}
            <div className="mt-4 p-3 rounded-lg bg-light-border/30 dark:bg-dark-border/30">
              <p className="text-xs text-light-muted">{corr.insight}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {corr.correlations.map((c, i) => (
              <motion.div
                key={c.factor}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass rounded-xl p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-light-text dark:text-dark-text">{c.factor}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    Math.abs(c.pearsonR) >= 0.4 ? 'bg-emerald-500/20 text-emerald-400' :
                    Math.abs(c.pearsonR) >= 0.2 ? 'bg-yellow-500/20 text-yellow-400' :
                    'bg-gray-500/20 text-gray-400'
                  }`}>
                    {c.interpretation}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-lg font-bold text-light-text dark:text-dark-text">r = {c.pearsonR.toFixed(2)}</span>
                  {c.pearsonR > 0 ? (
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                  ) : (
                    <TrendingDown className="w-4 h-4 text-red-400" />
                  )}
                </div>
                <div className="text-xs text-light-muted mt-1">{c.sampleSize} samples</div>
              </motion.div>
            ))}
          </div>
        </>
      )}

      {viewMode === 'anomalies' && (
        <div className="glass rounded-xl p-6">
          <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400" />
            Performance Anomalies
            <span className="text-xs text-light-muted font-normal">{'(>100% deviation from predicted)'}</span>
          </h3>
          {anomalies.length > 0 ? (
            <div className="space-y-2">
              {anomalies.map((a, i) => (
                <motion.div
                  key={a.videoId}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`flex items-center justify-between p-3 rounded-lg ${
                    a.type === 'overperformer'
                      ? 'bg-emerald-500/5 border border-emerald-500/10'
                      : 'bg-red-500/5 border border-red-500/10'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {a.type === 'overperformer'
                        ? <TrendingUp className="w-4 h-4 text-emerald-400" />
                        : <TrendingDown className="w-4 h-4 text-red-400" />
                      }
                      <span className="text-sm font-medium text-light-text dark:text-dark-text truncate">
                        {a.title || a.videoId}
                      </span>
                      <span className="text-[10px] uppercase px-1.5 py-0.5 rounded font-medium"
                        style={{ background: a.format === 'shorts' ? 'rgba(236,19,62,0.15)' : 'rgba(16,185,129,0.15)', color: a.format === 'shorts' ? '#ec133e' : '#10B981' }}
                      >
                        {a.format}
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-light-muted">
                      <span>Predicted: {formatNum(a.predictedViews)}</span>
                      <span>Actual: {formatNum(a.actualViews)}</span>
                      <span className={a.deviation > 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {a.deviation > 0 ? '+' : ''}{a.deviation}%
                      </span>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <CheckCircle className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
              <p className="text-sm text-light-muted">No significant anomalies detected. All videos performed within expected range.</p>
              <p className="text-xs text-light-muted/50 mt-1">Anomalies are videos where actual views differ by more than 100% from predicted.</p>
            </div>
          )}
        </div>
      )}

      {viewMode === 'breakdown' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass rounded-xl p-6">
            <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4">By Format</h3>
            {corr.formatBreakdown.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={corr.formatBreakdown} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6B7280' }} />
                    <YAxis tickFormatter={formatNum} tick={{ fontSize: 11, fill: '#6B7280' }} />
                    <Tooltip
                      contentStyle={{ background: 'rgba(0,0,0,0.8)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '12px', fontSize: '12px' }}
                      formatter={(value: any) => [formatNum(Number(value)), 'Avg Views']}
                    />
                    <Bar dataKey="avgViews" radius={[6, 6, 0, 0]} maxBarSize={60}>
                      {corr.formatBreakdown.map((_, idx) => (
                        <Cell key={idx} fill={idx === 0 ? '#ec133e' : '#10B981'} fillOpacity={0.7} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-sm text-light-muted">No data</div>
            )}
          </div>
          <div className="glass rounded-xl p-6">
            <h3 className="text-sm font-semibold text-light-text dark:text-dark-text mb-4">By Category</h3>
            {corr.categoryBreakdown.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {corr.categoryBreakdown.map((c, i) => (
                  <div key={c.name} className="flex items-center justify-between p-2 rounded-lg hover:bg-light-border/30 transition-colors">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-light-muted w-5">{i + 1}.</span>
                      <span className="text-sm text-light-text dark:text-dark-text">{c.name}</span>
                      <span className="text-xs text-light-muted">({c.count} videos)</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Eye className="w-3 h-3 text-blue-400" />
                      <span className="text-sm font-medium text-blue-400">{formatNum(c.avgViews)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-48 flex items-center justify-center text-sm text-light-muted">No data</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
