'use client';

import Image from 'next/image';
import Link from 'next/link';
import { onAuthStateChanged } from 'firebase/auth';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/firebase';

export default function PublicNavFooter({ children }: { children: React.ReactNode }) {
  const router = useRouter();
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
    <div className="min-h-screen relative overflow-hidden" style={{ background: '#050510' }}>
      {/* Aurora background */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute w-[800px] h-[800px] rounded-full opacity-[0.08] blur-[120px]"
          style={{ background: 'radial-gradient(circle, #FF6B6B, transparent 70%)', left: '10%', top: '-20%' }} />
        <div className="absolute w-[600px] h-[600px] rounded-full opacity-[0.06] blur-[120px]"
          style={{ background: 'radial-gradient(circle, #4ECDC4, transparent 70%)', right: '10%', bottom: '-10%' }} />
      </div>

      {/* Nav */}
      <nav className="relative z-40 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={36} height={36} />
          </Link>
          <Link href="/" className="text-white font-bold text-lg hover:text-white/80 transition-colors">
            Vyom Ai Cloud
          </Link>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-gray-400">
          <Link href="/" className="hover:text-white transition-colors">Home</Link>
          <Link href="/#features" className="hover:text-white transition-colors">Features</Link>
          <Link href="/about" className="hover:text-white transition-colors">About</Link>
          <Link href="/faq" className="hover:text-white transition-colors">FAQ</Link>
          <a href="mailto:support@vyomai.cloud" className="hover:text-white transition-colors">Contact</a>
        </div>
        <div className="flex items-center gap-3">
          {user ? (
            <button
              onClick={() => router.push('/dashboard')}
              className="px-5 py-2 rounded-xl font-semibold text-sm text-white transition-all duration-300"
              style={{
                background: 'linear-gradient(135deg, #FF6969, #C80036)',
                boxShadow: '0 4px 20px rgba(255,105,105,0.3)',
              }}
            >
              Go to Dashboard
            </button>
          ) : (
            <>
              <Link
                href="/login"
                className="px-4 py-2 rounded-xl text-sm text-gray-300 hover:text-white border border-white/10 hover:border-white/20 transition-all"
              >
                Sign In
              </Link>
              <Link
                href="/signup"
                className="px-5 py-2 rounded-xl font-semibold text-sm text-white transition-all duration-300"
                style={{
                  background: 'linear-gradient(135deg, #FF6969, #C80036)',
                  boxShadow: '0 4px 20px rgba(255,105,105,0.3)',
                }}
              >
                Get Started
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* Main content */}
      <main className="relative z-30">
        {children}
      </main>

      {/* Footer */}
      <footer className="relative z-30 border-t border-white/5 py-10 px-6 mt-16">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={24} height={24} />
            <span className="text-sm text-gray-500">&copy; {new Date().getFullYear()} Vyom Ai Cloud. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6 text-sm flex-wrap justify-center">
            <Link href="/" className="text-gray-500 hover:text-gray-300 transition-colors">Home</Link>
            <Link href="/about" className="text-gray-500 hover:text-gray-300 transition-colors">About</Link>
            <Link href="/faq" className="text-gray-500 hover:text-gray-300 transition-colors">FAQ</Link>
            <a href="mailto:support@vyomai.cloud" className="text-gray-500 hover:text-gray-300 transition-colors">Contact</a>
            <Link href="/terms" className="text-gray-500 hover:text-gray-300 transition-colors">Terms</Link>
            <Link href="/privacy" className="text-gray-500 hover:text-gray-300 transition-colors">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
