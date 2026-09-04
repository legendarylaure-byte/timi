'use client';

import { useEffect, useState } from 'react';
import { collection, doc, onSnapshot, Timestamp } from 'firebase/firestore';
import { db } from '@/lib/firebase';
import { Card } from '@/components/ui/Card';
import { Clapperboard } from 'lucide-react';
import { AGENT_ROLES } from '@/lib/constants';
import { LivePayload } from '@/lib/monitor';

interface AgentRow {
  agent_id: string;
  name: string;
  status: string;
  current_action: string;
  enabled: boolean;
  last_updated: Timestamp;
}

function roleFor(id: string) {
  const r = AGENT_ROLES.find((a) => a.id === id);
  return r || { name: id, emoji: '🤖', color: '#888' };
}

function statusColor(status: string): string {
  if (status === 'working') return '#10B981';
  if (status === 'completed') return '#0EA5E9';
  if (status === 'error') return '#EF4444';
  return '#9CA3AF';
}

export function LivePipeline({ live }: { live: LivePayload | null }) {
  const [agents, setAgents] = useState<Map<string, AgentRow>>(new Map());
  const nextRun = '8:50 PM NPT';

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'agent_status'), (snap) => {
      const map = new Map<string, AgentRow>();
      snap.docs.forEach((d) => {
        const data = d.data() as AgentRow;
        map.set(data.agent_id, data);
      });
      setAgents(map);
    }, () => {});
    return () => unsub();
  }, []);

  const row = (agentId: string): AgentRow | undefined => agents.get(agentId);

  return (
    <Card icon={Clapperboard} iconColor="text-light-primary dark:text-dark-primary" className="h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-bold text-light-text dark:text-dark-text">Production Crew</h3>
        <span className={`text-xs font-medium ${live?.running ? 'text-emerald-500' : 'text-light-muted dark:text-dark-muted'}`}>
          {live?.running ? '● Working' : `Idle — next ${nextRun}`}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {AGENT_ROLES.map((role) => {
          const a = row(role.id);
          const status = a?.status || 'idle';
          const color = statusColor(status);
          const action = a?.current_action || (status === 'idle' ? 'Ready' : '');
          return (
            <div
              key={role.id}
              className="rounded-xl border p-2.5 transition-all"
              style={{ borderColor: status === 'working' ? `${color}55` : undefined, backgroundColor: status === 'working' ? `${color}0d` : undefined }}
            >
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{role.emoji}</span>
                <span className="text-xs font-medium text-light-text dark:text-dark-text truncate">{role.name}</span>
                <span className="ml-auto w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
              </div>
              <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1 truncate">{action || 'Ready'}</p>
            </div>
          );
        })}
      </div>
      {live?.current_video && (
        <div className="mt-4 pt-3 border-t border-light-border/40 dark:border-dark-border/40 text-xs text-light-muted dark:text-dark-muted">
          Working on: <span className="font-medium text-light-text dark:text-dark-text">“{live.current_video}”</span>
        </div>
      )}
    </Card>
  );
}