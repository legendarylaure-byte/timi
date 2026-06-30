'use client';

import { motion } from 'framer-motion';
import { AGENT_ROLES } from '@/lib/constants';

interface IdleAgentExplainerProps {
  agentId: string;
  idleInfo: string;
  onClose: () => void;
}

export function IdleAgentExplainer({ agentId, idleInfo, onClose }: IdleAgentExplainerProps) {
  const agent = AGENT_ROLES.find(a => a.id === agentId);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="fixed bottom-6 right-6 max-w-sm z-50 p-4 rounded-2xl border border-light-border/60 dark:border-dark-border/60 bg-light-card dark:bg-dark-card shadow-2xl"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl mt-0.5">{agent?.emoji || '🤖'}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <h4 className="text-sm font-bold text-light-text dark:text-dark-text">
              {agent?.name || agentId}
            </h4>
            <button
              onClick={onClose}
              className="w-5 h-5 rounded-md flex items-center justify-center text-light-muted hover:text-light-text transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p className="text-xs text-light-muted dark:text-dark-muted mt-2 leading-relaxed">
            {idleInfo}
          </p>
          <p className="text-[10px] text-light-muted/60 dark:text-dark-muted/60 mt-2 italic">
            Each agent handles one step of video creation. They activate automatically when new work is ready for them.
          </p>
        </div>
      </div>
    </motion.div>
  );
}
