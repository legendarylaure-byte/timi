'use client';

import { useCallback, useRef } from 'react';
import { useReducedMotion } from 'framer-motion';

/**
 * Feeds pointer position into CSS custom properties so `.glass-specular` can
 * track the cursor. Writes to the element's style rather than React state,
 * because a re-render per mousemove is a re-render of the whole subtree.
 *
 * Disabled on coarse pointers (touch) -- there is no hover to track, and the
 * listener would only ever fire on tap. Disabled under prefers-reduced-motion
 * per F5: the specular is decorative movement, and the OS asked for none.
 *
 * ponytail: a hook rather than a shared event bus or a context. Five glass
 * surfaces use it; anything more elaborate would be plumbing for a one-line
 * effect. Ceiling: each instance adds its own pointermove listener, which is
 * fine for the handful of cards that opt in -- move to a single delegated
 * listener if this ever lands on a long list.
 */
export function useGlassPointer<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const frame = useRef(0);
  // MotionConfig does not reach a raw DOM listener, so the reduced-motion
  // check has to be explicit here. This is exactly the gap F5 exists to close:
  // a CSS media query cannot switch off a JS pointer handler.
  const reduced = useReducedMotion();

  const onPointerMove = useCallback((e: React.PointerEvent<T>) => {
    const el = ref.current;
    if (!el) return;
    if (reduced) return;
    if (e.pointerType !== 'mouse') return;
    if (frame.current) return;
    const { clientX, clientY } = e;
    frame.current = requestAnimationFrame(() => {
      frame.current = 0;
      const r = el.getBoundingClientRect();
      el.style.setProperty('--glass-x', `${((clientX - r.left) / r.width) * 100}%`);
      el.style.setProperty('--glass-y', `${((clientY - r.top) / r.height) * 100}%`);
    });
  }, [reduced]);

  return { ref, onPointerMove };
}
