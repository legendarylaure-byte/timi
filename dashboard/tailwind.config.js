/** @type {import('tailwindcss').Config} */
// ponytail: the palette is retyped here rather than imported, because a CJS
// config cannot require() a .ts file. That duplication is deliberate and is
// asserted equal to src/lib/brand.ts by brandTokens.test.ts, which is what makes
// it safe. Do not 'fix' it by inlining a second copy of the numbers into the
// test -- the test derives from brand.ts, so one side is never hand-copied.
module.exports = {
  darkMode: 'class',
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      // Two real themes, both read from src/lib/brand.ts.
      //
      // There are ~2,900 `light-*` / `dark:*` utility usages in this codebase
      // and rewriting them file by file is a diff nobody can review. The class
      // *structure* was always correct for two themes -- `bg-light-bg
      // dark:bg-dark-bg` picks the right surface once the two namespaces hold
      // different values -- so the only change needed was to stop forcing them
      // to be identical.
      //
      // It used to: both namespaces resolved to the same dark palette, a second
      // palette lived unused in src/lib/theme.ts, and the pre-paint script
      // force-wrote `dark` to localStorage. The theme toggle therefore changed
      // nothing at all.
      //
      // The light accents are darkened brand colours, not new hues, so buttons
      // still read as the brand purple while text clears WCAG AA on white.
      // See LIGHT_THEME in src/lib/brand.ts and the contrast assertions in
      // src/__tests__/brandTokens.test.ts -- change one, change both.
      colors: {
        light: {
          bg: '#FAF7FA',
          card: '#FFFFFF',
          primary: '#9148EF',
          secondary: '#6641FC',
          accent: '#C14381',
          success: '#20815E',
          info: '#4474B0',
          warning: '#89700C',
          error: '#D13B31',
          text: '#1B1212',
          muted: '#796F79',
          border: '#E7DEE9',
          'border-strong': '#9A8B9D',
        },
        dark: {
          bg: '#0E0909',
          card: '#1B1212',
          primary: '#9B4DFF',
          secondary: '#6641FC',
          accent: '#F856A5',
          success: '#34D399',
          info: '#60A5FA',
          warning: '#FACC15',
          error: '#F04438',
          text: '#FFFFFF',
          muted: '#A396A3',
          border: '#3D3131',
          'border-strong': '#6C595B',
        },
      },
      fontFamily: {
        // Loaded in src/app/layout.tsx via next/font, matching
        // www.vyomai.cloud so the two sites read as one company.
        sans: ['var(--font-body)', 'system-ui', 'sans-serif'],
        display: ['var(--font-display)', 'system-ui', 'sans-serif'],
        mono: ['var(--font-mono)', 'ui-monospace', 'monospace'],
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'float-slow': 'float 8s ease-in-out infinite',
        'bounce-slow': 'bounce 3s ease-in-out infinite',
        'spin-slow': 'spin 20s linear infinite',
        'aurora': 'aurora 15s ease-in-out infinite',
        'shimmer': 'shimmer 3s ease-in-out infinite',
        'slide-up': 'slideUp 0.5s ease-out',
        'slide-in-right': 'slideInRight 0.4s ease-out',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-20px)' },
        },
        aurora: {
          '0%, 100%': { backgroundPosition: '0% 50%' },
          '25%': { backgroundPosition: '100% 50%' },
          '50%': { backgroundPosition: '100% 100%' },
          '75%': { backgroundPosition: '0% 100%' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(40px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      boxShadow: {
        // Retired: glow-red / glow-navy / glow-crimson. Kept as violet glows
        // rather than deleted because ~30 files reference `shadow-glow-red`
        // and renaming them all is a bigger diff than recolouring here.
        'glow-red': '0 0 20px rgba(155, 77, 255, 0.4)',
        'glow-navy': '0 0 20px rgba(102, 65, 252, 0.4)',
        'glow-crimson': '0 0 20px rgba(248, 86, 165, 0.4)',
        'glow-emerald': '0 0 20px rgba(52, 211, 153, 0.4)',
        'glow-blue': '0 0 20px rgba(96, 165, 250, 0.4)',
        glass: '0 1px 0 0 rgba(255,255,255,0.06) inset, 0 8px 32px rgba(0,0,0,0.36)',
      },
      backgroundImage: {
        // One gradient, one definition. The old file had five, three of which
        // were crimson ramps, and components picked between them at random.
        'gradient-primary': 'linear-gradient(135deg, #9B4DFF, #6641FC)',
        'gradient-warm': 'linear-gradient(135deg, #FF8133, #FFB05F)',
        'gradient-cool': 'linear-gradient(135deg, #6641FC, #F856A5)',
        'gradient-success': 'linear-gradient(135deg, #34D399, #60A5FA)',
        'gradient-aurora': 'linear-gradient(90deg, #9B4DFF 0%, #6641FC 25%, #F856A5 55%, #FF8133 80%, #FFB05F 100%)',
      },
    },
  },
  plugins: [],
};
