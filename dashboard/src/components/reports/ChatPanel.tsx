'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, Send, Loader2, Sparkles, ExternalLink, Trash2, RefreshCw } from 'lucide-react';
import { auth } from '@/lib/firebase';

interface ChatAction {
  label: string;
  type: 'link' | 'trigger';
  target: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  actions?: ChatAction[];
  timestamp: string;
}

function generateId() {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function formatTime(iso: string) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function MessageContent({ content }: { content: string }) {
  const parts = content.split(/(\*\*.*?\*\*)/g);
  return (
    <div className="text-sm text-light-text dark:text-dark-text leading-relaxed">
      {parts.map((part, i) => {
        if (part.startsWith('**') && part.endsWith('**')) {
          return <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>;
        }
        const lines = part.split('\n');
        return lines.map((line, j) => {
          if (line.startsWith('- ')) {
            return <div key={`${i}-${j}`} className="ml-3 text-light-muted">• {line.slice(2)}</div>;
          }
          if (/^\d+\.\s/.test(line)) {
            return <div key={`${i}-${j}`} className="ml-3 text-light-muted">{line}</div>;
          }
          return <span key={`${i}-${j}`}>{line}{j < lines.length - 1 ? <br /> : ''}</span>;
        });
      })}
    </div>
  );
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [showWelcome, setShowWelcome] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    setShowWelcome(false);
    setError(null);

    const userMsg: Message = {
      id: generateId(),
      role: 'user',
      content: text.trim(),
      timestamp: new Date().toISOString(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const user = auth.currentUser;
      if (!user) throw new Error('Not authenticated');
      const token = await user.getIdToken();

      const res = await fetch('/api/reports/chat', {
        method: 'POST',
        headers: {
          authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text.trim(),
          sessionId: sessionId || undefined,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      if (data.sessionId) setSessionId(data.sessionId);

      const assistantMsg: Message = {
        id: generateId(),
        role: 'assistant',
        content: data.message || 'No response',
        actions: data.actions || [],
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e: any) {
      setError(e.message);
      setMessages(prev => [...prev, {
        id: generateId(),
        role: 'assistant',
        content: `Sorry, I encountered an error: ${e.message}. Please try again.`,
        timestamp: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleAction = (action: ChatAction) => {
    if (action.type === 'link') {
      window.location.href = action.target;
    }
  };

  const clearChat = () => {
    setMessages([]);
    setSessionId(null);
    setShowWelcome(true);
    setError(null);
  };

  const quickActions = [
    'How are my videos performing?',
    'What can I improve?',
    'Any pipeline errors?',
    'Which category performs best?',
  ];

  return (
    <div className="glass rounded-xl overflow-hidden flex flex-col" style={{ height: 'calc(100vh - 220px)' }}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-light-border/50 dark:border-dark-border/50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-light-primary to-purple-500 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">Vyom AI</h3>
            <p className="text-[10px] text-light-muted">Content Strategy Analyst</p>
          </div>
        </div>
        <button onClick={clearChat} className="p-1.5 rounded-lg hover:bg-light-border/50 text-light-muted hover:text-light-text transition-all"
          title="Clear conversation">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showWelcome && messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="text-center py-8"
          >
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-light-primary/20 to-purple-500/20 flex items-center justify-center mx-auto mb-4">
              <Sparkles className="w-8 h-8 text-light-primary" />
            </div>
            <h3 className="text-lg font-bold text-light-text dark:text-dark-text mb-2">
              Welcome to Vyom AI
            </h3>
            <p className="text-sm text-light-muted max-w-md mx-auto mb-6">
              Your AI content strategist. Ask me anything about your channel performance, pipeline health, or growth strategy.
            </p>
            <div className="flex flex-wrap justify-center gap-2">
              {quickActions.map((action) => (
                <button
                  key={action}
                  onClick={() => sendMessage(action)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-light-border/30 dark:bg-dark-border/30 text-light-muted hover:text-light-text hover:bg-light-border/50 transition-all"
                >
                  {action}
                </button>
              ))}
            </div>
          </motion.div>
        )}

        <AnimatePresence>
          {messages.map((msg) => (
            <motion.div
              key={msg.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-light-primary/20 to-purple-500/20 flex items-center justify-center shrink-0 mt-1">
                  <Bot className="w-4 h-4 text-light-primary" />
                </div>
              )}
              <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : ''}`}>
                <div className={`rounded-xl p-3 ${
                  msg.role === 'user'
                    ? 'bg-light-primary text-white'
                    : 'bg-light-border/30 dark:bg-dark-border/30'
                }`}>
                  <MessageContent content={msg.content} />
                  {msg.actions && msg.actions.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3 pt-2 border-t border-light-border/30">
                      {msg.actions.map((action, i) => (
                        <button
                          key={i}
                          onClick={() => handleAction(action)}
                          className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-light-primary/10 text-light-primary hover:bg-light-primary/20 transition-all"
                        >
                          <ExternalLink className="w-3 h-3" />
                          {action.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className={`text-[10px] text-light-muted/50 mt-1 ${msg.role === 'user' ? 'text-right' : ''}`}>
                  {formatTime(msg.timestamp)}
                </div>
              </div>
              {msg.role === 'user' && (
                <div className="w-8 h-8 rounded-lg bg-blue-500/20 flex items-center justify-center shrink-0 mt-1">
                  <span className="text-sm text-blue-400 font-medium">
                    {(auth.currentUser?.displayName?.[0] || 'U').toUpperCase()}
                  </span>
                </div>
              )}
            </motion.div>
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex gap-3"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-light-primary/20 to-purple-500/20 flex items-center justify-center shrink-0 mt-1">
              <Bot className="w-4 h-4 text-light-primary" />
            </div>
            <div className="rounded-xl p-3 bg-light-border/30 dark:bg-dark-border/30">
              <Loader2 className="w-4 h-4 animate-spin text-light-muted" />
            </div>
          </motion.div>
        )}

        {error && (
          <div className="text-center py-2">
            <span className="text-xs text-red-400">{error}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 border-t border-light-border/50 dark:border-dark-border/50">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && sendMessage(input)}
            placeholder="Ask about your content performance..."
            className="flex-1 px-4 py-2.5 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-dark-border text-sm text-light-text dark:text-dark-text placeholder:text-light-muted/50 focus:outline-none focus:border-light-primary/50 transition-all"
            disabled={loading}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="p-2.5 rounded-xl bg-light-primary text-white hover:bg-light-primary/90 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-light-muted/50 text-center mt-1">
          Vyom AI analyzes your data and provides recommendations. Enable GEMINI_API_KEY for AI-powered responses.
        </p>
      </div>
    </div>
  );
}
