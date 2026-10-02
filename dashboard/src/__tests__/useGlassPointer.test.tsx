// Covers the three ways useGlassPointer decides NOT to move the specular, plus
// the one thing it does. The decision branches are the whole hook: a specular
// that follows a finger on a touch device, or that keeps animating under
// prefers-reduced-motion, is a bug the CSS media query in .glass-specular
// cannot catch, because this is a JS pointer handler.
//
// The returned `onPointerMove` is invoked directly rather than through a
// dispatched DOM event. That is not a shortcut: `renderHook` renders no
// element, so a synthetic event on a detached node never reaches React's
// delegated listener and the test would pass by never running the handler.
//
// framer-motion's useReducedMotion is mocked rather than driven through
// matchMedia: jsdom has no matchMedia, and the point here is the hook's
// response to the flag, not framer-motion's media detection.
let reduced = false;
jest.mock('framer-motion', () => ({
  useReducedMotion: () => reduced,
}));

import { renderHook, act } from '@testing-library/react';
import { useGlassPointer } from '@/hooks/useGlassPointer';

/** Flush the requestAnimationFrame the hook coalesces into. */
const flushFrame = () =>
  act(() => {
    jest.advanceTimersByTime(32);
  });

/** A pointer event, as React would hand it to the handler. */
type PEvent = React.PointerEvent<HTMLDivElement>;
const at = (over: Partial<PEvent> = {}) =>
  ({ clientX: 300, clientY: 150, pointerType: 'mouse', ...over }) as unknown as PEvent;

/** Mount the hook with its ref pointing at a measurable element. */
function mount(overrides: Partial<DOMRect> = {}) {
  const el = document.createElement('div');
  el.getBoundingClientRect = () =>
    ({ left: 100, top: 50, width: 400, height: 200, ...overrides }) as DOMRect;

  const view = renderHook(() => useGlassPointer<HTMLDivElement>());
  act(() => {
    // The ref is readonly from outside; the hook itself assigns it on mount.
    (view.result.current.ref as { current: HTMLDivElement | null }).current = el;
  });
  return { el, view };
}

const move = (view: ReturnType<typeof mount>['view'], over?: Partial<PEvent>) => {
  act(() => {
    view.result.current.onPointerMove(at(over));
  });
  flushFrame();
};

beforeEach(() => {
  reduced = false;
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

describe('useGlassPointer', () => {
  it('writes cursor position as a percentage of the element box', () => {
    const { el, view } = mount();
    move(view);
    // (300-100)/400 = 50%, (150-50)/200 = 50%
    expect(el.style.getPropertyValue('--glass-x')).toBe('50%');
    expect(el.style.getPropertyValue('--glass-y')).toBe('50%');
  });

  it('clamps nothing and follows the cursor off the box edge', () => {
    // Not clamped by design: the specular is a gradient position, and a
    // pointer dragged off the card should push the highlight off with it.
    const { el, view } = mount();
    move(view, { clientX: 500, clientY: 250 });
    expect(el.style.getPropertyValue('--glass-x')).toBe('100%');
    expect(el.style.getPropertyValue('--glass-y')).toBe('100%');
  });

  it('ignores touch pointers -- there is no hover to track', () => {
    const { el, view } = mount();
    move(view, { pointerType: 'touch' });
    expect(el.style.getPropertyValue('--glass-x')).toBe('');
  });

  it('ignores mouse movement under prefers-reduced-motion', () => {
    reduced = true;
    const { el, view } = mount();
    move(view);
    expect(el.style.getPropertyValue('--glass-x')).toBe('');
  });

  it('coalesces a burst of moves into a single frame', () => {
    const { el, view } = mount();
    const spy = jest.spyOn(el.style, 'setProperty');

    for (const clientX of [110, 200, 300, 480]) {
      act(() => {
        view.result.current.onPointerMove(at({ clientX } as Partial<PEvent>));
      });
    }
    flushFrame();

    // One write per property for the whole burst, not one per event.
    expect(spy.mock.calls.filter((c) => c[0] === '--glass-x')).toHaveLength(1);
  });

  it('does not throw before the ref is attached', () => {
    const view = renderHook(() => useGlassPointer<HTMLDivElement>());
    expect(() => {
      act(() => {
        view.result.current.onPointerMove(at());
      });
    }).not.toThrow();
  });
});
