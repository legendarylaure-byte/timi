'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { auth } from '@/lib/firebase';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';
import { Play, TrendingUp, Music, Zap, Bot, Rocket, Shield, Lock, CheckCircle } from 'lucide-react';

const TAGLINES = [
  'Create AI-powered tech videos',
  'Publish across every platform',
  'Grow your educational audience',
  'Automate your content pipeline',
];

const FEATURES = [
  { icon: Play, title: 'AI Video Gen', desc: '9 agents working together', gradient: 'from-rose-400/20 to-pink-400/20' },
  { icon: TrendingUp, title: 'Auto Publishing', desc: 'YT, TikTok, FB, IG', gradient: 'from-orange-400/20 to-amber-400/20' },
  { icon: Music, title: 'Music & Voice', desc: 'AI-generated audio', gradient: 'from-purple-400/20 to-violet-400/20' },
  { icon: Zap, title: 'Trend Discovery', desc: 'AI-powered topics', gradient: 'from-yellow-400/20 to-orange-400/20' },
];

export default function LoginPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [taglineIdx, setTaglineIdx] = useState(0);
  const [cardTilt, setCardTilt] = useState({ x: 0, y: 0 });
  const [isHoveringCard, setIsHoveringCard] = useState(false);
  const [btnMagnetic, setBtnMagnetic] = useState({ x: 0, y: 0 });
  
  const cardRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setTaglineIdx(prev => (prev + 1) % TAGLINES.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const x = e.clientX / window.innerWidth;
    const y = e.clientY / window.innerHeight;
    setMousePos({ x, y });

    // Card tilt
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const rotateX = ((e.clientY - centerY) / (rect.height / 2)) * -8;
      const rotateY = ((e.clientX - centerX) / (rect.width / 2)) * 8;
      setCardTilt({ x: rotateX, y: rotateY });
    }

    // Magnetic button
    if (btnRef.current) {
      const rect = btnRef.current.getBoundingClientRect();
      const btnCenterX = rect.left + rect.width / 2;
      const btnCenterY = rect.top + rect.height / 2;
      const distX = e.clientX - btnCenterX;
      const distY = e.clientY - btnCenterY;
      const dist = Math.sqrt(distX * distX + distY * distY);
      if (dist < 150) {
        const pull = Math.max(0, 1 - dist / 150);
        setBtnMagnetic({ x: distX * pull * 0.15, y: distY * pull * 0.15 });
      } else {
        setBtnMagnetic({ x: 0, y: 0 });
      }
    }

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
    <div
      className="min-h-screen relative overflow-hidden flex items-center justify-center"
      onMouseMove={handleMouseMove}
      style={{
        backgroundColor: '#0C1844',
        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.05) 1px, transparent 0)',
        backgroundSize: '40px 40px',
      }}
    >
      <div className="fixed top-4 right-4 z-50"><ThemeToggle /></div>

      {/* Aurora glow */}
      {mounted && (
        <motion.div
          className="absolute inset-0 pointer-events-none"
          style={{
            background: `radial-gradient(ellipse at ${30 + mousePos.x * 40}% ${20 + mousePos.y * 30}%, rgba(255,105,105,0.15) 0%, transparent 50%)`,
          }}
          animate={{
            background: [
              `radial-gradient(ellipse at 30% 20%, rgba(255,105,105,0.15) 0%, transparent 50%)`,
              `radial-gradient(ellipse at 60% 40%, rgba(200,0,54,0.1) 0%, transparent 50%)`,
              `radial-gradient(ellipse at 30% 20%, rgba(255,105,105,0.15) 0%, transparent 50%)`,
            ],
          }}
          transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}
        />
      )}

      {/* Main content */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.8 }}
        className="relative z-10 w-full max-w-6xl mx-4 flex flex-col lg:flex-row items-center gap-8 lg:gap-20"
      >
        {/* Left side - Branding */}
        <motion.div
          initial={{ opacity: 0, x: -50 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, duration: 0.8, type: 'spring', stiffness: 100 }}
          className="flex-1 text-center lg:text-left"
        >
          {/* Floating logo */}
          <motion.div
            className="relative w-48 h-32 mx-auto lg:mx-0 mb-6"
            animate={{ y: [0, -10, 0], rotate: [0, 2, -1, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          >
            <Image
              src="/logo-vyomai.png"
              alt="Vyom Ai Cloud"
              fill
              className="object-contain drop-shadow-2xl"
              priority
            />
          </motion.div>

          {/* Title with shimmer */}
          <motion.h1
            className="text-5xl sm:text-6xl lg:text-7xl font-black mb-4 tracking-tight"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            style={{
              background: 'linear-gradient(135deg, #FF6969 0%, #C80036 50%, #FF6969 100%)',
              backgroundSize: '300% auto',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              animation: 'shimmer 3s ease-in-out infinite',
            }}
          >
            Vyom Ai Cloud
          </motion.h1>

          {/* Cycling tagline */}
          <div className="h-8 mb-8 overflow-hidden">
            <AnimatePresence mode="wait">
                <motion.p
                  key={taglineIdx}
                  className="text-xl text-red-200/80 font-medium max-w-md mx-auto lg:mx-0"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -30 }}
                transition={{ duration: 0.5, type: 'spring', stiffness: 200 }}
              >
                {TAGLINES[taglineIdx]}
              </motion.p>
            </AnimatePresence>
          </div>

          {/* Feature cards */}
          <div className="grid grid-cols-2 gap-3 max-w-md mx-auto lg:mx-0">
            {FEATURES.map((feature, i) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 30, scale: 0.9 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ delay: 0.7 + i * 0.1, type: 'spring', stiffness: 200 }}
                whileHover={{ y: -8, scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                className={`relative p-4 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm cursor-pointer overflow-hidden group`}
              >
                <motion.div
                  className={`absolute inset-0 bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
                />
                <div className="relative z-10">
                  <motion.div
                    className="mb-2"
                    whileHover={{ scale: 1.3, rotate: [0, -10, 10, 0] }}
                    transition={{ duration: 0.4 }}
                  >
                    <feature.icon className="w-7 h-7 text-red-300" />
                  </motion.div>
                  <h3 className="text-sm font-bold text-white">{feature.title}</h3>
                  <p className="text-xs text-red-200/60 mt-0.5">{feature.desc}</p>
                </div>
                <motion.div
                  className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-16 h-4 bg-orange-300/20 blur-xl rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
                />
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Right side - Login card */}
        <motion.div
          initial={{ opacity: 0, y: 50, rotateX: 10 }}
          animate={{ opacity: 1, y: 0, rotateX: 0 }}
          transition={{ delay: 0.5, duration: 0.8, type: 'spring', stiffness: 100 }}
          className="w-full max-w-md"
          style={{ perspective: '1000px' }}
        >
          <motion.div
            ref={cardRef}
            className="relative rounded-3xl overflow-hidden"
            animate={{
              rotateX: isHoveringCard ? cardTilt.x : 0,
              rotateY: isHoveringCard ? cardTilt.y : 0,
            }}
            transition={{ type: 'spring', stiffness: 150, damping: 15 }}
            onHoverStart={() => setIsHoveringCard(true)}
            onHoverEnd={() => setIsHoveringCard(false)}
            style={{
              background: 'linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.03))',
              backdropFilter: 'blur(40px)',
              border: '1px solid rgba(255,105,105,0.2)',
              boxShadow: isHoveringCard
                ? '0 35px 80px rgba(255,105,105,0.15), 0 15px 40px rgba(12,1,68,0.3)'
                : '0 25px 60px rgba(255,105,105,0.1), 0 10px 30px rgba(12,1,68,0.2)',
              transformStyle: 'preserve-3d',
            }}
          >
            {/* Animated gradient border */}
            <motion.div
              className="absolute inset-0 rounded-3xl opacity-40"
              style={{
                background: 'conic-gradient(from 0deg, #FF6969, #C80036, #0C1844, #FF6969, #C80036, #FF6969)',
                mask: 'linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0)',
                WebkitMaskComposite: 'xor',
                maskComposite: 'exclude',
                padding: '2px',
              }}
              animate={{ rotate: 360 }}
              transition={{ duration: 6, repeat: Infinity, ease: 'linear' }}
            />

            {/* Inner glow following mouse */}
            {isHoveringCard && (
              <motion.div
                className="absolute inset-0 pointer-events-none"
                style={{
                  background: `radial-gradient(600px circle at ${mousePos.x * 100}% ${mousePos.y * 100}%, rgba(255,105,105,0.12), transparent 40%)`,
                }}
              />
            )}

            <div className="relative z-10 p-8 sm:p-10" style={{ transform: 'translateZ(40px)' }}>
              {/* Welcome header */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 }}
                className="text-center mb-8"
              >
                  <motion.h2
                    className="text-3xl font-black text-white mb-2"
                    animate={{ scale: isHoveringCard ? [1, 1.02, 1] : 1 }}
                    transition={{ duration: 2, repeat: isHoveringCard ? Infinity : 0 }}
                  >
                    Welcome Back
                  </motion.h2>
                  <p className="text-sm text-red-200/60">Sign in to manage your AI video pipeline</p>
              </motion.div>

              {/* Error message */}
              <AnimatePresence>
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0, scale: 0.95 }}
                    animate={{ opacity: 1, height: 'auto', scale: 1 }}
                    exit={{ opacity: 0, height: 0, scale: 0.95 }}
                    className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Google login button */}
              <motion.button
                ref={btnRef}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={handleGoogleLogin}
                disabled={loading}
                className="relative w-full py-4 rounded-2xl font-bold text-white transition-all duration-300 disabled:opacity-50 overflow-hidden"
                style={{
                  background: 'linear-gradient(135deg, #FF6969, #C80036)',
                  backgroundSize: '200% auto',
                  boxShadow: '0 10px 30px rgba(255,105,105,0.3)',
                  transform: `translate(${btnMagnetic.x}px, ${btnMagnetic.y}px)`,
                }}
                animate={{
                  backgroundPosition: ['0% center', '100% center', '0% center'],
                }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <div className="relative z-10 flex items-center justify-center gap-3">
                  {loading ? (
                    <motion.div
                      className="flex items-center gap-3"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <Bot className="w-5 h-5" />
                      <span>Launching your workspace...</span>
                    </motion.div>
                  ) : (
                    <>
                      <motion.svg
                        className="w-5 h-5"
                        viewBox="0 0 24 24"
                        whileHover={{ rotate: [0, -10, 10, 0] }}
                        transition={{ duration: 0.4 }}
                      >
                        <path fill="white" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" opacity="0.8" />
                        <path fill="white" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" opacity="0.9" />
                        <path fill="white" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" opacity="0.9" />
                        <path fill="white" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" opacity="0.9" />
                      </motion.svg>
                      <span>Continue with Google</span>
                    </>
                  )}
                </div>
              </motion.button>

              {/* Divider */}
              <motion.div
                className="flex items-center gap-4 my-6"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.9 }}
              >
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-red-400/20 to-transparent" />
                <span className="text-xs text-red-200/40 font-medium">SECURED BY</span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-red-400/20 to-transparent" />
              </motion.div>

              {/* Security badges */}
              <motion.div
                className="flex items-center justify-center gap-6 text-xs text-stone-500"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1 }}
              >
                {[
                  { icon: Lock, label: 'Google Auth' },
                  { icon: Shield, label: 'Encrypted' },
                  { icon: CheckCircle, label: 'Secure' },
                ].map((item, i) => {
                  const BadgeIcon = item.icon;
                  return (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 1.1 + i * 0.1, type: 'spring', stiffness: 300 }}
                    className="flex items-center gap-1.5 hover:scale-110 transition-transform cursor-default"
                  >
                    <BadgeIcon className="w-3.5 h-3.5 text-red-300" />
                    <span className="text-red-200/60">{item.label}</span>
                  </motion.div>
                  );
                })}
              </motion.div>

              {/* Signup link */}
              <motion.p
                className="text-center mt-8 text-sm text-red-200/40"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.2 }}
              >
                Don&apos;t have an account?{' '}
                <Link href="/signup" className="text-red-400 hover:text-red-300 font-bold transition-colors relative group">
                  Create one
                  <span className="absolute -bottom-0.5 left-0 w-0 h-0.5 bg-red-400 group-hover:w-full transition-all duration-300" />
                </Link>
              </motion.p>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
