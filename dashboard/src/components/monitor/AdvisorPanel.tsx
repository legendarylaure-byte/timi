'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/Card';
import { Sparkles, Copy, Terminal, RotateCcw } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';
import { ReviewPayload } from '@/lib/monitor';

async function copy(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }
}

export function AdvisorPanel({ review }: { review: ReviewPayload | null }) {
  const [command, setCommand] = useState('python -m agents.scripts.advisor');
  const [notes, setNotes] = useState('');
  const [context, setContext] = useState('');
  const { addToast } = useToast();

  useEffect(() => {
    if (!review) return;
    const subs = review.channel.subscribers ?? 0;
    const shorts = review.videos.filter((v) => v.format === 'shorts').length;
    const longs = review.videos.filter((v) => v.format === 'long').length;
    setContext(
      `Subscribers: ${subs} | Total views: ${review.channel.total_views} | Watch hours: ${Math.round(review.channel.total_watch_hours)} | Recent videos: ${shorts} shorts / ${longs} longs | Pipeline success: ${review.pipeline.success_rate}% (${review.pipeline.total_runs} runs)`
    );
  }, [review]);

  const buildCommand = () => {
    let cmd = 'python -m agents.scripts.advisor';
    if (notes.trim()) cmd += ` --manual-analysis "${notes.trim()}"`;
    setCommand(cmd);
    return cmd;
  };

  const runAndCopy = async () => {
    const cmd = buildCommand();
    await copy(cmd);
    addToast('Copied command — paste it into your Mac terminal', 'success');
  };

  const copyContext = async () => {
    const text = `context=${context}`;
    await copy(text);
    addToast('Kept context — will be appended to the prompt output.', 'success');
  };

  return (
    <Card icon={Sparkles} iconColor="text-light-primary dark:text-dark-primary">
      <div className="flex items-center justify-between mb-1">
        <h3 className="text-sm font-bold gradient-text">AI Improvement Advisor</h3>
        <span className="text-[10px] uppercase tracking-widest text-light-muted dark:text-dark-muted bg-light-bg/60 dark:bg-dark-bg/60 rounded-full px-2 py-1">local model · no cloud AI</span>
      </div>
      <p className="text-[11px] text-light-muted dark:text-dark-muted mb-4 leading-relaxed">
        This reads your latest performance and writes a <strong className="text-light-text dark:text-dark-text">ready-to-paste improvement prompt</strong> for your coding assistant. Run it on this Mac (the AI stays 100% local).
      </p>

      <div className="rounded-xl border border-light-border/40 dark:border-dark-border/40 p-3 mb-3">
        <div className="flex items-center gap-2 mb-2">
          <Terminal className="w-4 h-4 text-light-muted dark:text-dark-muted shrink-0" />
          <span className="text-[11px] font-bold text-light-text dark:text-dark-text">Advice on current performance</span>
        </div>
        <p className="text-[10px] text-light-muted/70 dark:text-dark-muted/70 mb-2">{context || 'Loading your stats…'}</p>
        <code className="block bg-light-bg/70 dark:bg-dark-bg/70 border border-light-border/40 dark:border-dark-border/40 rounded-lg px-3 py-2 text-xs font-mono text-light-text dark:text-dark-text break-all">
          {command}
        </code>
      </div>

      <div className="mb-3">
        <p className="text-[10px] font-bold text-light-muted dark:text-dark-muted mb-1.5">Add your own note (optional)</p>
        <input
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="e.g. Need to boost shorts, ignore long-form this week…"
          className="w-full text-sm rounded-xl border border-light-border/40 dark:border-dark-border/40 bg-light-bg/40 dark:bg-dark-bg/40 px-3 py-2 text-light-text dark:text-dark-text placeholder:text-light-muted/50 focus:outline-none focus:ring-2 focus:ring-light-primary/40"
        />
      </div>

      <div className="flex flex-wrap gap-2">
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={runAndCopy}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-medium text-white bg-gradient-to-r from-light-primary to-light-secondary hover:opacity-90 transition-opacity"
        >
          <Sparkles className="w-4 h-4" /> Generate &amp; copy command
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={copyContext}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium border border-light-border/40 dark:border-dark-border/40 text-light-text dark:text-dark-text hover:bg-light-bg/40 dark:hover:bg-dark-bg/40 transition-colors"
        >
          <Copy className="w-4 h-4" /> Copy context
        </motion.button>
        <motion.button
          whileTap={{ scale: 0.97 }}
          onClick={() => { setNotes(''); buildCommand(); }}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text transition-colors"
        >
          <RotateCcw className="w-4 h-4" /> Reset
        </motion.button>
      </div>
    </Card>
  );
}