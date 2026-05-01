'use client';

import { motion } from 'framer-motion';
import { AGENT_STATUS } from '@/lib/constants';

interface AgentStatusProps {
  name: string;
  color: string;
  status: string;
  task?: string;
}

export function AgentStatus({ name, color, status, task }: AgentStatusProps) {
  const statusColors: Record<string, string> = {
    [AGENT_STATUS.WORKING]: 'bg-green-500',
    [AGENT_STATUS.IDLE]: 'bg-gray-400',
    [AGENT_STATUS.COMPLETED]: 'bg-blue-500',
    [AGENT_STATUS.ERROR]: 'bg-red-500',
  };

  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-center gap-3 p-3 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50"
    >
      <div className={`w-3 h-3 rounded-full ${statusColors[status]} ${status === AGENT_STATUS.WORKING ? 'animate-pulse' : ''}`} />
      <div className="w-1 h-8 rounded-full" style={{ backgroundColor: color }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-light-text dark:text-dark-text truncate">{name}</p>
        {task && <p className="text-xs text-light-muted dark:text-dark-muted truncate">{task}</p>}
      </div>
      <span className="text-xs capitalize text-light-muted dark:text-dark-muted">{status}</span>
    </motion.div>
  );
}
