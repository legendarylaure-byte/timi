'use client';

import { useState, useEffect } from 'react';
import { auth } from '@/lib/firebase';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';

interface FloatingOrb {
  id: number;
  x: number;
  y: number;
  size: number;
  color: string;
  duration: number;
  delay: number;
}

const features = [
  { icon: '🎬', title: 'AI Video Generation', desc: '9 agents working together' },
  { icon: '📈', title: 'Auto Publishing', desc: 'YouTube, TikTok, Facebook' },
  { icon: '🌍', title: 'Multi-Language', desc: 'Reach global audiences' },
  { icon: '🔥', title: 'Trend Discovery', desc: 'AI-powered topic finding' },
];

const orbs: FloatingOrb[] = [
  { id: 1, x: 10, y: 15, size: 350, color: 'rgba(255,182,193,0.4)', duration: 8, delay: 0 },
  { id: 2, x: 65, y: 25, size: 280, color: 'rgba(255,218,185,0.35)', duration: 10, delay: 2 },
  { id: 3, x: 35, y: 70, size: 320, color: 'rgba(255,223,186,0.3)', duration: 12, delay: 4 },
  { id: 4, x: 80, y: 75, size: 200, color: 'rgba(255,192,203,0.25)', duration: 9, delay: 1 },
  { id: 5, x: 20, y: 50, size: 180, color: 'rgba(255,165,0,0.15)', duration: 11, delay: 3 },
];

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleGoogleLogin = async () => {
    setLoading(true);
    setError('');
    try {
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      if (result.user) {
        router.replace('/dashboard');
      }
    } catch (err: any) {
      if (err.code !== 'auth/popup-closed-by-user') {
        setError(err.code === 'auth/unauthorized-domain'
          ? 'Domain not authorized. Add localhost to Firebase Console.'
          : err.message || 'Login failed. Please try again.'
        );
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen relative overflow-hidden flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #FFF5F0 0%, #FFE8D6 30%, #FFF0E6 60%, #FFDAB9 100%)' }}>
      <div className="fixed top-4 right-4 z-50"><ThemeToggle /></div>

      {/* Animated background orbs */}
      {mounted && orbs.map((orb) => (
        <motion.div
          key={orb.id}
          className="absolute rounded-full blur-3xl"
          style={{
            width: orb.size,
            height: orb.size,
            background: orb.color,
            left: `${orb.x}%`,
            top: `${orb.y}%`,
          }}
          animate={{
            x: [0, 50, -30, 0],
            y: [0, -40, 30, 0],
            scale: [1, 1.15, 0.9, 1],
          }}
          transition={{
            duration: orb.duration,
            repeat: Infinity,
            delay: orb.delay,
            ease: 'easeInOut',
          }}
        />
      ))}

      {/* Subtle sparkle dots */}
      {mounted && Array.from({ length: 20 }).map((_, i) => (
        <motion.div
          key={`sparkle-${i}`}
          className="absolute rounded-full"
          style={{
            width: 4 + Math.random() * 6,
            height: 4 + Math.random() * 6,
            background: ['rgba(255,182,193,0.6)', 'rgba(255,218,185,0.5)', 'rgba(255,165,0,0.4)', 'rgba(255,255,255,0.7)'][i % 4],
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
          }}
          animate={{
            opacity: [0.3, 1, 0.3],
            scale: [0.8, 1.2, 0.8],
          }}
          transition={{
            duration: 2 + Math.random() * 3,
            repeat: Infinity,
            delay: Math.random() * 4,
            ease: 'easeInOut',
          }}
        />
      ))}

      {/* Main content */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.6 }}
        className="relative z-10 w-full max-w-6xl mx-4 flex flex-col lg:flex-row items-center gap-8 lg:gap-20"
      >
        {/* Left side - Branding */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.6 }}
          className="flex-1 text-center lg:text-left"
        >
          {/* Logo image */}
          <div className="relative w-48 h-32 mx-auto lg:mx-0 mb-6">
            <Image
              src="/logo-vyomai.png"
              alt="Vyom Ai Cloud"
              fill
              className="object-contain drop-shadow-lg"
              priority
            />
          </div>

          <h1 className="text-4xl sm:text-5xl font-black mb-4 tracking-tight" style={{
            background: 'linear-gradient(135deg, #FF6B6B 0%, #FF8E53 40%, #FFB347 70%, #FF69B4 100%)',
            backgroundSize: '200% auto',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            animation: 'shimmer 4s ease-in-out infinite',
          }}>
            Vyom Ai Cloud
          </h1>
          <p className="text-lg text-stone-600 mb-8 max-w-md mx-auto lg:mx-0">
            AI-powered video creation pipeline. From script to publish, fully automated.
          </p>

          {/* Features grid */}
          <div className="grid grid-cols-2 gap-3 max-w-md mx-auto lg:mx-0">
            {features.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.4 + i * 0.1 }}
                className="p-3 rounded-xl bg-white/60 border border-orange-200/40 hover:border-orange-300/60 transition-colors backdrop-blur-sm"
              >
                <span className="text-2xl">{feature.icon}</span>
                <h3 className="text-sm font-semibold text-stone-800 mt-1">{feature.title}</h3>
                <p className="text-xs text-stone-500">{feature.desc}</p>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Right side - Login card */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="relative rounded-3xl overflow-hidden" style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.85), rgba(255,248,240,0.9))',
            backdropFilter: 'blur(40px)',
            border: '1px solid rgba(255,182,193,0.3)',
            boxShadow: '0 25px 60px rgba(255,140,66,0.15), 0 10px 30px rgba(255,182,193,0.1)',
          }}>
            {/* Animated gradient border */}
            <div className="absolute inset-0 rounded-3xl opacity-30" style={{
              background: 'conic-gradient(from 0deg, #FFB6C1, #FFA07A, #FFD700, #FF69B4, #FFA07A, #FFB6C1)',
              animation: 'spin 8s linear infinite',
              mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
              WebkitMaskComposite: 'xor',
              maskComposite: 'exclude',
              padding: '1px',
            }} />

            <div className="relative z-10 p-8 sm:p-10">
              <h2 className="text-2xl font-bold text-stone-800 mb-2">Welcome Back</h2>
              <p className="text-sm text-stone-500 mb-8">Sign in to continue your creative journey</p>

              {/* Error message */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Google login button */}
              <motion.button
                whileHover={{ scale: 1.02, boxShadow: '0 10px 30px rgba(255,107,107,0.3)' }}
                whileTap={{ scale: 0.98 }}
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full py-4 rounded-2xl font-semibold text-white transition-all duration-300 disabled:opacity-50"
                style={{ background: 'linear-gradient(135deg, #FF6B6B, #FF8E53)' }}
              >
                <div className="flex items-center justify-center gap-3">
                  {loading ? (
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                      className="w-5 h-5 border-2 border-white border-t-transparent rounded-full"
                    />
                  ) : (
                    <>
                      <svg className="w-5 h-5" viewBox="0 0 24 24">
                        <path fill="white" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" opacity="0.8" />
                        <path fill="white" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" opacity="0.9" />
                        <path fill="white" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" opacity="0.9" />
                        <path fill="white" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" opacity="0.9" />
                      </svg>
                      <span>Continue with Google</span>
                    </>
                  )}
                </div>
              </motion.button>

              {/* Security badges */}
              <div className="flex items-center justify-center gap-6 mt-8 text-xs text-stone-500">
                {[
                  { label: 'Google Auth', color: 'bg-green-400' },
                  { label: 'Encrypted', color: 'bg-orange-400' },
                  { label: 'Secure', color: 'bg-pink-400' },
                ].map((item, i) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.6 + i * 0.1 }}
                    className="flex items-center gap-2"
                  >
                    <span className={`w-2 h-2 rounded-full ${item.color}`} />
                    <span>{item.label}</span>
                  </motion.div>
                ))}
              </div>

              {/* Signup link */}
              <p className="text-center mt-8 text-sm text-stone-500">
                Don&apos;t have an account?{' '}
                <Link href="/signup" className="text-orange-500 hover:text-orange-600 font-medium transition-colors">
                  Create one
                </Link>
              </p>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </div>
  );
}
