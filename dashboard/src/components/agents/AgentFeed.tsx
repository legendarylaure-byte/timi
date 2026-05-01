'use client';

import { motion } from 'framer-motion';
import { HUMAN_READABLE_ACTIONS, AGENT_STATUS } from '@/lib/constants';

interface LogEntry {
  agent: string;
  action: string;
  time: string;
  status: string;
}

interface AgentFeedProps {
  logs: LogEntry[];
}

export function AgentFeed({ logs }: AgentFeedProps) {
  return (
    <div className="space-y-2 max-h-64 overflow-y-auto">
      {logs.map((log, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: i * 0.03 }}
          className="flex items-start gap-3 p-3 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50"
        >
          <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
            log.status === AGENT_STATUS.WORKING ? 'bg-green-500 animate-pulse' :
            log.status === AGENT_STATUS.COMPLETED ? 'bg-blue-500' : 'bg-gray-400'
          }`} />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-light-text dark:text-dark-text">
              <span className="font-medium">{log.agent}</span>{' '}
              {log.action}
            </p>
            <p className="text-xs text-light-muted dark:text-dark-muted">{log.time}</p>
          </div>
        </motion.div>
      ))}
    </div>
  );
}
