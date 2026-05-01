'use client';

import { useState, useEffect, useRef } from 'react';
import { auth } from '@/lib/firebase';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';

interface Particle {
  id: number;
  x: number;
  y: number;
  size: number;
  speed: number;
  color: string;
  opacity: number;
}

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mousePos, setMousePos] = useState({ x: 0.5, y: 0.5 });
  const [particles, setParticles] = useState<Particle[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const newParticles: Particle[] = Array.from({ length: 30 }, (_, i) => ({
      id: i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      size: Math.random() * 3 + 1,
      speed: Math.random() * 2 + 1,
      color: ['#FF4D6D', '#7C3AED', '#3B82F6', '#10B981', '#FBBF24'][i % 5],
      opacity: Math.random() * 0.5 + 0.2,
    }));
    setParticles(newParticles);
  }, []);

  useEffect(() => {
    const handleMouse = (e: MouseEvent) => {
      const x = e.clientX / window.innerWidth;
      const y = e.clientY / window.innerHeight;
      setMousePos({ x, y });

      setParticles((prev) =>
        prev.map((p) => {
          const dx = e.clientX - (p.x / 100) * window.innerWidth;
          const dy = e.clientY - (p.y / 100) * window.innerHeight;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            return { ...p, size: Math.min(p.size + 0.5, 6), opacity: Math.min(p.opacity + 0.2, 0.8) };
          }
          return { ...p, size: Math.max(p.size - 0.1, 1), opacity: Math.max(p.opacity - 0.05, 0.2) };
        })
      );
    };
    window.addEventListener('mousemove', handleMouse);
    return () => window.removeEventListener('mousemove', handleMouse);
  }, []);

  const handleGoogleSignup = async () => {
    setLoading(true);
    setError('');
    try {
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      if (result.user) {
        router.push('/dashboard');
      }
    } catch (err: any) {
      if (err.code === 'auth/popup-closed-by-user') {
        setError('');
      } else {
        setError(err.message || 'Signup failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const features = [
    { icon: '✨', label: '9 AI Agents' },
    { icon: '🚀', label: 'Daily Uploads' },
    { icon: '💎', label: '100% Free' },
  ];

  return (
    <div ref={containerRef} className="min-h-screen relative overflow-hidden flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #0B0F1A 0%, #151B2B 50%, #0B0F1A 100%)' }}>
      <ThemeToggle />

      {/* Aurora animated background */}
      <div className="absolute inset-0 aurora-bg opacity-20 blur-3xl" />

      {/* Gradient orbs following mouse */}
      <div className="absolute inset-0 pointer-events-none">
        <motion.div
          className="absolute w-[600px] h-[600px] rounded-full blur-[120px]"
          style={{
            background: 'radial-gradient(circle, rgba(255,77,109,0.3), transparent 70%)',
            left: `${mousePos.x * 80 - 10}%`,
            top: `${mousePos.y * 60 - 10}%`,
            transition: 'left 0.8s ease-out, top 0.8s ease-out',
          }}
        />
        <motion.div
          className="absolute w-[500px] h-[500px] rounded-full blur-[100px]"
          style={{
            background: 'radial-gradient(circle, rgba(124,58,237,0.25), transparent 70%)',
            right: `${(1 - mousePos.x) * 60 - 5}%`,
            bottom: `${(1 - mousePos.y) * 50 - 5}%`,
            transition: 'right 0.8s ease-out, bottom 0.8s ease-out',
          }}
        />
        <motion.div
          className="absolute w-[400px] h-[400px] rounded-full blur-[80px]"
          style={{
            background: 'radial-gradient(circle, rgba(251,191,36,0.2), transparent 70%)',
            left: '40%',
            top: '20%',
            animation: 'blobMorph 8s ease-in-out infinite',
          }}
        />
      </div>

      {/* Morphing blob shapes */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 -left-20 w-72 h-72 bg-light-primary/10 dark:bg-light-primary/5 blur-3xl" style={{ animation: 'blobMorph 8s ease-in-out infinite' }} />
        <div className="absolute bottom-20 -right-20 w-80 h-80 bg-light-secondary/10 dark:bg-light-secondary/5 blur-3xl" style={{ animation: 'blobMorph 10s ease-in-out infinite reverse' }} />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-light-accent/5 blur-3xl" style={{ animation: 'blobMorph 12s ease-in-out infinite' }} />
      </div>

      {/* Floating interactive particles */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {particles.map((p) => (
          <motion.div
            key={p.id}
            className="absolute rounded-full"
            style={{
              width: p.size,
              height: p.size,
              background: p.color,
              left: `${p.x}%`,
              top: `${p.y}%`,
              opacity: p.opacity,
            }}
            animate={{
              y: [0, -20 * p.speed, 0],
              x: [0, 10 * p.speed * (p.id % 2 === 0 ? 1 : -1), 0],
              scale: [1, 1.5, 1],
            }}
            transition={{
              duration: 3 + p.speed,
              repeat: Infinity,
              delay: p.id * 0.1,
              ease: 'easeInOut',
            }}
          />
        ))}
      </div>

      {/* Subtle grid */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: 'linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)',
        backgroundSize: '80px 80px',
      }} />

      {/* Main content */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 w-full max-w-md px-4"
      >
        <motion.div
          initial={{ y: 40, scale: 0.95 }}
          animate={{ y: 0, scale: 1 }}
          transition={{ duration: 0.6, delay: 0.2, type: 'spring' }}
          className="relative rounded-3xl overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02))',
            backdropFilter: 'blur(40px)',
            border: '1px solid rgba(255,255,255,0.1)',
          }}
        >
          {/* Rotating gradient border */}
          <div className="absolute inset-0 rounded-3xl opacity-50" style={{
            background: 'conic-gradient(from 0deg, #FF4D6D, #7C3AED, #3B82F6, #10B981, #FBBF24, #FF4D6D)',
            animation: 'spin 8s linear infinite',
            mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
            maskComposite: 'exclude',
            WebkitMaskComposite: 'xor',
            padding: '1px',
          }} />

          <div className="relative z-10 p-8 sm:p-10">
            {/* Logo */}
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ delay: 0.4, type: 'spring', stiffness: 200, duration: 0.8 }}
              className="text-center mb-8"
            >
              <div className="relative w-20 h-20 mx-auto mb-6">
                <div className="absolute inset-0 blur-xl opacity-40" style={{
                  background: 'linear-gradient(135deg, #FF4D6D, #7C3AED, #3B82F6)',
                  animation: 'pulse 3s ease-in-out infinite',
                }} />
                <motion.div
                  animate={{ y: [0, -6, 0], rotate: [0, 3, -3, 0] }}
                  transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
                  className="relative"
                >
                  <Image src="/logo.svg" alt="Vyom Ai Cloud" width={80} height={80} priority />
                </motion.div>
              </div>

              <h1 className="text-4xl font-black mb-2 tracking-tight" style={{
                background: 'linear-gradient(135deg, #FFFFFF 0%, #FF4D6D 25%, #7C3AED 50%, #3B82F6 75%, #10B981 100%)',
                backgroundSize: '200% auto',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                animation: 'shimmer 4s ease-in-out infinite',
              }}>
                Vyom Ai Cloud
              </h1>
              <p className="text-light-muted dark:text-dark-muted text-sm">Create. Automate. Inspire.</p>
            </motion.div>

            {/* Error */}
            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="mb-6 p-4 rounded-xl bg-light-primary/10 border border-light-primary/20 text-light-primary text-sm"
                >
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Google button */}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleGoogleSignup}
              disabled={loading}
              className="group relative w-full py-4 rounded-2xl font-semibold text-white overflow-hidden transition-all duration-300 disabled:opacity-50"
              style={{
                background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)',
              }}
            >
              <div className="absolute inset-0 bg-gradient-to-r from-light-primary via-light-accent to-light-secondary opacity-0 group-hover:opacity-80 transition-opacity blur-xl" />
              <div className="relative flex items-center justify-center gap-3">
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

            {/* Features */}
            <div className="mt-8 grid grid-cols-3 gap-3">
              {features.map((item, i) => (
                <motion.div
                  key={item.label}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.6 + i * 0.1 }}
                  whileHover={{ scale: 1.05 }}
                  className="text-center p-3 rounded-xl bg-white/5 border border-white/10"
                >
                  <div className="w-8 h-8 mx-auto mb-2 rounded-full bg-gradient-to-br from-light-primary/20 to-light-secondary/20 flex items-center justify-center">
                    <span className="text-sm">{item.icon}</span>
                  </div>
                  <p className="text-xs text-light-muted dark:text-dark-muted">{item.label}</p>
                </motion.div>
              ))}
            </div>

            {/* Login link */}
            <p className="text-center mt-8 text-sm text-light-muted dark:text-dark-muted">
              Already have an account?{' '}
              <Link href="/login" className="text-light-primary hover:text-light-secondary font-medium transition-colors">
                Sign in
              </Link>
            </p>
          </div>
        </motion.div>

        {/* Bottom glow */}
        <div className="absolute -bottom-20 left-1/2 -translate-x-1/2 w-64 h-40 rounded-full blur-3xl opacity-20" style={{
          background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)',
        }} />
      </motion.div>
    </div>
  );
}
