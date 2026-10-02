/**
 * Theme switching. One module, one decision.
 *
 * ponytail: there is no theme *config* here any more. For a long time this file
 * held a `themeConfig` object with a full second palette in it -- whose "light"
 * values were retired pre-rebrand colours (#FF6B6B, #4ECDC4) and which nothing
 * ever read. `tailwind.config.js` separately mapped `light.*` and `dark.*` to
 * the same dark values, and layout.tsx force-wrote `dark` to localStorage on
 * every load. Three systems, no agreement, and a toggle that flipped a class
 * which changed nothing. The palette now lives in `lib/brand.ts` and this file
 * only decides *which* one is on.
 *
 * The three failure modes this is written against:
 *   1. A stored preference that is silently overwritten. The pre-paint script
 *      in layout.tsx used to do `localStorage.setItem('theme','dark')`
 *      unconditionally, so a light-mode user was overruled on every navigation.
 *      That write is gone; the script only reads.
 *   2. Assuming a stored value is valid. Anything that is not exactly 'light'
 *      or 'dark' is treated as absent rather than trusted.
 *   3. Assuming localStorage exists. It throws in private Safari and in some
 *      embedded webviews, which would take the whole app down during boot.
 */

import type { ThemeName } from './brand';

export type ThemeMode = ThemeName;

export const THEME_STORAGE_KEY = 'timi.theme';

function isTheme(v: unknown): v is ThemeMode {
  return v === 'light' || v === 'dark';
}

/** localStorage is not guaranteed. Every access is guarded. */
function readStored(): ThemeMode | null {
  try {
    const v = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isTheme(v) ? v : null;
  } catch {
    return null;
  }
}

function writeStored(mode: ThemeMode): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
  } catch {
    /* private mode: the class still applies for this page view */
  }
}

/** Apply to <html>. The `dark` class is what Tailwind's `dark:` variants key on. */
export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement;
  root.classList.toggle('dark', mode === 'dark');
  root.style.colorScheme = mode;
  // Kept in sync for anything that wants to theme itself off the attribute
  // rather than the class (e.g. a native <dialog> or a canvas gradient).
  root.dataset.theme = mode;
}

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch {
    return true;
  }
}

/**
 * Resolve the theme: an explicit stored choice wins, otherwise the OS.
 * Dark is the default so a first visit with no preference and no media query
 * lands on the theme this product is actually designed around.
 */
export function resolveTheme(): ThemeMode {
  return readStored() ?? (systemPrefersDark() ? 'dark' : 'light');
}

/** Called from the ThemeToggle. Returns the mode now in effect. */
export function toggleTheme(): ThemeMode {
  const next: ThemeMode = document.documentElement.classList.contains('dark') ? 'light' : 'dark';
  applyTheme(next);
  writeStored(next);
  return next;
}

/**
 * Called once from the root ThemeProvider. Idempotent, and safe to call on
 * every render -- it re-applies the resolved theme so the first client render
 * agrees with whatever the pre-paint script already put on <html>.
 */
export function initTheme(): ThemeMode {
  const mode = resolveTheme();
  applyTheme(mode);
  return mode;
}
