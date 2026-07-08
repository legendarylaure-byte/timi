'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { doc, collection, onSnapshot, Timestamp } from 'firebase/firestore';
import { getNextUploadDisplay } from '@/lib/constants';

interface StatusPill {
  id: string;
  status: 'ok' | 'warn' | 'error' | 'unknown' | 'working' | 'cloud';
  value: string;
  tooltip: string;
}

interface StatusHelpContent {
  title: string;
  description: string;
  reasons: string[];
  fixes: string[];
}

const STATUS_HELP: Record<string, Partial<Record<'warn' | 'error' | 'cloud', StatusHelpContent>>> = {
  pipeline: {
    warn: {
      title: 'Pipeline Idle — Background Tasks Running',
      description: 'The main video pipeline is currently idle, but some agents are running scheduled background tasks like analysing analytics, repurposing content, or planning the daily content schedule.',
      reasons: [
        'The daily schedule runs at 11:45 AM Nepal time (06:00 UTC)',
        'Agents may be finishing up tasks from the last pipeline run',
        'No video has been manually triggered to run',
      ],
      fixes: [
        'Wait for the next scheduled daily run at 11:45 AM NPT',
        'Or type a topic in "Run Pipeline" above and click "Run Now" to start a video immediately',
        'If agents are stuck, try toggling them off and on in the Agents section',
      ],
    },
  },
  docker: {
    warn: {
      title: 'Docker — Some Containers Having Issues',
      description: 'Docker is running but some of your containers are not healthy. Your pipeline may not work correctly until all containers are healthy.',
      reasons: [
        'A container may have crashed or exited unexpectedly',
        'There might be a port conflict with another application',
        'The container might be out of memory',
      ],
      fixes: [
        'Open Docker Desktop and check the container logs for errors',
        'Try restarting the container: "docker restart timi-pipeline"',
        'Or restart Docker Desktop: click Troubleshoot → Restart',
        'If it persists, rebuild the container: "docker compose build"',
      ],
    },
    cloud: {
      title: 'Docker — Not Available in Cloud',
      description: 'Docker is not available in this cloud environment (Vercel serverless). The pipeline runs on your local machine instead. This is expected when viewing the dashboard from the cloud deployment.',
      reasons: [
        'The dashboard is accessed via the cloud URL (timi.vyomai.cloud)',
        'Vercel serverless functions cannot run Docker containers',
        'Pipeline execution happens on your local machine, not in the cloud',
      ],
      fixes: [
        'This is normal — no action needed',
        'To see Docker status, open the dashboard on localhost:5001',
        'The pipeline will still run on your local machine as scheduled',
      ],
    },
    error: {
      title: 'Docker Is Offline',
      description: 'Docker powers all your AI agents and video pipeline. Without it, no videos can be generated on your local machine.',
      reasons: [
        'Docker Desktop might not be running',
        'The Docker daemon may have crashed',
        'Your computer may have restarted recently',
        'Docker might be updating itself',
      ],
      fixes: [
        'Open Docker Desktop from your Applications folder',
        'Wait for the green light in the bottom-left corner (about 30 seconds)',
        'If Docker is stuck, click Troubleshoot → Restart in Docker Desktop',
        'If nothing helps, restart your computer',
      ],
    },
  },
  firebase: {
    warn: {
      title: 'Firebase — Higher Latency Than Usual',
      description: 'Firebase is your app\'s cloud database. It stores all video data, agent status, and activity logs. The connection is working but response times are higher than usual.',
      reasons: [
        'Your internet connection might be slow right now',
        'Firebase servers may be experiencing high traffic',
        'From Nepal, latency between 500ms-1000ms is normal',
      ],
      fixes: [
        'Check your internet connection speed',
        'Wait a few minutes — it often resolves on its own',
        'If it persists, check the Firebase Status Dashboard',
      ],
    },
    error: {
      title: 'Firebase Is Disconnected',
      description: 'Cannot reach Firebase. Without Firebase, your dashboard cannot load any data — no videos, agents, or activity logs will show.',
      reasons: [
        'Your internet connection is down',
        'Firebase servers may be experiencing an outage',
        'A firewall or VPN might be blocking the connection',
        'The Firebase service account key may not be set on this deployment',
      ],
      fixes: [
        'Check your internet connection — try opening a website in your browser',
        'Disable any VPN or proxy and refresh the page',
        'Check the Firebase Status Dashboard for ongoing issues',
        'If viewing on Vercel (cloud), ensure FIREBASE_SERVICE_ACCOUNT_KEY is set in Vercel env vars',
      ],
    },
  },
  storage: {
    warn: {
      title: 'Cloud Storage — Running Low on Space',
      description: 'Your Cloudflare R2 storage is running low on free space. Videos are stored here and new uploads may fail if it fills up completely.',
      reasons: [
        'Many videos have been uploaded without cleaning up old ones',
        'Your storage plan may need to be upgraded',
        'Large video files are taking up more space than expected',
      ],
      fixes: [
        'Delete old or unused videos from the Archive section',
        'Consider upgrading your R2 storage plan for more space',
        'Or set up automatic cleanup to remove videos older than 30 days',
      ],
    },
    error: {
      title: 'Cloud Storage Not Configured',
      description: 'Cloudflare R2 is not connected yet. Your videos are stored locally on your machine, which means they won\'t be backed up to the cloud.',
      reasons: [
        'R2 credentials have not been added to this project',
        'The .env file may be missing R2 configuration values',
        'This is the initial setup and cloud storage hasn\'t been configured yet',
      ],
      fixes: [
        'Add your R2 credentials to the .env.local file:',
        '   R2_ACCOUNT_ID=your_account_id',
        '   R2_ACCESS_KEY_ID=your_access_key',
        '   R2_SECRET_ACCESS_KEY=your_secret_key',
        '   R2_BUCKET=your_bucket_name',
        'Get these from your Cloudflare dashboard under R2 → API Tokens',
        'After adding, restart the development server',
      ],
    },
  },
  agents: {
    warn: {
      title: 'Agent Heartbeat Stale',
      description: 'Some of your AI agents haven\'t reported their status recently. They may still be working or could have crashed.',
      reasons: [
        'The agent process might be busy with a long-running task',
        'The agent process might have crashed',
        'There might be a communication issue between the dashboard and agents',
      ],
      fixes: [
        'Wait a few minutes — agents may report in once their task finishes',
        'Check the Docker container logs for errors',
        'Try restarting the container: "docker restart timi-pipeline"',
        'If specific agents are stuck, toggle them off and on in the Agents section',
      ],
    },
    error: {
      title: 'Agents Cannot Be Reached',
      description: 'Unable to check agent health. The dashboard can\'t see what your AI agents are doing right now.',
      reasons: [
        'The Docker container running the agents may be offline',
        'The agent heartbeat endpoint might be down',
        'There could be a network issue between services',
      ],
      fixes: [
        'Check if Docker is running (see Docker pill above)',
        'Open Docker Desktop and check if the timi-pipeline container is running',
        'If the container shows "exited", restart it from Docker Desktop',
      ],
    },
  },
  nextUpload: {
    warn: {
      title: 'Next Upload Due Soon',
      description: 'The daily scheduled upload is coming up within the next hour. Make sure the pipeline is ready or you can trigger a video manually.',
      reasons: [
        'The daily schedule runs at 11:45 AM Nepal time (06:00 UTC)',
        'You\'re within 1 hour of the next scheduled upload time',
        'No manual upload has been triggered today',
      ],
      fixes: [
        'Wait for the scheduled run at 11:45 AM NPT',
        'Or go ahead and trigger a video in "Run Pipeline" above',
        'No action needed — this is just a heads up!',
      ],
    },
  },
};

const OK_MESSAGES: Record<string, { title: string; description: string }> = {
  pipeline: {
    title: 'Pipeline — Idle',
    description: 'The pipeline is idle and waiting for the next scheduled daily run at 11:45 AM NPT, or you can trigger a video manually anytime from the "Run Pipeline" section.',
  },
  docker: {
    title: 'Docker — All Good',
    description: 'Docker is running your pipeline container in the background. This is the engine that powers all your AI agents. Everything is working normally.',
  },
  firebase: {
    title: 'Firebase — Connected',
    description: 'Firebase is your app\'s cloud database. It stores all your video data, agent status, and activity logs. Connection is healthy and responding well.',
  },
  storage: {
    title: 'Cloud Storage — All Set',
    description: 'Cloudflare R2 stores your video files in the cloud. There\'s plenty of space available and everything is syncing correctly.',
  },
    agents: {
      title: 'Agents — All Healthy',
      description: 'All AI agents are online and ready for work. They\'ll spring into action when the next video pipeline run starts.',
    },
  nextUpload: {
    title: 'Next Upload — On Schedule',
    description: 'The daily upload schedule is on track. The next automatic run is at 11:45 AM Nepal time (06:00 UTC) as planned.',
  },
};

const WORKING_MESSAGES: Record<string, { title: string; description: string }> = {
  pipeline: {
    title: 'Pipeline — Running',
    description: 'A video is being generated right now — agents are working through the pipeline steps from script to publishing.',
  },
};

async function fetchJson(url: string): Promise<any> {
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(8000) });
    if (!res.ok) return null;
    return res.json();
  } catch { return null; }
}

const pillIds = ['pipeline', 'docker', 'firebase', 'storage', 'agents', 'nextUpload'] as const;

const statusColor: Record<string, string> = {
  ok: 'bg-emerald-500',
  working: 'bg-purple-500',
  warn: 'bg-amber-400',
  error: 'bg-red-500',
  unknown: 'bg-gray-400',
    cloud: 'bg-emerald-500',
};

function SkeletonPill() {
  return (
    <div className="rounded-2xl p-3 min-w-[110px] bg-light-bg/60 dark:bg-dark-bg/40 border border-light-border/40 dark:border-dark-border/40 animate-pulse">
      <div className="flex items-center gap-2">
        <div className="w-3 h-3 rounded-full bg-light-border/60 dark:bg-dark-border/60" />
        <div className="flex-1 space-y-1.5">
          <div className="h-2.5 w-16 rounded bg-light-border/60 dark:bg-dark-border/60" />
          <div className="h-3 w-20 rounded bg-light-border/60 dark:bg-dark-border/60" />
        </div>
      </div>
    </div>
  );
}

function HelpPopover({ pillId, pills, onClose }: { pillId: string; pills: StatusPill[]; onClose: () => void }) {
  const pill = pills.find(p => p.id === pillId);
          const isOk = pill?.status === 'ok';
          const isWorking = pill?.status === 'working';
          const isCloud = pill?.status === 'cloud';
          const okContent = isOk && pill ? OK_MESSAGES[pill.id] : null;
          const workingContent = isWorking && pill ? WORKING_MESSAGES[pill.id] : null;
          const cloudContent = isCloud && pill ? STATUS_HELP[pill.id]?.cloud : null;
          const content = !isOk && !isWorking && !isCloud && pill ? STATUS_HELP[pill.id]?.[pill.status as 'warn' | 'error'] : null;
          if (!content && !okContent && !workingContent && !cloudContent) return null;
          const statusDotColor = pill ? statusColor[pill.status] : 'bg-gray-400';
          const statusLabel = pill?.status === 'error' ? 'Error' : pill?.status === 'warn' ? 'Notice' : '';
          const displayTitle = isOk ? okContent!.title : isWorking ? workingContent!.title : isCloud ? cloudContent!.title : content!.title;
          const displayDescription = isOk ? okContent!.description : isWorking ? workingContent!.description : isCloud ? cloudContent!.description : content!.description;
          const displayReasons = (isOk || isWorking || isCloud) ? null : content!.reasons;
          const displayFixes = (isOk || isWorking || isCloud) ? null : content!.fixes;
  return (
    <motion.div
      key="help-popover"
      initial={{ opacity: 0, scale: 0.95, y: -4 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: -4 }}
      data-help-popover
      className="fixed top-20 left-1/2 -translate-x-1/2 z-50 w-full max-w-lg mx-4"
    >
      <div className="rounded-2xl bg-white dark:bg-dark-card border border-light-border/60 dark:border-dark-border/60 shadow-2xl p-5 space-y-3 max-h-[70vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className={`w-3 h-3 rounded-full ${statusDotColor}`} />
            <h3 className="text-sm font-bold gradient-text">{displayTitle}</h3>
            {statusLabel && (
              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                pill?.status === 'error' ? 'bg-red-100 text-red-600' : 'bg-amber-100 text-amber-600'
              }`}>{statusLabel}</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-light-muted hover:text-light-text hover:bg-light-bg transition-colors"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <p className="text-xs text-light-text/80 dark:text-dark-text/80 leading-relaxed">
          {displayDescription}
        </p>

        {displayReasons && (
        <div>
          <p className="text-[11px] font-bold text-light-text/60 dark:text-dark-text/60 uppercase tracking-wider mb-1.5">
            Possible reasons
          </p>
          <ul className="space-y-1">
            {displayReasons.map((r, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-light-muted dark:text-dark-muted">
                <span className="text-light-primary mt-0.5 shrink-0">•</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
        )}

        {displayFixes && (
        <div>
          <p className="text-[11px] font-bold text-light-text/60 dark:text-dark-text/60 uppercase tracking-wider mb-1.5">
            How to fix
          </p>
          <ol className="space-y-1">
            {displayFixes.map((f, i) => (
              <li key={i} className="flex items-start gap-1.5 text-xs text-light-text/80 dark:text-dark-text/80">
                <span className="w-4 h-4 rounded-full bg-light-primary/10 text-light-primary text-[10px] font-bold flex items-center justify-center shrink-0 mt-0.5">
                  {i + 1}
                </span>
                <span>{f}</span>
              </li>
            ))}
          </ol>
        </div>
        )}
      </div>
    </motion.div>
  );
}

export function GlobalStatusBar() {
  const [pills, setPills] = useState<StatusPill[]>([
    { id: 'pipeline', status: 'unknown', value: '...', tooltip: 'Checking pipeline status...' },
    { id: 'docker', status: 'unknown', value: '...', tooltip: 'Checking Docker...' },
    { id: 'firebase', status: 'unknown', value: '...', tooltip: 'Checking Firebase...' },
    { id: 'storage', status: 'unknown', value: '...', tooltip: 'Checking storage...' },
    { id: 'agents', status: 'unknown', value: '...', tooltip: 'Checking agents...' },
    { id: 'nextUpload', status: 'unknown', value: '...', tooltip: 'Calculating next upload...' },
  ]);
  const [loaded, setLoaded] = useState(false);
  const [helpPill, setHelpPill] = useState<string | null>(null);

  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [agentsWorking, setAgentsWorking] = useState(0);

  useEffect(() => {
    const unsubPipe = onSnapshot(doc(db, 'system', 'pipeline'), (snap) => {
      if (snap.exists()) setPipelineRunning(snap.data().running || false);
    }, () => {});
    const unsubAgents = onSnapshot(collection(db, 'agent_status'), (snap) => {
      const now = Date.now();
      let count = 0;
      snap.docs.forEach(d => {
        const data = d.data();
        const date = data.last_updated?.toDate ? data.last_updated.toDate() : new Date(data.last_updated);
        const stale = (now - date.getTime()) > 5 * 60 * 1000;
        if (data.status === 'working' && !stale) count++;
      });
      setAgentsWorking(count);
    }, () => {});
    return () => { unsubPipe(); unsubAgents(); };
  }, []);

  const poll = useCallback(async () => {
    const [health, dockerData, fbData, storageData] = await Promise.all([
      fetchJson('/api/health'),
      fetchJson('/api/docker'),
      fetchJson('/api/firebase'),
      fetchJson('/api/storage'),
    ]);

    const newPills: StatusPill[] = [];

    if (pipelineRunning) {
      newPills.push({
        id: 'pipeline', status: 'working',
        value: 'Running',
        tooltip: 'A video is being generated right now — agents are working through the pipeline steps from script to publishing',
      });
    } else if (agentsWorking > 0) {
      newPills.push({
        id: 'pipeline', status: 'ok',
        value: `Idle — ${agentsWorking} active`,
        tooltip: `The pipeline is idle, but ${agentsWorking} agent${agentsWorking > 1 ? 's are' : ' is'} finishing up tasks from a recent run.`,
      });
    } else {
      newPills.push({
        id: 'pipeline', status: 'ok',
        value: 'Idle',
        tooltip: 'The pipeline is idle and waiting for the next scheduled daily run at 11:45 AM NPT, or you can trigger a video manually.',
      });
    }

    if (dockerData?.available && dockerData?.all_running) {
      newPills.push({
        id: 'docker', status: 'ok',
        value: `${dockerData.container_count} container${dockerData.container_count !== 1 ? 's' : ''}`,
        tooltip: 'Docker is running your pipeline container in the background. This is the engine that powers all your AI agents',
      });
    } else if (dockerData?.available) {
      newPills.push({
        id: 'docker', status: 'warn',
        value: `${dockerData.container_count} container${dockerData.container_count !== 1 ? 's' : ''} (partial)`,
        tooltip: 'Docker is running but some containers are not healthy — your pipeline may have issues',
      });
    } else if (dockerData?.reason === 'vercel_serverless') {
      newPills.push({
        id: 'docker', status: 'cloud',
        value: 'Cloud — local pipeline',
        tooltip: 'Docker is not available in this cloud environment (Vercel serverless). Pipeline runs on your local machine instead.',
      });
    } else {
      newPills.push({
        id: 'docker', status: 'error',
        value: 'Offline',
        tooltip: 'Docker is not running. Your AI agents need Docker to operate. Try starting Docker Desktop',
      });
    }

    if (fbData?.connected) {
      const lat = fbData.latency_ms;
      const status = lat < 500 ? 'ok' : lat < 1000 ? 'warn' : 'error';
      newPills.push({
        id: 'firebase', status,
        value: `${lat}ms`,
        tooltip: `Firebase is your app's database — it stores all video data, agent status, and activity logs. ${lat}ms response time from Nepal is normal`,
      });
    } else {
      newPills.push({
        id: 'firebase', status: 'error',
        value: 'Disconnected',
        tooltip: 'Cannot reach Firebase — your dashboard data won\'t load. Check your internet connection',
      });
    }

    if (storageData?.connected) {
      const freePct = storageData.free_percent;
      const status = freePct > 20 ? 'ok' : freePct > 10 ? 'warn' : 'error';
      newPills.push({
        id: 'storage', status,
        value: `${storageData.total_size_gb}GB / ${storageData.limit_gb}GB`,
        tooltip: `Cloudflare R2 stores your video files in the cloud. ${storageData.objects} videos saved, ${freePct}% space remaining`,
      });
    } else {
      const configured = storageData?.configured;
      newPills.push({
        id: 'storage', status: configured === false ? 'warn' : 'error',
        value: 'Not configured',
        tooltip: 'Cloudflare R2 is not yet connected. Videos are stored locally on your machine. Add R2 credentials to enable cloud storage',
      });
    }

    if (health?.checks?.agent_heartbeat) {
      const hb = health.checks.agent_heartbeat;
      const status = hb.status === 'ok' ? 'ok' : hb.status === 'stale' ? 'warn' : 'error';
      newPills.push({
        id: 'agents', status,
        value: status === 'ok' ? `${agentsWorking > 0 ? `${agentsWorking} working` : 'All healthy'}` : hb.detail || 'Unknown',
        tooltip: hb.status === 'ok'
          ? `All ${agentsWorking > 0 ? `${agentsWorking} agents are actively working` : 'agents are online and healthy'}`
          : 'Some agents haven\'t reported in recently. They may be busy or there could be a connection issue',
      });
    } else {
      newPills.push({
        id: 'agents', status: 'unknown',
        value: 'Unknown',
        tooltip: 'Unable to check agent health',
      });
    }

    const next = getNextUploadDisplay();
    const nextStatus = next.hours < 1 ? 'warn' : 'ok';
    newPills.push({
      id: 'nextUpload', status: nextStatus,
      value: pipelineRunning ? 'Pending' : `${next.nptTime} NPT`,
      tooltip: pipelineRunning
        ? 'A video is currently being generated — the upload will happen once it\'s ready'
        : `The daily schedule runs every morning at 11:45 AM Nepal time (06:00 UTC). Next upload is in ${next.hours}h ${next.minutes}m`,
    });

    setPills(newPills);
    if (!loaded) setLoaded(true);
  }, [pipelineRunning, agentsWorking, loaded]);

  useEffect(() => {
    poll();
    const interval = setInterval(poll, 30000);
    return () => clearInterval(interval);
  }, [poll]);

  useEffect(() => {
    if (!helpPill) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('[data-help-popover]') && !target.closest('[data-help-trigger]')) {
        setHelpPill(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [helpPill]);

  const criticalPills = pills.filter(p => p.status === 'error' || p.status === 'warn');

  return (
    <>
      {/* Desktop — pill cards */}
      <div className="hidden md:flex items-stretch gap-2 flex-wrap">
        {!loaded ? (
          <>
            {pillIds.map(id => <SkeletonPill key={id} />)}
          </>
        ) : (
          <>
            {pills.map((pill, i) => {
              const helpContent = STATUS_HELP[pill.id]?.[pill.status as 'warn' | 'error' | 'cloud'];
              const needsHelp = !!helpContent;
              const isClickable = pill.status !== 'unknown';
              return (
                <motion.div
                  key={pill.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.06, duration: 0.25 }}
                  data-help-trigger
                  onClick={isClickable ? () => setHelpPill(helpPill === pill.id ? null : pill.id) : undefined}
                  className={`rounded-2xl p-3 min-w-[110px] glass-warm glow-red hover:-translate-y-0.5 transition-all duration-200 shrink-0 group relative ${
                    isClickable ? 'cursor-pointer' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-3 h-3 rounded-full ${statusColor[pill.status]} shrink-0 ${
                      pill.status === 'ok' || pill.status === 'cloud' ? '' : 'animate-pulse'
                    }`} />
                    <div className="min-w-0">
                      <p className="gradient-text text-[10px] font-bold">
                        {pill.id === 'nextUpload' ? 'Next Upload' : pill.id.charAt(0).toUpperCase() + pill.id.slice(1)}
                      </p>
                      <p className="text-sm font-bold text-light-text/90 dark:text-dark-text truncate max-w-[150px]">
                        {pill.value}
                      </p>
                    </div>
                    {needsHelp && (
                      <span className="shrink-0 w-4 h-4 rounded-full bg-light-primary/10 flex items-center justify-center">
                        <svg className="w-2.5 h-2.5 text-light-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </span>
                    )}
                  </div>
                  {isClickable && (
                    <p className="text-[9px] text-light-primary/70 dark:text-light-primary/60 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      {pill.status === 'ok' ? 'Click for status update' : 'Click for details'}
                    </p>
                  )}
                </motion.div>
              );
            })}
          </>
        )}
      </div>

      {/* Mobile — compact dot row */}
      <div className="md:hidden flex items-center gap-1.5 px-2 py-1.5">
        {pills.map((pill) => (
          <div key={pill.id} className="group relative" title={pill.tooltip}>
            <span className={`block w-2 h-2 rounded-full ${statusColor[pill.status]} ${
              pill.status === 'ok' ? '' : 'animate-pulse'
            }`} />
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 px-2 py-1 rounded-lg bg-dark-bg text-dark-text text-[10px] whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-lg">
              {pill.id}: {pill.value}
            </div>
          </div>
        ))}
        {criticalPills.length > 0 && (
          <span className="text-[10px] text-light-muted dark:text-dark-muted ml-1 font-medium">
            {criticalPills.length} issue{criticalPills.length > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Help popover */}
      <AnimatePresence>
        {helpPill && (
          <HelpPopover
            pillId={helpPill}
            pills={pills}
            onClose={() => setHelpPill(null)}
          />
        )}
      </AnimatePresence>
    </>
  );
}
