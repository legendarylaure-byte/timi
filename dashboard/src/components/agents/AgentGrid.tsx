'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, query, orderBy, limit, Timestamp, where, getDocs, doc } from 'firebase/firestore';
import { AgentCard } from './AgentCard';
import { IdleAgentExplainer } from './IdleAgentExplainer';

interface AgentStatus {
  agent_id: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: Timestamp;
  error_message?: string;
}

interface ActivityEntry {
  timestamp: Timestamp;
  level: string;
}

const IDLE_AGENT_INFO: Record<string, string> = {
  scriptwriter: 'Writes the script for each video — plans what the narrator will say and how each scene flows. Works with topics from the daily content plan.',
  storyboard: 'Plans what viewers will see on screen for each scene — creates a visual storyboard that guides the animation and visuals.',
  voice: 'Records the narration using AI voices so your videos have professional-sounding audio. Supports multiple languages.',
  composer: 'Creates custom background music that matches the mood of each scene — from energetic tech explainers to calm tutorials.',
  animator: 'Gathers all the visuals — stock footage, screen recordings, diagrams, and code snippets — and matches them to each scene.',
  editor: 'Stitches voice, music, and visuals together into the final video using smooth transitions and professional compositing.',
  thumbnail: 'Designs the clickable cover image that makes people want to watch your video on YouTube and other platforms.',
  metadata: 'Writes the title, description, and tags so search engines and viewers can find your video easily.',
  publisher: 'Uploads your finished video to YouTube, TikTok, Instagram, and Facebook with the right settings for each platform.',
  quality_scorer: 'Reads the script and predicts how much viewers will enjoy it before the team invests time making the full video.',
  trend_discovery: 'Scans YouTube and the internet to find what tech topics are popular right now — helps pick the best subjects for new videos.',
  repurposer: 'Splits long videos into short clips so you can share highlights across multiple platforms with less effort.',
  scheduler: 'Plans the daily content schedule — decides which videos to make each day and when to publish them for the best audience reach.',
};

async function fetchActivityForAgent(agentId: string): Promise<ActivityEntry[]> {
  try {
    const q = query(
      collection(db, 'activity_logs'),
      where('agent_id', '==', agentId),
      orderBy('timestamp', 'desc'),
      limit(5),
    );
    const snap = await getDocs(q);
    return snap.docs.map(d => ({
      timestamp: d.data().timestamp as Timestamp,
      level: d.data().level || 'info',
    }));
  } catch {
    return [];
  }
}

export function AgentGrid() {
  const [agentStatuses, setAgentStatuses] = useState<Map<string, AgentStatus>>(new Map());
  const [activities, setActivities] = useState<Map<string, ActivityEntry[]>>(new Map());
  const [idleInfoAgent, setIdleInfoAgent] = useState<string | null>(null);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'system', 'pipeline'), () => {}, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'agent_status'), (snap) => {
      const now = Date.now();
      const map = new Map<string, AgentStatus>();
      snap.docs.forEach(doc => {
        const data = doc.data() as AgentStatus;
        if (data.status === 'working' && data.last_updated) {
          const date = data.last_updated.toDate ? data.last_updated.toDate() : new Date(data.last_updated as any);
          if ((now - date.getTime()) > 5 * 60 * 1000) {
            map.set(doc.id, { ...data, status: 'idle', current_action: 'Ready' });
            return;
          }
        }
        map.set(doc.id, data);
      });
      setAgentStatuses(map);
    }, () => {});
    return () => unsub();
  }, []);

  useEffect(() => {
    if (agentStatuses.size === 0) return;
    const agentIds = Array.from(agentStatuses.keys());
    Promise.all(agentIds.map(id => fetchActivityForAgent(id))).then(results => {
      const actMap = new Map<string, ActivityEntry[]>();
      agentIds.forEach((id, i) => {
        actMap.set(id, results[i]);
      });
      setActivities(actMap);
    });
  }, [agentStatuses]);

  const handleToggle = useCallback(async (agentId: string, currentEnabled: boolean) => {
    try {
      const res = await fetch(`/api/agents/${agentId}/toggle`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !currentEnabled }),
      });
      if (!res.ok) {
        const err = await res.json();
        console.error('Toggle failed:', err.error);
      }
    } catch (err) {
      console.error('Failed to toggle agent:', err);
    }
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text" title="Each AI agent handles one step of video creation — from writing scripts to publishing. Toggle agents on/off or click ? to learn what each one does">
          Agents
        </h2>
        <span className="text-xs text-light-muted dark:text-dark-muted">
          {agentStatuses.size} agents ·{' '}
          {Array.from(agentStatuses.values()).filter(s => s.status === 'working').length} working
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {Array.from(agentStatuses.entries()).map(([agentId, status]) => (
          <AgentCard
            key={agentId}
            agentId={agentId}
            status={status}
            recentActivity={activities.get(agentId) || []}
            onToggle={handleToggle}
            onShowIdleInfo={setIdleInfoAgent}
          />
        ))}
      </div>

      <AnimatePresence>
        {idleInfoAgent && (
          <IdleAgentExplainer
            key="explainer"
            agentId={idleInfoAgent}
            idleInfo={IDLE_AGENT_INFO[idleInfoAgent] || 'This agent monitors for new work periodically.'}
            onClose={() => setIdleInfoAgent(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
