/**
 * Single source of truth for Vyom Ai Cloud brand tokens.
 *
 * ponytail: these are a hand-mirror of `agents/utils/brand_palette.py`, which
 * is what actually renders into every video. `src/__tests__/brandTokens.test.ts`
 * asserts the two agree, because a palette that only exists in the dashboard
 * is exactly how purple ended up on the logo while the CSS said crimson.
 *
 * Retired hexes that must never come back (the 2026 pre-rebrand crimson/teal
 * theme, plus the older purple used on www.vyomai.cloud):
 *   #ec133e #bd0f32 #f4718b #FF6969 #FF4757 #D4B896 #0C1844 #1A2248
 *   #4ECDC4 #FF6B6B #8a50e8 #f59e0b
 */

export const BRAND = {
  /** Violet-leaning magenta. Primary interactive + the wordmark's lead colour. */
  purple: '#9B4DFF',
  /** Deep indigo-violet. Gradient partner, used for fills and depth. */
  violet: '#6641FC',
  /** Magenta-pink. The bridge between violet and orange in the gradient. */
  pink: '#F856A5',
  /** Warm orange. Primary CTA. */
  orange: '#FF8133',
  /** Soft amber-orange. Gradient tail, hover states, warm highlights. */
  lightOrange: '#FFB05F',
  /** Text and accent surfaces. */
  white: '#FFFFFF',
  /**
   * Licorice - the near-black warm base. Deliberately NOT pure black: liquid
   * glass needs something with tone underneath it to refract, and pure black
   * makes the blur bands.
   */
  licorice: '#1B1212',
  /**
   * The page surface, a shade deeper than licorice so cards read as raised.
   *
   * These three are dashboard-only -- brand_palette.py has no equivalent,
   * because nothing in a rendered video needs a page background or a 1px
   * divider. They live here anyway so that brand.ts is the one place a colour
   * is written down; they used to exist only as literals inside the Tailwind
   * config and inside this test, which is how a surface colour ends up
   * unowned while the accent ramp is pinned.
   */
  base: '#0E0909',
  surfaceMuted: '#A396A3',
  border: '#3D3131',

  /**
   * The always-dark canvas: login, signup, and /review. Cooler and bluer than
   * `base` on purpose -- those screens carry a violet aurora, which reads as a
   * spotlight against a cool black and as a bruise against a warm one.
   *
   * This value existed as four separate literals -- `#050510` in
   * PublicNavFooter, `BRAND.base` on login/signup, and `#0f1220` on /review --
   * so three adjacent "dark" surfaces were three different blacks. Named once,
   * so a fourth cannot appear.
   *
   * The public marketing pages deliberately do NOT use this any more. They used
   * to, which is the whole reason light mode could never reach them: a hardcoded
   * dark on a themed `<body>`. They are now `bg-light-bg dark:bg-dark-bg`, so
   * light mode exists.
   *
   * KNOWN VISUAL DELTA, needs a human eye: in dark mode those pages now sit on
   * `DARK_THEME.bg` = `base` = #0E0909, a warmer black, rather than this
   * cooler #050510. `DARK_THEME.bg` was left alone deliberately -- repointing
   * it would move the background of every dashboard screen too, which is a far
   * larger unreviewed change. The marketing pages and the dashboard now share
   * one dark canvas, and it is the dashboard's.
   */
  canvas: '#050510',
} as const;

/**
 * ---------------------------------------------------------------------------
 * The two themes.
 * ---------------------------------------------------------------------------
 *
 * There used to be three theme systems that disagreed: `tailwind.config.js`
 * mapped `light.*` AND `dark.*` to the same dark values, `lib/theme.ts` held a
 * second "light theme" built from retired pre-rebrand colours, and the pre-paint
 * script force-wrote `dark` into localStorage on every load. Net effect: the
 * theme toggle flipped a class, the class changed nothing, and the next page
 * load overwrote the choice. A control that cannot change anything.
 *
 * `lib/theme.ts` is now gone and this is the only palette. `tailwind.config.js`
 * reads these two objects, and `brandTokens.test.ts` asserts (a) they still
 * agree with tailwind, (b) every text token clears WCAG AA against its own
 * surface, and (c) the two themes are actually different.
 *
 * ponytail: the light accents are *darkened* brand colours, not new ones.
 * #9B4DFF is the video palette and stays read-only; on white it measures
 * 4.03:1 and fails AA, so light mode uses #9148EF -- the same hue, 4.51:1.
 * Buttons in light mode therefore still read as brand purple. Solving for the
 * minimal shift rather than inventing a second palette is why there is one
 * brand and not two.
 */
export interface ThemeTokens {
  bg: string; card: string; text: string; muted: string; border: string;
  primary: string; secondary: string; accent: string;
  success: string; info: string; warning: string; error: string;
  borderStrong: string;
}

export const LIGHT_THEME: ThemeTokens = {
  /** Warm off-white. Not #FFF: a pure-white page makes the glass unseeable. */
  bg: '#FAF7FA',
  card: '#FFFFFF',
  /** Licorice. 17.3:1 on bg -- the dark theme's card colour, doing the same job. */
  text: '#1B1212',
  /** 4.53:1. Was #A396A3, which is 2.65:1 on white and unreadable. */
  muted: '#796F79',
  /** Card edges. Subtle by design; controls that need 3:1 get dark.border. */
  border: '#E7DEE9',
  /** 4.51:1 -- the same purple, one step down. */
  primary: '#9148EF',
  secondary: '#6641FC',
  /** 4.50:1. Was #F856A5 at 2.88:1. */
  accent: '#C14381',
  success: '#20815E',
  info: '#4474B0',
  warning: '#89700C',
  error: '#D13B31',
  /**
   * Input and control outlines. WCAG 1.4.11 wants 3:1 for the boundary of a
   * control, which a decorative card border does not. This is the one token
   * that has to work on both a page and a card.
   */
  borderStrong: '#9A8B9D',
} as const;

export const DARK_THEME: ThemeTokens = {
  bg: BRAND.base,
  card: BRAND.licorice,
  text: BRAND.white,
  muted: BRAND.surfaceMuted,
  border: BRAND.border,
  primary: BRAND.purple,
  secondary: BRAND.violet,
  accent: BRAND.pink,
  success: '#34D399',
  info: '#60A5FA',
  warning: '#FACC15',
  error: '#F04438',
  borderStrong: '#6C595B',
} as const;

export type ThemeName = 'light' | 'dark';
/** Alias kept because ThemeToggle and ThemeProvider import this name. */
export type ThemeMode = ThemeName;
export const THEMES: Record<ThemeName, ThemeTokens> = { light: LIGHT_THEME, dark: DARK_THEME };

/** WCAG 2.1 relative luminance. Exported so the contrast test and any future
 *  tooling compute it the same way instead of eyeballing it. */
export function relativeLuminance(hex: string): number {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG contrast ratio, 1..21. */
export function contrastRatio(a: string, b: string): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Retired hexes, kept so the drift test can assert they are gone. */
export const RETIRED_HEXES = [
  '#ec133e', '#bd0f32', '#f4718b',
  '#FF6969', '#FF4757', '#D4B896', '#0C1844', '#1A2248',
  '#4ECDC4', '#FF6B6B', '#8a50e8', '#f59e0b',
  // The crimson half of the old public-site CTA gradient. It survived the first
  // pass because the list was written from the button, not the ramp, so the
  // gradient's second stop was never on the forbidden list.
  '#C80036',
] as const;

/**
 * The one gradient. Drives the VYOMAI wordmark, primary CTAs, active nav,
 * agent/loading progress and the orbs behind the glass. Previously the app
 * had three competing gradients (aurora-bg, gradient-border, glass-panel)
 * plus eight copy-pasted button literals.
 */
export const BRAND_GRADIENT =
  `linear-gradient(90deg, ${BRAND.purple} 0%, ${BRAND.violet} 25%, ` +
  `${BRAND.pink} 55%, ${BRAND.orange} 80%, ${BRAND.lightOrange} 100%)`;

/** For CSS `background-image`. */
export const BRAND_GRADIENT_CSS = BRAND_GRADIENT;

/** Stops for ConicGradient / SVG / anything that needs the raw ramp. */
export const BRAND_GRADIENT_STOPS = [
  BRAND.purple, BRAND.violet, BRAND.pink, BRAND.orange, BRAND.lightOrange,
] as const;

export interface BrandOrb {
  color: string; size: string; opacity: number;
  top?: string; left?: string; right?: string; bottom?: string;
}

export const BRAND_ORBS: readonly BrandOrb[] = [
  { color: BRAND.purple, size: '55rem', opacity: 0.30, top: '-10%', left: '-5%' },
  { color: BRAND.violet, size: '45rem', opacity: 0.24, top: '20%', right: '-8%' },
  { color: BRAND.pink, size: '40rem', opacity: 0.16, bottom: '5%', left: '10%' },
  { color: BRAND.orange, size: '38rem', opacity: 0.14, bottom: '-12%', right: '5%' },
  { color: BRAND.lightOrange, size: '26rem', opacity: 0.10, top: '55%', left: '35%' },
];

/**
 * Type stack, matching www.vyomai.cloud exactly so the two sites read as one
 * company. Loaded via next/font in src/app/layout.tsx and exposed as
 * --font-display / --font-body / --font-mono.
 */
export const FONT_STACK = {
  display: '"Space Grotesk", system-ui, sans-serif',
  body: '"Plus Jakarta Sans", system-ui, sans-serif',
  mono: '"JetBrains Mono", ui-monospace, monospace',
} as const;

/** Contact. One constant - previously six hardcoded support@ addresses. */
export const CONTACT_EMAIL = 'info@vyomai.cloud';

/** Parent company. Timi is one product of Vyom Ai Cloud, not a separate brand. */
export const COMPANY = {
  legalName: 'Vyom A.I. Cloud Pvt.Ltd.',
  shortName: 'Vyom Ai Cloud',
  tagline: 'AI Solutions from Nepal to the World',
  productName: 'Timi',
} as const;

/**
 * Semantic status vocabulary.
 *
 * ponytail: `error` and `warning` are separate tokens on purpose. They used to
 * be aliased onto `primary` in Toast.tsx and StatusBadge.tsx, so re-theming
 * primary to purple would have turned every error message purple. And
 * `warning` sits at yellow-400 rather than amber-500 so it cannot be confused
 * with the brand's own orange at #FF8133.
 */
export const STATUS = {
  success: { label: 'Live', fg: '#34D399', bg: 'rgba(52,211,153,0.14)', border: 'rgba(52,211,153,0.34)' },
  info:    { label: 'Publishing', fg: '#60A5FA', bg: 'rgba(96,165,250,0.14)', border: 'rgba(96,165,250,0.34)' },
  warning: { label: 'Working', fg: '#FACC15', bg: 'rgba(250,204,21,0.14)', border: 'rgba(250,204,21,0.34)' },
  // Its own tone, deliberately. `pending_review` is not "in progress" -- the
  // render finished and a human is being asked to look at it. Sharing the
  // yellow "working" tone with `generating` is precisely the confusion this
  // vocabulary exists to remove.
  review:  { label: 'Needs review', fg: '#C99BFF', bg: 'rgba(155,77,255,0.16)', border: 'rgba(155,77,255,0.38)' },
  error:   { label: 'Failed', fg: '#F04438', bg: 'rgba(240,68,56,0.14)', border: 'rgba(240,68,56,0.34)' },
  muted:   { label: 'Idle', fg: '#A396A3', bg: 'rgba(163,150,163,0.12)', border: 'rgba(163,150,163,0.28)' },
} as const;

export type StatusTone = keyof typeof STATUS;

/**
 * The pipeline writes these into `videos.status`. Two fields matter and they
 * are not the same field:
 *
 *   videos.status      "pending_review" | "blocked_review" | "uploaded" | ...
 *   videos.review_status  "manual_review" | "auto_approve" | "block"
 *
 * Both were missing from archive/page.tsx's statusColors map, so a held video
 * fell through to the `generating` fallback and rendered as a yellow
 * "generating" badge. See src/__tests__/statusMeta.test.ts.
 */
export const STATUS_META: Record<string, { label: string; tone: StatusTone; hint?: string }> = {
  generating:          { label: 'Generating', tone: 'warning' },
  testing:             { label: 'Testing', tone: 'info' },
  pending_review:      { label: 'Needs review', tone: 'review', hint: 'Rendered and waiting on a person, not being worked on.' },
  blocked_review:      { label: 'Blocked by review', tone: 'error', hint: 'The review gate stopped this one.' },
  uploaded:            { label: 'Published', tone: 'success' },
  published:           { label: 'Published', tone: 'success' },
  scheduled:           { label: 'Scheduled', tone: 'info' },
  upload_failed:       { label: 'Upload failed', tone: 'error' },
  failed:              { label: 'Failed', tone: 'error' },
  blocked:             { label: 'Blocked', tone: 'error' },
  blocked_virality:    { label: 'Held: not viral enough', tone: 'review' },
  blocked_compliance:  { label: 'Held: failed safety check', tone: 'error' },
  render_only:         { label: 'Preview only', tone: 'muted', hint: 'Rendered, deliberately not published.' },
};

export const DEFAULT_STATUS_META = { label: 'Unknown', tone: 'muted' as StatusTone };

/**
 * Resolves a raw `videos.status` string. Never returns undefined, so a status
 * the pipeline invents later degrades to a visible "Unknown" badge rather than
 * silently borrowing another state's colour.
 */
export function statusMeta(status: string | undefined | null) {
  return STATUS_META[status ?? ''] ?? DEFAULT_STATUS_META;
}

/** Tailwind classes for a tone, kept here so no file re-invents them. */
export function statusClasses(status: string | undefined | null): string {
  const { tone } = statusMeta(status);
  const map: Record<StatusTone, string> = {
    success: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    info: 'bg-sky-500/20 text-sky-400 border-sky-500/30',
    warning: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    review: 'bg-violet-500/20 text-violet-300 border-violet-500/40',
    error: 'bg-red-500/20 text-red-400 border-red-500/30',
    muted: 'bg-white/5 text-white/60 border-white/15',
  };
  return map[tone];
}
