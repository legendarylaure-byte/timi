'use client';

import { useEffect } from 'react';
import { MotionConfig } from 'framer-motion';
import { initTheme, applyTheme, THEME_STORAGE_KEY } from '@/lib/theme';
import type { ThemeMode } from '@/lib/brand';

/**
 * F5 prerequisite: the reduced-motion net.
 *
 * 51 files animate with framer-motion. `globals.css` has a
 * `@media (prefers-reduced-motion: reduce)` block, but that only covers CSS
 * animation -- it cannot touch a JS-driven `animate={{ opacity: [0, 1] }}`. So
 * the app had a reduced-motion stylesheet that did nothing for most of its
 * motion, and `useReducedMotion` / `MotionConfig` appeared nowhere in the
 * codebase.
 *
 * `reducedMotion="user"` is the whole fix and it is one wrapper: framer-motion
 * collapses transform/opacity animations to their end state and skips layout
 * animations whenever the OS asks for reduced motion. It applies to all 51
 * files at once, which is why it goes in rather than 51 per-component guards.
 *
 * Theme ownership moves here too. The root provider is the natural place to
 * call initTheme(), and doing it here (rather than in each component that cares)
 * means the theme is resolved once per mount instead of on every toggle click.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  // Resolve whatever the pre-paint script already applied, so the first client
  // render agrees with <html> and there is no hydration mismatch flash.
  useEffect(() => {
    initTheme();
  }, []);

  // Follow the OS only while the user has not made an explicit choice. Once
  // they pick, the OS must not override them -- that is the bug the old
  // unconditional `localStorage.setItem('theme','dark')` caused, in the other
  // direction.
  useEffect(() => {
    let mq: MediaQueryList;
    try {
      mq = window.matchMedia('(prefers-color-scheme: dark)');
    } catch {
      return;
    }
    const onChange = (e: MediaQueryListEvent) => {
      let stored: string | null = null;
      try {
        stored = window.localStorage.getItem(THEME_STORAGE_KEY);
      } catch {
        /* ignore */
      }
      if (stored === 'light' || stored === 'dark') return;
      applyTheme((e.matches ? 'dark' : 'light') as ThemeMode);
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // Reduced motion = "user", not an unconditional disable. It honours the OS
  // setting for every framer-motion consumer, so nothing has to opt in and
  // nothing can forget to. Keep it outermost so no animated subtree sits
  // outside the boundary.
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
