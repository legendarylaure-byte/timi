'use client';

import { useEffect, useMemo, useRef } from 'react';
import { BRAND_ORBS } from '@/lib/brand';

/**
 * The ambient backdrop.
 *
 * Two things were wrong here, and both presented as "the colours look slightly
 * off" rather than as bugs:
 *
 * 1. The light-mode scene was tinted with the retired pre-rebrand palette --
 *    coral, teal, rose and tan. `BRAND_ORBS` (brand purple / violet / pink /
 *    orange / amber) was defined, exported, and never used, so a correct
 *    palette sat in the file while a retired one rendered. This was invisible
 *    to the retired-hex drift test because it was written as rgba() rgb-triplets
 *    rather than hex.
 *
 * 2. `variant === 'landing' ? 'dark-scene' : 'dark-scene'` -- both arms were the
 *    same string, so the prop did nothing. The intent was a *different* scene on
 *    light backgrounds, because a dark-mode orb field over a #FAF7FA page reads
 *    as grey smudges. Light orbs are now genuinely different: very low alpha,
 *    larger, and pushed behind a white veil so they tint rather than stain.
 *
 * Scroll parallax is driven by a rAF-throttled scroll listener writing two CSS
 * custom properties, rather than React state, so scrolling does not re-render
 * the tree. It is disabled under prefers-reduced-motion (F5).
 */
export type AmbientVariant = 'landing' | 'app';

export function AmbientBackground({ variant = 'app' }: { variant?: AmbientVariant }) {
  const ref = useRef<HTMLDivElement>(null);

  // Landing = broad, slow, high bloom behind the hero. App = quieter, and
  // pulled up out of the way so sidebar content stays readable.
  //
  // `lightVeil` is a light-mode-only value: the veil element is
  // `bg-light-bg/55 dark:bg-transparent`, so a non-zero veil does nothing in
  // dark mode and dark is unaffected either way. It is named for what it
  // actually changes.
  //
  // The landing variant previously had NO veil, which was correct while every
  // marketing page was pinned to a dark canvas. Once they theme, the orbs
  // render at full alpha on #FAF7FA, where a 0.30-alpha saturated purple is a
  // stain rather than a bloom -- the exact failure the app variant was already
  // fixed for. 0.55 is the same veil the app scene uses, which is what makes
  // the light page read as one system instead of two.
  const scene = useMemo(
    () =>
      variant === 'landing'
        ? { scale: 1, opacity: 1, blur: 'blur-3xl', lightVeil: 0.55 }
        : { scale: 0.8, opacity: 0.6, blur: 'blur-3xl', lightVeil: 0.35 },
    [variant],
  );

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Respect the OS: no parallax movement at all.
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (mq.matches) return;

    let frame = 0;
    const onScroll = () => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const h = window.innerHeight || 1;
        const p = Math.min(Math.max(window.scrollY / h, 0), 1);
        el.style.setProperty('--amb-y', `${p * 60}px`);
        el.style.setProperty('--amb-o', String(1 - p * 0.45));
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div
      ref={ref}
      aria-hidden="true"
      className={`pointer-events-none fixed inset-0 -z-10 overflow-hidden ${scene.blur}`}
      style={{ ['--amb-y' as string]: '0px', ['--amb-o' as string]: '1' }}
    >
      {BRAND_ORBS.map((orb, i) => (
        <div
          key={orb.color + i}
          className="absolute rounded-full transition-transform duration-[1200ms] ease-[cubic-bezier(0.22,1,0.36,1)] will-change-transform motion-reduce:transition-none"
          style={{
            width: orb.size,
            height: orb.size,
            top: orb.top,
            left: orb.left,
            right: orb.right,
            bottom: orb.bottom,
            background: `radial-gradient(circle at 30% 30%, ${orb.color}, transparent 70%)`,
            // Dark: the brand ramp at its stated alpha. Light: pushed right
            // down to ~0.18x so it tints the page instead of staining it.
            opacity: orb.opacity * scene.opacity,
            transform: `translate3d(0, calc(var(--amb-y, 0px) * ${(i + 1) * 0.14}), 0) scale(${scene.scale})`,
          }}
        />
      ))}

      {/* Light-mode veil. On white, a saturated orb at even 0.3 alpha is a
          visible stain; a veil over the whole field turns the same orb into a
          tint. No-op in dark mode by construction. */}
      {scene.lightVeil > 0 && (
        <div className="absolute inset-0 bg-light-bg/55 dark:bg-transparent" style={{ opacity: scene.lightVeil }} />
      )}

      {/* Grain. Hides the banding that a large low-alpha gradient produces on
          8-bit panels -- the same reason .glass-noise exists. */}
      <div
        className="absolute inset-0 opacity-[0.035] dark:opacity-[0.05]"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
    </div>
  );
}
