'use client';

import { useEffect, useState } from 'react';
import { auth } from '@/lib/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';

export default function Home() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user) {
        router.replace('/dashboard');
      } else {
        router.replace('/login');
      }
      setChecking(false);
    }, (error) => {
      console.error('Auth error:', error);
      router.replace('/login');
      setChecking(false);
    });
    return () => unsubscribe();
  }, [router]);

  if (checking) {
    return (
      <div className="min-h-screen relative overflow-hidden flex flex-col items-center justify-center gap-6" style={{ background: '#050510' }}>
        <ThemeToggle />

        <div className="absolute inset-0">
          <div className="absolute w-[600px] h-[600px] rounded-full opacity-10 blur-[100px]" style={{
            background: 'radial-gradient(circle, #FF6B6B, transparent 70%)',
            left: '20%', top: '30%',
          }} />
          <div className="absolute w-[500px] h-[500px] rounded-full opacity-10 blur-[100px]" style={{
            background: 'radial-gradient(circle, #4ECDC4, transparent 70%)',
            right: '20%', bottom: '20%',
          }} />
        </div>

        <motion.div
          initial={{ scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, type: 'spring' }}
          className="relative"
        >
          <div className="absolute inset-0 blur-xl opacity-40 rounded-full" style={{
            background: 'radial-gradient(circle, #FF6B6B, #4ECDC4, #FFD93D)',
          }} />
          <motion.div
            animate={{ y: [0, -8, 0], rotate: [0, 3, -3, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
            className="relative z-10"
          >
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={80} height={80} priority />
          </motion.div>
        </motion.div>

        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="w-10 h-10 border-4 border-teal-400 border-t-transparent rounded-full"
        />

        <p className="text-gray-400 font-medium text-sm">Loading Vyom Ai Cloud...</p>
      </div>
    );
  }

  return null;
}
