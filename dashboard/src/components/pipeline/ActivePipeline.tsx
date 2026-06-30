'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, doc, onSnapshot, query, orderBy, limit, Timestamp } from 'firebase/firestore';
import { PIPELINE_STEPS, AGENT_COLORS } from '@/lib/constants';

interface PipelineStatus {
  running: boolean;
  current_video: string;
  paused_by_user: boolean;
  last_updated: Timestamp;
}

interface Checkpoint {
  id: string;
  step: string;
  state: Record<string, any>;
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

const AGENT_ICONS: Record<string, string> = {
  scriptwriter: '✍️',
  storyboard: '🎨',
  voice: '🎙️',
  composer: '🎵',
  animator: '🎬',
  editor: '✂️',
  thumbnail: '🖼️',
  metadata: '📋',
  publisher: '🚀',
};

export function ActivePipeline() {
  const [pipeline, setPipeline] = useState<PipelineStatus | null>(null);
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [expanded, setExpanded] = useState(false);
  const [expandedStep, setExpandedStep] = useState<string | null>(null);
  const [agentsWorking, setAgentsWorking] = useState(0);
  const [agents, setAgents] = useState<Map<string, AgentInfo>>(new Map());

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'agent_status'), (snap) => {
      let count = 0;
      const map = new Map<string, AgentInfo>();
      snap.docs.forEach(d => {
        const data = d.data() as AgentInfo;
        if (data.status === 'working') count++;
        map.set(data.agent_id, data);
      });
      setAgentsWorking(count);
      setAgents(map);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) {
        setPipeline(snap.data() as PipelineStatus);
      }
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    if (!pipeline?.running) return;
    const q = query(collection(db, 'pipeline_checkpoints'), orderBy('updated_at', 'desc'), limit(20));
    const unsub = onSnapshot(q, (snap) => {
      const items: Checkpoint[] = [];
      snap.docs.forEach(d => {
        items.push({ id: d.id, ...d.data() } as Checkpoint);
      });
      setCheckpoints(items);
    }, () => {});
    return () => unsub();
  }, [pipeline?.running]);

  if (!pipeline) return null;

  const currentStepIndex = checkpoints.length > 0
    ? PIPELINE_STEPS.findIndex(s => s.key === checkpoints[0].step)
    : -1;

  const formatTime = (seconds: number) => {
    const d = new Date(seconds * 1000);
    return d.toLocaleTimeString();
  };

  const particles = Array.from({ length: 5 }, (_, i) => i);

  return (
    <div className="rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card overflow-hidden glow-red">
      <button
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
        className="w-full flex items-center justify-between p-4 hover:bg-light-bg/50 dark:hover:bg-dark-bg/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${pipeline.running ? 'bg-emerald-500 animate-pulse' : agentsWorking > 0 ? 'bg-amber-400' : 'bg-gray-400'}`} />
          <div className="text-left">
            <h3 className="text-sm font-bold gradient-text" title="Neural Pipeline — live agent activity">
              Neural Pipeline
            </h3>
            <p className="text-xs text-light-muted dark:text-dark-muted truncate max-w-[260px]">
              {pipeline.running
                ? (agentsWorking > 0 ? `${agentsWorking} agent${agentsWorking > 1 ? 's' : ''} active — ${pipeline.current_video || 'generating...'}` : 'Flagged running — no agents active')
                : agentsWorking > 0
                  ? `${agentsWorking} agent${agentsWorking > 1 ? 's' : ''} running background tasks`
                  : 'Idle — waiting for next dispatch'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-light-muted dark:text-dark-muted">
            {checkpoints.length > 0 ? `Step ${currentStepIndex + 1}/${PIPELINE_STEPS.length}` : ''}
          </span>
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
        {expanded && pipeline.running && (
          <motion.div
            key="running"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-light-border/50 dark:border-dark-border/50"
          >
            <div className="p-4 pt-3">
              <div className="space-y-0">
                {PIPELINE_STEPS.map((step, i) => {
                  const isComplete = checkpoints.some(c => c.step === step.key) || agent?.status === 'completed';
                  const checkpoint = checkpoints.find(c => c.step === step.key);
                  const isCurrent = i === currentStepIndex || agent?.status === 'working';
                  const isPast = i < currentStepIndex;
                  const isExpanded = expandedStep === step.key;
                  const hasState = checkpoint && checkpoint.state && Object.keys(checkpoint.state).length > 0;

                  const agent = agents.get(step.agentId);
                  const agentColor = AGENT_COLORS[step.agentId] || '#6366f1';
                  const agentIsWorking = agent?.status === 'working';
                  const agentAction = agent?.current_action || '';
                  const agentName = agent?.name || step.agentId;

                  return (
                    <div key={step.key}>
                      <button
                        onClick={() => setExpandedStep(isExpanded ? null : hasState ? step.key : null)}
                        aria-expanded={isExpanded}
                        className={`w-full flex items-start gap-3 py-2.5 px-1 rounded-lg transition-colors ${
                          isExpanded ? 'bg-light-bg/50 dark:bg-dark-bg/50' : 'hover:bg-light-bg/30 dark:hover:bg-dark-bg/30'
                        } ${hasState ? 'cursor-pointer' : 'cursor-default'}`}
                      >
                        {/* Connector line with particle flow */}
                        <div className="flex flex-col items-center shrink-0 pt-1">
                          <div className={`
                            w-2.5 h-2.5 rounded-full relative
                            ${isComplete ? 'bg-emerald-500' : ''}
                            ${isCurrent ? 'bg-light-primary dark:bg-dark-primary' : ''}
                            ${isPast && !isCurrent ? 'bg-emerald-400' : ''}
                            ${!isComplete && !isCurrent && !isPast ? 'bg-light-muted/30 dark:bg-dark-muted/30' : ''}
                          `}>
                            {/* Neon glow ring for current step */}
                            {isCurrent && (
                              <motion.span
                                animate={{ opacity: [0.4, 1, 0.4], scale: [1, 1.6, 1] }}
                                transition={{ repeat: Infinity, duration: 2 }}
                                className="absolute inset-0 rounded-full bg-light-primary/30 dark:bg-dark-primary/30"
                              />
                            )}
                          </div>
                          {/* Particle flow along connector */}
                          {i < PIPELINE_STEPS.length - 1 && (
                            <div className="relative w-0.5 h-6">
                              <div className={`absolute inset-0 rounded-full ${
                                isPast && !isCurrent ? 'bg-emerald-400/50' :
                                isComplete ? 'bg-emerald-500/50' :
                                'bg-light-border dark:bg-dark-border'
                              }`} />
                              {isCurrent && particles.map((p) => (
                                <motion.div
                                  key={p}
                                  initial={{ top: '100%', opacity: 0 }}
                                  animate={{
                                    top: ['100%', '0%'],
                                    opacity: [0, 1, 0],
                                  }}
                                  transition={{
                                    repeat: Infinity,
                                    duration: 1.2,
                                    delay: p * 0.2,
                                    ease: 'linear',
                                  }}
                                  className="absolute w-0.5 h-0.5 rounded-full bg-cyan-400 left-1/2 -translate-x-1/2"
                                />
                              ))}
                              {isPast && !isCurrent && (
                                <motion.div
                                  initial={{ top: '100%', opacity: 0 }}
                                  animate={{ top: ['100%', '0%'], opacity: [0, 0.6, 0] }}
                                  transition={{ repeat: Infinity, duration: 1.5, ease: 'linear' }}
                                  className="absolute w-0.5 h-0.5 rounded-full bg-emerald-400/60 left-1/2 -translate-x-1/2"
                                />
                              )}
                            </div>
                          )}
                        </div>

                        <div className="flex-1 flex items-start justify-between min-w-0 gap-2">
                          {/* Step info */}
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2">
                              <span className={`text-xs font-medium ${
                                isComplete ? 'text-emerald-600 dark:text-emerald-400' :
                                isCurrent ? 'text-light-text dark:text-dark-text' :
                                'text-light-muted/60 dark:text-dark-muted/60'
                              }`}>
                                {step.label}
                              </span>
                              {isComplete && (
                                <motion.span
                                  initial={{ scale: 0 }}
                                  animate={{ scale: 1 }}
                                  className="text-[10px]"
                                >
                                  ✓
                                </motion.span>
                              )}
                              {isCurrent && (
                                <span className="text-[9px] font-mono text-light-primary dark:text-dark-primary tracking-widest animate-pulse">
                                  ACTIVE
                                </span>
                              )}
                            </div>

                            {/* Agent holographic card (appears for current/completed step) */}
                            {(isCurrent || (isComplete && agent)) && (
                              <motion.div
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                className="mt-1.5"
                              >
                                <div
                                  className={`
                                    flex flex-col gap-1 px-3 py-2 min-h-[48px] rounded-lg text-[10px]
                                    backdrop-blur-sm border transition-all
                                    ${isCurrent
                                      ? 'border-cyan-500/30 bg-cyan-500/5 shadow-[0_0_8px_rgba(6,182,212,0.15)]'
                                      : 'border-emerald-500/20 bg-emerald-500/5'
                                    }
                                  `}
                                >
                                  <div className="flex items-center gap-1.5">
                                    <span className="text-xs">{AGENT_ICONS[step.agentId] || '🤖'}</span>
                                    <span
                                      className="font-medium"
                                      style={{ color: agentColor }}
                                    >
                                      {agentName}
                                    </span>
                                    {isComplete && !isCurrent && (
                                      <span className="text-emerald-500 ml-1">✓ Done</span>
                                    )}
                                  </div>
                                  {isCurrent && agentIsWorking && agentAction && (
                                    <div className="flex items-center gap-1 text-light-muted dark:text-dark-muted">
                                      <motion.span
                                        initial={{ opacity: 0 }}
                                        animate={{ opacity: 1 }}
                                        key={agentAction}
                                      >
                                        ⚡ {agentAction}
                                      </motion.span>
                                    </div>
                                  )}
                                </div>
                              </motion.div>
                            )}

                            {/* Waiting indicator */}
                            {isCurrent && !agentIsWorking && !isComplete && (
                              <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: [0.4, 0.8, 0.4] }}
                                transition={{ repeat: Infinity, duration: 2 }}
                                className="text-[10px] text-light-muted/50 dark:text-dark-muted/50 italic mt-1"
                              >
                                dispatching agent...
                              </motion.div>
                            )}
                          </div>

                          {/* State expander */}
                          {hasState && (
                            <div className="flex items-center gap-2 shrink-0 mt-0.5">
                              <span className="text-[10px] text-light-muted dark:text-dark-muted hidden sm:block truncate max-w-[120px]">
                                {Object.keys(checkpoint.state).slice(0, 3).join(', ')}
                                {Object.keys(checkpoint.state).length > 3 ? '...' : ''}
                              </span>
                              <motion.svg
                                animate={{ rotate: isExpanded ? 180 : 0 }}
                                className="w-3 h-3 text-light-muted/50 dark:text-dark-muted/50 shrink-0"
                                fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                              >
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                              </motion.svg>
                            </div>
                          )}
                        </div>
                      </button>

                      <AnimatePresence>
                        {isExpanded && checkpoint && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="ml-8 mr-2 mb-2 p-2.5 rounded-lg bg-light-bg/40 dark:bg-dark-bg/40 border border-light-border/30 dark:border-dark-border/30 space-y-1.5">
                              {Object.entries(checkpoint.state).map(([key, value]) => (
                                <div key={key} className="flex items-start gap-2 text-[11px]">
                                  <span className="text-light-muted dark:text-dark-muted font-medium shrink-0 w-24 capitalize">
                                    {key.replace(/_/g, ' ')}
                                  </span>
                                  <span className="text-light-text dark:text-dark-text break-words">
                                    {typeof value === 'object' ? JSON.stringify(value).slice(0, 80) : String(value).slice(0, 120)}
                                  </span>
                                </div>
                              ))}
                              {checkpoint.updated_at && (
                                <div className="flex items-start gap-2 text-[11px] pt-1 border-t border-light-border/20 dark:border-dark-border/20">
                                  <span className="text-light-muted dark:text-dark-muted font-medium shrink-0 w-24">
                                    Last updated
                                  </span>
                                  <span className="text-light-muted dark:text-dark-muted">
                                    {formatTime(checkpoint.updated_at)}
                                  </span>
                                </div>
                              )}
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  );
                })}
              </div>
            </div>
          </motion.div>
        )}

        {expanded && !pipeline.running && (
          <motion.div
            key="idle"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="border-t border-light-border/50 dark:border-dark-border/50"
          >
            <div className="p-6 text-center">
              <p className="text-sm text-light-text/80 dark:text-dark-muted">
                {agentsWorking > 0
                  ? `${agentsWorking} agent${agentsWorking > 1 ? 's are' : ' is'} running scheduled tasks while the main pipeline waits for the next dispatch`
                  : <>Pipeline offline. Next automatic run at <strong className="text-light-text dark:text-dark-text">11:45 AM Nepal time</strong> (06:00 UTC).</>
                }
              </p>
              {pipeline.paused_by_user && (
                <p className="text-xs text-amber-500 mt-2">
                  Pipeline is paused by user.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
