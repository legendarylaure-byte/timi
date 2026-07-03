'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, doc, onSnapshot, query, orderBy, limit, Timestamp } from 'firebase/firestore';
import { PIPELINE_STEPS, AGENT_ROLES } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import Tooltip from '@/components/ui/Tooltip';

interface PipelineStatus {
  running: boolean;
  current_video: string;
  paused_by_user: boolean;
  last_updated: Timestamp;
}

interface Checkpoint {
  id: string;
  step: string;
  updated_at: number;
}

interface AgentInfo {
  agent_id: string;
  name: string;
  color: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: Timestamp;
}

function isStale(ts: Timestamp | undefined): boolean {
  if (!ts) return true;
  const date = ts.toDate ? ts.toDate() : new Date(ts as any);
  return (Date.now() - date.getTime()) > 5 * 60 * 1000;
}

function agentRole(agentId: string) {
  return AGENT_ROLES.find(r => r.id === agentId);
}

export function ActivePipeline() {
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [agents, setAgents] = useState<Map<string, AgentInfo>>(new Map());
  const [showComplete, setShowComplete] = useState(false);
  const [prevRunning, setPrevRunning] = useState(false);
  const [resetting, setResetting] = useState(false);
  const { addToast } = useToast();

  const handleReset = async () => {
    if (!window.confirm('Reset all agent statuses to idle and clear the pipeline flag? This will NOT affect any running processes.')) return;
    setResetting(true);
    try {
      const res = await fetch('/api/pipeline/reset', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        addToast(`Reset ${data.resetCount || 0} agent statuses`, 'success');
      } else {
        addToast(data.error || 'Reset failed', 'error');
      }
    } catch {
      addToast('Network error — could not reach reset endpoint', 'error');
    } finally {
      setResetting(false);
    }
  };

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'agent_status'), (snap) => {
      const map = new Map<string, AgentInfo>();
      snap.docs.forEach(d => {
        const data = d.data() as AgentInfo;
        const stale = data.status === 'working' && isStale(data.last_updated);
        map.set(data.agent_id, stale ? { ...data, status: 'idle', current_action: 'Ready' } : data);
      });
      setAgents(map);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) setPipeline(snap.data() as PipelineStatus);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    if (!pipeline?.running) return;
    const q = query(collection(db, 'pipeline_checkpoints'), orderBy('updated_at', 'desc'), limit(PIPELINE_STEPS.length));
    const unsub = onSnapshot(q, (snap) => {
      const items: Checkpoint[] = [];
      snap.docs.forEach(d => {
        const data = d.data();
        items.push({ id: d.id, step: data.step, updated_at: data.updated_at });
      });
      setCheckpoints(items);
    }, () => {});
    return () => unsub();
  }, [pipeline?.running]);

  useEffect(() => {
    if (prevRunning && !pipeline?.running) {
      setShowComplete(true);
      const timer = setTimeout(() => setShowComplete(false), 13000);
      return () => clearTimeout(timer);
    }
    setPrevRunning(!!pipeline?.running);
  }, [pipeline?.running, prevRunning]);

  if (!pipeline) {
    return (
      <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red animate-pulse">
        <div className="p-4">
          <div className="flex items-center gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-light-border/60" />
            <div className="flex-1">
              <div className="h-4 w-28 rounded bg-light-border/60" />
              <div className="h-3 w-44 rounded bg-light-border/40 mt-1.5" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  const running = pipeline.running;
  const workingAgents = Array.from(agents.values()).filter(
    a => a.status === 'working' && !isStale(a.last_updated)
  );
  const completedAgents = Array.from(agents.values()).filter(
    a => a.status === 'completed' && (running || showComplete)
  );
  const errorAgents = Array.from(agents.values()).filter(
    a => a.status === 'error'
  );
  const workingCount = workingAgents.length;

  const active = running || workingAgents.length > 0;
  const completedSteps = new Set(checkpoints.map(c => c.step)).size;
  const hasProgress = checkpoints.length > 0;
  const progress = Math.round((completedSteps / PIPELINE_STEPS.length) * 100);

  return (
    <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${running ? 'bg-emerald-500 animate-pulse' : workingCount > 0 ? 'bg-violet-400' : 'bg-gray-400'}`} />
          <div className="text-left">
            <h3 className="text-sm font-bold gradient-text">Live Production</h3>
            <p className="text-xs text-light-muted dark:text-dark-muted truncate max-w-[260px]">
              {running && workingCount > 0
                ? `${workingCount} agent${workingCount > 1 ? 's' : ''} working on "${pipeline.current_video || 'a new video'}"`
                : running
                  ? 'Starting up — dispatching agents...'
                : workingCount > 0
                  ? `${workingCount} agent${workingCount > 1 ? 's' : ''} on background tasks`
                : pipeline.paused_by_user
                  ? 'Paused — resume from the controls above'
                  : 'Idle — next run at 11:45 AM NPT'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {running && hasProgress && (
            <span className="text-xs text-light-muted dark:text-dark-muted">{progress}%</span>
          )}
          <motion.svg
            animate={{ rotate: expanded ? 180 : 0 }}
            className="w-4 h-4 text-light-muted dark:text-dark-muted"
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </motion.svg>
        </div>
      </button>

      <AnimatePresence>
        {expanded && active && (
          <motion.div
            key="running"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-light-border/50 dark:border-dark-border/50"
          >
            <div className="p-4 pt-3 space-y-4">

              {/* Progress bar — only when pipeline is running */}
              {running && (
              <div>
                <div className="w-full h-2 rounded-full bg-light-border/40 dark:bg-dark-border/40 overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: hasProgress ? `${progress}%` : '30%' }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                    className={`h-full rounded-full ${hasProgress ? 'bg-gradient-to-r from-emerald-500 to-emerald-400' : 'bg-gradient-to-r from-cyan-500 to-cyan-400 animate-pulse'}`}
                  />
                </div>
                <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">
                  {hasProgress
                    ? `${completedSteps} of ${PIPELINE_STEPS.length} production steps done`
                    : 'Agents are being dispatched...'}
                </p>
              </div>
              )}

              {/* Error agents */}
              {errorAgents.length > 0 && (
                <div>
                  <p className="text-[11px] font-bold text-red-500 mb-2">⚠️ Having trouble</p>
                  <div className="space-y-1.5">
                    {errorAgents.map(agent => {
                      const role = agentRole(agent.agent_id);
                      return (
                        <div key={agent.agent_id} className="flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20">
                          <span>{role?.emoji || '🤖'}</span>
                          <span className="font-medium text-light-text dark:text-dark-text">{agent.name}</span>
                          <span className="text-light-muted dark:text-dark-muted">— ran into an issue, will retry</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Working agents */}
              {workingAgents.length > 0 && (
                <div>
                  <p className="text-[11px] font-bold text-cyan-600 dark:text-cyan-400 mb-2">🎬 Currently working</p>
                  <div className="space-y-2">
                    {workingAgents.map(agent => {
                      const role = agentRole(agent.agent_id);
                      return (
                        <div key={agent.agent_id} className="flex flex-col gap-0.5 px-3 py-2 rounded-lg border border-cyan-500/30 bg-cyan-500/5">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded flex items-center justify-center text-xs bg-cyan-500/10">
                              {role?.emoji || '🤖'}
                            </span>
                            <span className="text-xs font-medium text-light-text dark:text-dark-text">{agent.name}</span>
                            {agent.current_action && (
                              <span className="text-[11px] text-cyan-600 dark:text-cyan-400 truncate max-w-[200px] sm:max-w-[300px]">
                                ➜ {agent.current_action}
                              </span>
                            )}
                          </div>
                          {role?.description && (
                            <p className="text-[10px] text-light-muted/50 dark:text-dark-muted/60 ml-7 leading-relaxed">
                              {role.description}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* No agents yet */}
              {workingAgents.length === 0 && !hasProgress && (
                <div className="text-center py-4">
                  <motion.p
                    animate={{ opacity: [0.4, 0.8, 0.4] }}
                    transition={{ repeat: Infinity, duration: 2 }}
                    className="text-xs text-light-muted dark:text-dark-muted italic"
                  >
                    Starting up — agents are being dispatched...
                  </motion.p>
                </div>
              )}

              {/* Completed agents */}
              {completedAgents.length > 0 && (
                <div>
                  <p className="text-[11px] font-bold text-emerald-600 dark:text-emerald-400 mb-2">✅ Completed</p>
                  <div className="flex flex-wrap gap-1.5">
                    {completedAgents.map(agent => {
                      const role = agentRole(agent.agent_id);
                      return (
                        <div key={agent.agent_id} className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                          <span>{role?.emoji || '🤖'}</span>
                          <span className="font-medium text-emerald-700 dark:text-emerald-400">{agent.name}</span>
                          <span className="text-emerald-500 ml-0.5">✓</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Waiting agents — only when pipeline is running */}
              {running && (() => {
                const seen = new Set<string>();
                const waiting = PIPELINE_STEPS.filter(s => {
                  if (seen.has(s.agentId)) return false;
                  seen.add(s.agentId);
                  const a = agents.get(s.agentId);
                  return !a || (a.status !== 'working' && a.status !== 'completed' && a.status !== 'error');
                });
                if (waiting.length === 0) return null;
                return (
                  <div>
                    <p className="text-[11px] font-bold text-light-muted/60 dark:text-dark-muted/60 mb-2">⏳ Waiting</p>
                    <div className="flex flex-wrap gap-1.5">
                      {waiting.map(s => {
                        const role = agentRole(s.agentId);
                        return (
                          <div key={s.agentId} className="flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg bg-light-bg/40 dark:bg-dark-bg/40 border border-light-border/30 dark:border-dark-border/30">
                            <span>{role?.emoji || '🤖'}</span>
                            <span className="font-medium text-light-muted dark:text-dark-muted">{role?.name || s.agentId}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              {/* Info hint */}
              <div className="pt-2 border-t border-light-border/30 dark:border-dark-border/30">
                <p className="text-[10px] text-light-muted/50 dark:text-dark-muted/50 leading-relaxed">
                  💡 AI agents work like a video production crew — each is a specialist handling one part of the process, from writing to publishing.
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {expanded && !active && (
          <motion.div
            key="idle"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-light-border/50 dark:border-dark-border/50"
          >
            <div className="p-6 text-center space-y-2">
              <p className="text-sm text-light-text/80 dark:text-dark-muted">
                {pipeline.paused_by_user
                  ? 'Pipeline is paused. Resume from the controls above.'
                  : <>Pipeline is resting. Next automatic video at <strong className="text-light-text dark:text-dark-text">11:45 AM Nepal time</strong> (06:00 UTC).</>
                }
              </p>
              {!pipeline.paused_by_user && (
                <p className="text-xs text-light-muted/60 dark:text-dark-muted/60">
                  Or start one manually using &quot;Run Pipeline&quot; above.
                </p>
              )}
              <div className="pt-3">
                <Tooltip content="Resets all agent statuses to idle and clears the pipeline running flag. Use this if agents appear stuck after a crash or cancellation." color="#EF4444">
                  <button
                    onClick={handleReset}
                    disabled={resetting}
                    className="px-4 py-2 rounded-xl text-xs font-medium transition-all border border-red-400/30 text-red-400 hover:bg-red-400/10 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {resetting ? 'Resetting...' : 'Reset Agent Statuses'}
                  </button>
                </Tooltip>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
