'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, updateDoc } from 'firebase/firestore';
import { AGENT_ROLES } from '@/lib/constants';
import { useToast } from '@/components/ui/Toast';
import Image from 'next/image';

function getContrastTextColor(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.5 ? '#1a1a1a' : '#ffffff';
}

interface WorkspaceAgent {
  id: string;
  name: string;
  emoji: string;
  color: string;
  status: string;
  currentAction: string;
  enabled: boolean;
  lastUpdated: any;
}

export default function WorkspacePage() {
  const [agents, setAgents] = useState<WorkspaceAgent[]>([]);
  const { addToast } = useToast();

  useEffect(() => {
    const q = collection(db, 'agent_status');
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const liveData: Record<string, Partial<WorkspaceAgent>> = {};
      snapshot.docs.forEach((d) => {
        liveData[d.id] = d.data() as Partial<WorkspaceAgent>;
      });

      const merged = AGENT_ROLES.map((role) => {
        const live = liveData[role.id] || {};
        return {
          id: role.id,
          name: role.name,
          emoji: role.emoji,
          color: role.color,
          status: (live.status as string) || 'idle',
          currentAction: (live.current_action as string) || 'Waiting for next task',
          enabled: live.enabled !== false,
          lastUpdated: live.last_updated,
        };
      });
      setAgents(merged);
    });
    return () => unsubscribe();
  }, []);

  const toggleAgent = useCallback(async (agentId: string, currentEnabled: boolean) => {
    try {
      const docRef = doc(db, 'agent_status', agentId);
      await updateDoc(docRef, { enabled: !currentEnabled });
      addToast(
        `${AGENT_ROLES.find((a) => a.id === agentId)?.name || agentId} ${!currentEnabled ? 'resumed' : 'paused'}`,
        !currentEnabled ? 'success' : 'info'
      );
    } catch {
      addToast('Failed to update agent status', 'error');
    }
  }, [addToast]);

  const statusColors: Record<string, string> = {
    working: 'text-emerald-400 bg-emerald-400/10',
    idle: 'text-gray-400 bg-gray-400/10',
    completed: 'text-blue-400 bg-blue-400/10',
    error: 'text-red-400 bg-red-400/10',
  };

  const activeCount = agents.filter((a) => a.status === 'working').length;
  const idleCount = agents.filter((a) => a.status === 'idle' || a.status === 'completed').length;

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-light-text dark:text-white">Agent Workspace</h1>
            <p className="text-light-muted dark:text-gray-400">
              {activeCount} active &middot; {idleCount} standby
            </p>
          </div>
        </div>
      </motion.div>

      <div className="relative h-64 rounded-2xl overflow-hidden border border-light-border/50 dark:border-white/10" style={{ background: 'linear-gradient(135deg, rgba(255,107,107,0.05), rgba(78,205,196,0.05), rgba(255,217,61,0.05))' }}>
        <div className="absolute inset-0 flex items-center justify-center gap-8 flex-wrap p-6">
          {agents.map((agent, i) => (
            <motion.div
              key={agent.id}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: i * 0.08 }}
              className="flex flex-col items-center gap-2"
            >
              <div className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold relative" style={{ backgroundColor: agent.color, color: getContrastTextColor(agent.color) }}>
                {agent.name.charAt(0)}
                {agent.status === 'working' && (
                  <div className="absolute -top-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full animate-pulse border-2 border-white dark:border-gray-800" />
                )}
              </div>
              <span className="text-xs text-light-text/70 dark:text-gray-300 font-medium text-center max-w-20 truncate">{agent.name}</span>
            </motion.div>
          ))}
        </div>
        <div className="absolute inset-0 overflow-hidden -z-10">
          <div className="absolute top-4 left-10 w-40 h-40 rounded-full opacity-10 animate-pulse" style={{ background: 'radial-gradient(circle, #FF6B6B, transparent)' }} />
          <div className="absolute bottom-4 right-16 w-48 h-48 rounded-full opacity-10 animate-pulse" style={{ background: 'radial-gradient(circle, #4ECDC4, transparent)', animationDelay: '1s' }} />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {agents.map((agent, i) => (
          <motion.div
            key={agent.id}
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            className="rounded-2xl p-5 glass-strong border border-light-border/50 dark:border-white/10 hover:shadow-lg hover:-translate-y-1 transition-all duration-300"
          >
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center font-bold shrink-0" style={{ backgroundColor: agent.color, color: getContrastTextColor(agent.color) }}>
                {agent.name.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-light-text dark:text-white text-sm truncate">{agent.name}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[agent.status] || statusColors.idle}`}>
                  {agent.status.charAt(0).toUpperCase() + agent.status.slice(1)}
                </span>
              </div>
            </div>
            <p className="text-xs text-light-muted dark:text-gray-400 mb-4 line-clamp-2">{agent.currentAction}</p>
            <div className="flex items-center justify-between pt-3 border-t border-light-border/30 dark:border-white/5">
              <span className="text-[10px] text-light-muted dark:text-gray-500">
                {agent.enabled ? 'Enabled' : 'Paused'}
              </span>
              <button
                onClick={() => toggleAgent(agent.id, agent.enabled)}
                className={`shrink-0 w-10 h-6 rounded-full transition-all duration-200 ${
                  agent.enabled
                    ? 'bg-light-success'
                    : 'bg-light-muted dark:bg-dark-muted'
                }`}
              >
                <motion.div
                  className="w-5 h-5 rounded-full bg-white shadow-sm"
                  animate={{ x: agent.enabled ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              </button>
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
