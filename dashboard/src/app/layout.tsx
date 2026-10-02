import type { Metadata } from 'next';
import { Space_Grotesk, Plus_Jakarta_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { ToastProvider } from '@/components/ui/Toast';
import { ThemeProvider } from '@/components/ThemeProvider';

// The same three faces www.vyomai.cloud uses, loaded through next/font so they
// are self-hosted (no third-party request, no layout shift, and they resolve
// the same way in the container and in CI). Exposed as CSS variables because
// tailwind.config.js cannot import this file.
const display = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
  weight: ['500', '600', '700'],
});

const body = Plus_Jakarta_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
  weight: ['400', '500', '600', '700'],
});

const mono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
  weight: ['400', '500'],
});

export const metadata: Metadata = {
  title: 'Timi — by Vyom Ai Cloud',
  description:
    'Timi turns verified news and pillar topics into researched, narrated, and published video — from Nepal.',
  applicationName: 'Timi',
  keywords: ['AI video automation', 'Vyom Ai Cloud', 'content automation', 'Nepal'],
  icons: {
    icon: [{ url: '/favicon.svg', type: 'image/svg+xml' }, { url: '/favicon.png', sizes: '32x32' }],
    apple: '/favicon.png',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // `className="dark"` is only a *first guess* for the no-JS / no-storage
    // case. The pre-paint script below overwrites it from localStorage before
    // paint, so a light-mode user never sees a dark frame.
    <html lang="en" className={`dark ${display.variable} ${body.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                // READ-ONLY on purpose. The previous version did
                // localStorage.setItem('theme', 'dark') unconditionally, which
                // meant the light theme could not survive a page load -- the
                // toggle appeared to work, then the next navigation reverted it.
                // That is the bug this script used to cause.
                var KEY = 'timi.theme';
                var mode = null;
                try { var v = localStorage.getItem(KEY); if (v === 'light' || v === 'dark') mode = v; } catch (e) {}
                if (!mode) {
                  try { mode = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'; } catch (e) { mode = 'dark'; }
                }
                var el = document.documentElement;
                el.classList.toggle('dark', mode === 'dark');
                el.style.colorScheme = mode;
                el.dataset.theme = mode;
              })();
            `,
          }}
        />
      </head>
      <body className="min-h-screen antialiased font-sans">
        {/* ThemeProvider outermost: it resolves the theme and owns the
            reduced-motion wrapper, so everything inside it (including toasts)
            inherits both. Rendering {children} in two places would mount the
            whole app twice. */}
        <ThemeProvider>
          <ToastProvider>{children}</ToastProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
