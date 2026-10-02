// The theme toggle was non-functional for the entire life of this app, and
// nothing failed. The cause was three systems disagreeing (tailwind mapping both
// namespaces to dark, an unused second palette in lib/theme.ts, and a pre-paint
// script that force-wrote `dark` into localStorage on every load) -- so flipping
// the class changed nothing and the next page load reverted the choice.
//
// These tests pin the mechanism, not the styling. The styling is checked by
// screenshots because jsdom cannot resolve Tailwind's `dark:` variants.
//
// ponytail: deliberately NOT asserting a computed background colour. jsdom does
// not load the Tailwind stylesheet, so `getComputedStyle` on a `dark:` variant
// returns the light value regardless of the class -- such a test would pass
// unconditionally and prove nothing. That is the same mistake as the hex test
// that could not see rgb().

import { toggleTheme, initTheme, applyTheme, resolveTheme, THEME_STORAGE_KEY } from '@/lib/theme';
import { LIGHT_THEME, DARK_THEME } from '@/lib/brand';

describe('theme switching actually switches', () => {
  beforeEach(() => {
    document.documentElement.className = '';
    document.documentElement.removeAttribute('style');
    delete document.documentElement.dataset.theme;
    window.localStorage.clear();
  });

  it('applyTheme("light") removes the dark class', () => {
    applyTheme('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    applyTheme('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('applyTheme sets color-scheme and data-theme too', () => {
    // Anything theming itself off the attribute (canvas gradients, native
    // dialogs) would be wrong if the class flipped but these did not.
    applyTheme('light');
    expect(document.documentElement.style.colorScheme).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
    applyTheme('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
  });

  it('toggleTheme flips the class and persists the new value', () => {
    applyTheme('dark');
    expect(toggleTheme()).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');

    expect(toggleTheme()).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
  });

  // The exact defect. The old pre-paint script wrote 'dark' to localStorage on
  // every load, so a light-mode user was overruled on the next navigation. If
  // anything in layout.tsx starts writing to that key again, this fails.
  it('initTheme respects a stored light preference instead of forcing dark', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    expect(resolveTheme()).toBe('light');
    expect(initTheme()).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    // And it must not have rewritten the stored value while doing so.
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('light');
  });

  it('a stored value that is not a theme is ignored, not trusted', () => {
    for (const junk of ['', 'DARK', 'sepia', '{"mode":"dark"}', 'null']) {
      window.localStorage.setItem(THEME_STORAGE_KEY, junk);
      expect(['light', 'dark']).toContain(resolveTheme());
    }
  });

  it('initTheme is idempotent', () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    expect(initTheme()).toBe('light');
    expect(initTheme()).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  // The reason the toggle was pointless. `bg-light-bg dark:bg-dark-bg` is the
  // pattern in ~2,900 places; it can only work if the two tokens differ.
  it('the class change actually changes the surface a component resolves to', () => {
    expect(LIGHT_THEME.bg).not.toBe(DARK_THEME.bg);
    expect(LIGHT_THEME.card).not.toBe(DARK_THEME.card);
    expect(LIGHT_THEME.text).not.toBe(DARK_THEME.text);
    // The dark one is the brand value and must never be nudged.
    expect(DARK_THEME.bg).toBe('#0E0909');
  });
});
