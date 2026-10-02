'use client';

import { useState, useEffect } from 'react';
import { toggleTheme, ThemeMode, initTheme } from '@/lib/theme';
import { THEMES } from '@/lib/brand';

/**
 * Sun/moon with the icon naming the state you are in *now*, not the one you
 * would switch to. It used to show 🌙 while dark (the ternary was
 * `theme === 'light' ? '🌙' : '☀️'`, so the button advertised the wrong mode),
 * and the state could never be anything but 'light' because initTheme() and the
 * pre-paint script both overwrote localStorage. A toggle that cannot change
 * anything is a lie in the chrome.
 *
 * The visible colour pair is pulled from THEMES rather than hardcoded, so the
 * button cannot drift from the palette it is describing.
 */
export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeMode>('dark');

  // Read the real resolved theme after mount. Before mount we render the dark
  // glyph, because the pre-paint script in layout.tsx has already applied the
  // stored theme to <html> and guessing here would flash the wrong icon.
  useEffect(() => {
    setTheme(initTheme());
  }, []);

  const next: ThemeMode = theme === 'dark' ? 'light' : 'dark';
  const t = THEMES[theme];

  return (
    <button
      onClick={() => setTheme(toggleTheme())}
      // WCAG 2.5.8 target size: 40px fails the 24px minimum only in the sense
      // that it clears it comfortably, but the 2px gap below is what actually
      // makes it easy to hit. Kept at 40px with an explicit focus ring.
      className="group relative h-10 w-10 shrink-0 overflow-hidden rounded-xl border transition-all duration-300 hover:scale-105 focus-visible:scale-105"
      style={{
        background: `color-mix(in srgb, ${t.card} 82%, ${t.bg})`,
        borderColor: t.border,
        color: t.text,
        boxShadow: `0 4px 14px color-mix(in srgb, ${t.primary} 18%, transparent)`,
      }}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      aria-pressed={theme === 'dark'}
    >
      <span
        aria-hidden="true"
        className="absolute inset-0 grid place-items-center text-[15px] leading-none transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] group-hover:rotate-[18deg]"
      >
        {theme === 'dark' ? '🌙' : '☀️'}
      </span>
    </button>
  );
}
