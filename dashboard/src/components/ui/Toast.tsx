'use client';

import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface Toast {
  id: string;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  addToast: (message: string, type: Toast['type'], duration?: number) => void;
  removeToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

const typeStyles: Record<string, { bg: string; border: string; icon: string }> = {
  success: { bg: 'bg-light-success/10 dark:bg-dark-success/10', border: 'border-light-success/30 dark:border-dark-success/30', icon: '✓' },
  error: { bg: 'bg-light-primary/10 dark:bg-dark-primary/10', border: 'border-light-primary/30 dark:border-dark-primary/30', icon: '✕' },
  info: { bg: 'bg-light-info/10 dark:bg-dark-info/10', border: 'border-light-info/30 dark:border-dark-info/30', icon: 'i' },
  warning: { bg: 'bg-light-warning/10 dark:bg-dark-warning/10', border: 'border-light-warning/30 dark:border-dark-warning/30', icon: '!' },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((message: string, type: Toast['type'], duration = 4000) => {
    const id = Math.random().toString(36).substring(7);
    setToasts((prev) => [...prev, { id, message, type, duration }]);
    if (duration > 0) {
      setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), duration);
    }
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toasts, addToast, removeToast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 40, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 40, scale: 0.9 }}
              className={`pointer-events-auto flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-xl ${typeStyles[toast.type].bg} ${typeStyles[toast.type].border}`}
            >
              <span className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${typeStyles[toast.type].bg} ${typeStyles[toast.type].border.replace('border-', 'text-')}`}>
                {typeStyles[toast.type].icon}
              </span>
              <p className="text-sm font-medium text-light-text dark:text-dark-text max-w-[280px]">{toast.message}</p>
              <button
                onClick={() => removeToast(toast.id)}
                className="ml-2 text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text transition-colors"
              >
                ×
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast must be used within ToastProvider');
  return context;
}
