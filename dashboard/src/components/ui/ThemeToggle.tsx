'use client';

import { useState, useEffect } from 'react';
import { toggleTheme, ThemeMode, initTheme } from '@/lib/theme';

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeMode>('light');

  useEffect(() => {
    setTheme(initTheme());
  }, []);

  const handleToggle = () => {
    const next = toggleTheme();
    setTheme(next);
  };

  return (
    <button
      onClick={handleToggle}
      className="w-10 h-10 rounded-xl flex items-center justify-center shadow-sm hover:shadow-md transition-all text-lg border border-light-border/50 dark:border-white/10 bg-light-card dark:bg-dark-card"
      aria-label="Toggle theme"
    >
      {theme === 'light' ? '🌙' : '☀️'}
    </button>
  );
}
