// Invariant: the dashboard palette and the palette that actually renders into
// every video are the same colours.
//
// Why this test exists: the logo shipped purple while `globals.css` still said
// `#ec133e`, because the CSS and the palette file were never compared. The
// video pipeline and the dashboard are edited on different days by different
// people, so "we updated the theme" only means something if the two ends are
// pinned together here.
//
// Two lessons are baked into the shape of this file:
//   1. It greps SOURCE, not config. A test that reads config cannot see a
//      hardcoded hex in a component.
//   2. It strips comments first. Naming a retired colour in prose is the
//      documented reason it is retired, so a naive grep would fail this file.
import { readFileSync, readdirSync, statSync } from 'fs';
import { join } from 'path';
import { BRAND, RETIRED_HEXES, LIGHT_THEME, DARK_THEME, THEMES, contrastRatio } from '@/lib/brand';
import type { ThemeTokens } from '@/lib/brand';

// The colours both ends must agree on. AMBER is deliberately excluded: it is
// subtitle-only in brand_palette.py and is calibrated for contrast against
// arbitrary footage, not chosen for brand reasons.
const SHARED = {
  LICORICE: BRAND.licorice,
  PURPLE: BRAND.purple,
  VIOLET: BRAND.violet,
  PINK: BRAND.pink,
  ORANGE: BRAND.orange,
  LIGHT_ORANGE: BRAND.lightOrange,
  WHITE: BRAND.white,
} as const;

// ---------------------------------------------------------------------------
// 1. dashboard/src/lib/brand.ts  ==  agents/utils/brand_palette.py
// ---------------------------------------------------------------------------
describe('brand palette: dashboard == video pipeline', () => {
  const py = readFileSync('../agents/utils/brand_palette.py', 'utf8');
  const found: Record<string, string> = {};
  for (const m of py.matchAll(/^([A-Z_]+) = "(#[0-9A-Fa-f]{6})"/gm)) found[m[1]] = m[2];

  it('found every shared colour in brand_palette.py', () => {
    for (const name of Object.keys(SHARED)) {
      expect(found[name]).toBeDefined();
    }
  });

  it.each(Object.entries(SHARED))('%s matches brand_palette.py', (name, ts) => {
    expect(found[name]).toBe(ts);
  });

  it('the two accent ramps are the same five colours in the same order', () => {
    // ACCENT_RAMP = (PURPLE, VIOLET, PINK, ORANGE, LIGHT_ORANGE) -- note these
    // are constant NAMES, so they have to be resolved through `found`.
    const ramp = py.match(/ACCENT_RAMP = \(([^)]*)\)/)?.[1] ?? '';
    const pyRamp = ramp
      .split(',').map((s) => s.trim()).filter(Boolean)
      .map((name) => found[name]);
    expect(pyRamp).toEqual([
      BRAND.purple, BRAND.violet, BRAND.pink, BRAND.orange, BRAND.lightOrange,
    ]);
  });
});

// ---------------------------------------------------------------------------
// 2. tailwind.config.js resolves to the new dark palette in BOTH namespaces
// ---------------------------------------------------------------------------
/** 'border-strong' -> 'borderStrong' so it can index the theme object. */
const camel = (k: string) => k.replace(/-([a-z])/g, (_, c) => c.toUpperCase()) as keyof ThemeTokens;

describe('tailwind tokens point at brand.ts', () => {
  // Both namespaces are derived from the theme objects in brand.ts, never
  // written here. A literal in this test is a colour with two homes, which is
  // the same bug the retired-hex list had: #C80036 stayed alive in a gradient
  // because the button was on the list and the gradient's second stop was not.
  //
  // This block used to assert that light.* and dark.* were IDENTICAL -- it
  // enforced the dark-only hack, so the test suite was the thing keeping light
  // mode from existing. It now asserts each namespace matches its own theme and
  // that the two actually diverge.
  const KEYS = [
    'bg', 'card', 'primary', 'secondary', 'accent',
    'text', 'muted', 'border', 'border-strong',
  ] as const;

  // require, not import: tailwind.config.js is untyped JS and jest runs this
  // through CommonJS. No @typescript-eslint plugin is loaded in .eslintrc.json,
  // so naming one of its rules in a disable comment is itself an ESLint error.
  const cfg = require('../../tailwind.config.js');
  const colors = cfg.theme.extend.colors;

  it('light and dark namespaces are defined', () => {
    expect(colors.light).toBeDefined();
    expect(colors.dark).toBeDefined();
  });

  it.each(KEYS)('light.%s and dark.%s each match their own theme', (key) => {
    expect(colors.light[key]).toBe(LIGHT_THEME[camel(key)]);
    expect(colors.dark[key]).toBe(DARK_THEME[camel(key)]);
  });

  it('every semantic colour matches its theme too', () => {
    for (const key of ['success', 'info', 'warning', 'error'] as const) {
      expect(colors.light[key]).toBe(LIGHT_THEME[key]);
      expect(colors.dark[key]).toBe(DARK_THEME[key]);
    }
  });

  // The load-bearing assertion. The old suite asserted these were equal; that
  // is precisely the bug, and a test that enforces a bug is worse than no test
  // because it reads as coverage. If both namespaces are ever pointed at the
  // same object again, light mode silently stops existing and every token test
  // still passes.
  it('the two themes are genuinely different, not aliases of each other', () => {
    const surfaceKeys = ['bg', 'card', 'text', 'muted', 'border'] as const;
    for (const k of surfaceKeys) {
      expect(colors.light[k]).not.toBe(colors.dark[k]);
    }
    // Accents: light is darkened for AA, dark is the vivid brand value. The
    // video palette (#9B4DFF) must survive untouched in dark.
    expect(colors.dark.primary).toBe(BRAND.purple);
    expect(colors.light.primary).not.toBe(BRAND.purple);
  });

  it('error is NOT aliased to primary in either namespace', () => {
    // Toast.tsx and StatusBadge.tsx both used to map error -> primary. If that
    // alias is ever re-introduced at the token layer, every error message in
    // the app turns purple.
    expect(colors.light.error).not.toBe(colors.light.primary);
    expect(colors.dark.error).not.toBe(colors.dark.primary);
  });

  it('warning is distinguishable from brand orange', () => {
    // #FACC15 vs #FF8133. Close enough to be easy to get wrong, far enough
    // apart to survive a glance.
    expect(colors.light.warning).not.toBe(colors.light.primary);
    expect(colors.light.warning).not.toBe(BRAND.orange);
    expect(colors.light.warning).not.toBe(BRAND.lightOrange);
  });

  it('font stacks match the company site', () => {
    const f = cfg.theme.extend.fontFamily;
    expect(f.sans.join(' ')).toContain('var(--font-body)');
    expect(f.display.join(' ')).toContain('var(--font-display)');
    expect(f.mono.join(' ')).toContain('var(--font-mono)');
  });
});

// ---------------------------------------------------------------------------
// 3. No retired hex survives anywhere in dashboard source or CSS
// ---------------------------------------------------------------------------
// Comment stripper shared by every source-scanning check in this file.
//
// ORDER IS LOAD-BEARING, and getting it wrong was a real false failure. Line
// comments are stripped FIRST. `app/page.tsx` carries the comment
// "(agents/crew/" + "*" + ".py, excluding __init__)", whose slash-star is a
// glob, not a block-comment opener -- but the block regex cannot tell. Stripping
// block comments first paired that glob with the next real closing delimiter (a
// JSX comment 90 lines later) and deleted everything in between, including the
// very line the check was asserting on.
//
// So: lines first, which removes the stray opener, then blocks, which are now
// balanced. This is also the only order in which a prose comment cannot
// satisfy a check -- and prose satisfying a check is how the canvas guard in 3c
// passed against its own bug, because the fix carried a comment naming
// `BRAND.canvas`.
//
// (Written as line comments on purpose: a block comment here cannot quote the
// delimiters it is describing without terminating itself mid-line.)
//
const STRIP = (s: string) =>
  s
    // line comments first, but not the `//` in https://
    .replace(/(^|[^:])\/\/.*$/gm, '$1')
    // then block comments (JSX `{/* ... */}` and /* ... */)
    .replace(/\/\*[\s\S]*?\*\//g, '');

describe('retired hexes are gone from dashboard source', () => {
  function walk(dir: string, out: string[] = []): string[] {
    for (const e of readdirSync(dir)) {
      if (e === 'node_modules' || e === '.next') continue;
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walk(p, out);
      else if (/\.(tsx?|css)$/.test(e)) out.push(p);
    }
    return out;
  }

  // brand.ts is where retired hexes are *declared*, so it necessarily contains
  // them. This test is the only other file allowed to, and for the same reason.
  const ALLOWED = new Set(['src/lib/brand.ts', 'src/__tests__/brandTokens.test.ts']);

  const files = [...walk('src'), 'public/logo.svg', 'public/favicon.svg'].filter((f) => {
    const p = f.replace(/\\/g, '/');
    if (ALLOWED.has(p)) return false;
    try { return statSync(f).isFile(); } catch { return false; }
  });

  it('scans a non-trivial number of files (guards against a broken walk)', () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it('the allowlist names only the two declaration files', () => {
    // An allowlist that grows is the same class of bug as a fallback that hides
    // a mismatch: it turns a failure into a pass. Pin its size.
    expect(ALLOWED.size).toBe(2);
  });

  /**
   * THE THIRD VERSION OF THIS SCAN, and the previous one was the exact bug this
   * file exists to catch.
   *
   * v1 matched hex strings only, and reported "retired hexes clean tree-wide"
   * while 9 files still carried retired coral/teal in `rgb()` / `rgba()` form --
   * including AmbientBackground, which sits behind the entire dashboard, and
   * both dark glass panels in globals.css. It could not see them because
   * `rgba(255,105,105,0.3)` is not `#FF6969`. A hex test cannot see an rgb
   * triple. It also had no coverage for `.css` in its walk list for the same
   * reason (CSS gradients are mostly written as rgba).
   *
   * v2 is a normaliser instead of a substring search: rewrite every colour in
   * the file -- hex, rgb(), rgba(), 3-digit hex, named-ish -- into canonical
   * `#rrggbb` and compare those. Alpha is discarded deliberately, because a
   * retired hue at 4% alpha is the same retired hue; otherwise the 12 listed
   * hexes only cover 12 of the infinite alphas they can be written at.
   *
   * 3-digit hex (#F69 -> #FF6699) is expanded too, because it is a legal way to
   * write the same colour and would otherwise be a hole in exactly the same
   * way. Case is folded.
   */
  const toHex = (r: number, g: number, b: number) =>
    '#' + [r, g, b].map((n) => n.toString(16).padStart(2, '0')).join('');

  /** Every colour in `src`, canonicalised to lowercase #rrggbb. */
  function normaliseColors(src: string): string[] {
    const out: string[] = [];
    const body = src.toLowerCase();
    // hex, long form
    for (const m of body.matchAll(/#([0-9a-f]{6})(?![0-9a-f])/g)) out.push('#' + m[1]);
    // hex, short form
    for (const m of body.matchAll(/#([0-9a-f]{3})(?![0-9a-f])/g)) {
      const [r, g, b] = m[1].split('');
      out.push(toHex(parseInt(r + r, 16), parseInt(g + g, 16), parseInt(b + b, 16)));
    }
    // rgb() / rgba(), integers or percentages, alpha discarded
    for (const m of body.matchAll(/rgba?\(\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)/g)) {
      const chan = (v: string) =>
        v.includes('.') ? Math.round(parseFloat(v) * 2.55) : parseInt(v, 10);
      out.push(toHex(chan(m[1]) & 255, chan(m[2]) & 255, chan(m[3]) & 255));
    }
    return out;
  }

  const offenders: string[] = [];
  for (const f of files) {
    const seen = new Set(normaliseColors(STRIP(readFileSync(f, 'utf8'))));
    for (const hex of RETIRED_HEXES) {
      // compare canonical: retired list is a mix of cases
      const canon = toHex(
        parseInt(hex.slice(1, 3), 16),
        parseInt(hex.slice(3, 5), 16),
        parseInt(hex.slice(5, 7), 16),
      );
      if (seen.has(canon)) offenders.push(`${f}: ${hex}`);
    }
  }

  // The design slice (Phase C) owns these four surfaces outright, so they are a
  // hard zero with no allowances.
  const SLICE = ['src/app/page.tsx', 'src/app/(auth)/login/page.tsx', 'src/app/dashboard/layout.tsx', 'src/app/dashboard/reports/page.tsx'];

  it('the four design-slice surfaces are completely clean', () => {
    expect(offenders.filter((o) => SLICE.some((s) => o.startsWith(s)))).toEqual([]);
  });

  // Phase D is done: the tree is now at a hard zero, so the ratchet is gone
  // rather than pinned. The 48-entry allow-all list that used to sit here was
  // itself a hazard -- an allowlist that grows is an allowlist that eventually
  // allows everything, and it made "still 48 to go" look like a passing state.
  //
  // A baseline is only honest while there is work left. With none, the strict
  // assertion is both simpler and stricter: any retired colour anywhere in src/
  // fails, with no list to add to.
  it('no retired colour appears anywhere in src/', () => {
    expect(offenders).toEqual([]);
  });

  it('the logo and favicon are the violet V, not the old crimson mark', () => {
    for (const f of ['public/logo.svg', 'public/favicon.svg']) {
      const body = STRIP(readFileSync(f, 'utf8')).toLowerCase();
      expect(body).toContain(BRAND.purple.toLowerCase());
    }
  });
});

// ---------------------------------------------------------------------------
// 3b. brand-facing surfaces carry no off-brand Tailwind named colour family
//
// The retired-hex scan above has a blind spot it cannot close: `text-teal-400`
// and `from-red-500/20` are Tailwind's *own* palette, not hex literals, so a
// scan for #00CCCC never sees them. Those families (red/teal/cyan/blue/...) are
// the same off-brand drift the hex list exists to catch, written a different way
// -- and the About page was shipping a red icon tile on the brand-purple site
// while every scan reported clean.
//
// Scope is the brand-facing surfaces, not src/ whole. Those pages force their
// own dark canvas (PublicNavFooter sets #050510, auth sets BRAND.base), so the
// brand ramp is the only correct colour source there and a hard zero is honest.
// The dashboard still has ~500 such classes across 50 files; pinning a number
// for those would be the ratchet that was deliberately deleted, so it is left
// as a documented remaining sweep rather than a green-looking baseline.
// ---------------------------------------------------------------------------
describe('brand-facing surfaces use the brand ramp, not Tailwind hue families', () => {
  const BRAND_FACING = [
    'src/app/page.tsx',
    'src/app/about/page.tsx',
    'src/app/faq/page.tsx',
    'src/app/privacy/page.tsx',
    'src/app/terms/page.tsx',
    'src/app/review/page.tsx',
    'src/app/(auth)/login/page.tsx',
    'src/app/(auth)/signup/page.tsx',
    'src/components/PublicNavFooter.tsx',
  ];

  // Hues that are not in the brand palette and stand in for one that is.
  // `purple`/`violet`/`fuchsia`/`orange`/`pink` are deliberately NOT listed:
  // they are adjacent enough to the ramp that flagging them would be noise.
  const OFF_BRAND =
    '(red|teal|cyan|green|emerald|blue|indigo|sky|lime|amber|yellow|rose)';
  const UTILS =
    '(text|bg|from|to|via|border|ring|fill|stroke|divide|placeholder|accent|caret|shadow|outline)';
  const re = new RegExp(`${UTILS}-${OFF_BRAND}-[0-9]{2,3}`, 'g');

  it.each(BRAND_FACING)('%s is clean', (f) => {
    const body = STRIP(readFileSync(f, 'utf8'));
    expect(body.match(re) ?? []).toEqual([]);
  });
});

// ---------------------------------------------------------------------------
// 3c. a page that paints text-white must own its own dark canvas
//
// Found by screenshotting, not by a grep. `/` (the landing page) rolls its own
// nav instead of using PublicNavFooter, so it had no background of its own and
// inherited the themed <body> -- `bg-light-bg`, i.e. #FAF7FA. It paints 23
// `text-white` classes, so under a light OS preference the entire landing page
// rendered white-on-white. Every scan in this file was green throughout: no
// retired hex, no off-brand family, correct tokens. The colour was simply
// white, on white.
//
// The invariant: white text needs a canvas that is not white. The body being
// themed for the dashboard is what makes this easy to get wrong.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// 3c. THEMED_PUBLIC pages: public marketing pages that share the same themed
// shell (PublicNavFooter) must join the light/dark theme and must still own a
// dark canvas when painting light text. The landing page is intentionally
// excluded here: it rolls its own nav and is kept in ALWAYS_DARK for the time
// being.
// ---------------------------------------------------------------------------
describe('THEMED_PUBLIC pages own a themed canvas', () => {
  // The canvas is a property of the SHELL, not of each page. PublicNavFooter is
  // the only element that paints one for about/faq/privacy/terms, so asserting
  // per-page that the page itself carries a canvas class is the wrong
  // assertion: it forces every child page to repaint the surface and it can
  // never see the shell's own classes. The shell is checked once, below; the
  // pages are checked for the thing that actually broke -- light text on a
  // white canvas.
  const THEMED_PUBLIC = [
    'src/app/about/page.tsx',
    'src/app/faq/page.tsx',
    'src/app/privacy/page.tsx',
    'src/app/terms/page.tsx',
  ];

  // `text-gray-100`/`200`/`300` count: they are light-on-dark text just as much
  // as `text-white`, and a check scoped to the literal word "white" would skip
  // any page that reaches for gray instead. This is the class of defect that
  // shipped white-on-white in the first place.
  const LIGHT_TEXT = /text-(white|gray-100|gray-200|gray-300)/;

  it.each(THEMED_PUBLIC)('%s still paints light text (so the shell must theme)', (f) => {
    expect(readFileSync(f, 'utf8')).toMatch(LIGHT_TEXT);
  });

  it.each(THEMED_PUBLIC)('%s wraps its content in the themed shell', (f) => {
    expect(STRIP(readFileSync(f, 'utf8'))).toMatch(/<PublicNavFooter/);
  });

  it('the shell itself is tokenised, not pinned to a dark literal', () => {
    // This is the assertion that would have caught the original bug. The shell
    // was `style={{ background: BRAND.canvas }}` -- a hardcoded dark -- while
    // <body> was themed, so all four pages were dark-only and the light theme
    // could never reach them however correct the tokens were.
    //
    // STRIP first: the fix carried a comment naming BRAND.canvas, and prose
    // about a fix must not be able to satisfy the guard for it.
    const body = STRIP(readFileSync('src/components/PublicNavFooter.tsx', 'utf8'));
    expect(body).toMatch(/bg-light-bg dark:bg-dark-bg/);
    expect(body).not.toMatch(/BRAND\.canvas/);
  });
});

describe('the landing page is themed but owns its own canvas', () => {
  // The odd one out. /about, /faq, /privacy and /terms inherit their surface
  // from PublicNavFooter; the landing page rolls its own nav, so there is no
  // shell to inherit from and it has to paint the background itself. It was
  // `style={{ background: BRAND.canvas }}` -- a hardcoded dark -- which is
  // exactly why it rendered white-on-white under a light OS preference while
  // every other scan in this file stayed green.
  //
  // Two-sided on purpose: it must be tokenised (no dark literal) AND it must
  // still paint a surface (no silent fallthrough to the themed <body>).
  const F = 'src/app/page.tsx';
  const body = () => STRIP(readFileSync(F, 'utf8'));

  it('paints light text, so it needs a surface to contrast against', () => {
    expect(readFileSync(F, 'utf8')).toMatch(/text-(white|gray-100|gray-200|gray-300)/);
  });

  it('declares its own themed canvas rather than inheriting the body', () => {
    expect(body()).toMatch(/bg-light-bg dark:bg-dark-bg/);
  });

  it('carries no hardcoded dark canvas', () => {
    expect(body()).not.toMatch(/BRAND\.canvas/);
    expect(body()).not.toMatch(/050510/);
  });
});

describe('ALWAYS_DARK pages own a dark canvas', () => {
  // Deliberately dark-only, and out of scope for the light theme: the
  // login/signup pair and the review surface keep painting their own dark, so
  // the light-text invariant still applies to them.
  const ALWAYS_DARK = [
    'src/app/review/page.tsx',
    'src/app/(auth)/login/page.tsx',
    'src/app/(auth)/signup/page.tsx',
  ];

  const LIGHT_TEXT = /text-(white|gray-100|gray-200|gray-300)/;

  it.each(ALWAYS_DARK)('%s paints light text', (f) => {
    // Guard against the list rotting: a page dropped from the list because it
    // stopped painting light text must not silently escape the check.
    expect(readFileSync(f, 'utf8')).toMatch(LIGHT_TEXT);
  });

  it.each(ALWAYS_DARK)('%s declares a dark canvas', (f) => {
    // Comments are stripped first, and that is not a nicety. Without it this
    // test passed against the *bug*: the fix carried an explanatory comment
    // naming `BRAND.canvas`, and the comment satisfied the grep. A guard that
    // can be satisfied by prose about the fix is not a guard.
    const body = STRIP(readFileSync(f, 'utf8'));
    const ownsCanvas =
      /PublicNavFooter/.test(body) || /BRAND\.canvas/.test(body) || /050510/.test(body);
    expect(ownsCanvas).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// 4. the two themes are legible (WCAG AA), computed not eyeballed
// ---------------------------------------------------------------------------
describe('every text token clears WCAG AA against its own surface', () => {
  // Computed from the palette objects rather than asserted as a number, so
  // changing a hex cannot leave a stale "4.5:1 passes" comment behind it.
  const AA = 4.5;

  it.each([
    ['light', 'text', 'bg'], ['light', 'text', 'card'],
    ['light', 'muted', 'bg'], ['light', 'muted', 'card'],
    ['light', 'primary', 'bg'], ['light', 'primary', 'card'],
    ['light', 'secondary', 'bg'], ['light', 'accent', 'bg'],
    ['light', 'success', 'bg'], ['light', 'info', 'bg'],
    ['light', 'warning', 'bg'], ['light', 'error', 'bg'],
  ] as const)('%s.%s on %s', (theme, fg, bg) => {
    const r = contrastRatio(THEMES[theme][fg], THEMES[theme][bg]);
    expect({ token: `${theme}.${fg}`, on: bg, ratio: Number(r.toFixed(2)) })
      .toMatchObject({});
    expect(r).toBeGreaterThanOrEqual(AA);
  });

  it('dark.text on dark.bg', () => {
    expect(contrastRatio(THEMES.dark.text, THEMES.dark.bg)).toBeGreaterThanOrEqual(AA);
  });

  // WCAG 1.4.11 non-text contrast: a control boundary needs 3:1, a decorative
  // card edge does not. This is the one place borderStrong exists.
  it.each(['light', 'dark'] as const)('%s.borderStrong clears 3:1 on its own background', (theme) => {
    expect(contrastRatio(THEMES[theme].borderStrong, THEMES[theme].bg)).toBeGreaterThanOrEqual(3);
  });

  // The value of computing this: the first pass of the light palette used the
  // dark semantic values unchanged and every one of them failed. 1.44:1 for
  // warning is a colour you cannot read, and it looked fine in a code review.
  it('the dark-tuned semantic values genuinely would have failed on white', () => {
    // Proves the test above is not vacuously passing: it has teeth.
    expect(contrastRatio('#FACC15', LIGHT_THEME.bg)).toBeLessThan(AA);
    expect(contrastRatio(LIGHT_THEME.warning, LIGHT_THEME.bg)).toBeGreaterThanOrEqual(AA);
  });
});

// ---------------------------------------------------------------------------
// Public pages use the token classes, not inline brand hexes
// ---------------------------------------------------------------------------
describe('public CTAs are not hand-rolled brand gradients', () => {
  // Four public CTAs each re-implemented .btn-primary with the same two hardcoded
  // stops. Two painted body text on that gradient in light mode, and one shipped
  // href="mailto:${CONTACT_EMAIL}" as a double-quoted literal, so the address was
  // never interpolated at all. The class already exists and is contrast-asserted;
  // the defect was not knowing that. Greps source, and skips comments for the
  // reason stated at the top of this file.
  const PUBLIC = [
    'src/app/page.tsx',
    'src/app/about/page.tsx',
    'src/app/faq/page.tsx',
    'src/app/privacy/page.tsx',
    'src/app/terms/page.tsx',
    'src/components/PublicNavFooter.tsx',
  ];

  const code = (f: string) =>
    readFileSync(join(process.cwd(), f), 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/\/\/.*$/gm, '');

  it('has no inline brand-gradient stops', () => {
    const offenders: string[] = [];
    for (const f of PUBLIC) {
      for (const line of code(f).split('\n')) {
        if (/linear-gradient\([^)]*(#9B4DFF|#F856A5)/.test(line)) offenders.push(`${f}: ${line.trim()}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it('interpolates mailto addresses rather than shipping a literal ${...}', () => {
    const offenders = PUBLIC.filter((f) => /href="mailto:\$\{/.test(code(f)));
    expect(offenders).toEqual([]);
  });
});

describe('the about page derives its agent count', () => {
  const src = readFileSync(join(process.cwd(), 'src/app/about/page.tsx'), 'utf8');

  it('never hardcodes the total in prose', () => {
    // It read "Our 9 AI agents" as a literal beside a 13-agent pipeline while the
    // heading separately counted the list, so the page contradicted itself and
    // only one of the two numbers could be trusted.
    expect(src).not.toMatch(/Our \d+ AI agents/);
    expect(src).toMatch(/Our \{AGENTS\.length\} AI agents/);
  });

  it('still enumerates the agents it claims', () => {
    const body = src.match(/const AGENTS = \[([\s\S]*?)\n\];/);
    expect(body).not.toBeNull();
    expect((body![1].match(/\{ icon:/g) || []).length).toBeGreaterThan(0);
    expect(src).toMatch(/AGENTS\.map\(/);
  });
});

// WCAG 1.4.3 / 1.4.11. Guards text that a computed-style pass measured as too
// low, so a rebrand cannot silently reintroduce it.
//
// These are measured claims, not guesses: the ratios below were read out of a
// live computed-style probe (elementFromPoint for the painted surface, real
// alpha compositing) at 1440x900 in both themes. The probe scrolled the page
// and evaluated at EVERY step -- the first version only measured the final
// scroll position, which is how a real 2.94:1 failure first read as clean.
//
// The rule being encoded: on `light-bg` (rgb(250,247,250)) the de-emphasised
// `light-text/70` alpha lands at 2.94:1, which fails even the relaxed 3:1
// large-text threshold, so 72px bold hero text cannot use it. `light-muted`
// (#796F79) measures 4.53:1 and `dark-muted` (#A396A3) measures 7.02:1.
describe('text contrast claims measured in a live computed-style probe', () => {
  const read = (f: string) =>
    readFileSync(join(process.cwd(), f), 'utf8')
      .replace(/\/\*[\s\S]*?\*\//g, '')
      .replace(/(^|[^:])\/\/.*$/gm, '$1');

  it('hero tagline uses the muted tokens, not a 70% alpha on light-text', () => {
    const src = read('src/app/page.tsx');
    const tagline = src.match(/<span className="([^"]*)">by Vyom Ai Cloud<\/span>/);
    expect(tagline).not.toBeNull();
    expect(tagline![1]).toContain('text-light-muted');
    expect(tagline![1]).toContain('dark:text-dark-muted');
    // The exact class that measured 2.94:1.
    expect(tagline![1]).not.toMatch(/text-light-text\/\d+/);
    expect(tagline![1]).not.toMatch(/text-white\/\d+/);
  });

  it('keeps the review page action buttons on the calibrated brand hexes', () => {
    // Measured low as #2563eb and #059669 on the #050510 review canvas. Both
    // are also Tailwind defaults rather than brand tokens, so the test names
    // the values instead of trusting a class.
    const src = read('src/app/review/page.tsx');
    expect(src).not.toMatch(/#2563eb/i);
    expect(src).not.toMatch(/#059669/i);
    expect(src).toMatch(/#0f5fbf/i);
    expect(src).toMatch(/#047857/i);
    // An action on a near-black canvas still has to be legible white.
    expect(src).toMatch(/text-white/);
  });

  it('never dims auth-page text below the floor the canvas can carry', () => {
    // login/signup are deliberately always-dark (BRAND.canvas #050510, see
    // lib/brand.ts), so their text alpha has a hard contrast floor. Measured
    // against the composited canvas: white/40 = 3.72:1 (fails the 4.5 needed
    // for these sizes), white/50 = 5.31:1, white/60 = 7.32:1.
    //
    // The scan is an alpha floor rather than a banned string, so the next dim
    // value someone reaches for is caught too. `placeholder-` is excluded:
    // a placeholder is not required to meet the text contrast minimum.
    for (const f of ['src/app/(auth)/login/page.tsx', 'src/app/(auth)/signup/page.tsx']) {
      const src = read(f);
      const alphas = [...src.matchAll(/(?<!placeholder-)text-white\/(\d+)/g)].map(m => Number(m[1]));
      expect(alphas.length).toBeGreaterThan(0);
      expect(Math.min(...alphas)).toBeGreaterThanOrEqual(50);
    }
  });
});
