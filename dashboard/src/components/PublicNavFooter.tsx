'use client';

import Image from 'next/image';
import Link from 'next/link';
import { onAuthStateChanged } from 'firebase/auth';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/firebase';
import { useGoToDashboard } from '@/lib/auth-nav';
import { CONTACT_EMAIL } from '@/lib/brand';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

export default function PublicNavFooter({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const goToDashboard = useGoToDashboard();
  const [user, setUser] = useState<any>(null);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setAuthChecked(true);
    });
    return () => unsubscribe();
  }, []);

  return (
    // This shell is the canvas for /about, /faq, /privacy and /terms. It was
    // `style={{ background: BRAND.canvas }}` -- a hardcoded dark -- while
    // <body> is themed, so those four pages were dark-only by construction and
    // could not join the light theme no matter what the toggle did. Tokenised
    // now; BRAND.canvas survives only for the auth/review pages, which are
    // deliberately always-dark.
    <div className="min-h-screen relative overflow-hidden bg-light-bg dark:bg-dark-bg">
      {/* Aurora background. Alpha is low enough (0.08 / 0.06) to read as a tint
          rather than a stain on the light canvas, so it needs no veil here --
          unlike AmbientBackground, which is rendering orbs, not a two-stop wash. */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute w-[800px] h-[800px] rounded-full opacity-[0.08] blur-[120px]"
          style={{ background: 'radial-gradient(circle, #FF8133, transparent 70%)', left: '10%', top: '-20%' }} />
        <div className="absolute w-[600px] h-[600px] rounded-full opacity-[0.06] blur-[120px]"
          style={{ background: 'radial-gradient(circle, #6641FC, transparent 70%)', right: '10%', bottom: '-10%' }} />
      </div>

      {/* Nav */}
      <nav className="relative z-40 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={36} height={36} />
          </Link>
          <Link href="/" className="text-light-text dark:text-white font-bold text-lg hover:text-light-primary dark:hover:text-white transition-colors">
            Vyom Ai Cloud
          </Link>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-light-muted dark:text-gray-400">
          <Link href="/" className="hover:text-light-text dark:hover:text-white transition-colors">Home</Link>
          <Link href="/#features" className="hover:text-light-text dark:hover:text-white transition-colors">Features</Link>
          <Link href="/about" className="hover:text-light-text dark:hover:text-white transition-colors">About</Link>
          <Link href="/faq" className="hover:text-light-text dark:hover:text-white transition-colors">FAQ</Link>
          <a href={`mailto:${CONTACT_EMAIL}`} className="hover:text-light-text dark:hover:text-white transition-colors">Contact</a>
        </div>
        <div className="flex items-center gap-3">
          {!authChecked ? (
            <div className="px-5 py-2 rounded-xl bg-light-border dark:bg-white/10 animate-pulse" aria-hidden />
          ) : user ? (
            <button
              onClick={goToDashboard}
              className="btn-primary"
            >
              Go to Dashboard
            </button>
          ) : (
            <>
              {/* Always visible, not behind the md: breakpoint -- a theme
                  control that only exists on desktop is a theme control most
                  visitors never see. */}
              <ThemeToggle />
              <Link
                href="/login"
                className="px-4 py-2 rounded-xl text-sm text-light-muted dark:text-gray-300 hover:text-light-text dark:hover:text-white border border-light-border dark:border-white/10 hover:border-light-border-strong dark:hover:border-white/20 transition-all"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="btn-primary"
              >
                Get Started
              </Link>
            </>
          )}
          {/* Signed-in visitors get the toggle too: it used to live only in the
              signed-out branch, so a logged-in user could not switch theme on
              any public page. */}
          {authChecked && user && <ThemeToggle />}
        </div>
      </nav>

      {/* Main content */}
      <main className="relative z-30">
        {children}
      </main>

      {/* Footer */}
      <footer className="relative z-30 border-t border-light-border dark:border-white/5 py-10 px-6 mt-16">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={24} height={24} />
            <span className="text-sm text-light-muted dark:text-dark-muted">&copy; {new Date().getFullYear()} Vyom Ai Cloud. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6 text-sm flex-wrap justify-center">
            <Link href="/" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">Home</Link>
            <Link href="/about" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">About</Link>
            <Link href="/faq" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">FAQ</Link>
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">Contact</a>
            <Link href="/terms" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">Terms</Link>
            <Link href="/privacy" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-gray-300 transition-colors">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
