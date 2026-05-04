'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { auth } from '@/lib/firebase';
import { signInWithPopup, GoogleAuthProvider } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';

const TAGLINES = [
  '9 AI Agents at your service ✨',
  'Daily content creation 🚀',
  '100% Free, Local AI 💎',
  'From script to publish 🎬',
];

const PERKS = [
  { icon: '✨', title: '9 AI Agents', desc: 'Script to publish, automated', gradient: 'from-rose-400/20 to-pink-400/20' },
  { icon: '🚀', title: 'Daily Content', desc: 'Shorts + long-form videos', gradient: 'from-orange-400/20 to-amber-400/20' },
  { icon: '💎', title: '100% Free', desc: 'Local AI, no API costs', gradient: 'from-purple-400/20 to-violet-400/20' },
];

const FLOATING_EMOJIS = ['🎬', '🎵', '🎨', '⚡', '🌟', '🚀', '💎', '🎭'];

interface Ripple {
  id: number;
  x: number;
  y: number;
}

export default function SignupPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [taglineIdx, setTaglineIdx] = useState(0);
  const [cardTilt, setCardTilt] = useState({ x: 0, y: 0 });
  const [isHoveringCard, setIsHoveringCard] = useState(false);
  const [ripples, setRipples] = useState<Ripple[]>([]);
  const [btnMagnetic, setBtnMagnetic] = useState({ x: 0, y: 0 });
  const [cursorTrail, setCursorTrail] = useState<{ id: number; x: number; y: number }[]>([]);

  const cardRef = useRef<HTMLDivElement>(null);
  const btnRef = useRef<HTMLButtonElement>(null);
  const rippleId = useRef(0);
  const trailId = useRef(0);

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

    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      const centerX = rect.left + rect.width / 2;
      const centerY = rect.top + rect.height / 2;
      const rotateX = ((e.clientY - centerY) / (rect.height / 2)) * -8;
      const rotateY = ((e.clientX - centerX) / (rect.width / 2)) * 8;
      setCardTilt({ x: rotateX, y: rotateY });
    }

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

    if (Math.random() > 0.7) {
      const newDot = { id: trailId.current++, x: e.clientX, y: e.clientY };
      setCursorTrail(prev => [...prev.slice(-8), newDot]);
      setTimeout(() => {
        setCursorTrail(prev => prev.slice(1));
      }, 800);
    }
  }, []);

  const handleRipple = (e: React.MouseEvent<HTMLButtonElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const newRipple = { id: rippleId.current++, x: e.clientX - rect.left, y: e.clientY - rect.top };
    setRipples(prev => [...prev, newRipple]);
    setTimeout(() => {
      setRipples(prev => prev.filter(r => r.id !== newRipple.id));
    }, 600);
  };

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
      if (err.code !== 'auth/popup-closed-by-user') {
        setError(err.message || 'Signup failed. Please try again.');
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
        background: 'linear-gradient(135deg, #FFF7F0 0%, #FFE8D6 25%, #FFD4B8 50%, #FFCBA4 75%, #FFF0E6 100%)',
      }}
    >
      <div className="fixed top-4 right-4 z-50"><ThemeToggle /></div>

      {/* Cursor trail */}
      {mounted && cursorTrail.map((dot, i) => (
        <motion.div
          key={dot.id}
          className="fixed rounded-full pointer-events-none z-[100]"
          style={{
            left: dot.x - 4,
            top: dot.y - 4,
            width: 8,
            height: 8,
            background: `rgba(255, ${140 + i * 10}, ${100 + i * 10}, ${0.6 - i * 0.06})`,
          }}
          initial={{ scale: 1, opacity: 0.6 }}
          animate={{ scale: 0, opacity: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
      ))}

      {/* Aurora background layers */}
      {mounted && (
        <>
          <motion.div
            className="absolute inset-0"
            style={{
              background: `radial-gradient(ellipse at ${30 + mousePos.x * 40}% ${20 + mousePos.y * 30}%, rgba(255,107,107,0.2) 0%, transparent 50%)`,
            }}
            animate={{
              background: [
                `radial-gradient(ellipse at 30% 20%, rgba(255,107,107,0.2) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 60% 40%, rgba(255,142,83,0.2) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 40% 60%, rgba(255,179,71,0.2) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 30% 20%, rgba(255,107,107,0.2) 0%, transparent 50%)`,
              ],
            }}
            transition={{ duration: 12, repeat: Infinity, ease: 'linear' }}
          />
          <motion.div
            className="absolute inset-0"
            style={{
              background: `radial-gradient(ellipse at ${70 - mousePos.x * 30}% ${80 - mousePos.y * 40}%, rgba(255,105,180,0.15) 0%, transparent 50%)`,
            }}
            animate={{
              background: [
                `radial-gradient(ellipse at 70% 80%, rgba(255,105,180,0.15) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 50% 50%, rgba(255,179,71,0.15) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 80% 30%, rgba(255,215,0,0.15) 0%, transparent 50%)`,
                `radial-gradient(ellipse at 70% 80%, rgba(255,105,180,0.15) 0%, transparent 50%)`,
              ],
            }}
            transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
          />
          <motion.div
            className="absolute inset-0"
            style={{
              background: `radial-gradient(ellipse at ${50 + mousePos.x * 20}% ${50 + mousePos.y * 20}%, rgba(255,215,0,0.12) 0%, transparent 40%)`,
            }}
            animate={{
              background: [
                `radial-gradient(ellipse at 50% 50%, rgba(255,215,0,0.12) 0%, transparent 40%)`,
                `radial-gradient(ellipse at 70% 30%, rgba(255,107,107,0.12) 0%, transparent 40%)`,
                `radial-gradient(ellipse at 30% 70%, rgba(255,105,180,0.12) 0%, transparent 40%)`,
                `radial-gradient(ellipse at 50% 50%, rgba(255,215,0,0.12) 0%, transparent 40%)`,
              ],
            }}
            transition={{ duration: 18, repeat: Infinity, ease: 'linear' }}
          />
        </>
      )}

      {/* Floating emojis */}
      {mounted && FLOATING_EMOJIS.map((emoji, i) => (
        <motion.div
          key={`emoji-${i}`}
          className="absolute text-3xl select-none pointer-events-none"
          style={{
            left: `${10 + (i * 80) % 80}%`,
            bottom: '-50px',
            filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.1))',
          }}
          animate={{
            y: [0, -window.innerHeight - 100],
            x: [0, Math.sin(i) * 60, -Math.sin(i) * 40, 0],
            rotate: [0, 15, -10, 0],
            scale: [0.8, 1, 0.9, 0.8],
          }}
          transition={{
            duration: 12 + i * 2,
            repeat: Infinity,
            delay: i * 1.5,
            ease: 'easeOut',
          }}
        >
          {emoji}
        </motion.div>
      ))}

      {/* Confetti particles */}
      {mounted && Array.from({ length: 25 }).map((_, i) => (
        <motion.div
          key={`confetti-${i}`}
          className="absolute rounded-full pointer-events-none"
          style={{
            width: 4 + Math.random() * 8,
            height: 4 + Math.random() * 8,
            background: ['#FF6B6B', '#FF8E53', '#FFB347', '#FF69B4', '#FFD700', '#FFA07A'][i % 6],
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            borderRadius: i % 3 === 0 ? '50%' : '2px',
          }}
          animate={{
            y: [0, -30 - Math.random() * 40],
            x: [0, Math.sin(i * 0.5) * 50],
            opacity: [0, 0.6, 0.2, 0],
            rotate: [0, 180 + Math.random() * 180],
            scale: [0.5, 1.2, 0.8, 0.5],
          }}
          transition={{
            duration: 4 + Math.random() * 4,
            repeat: Infinity,
            delay: Math.random() * 5,
            ease: 'easeInOut',
          }}
        />
      ))}

      {/* Morphing blobs */}
      {mounted && [0, 1, 2].map((i) => (
        <motion.div
          key={`blob-${i}`}
          className="absolute rounded-full blur-3xl pointer-events-none"
          style={{
            width: 300 + i * 100,
            height: 300 + i * 100,
            background: ['rgba(255,182,193,0.3)', 'rgba(255,218,185,0.25)', 'rgba(255,223,186,0.2)'][i],
            left: `${[20, 60, 40][i]}%`,
            top: `${[20, 60, 80][i]}%`,
          }}
          animate={{
            borderRadius: ['30% 70% 70% 30% / 30% 30% 70% 70%', '60% 40% 30% 70% / 60% 30% 70% 40%', '30% 70% 70% 30% / 30% 30% 70% 70%'],
            scale: [1, 1.1, 0.95, 1],
          }}
          transition={{
            duration: 8 + i * 3,
            repeat: Infinity,
            ease: 'easeInOut',
          }}
        />
      ))}

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

          <motion.h1
            className="text-5xl sm:text-6xl lg:text-7xl font-black mb-4 tracking-tight"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            style={{
              background: 'linear-gradient(135deg, #FF6B6B 0%, #FF8E53 25%, #FFB347 50%, #FF69B4 75%, #FF6B6B 100%)',
              backgroundSize: '300% auto',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              animation: 'shimmer 3s ease-in-out infinite',
            }}
          >
            Vyom Ai Cloud
          </motion.h1>

          <div className="h-8 mb-8 overflow-hidden">
            <AnimatePresence mode="wait">
              <motion.p
                key={taglineIdx}
                className="text-xl text-stone-600 font-medium max-w-md mx-auto lg:mx-0"
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -30 }}
                transition={{ duration: 0.5, type: 'spring', stiffness: 200 }}
              >
                {TAGLINES[taglineIdx]}
              </motion.p>
            </AnimatePresence>
          </div>

          {/* Perk cards */}
          <div className="space-y-3 max-w-sm mx-auto lg:mx-0">
            {PERKS.map((perk, i) => (
              <motion.div
                key={perk.title}
                initial={{ opacity: 0, x: -30, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={{ delay: 0.7 + i * 0.1, type: 'spring', stiffness: 200 }}
                whileHover={{ x: 8, scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className="relative flex items-center gap-4 p-4 rounded-2xl bg-white/70 border border-orange-200/30 backdrop-blur-sm cursor-pointer overflow-hidden group"
              >
                <motion.div
                  className={`absolute inset-0 bg-gradient-to-br ${perk.gradient} opacity-0 group-hover:opacity-100 transition-opacity duration-300`}
                />
                <motion.div
                  className="relative z-10 w-12 h-12 rounded-xl bg-gradient-to-br from-orange-200/50 to-pink-200/50 flex items-center justify-center text-2xl"
                  whileHover={{ scale: 1.2, rotate: [0, -10, 10, 0] }}
                  transition={{ duration: 0.4 }}
                >
                  {perk.icon}
                </motion.div>
                <div className="relative z-10">
                  <h3 className="text-sm font-bold text-stone-800">{perk.title}</h3>
                  <p className="text-xs text-stone-500">{perk.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </motion.div>

        {/* Right side - Signup card */}
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
              background: 'linear-gradient(135deg, rgba(255,255,255,0.9), rgba(255,248,240,0.95))',
              backdropFilter: 'blur(40px)',
              border: '1px solid rgba(255,182,193,0.3)',
              boxShadow: isHoveringCard
                ? '0 35px 80px rgba(255,140,66,0.2), 0 15px 40px rgba(255,182,193,0.15)'
                : '0 25px 60px rgba(255,140,66,0.15), 0 10px 30px rgba(255,182,193,0.1)',
              transformStyle: 'preserve-3d',
            }}
          >
            {/* Animated gradient border */}
            <motion.div
              className="absolute inset-0 rounded-3xl opacity-40"
              style={{
                background: 'conic-gradient(from 0deg, #FFB6C1, #FFA07A, #FFD700, #FF69B4, #FFA07A, #FFB6C1)',
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
                  background: `radial-gradient(600px circle at ${mousePos.x * 100}% ${mousePos.y * 100}%, rgba(255,182,193,0.15), transparent 40%)`,
                }}
              />
            )}

            <div className="relative z-10 p-8 sm:p-10" style={{ transform: 'translateZ(40px)' }}>
              {/* Header */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.7 }}
                className="text-center mb-8"
              >
                <motion.h2
                  className="text-3xl font-black text-stone-800 mb-2"
                  animate={{ scale: isHoveringCard ? [1, 1.02, 1] : 1 }}
                  transition={{ duration: 2, repeat: isHoveringCard ? Infinity : 0 }}
                >
                  Get Started
                </motion.h2>
                <p className="text-sm text-stone-500">Create your account and start creating</p>
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

              {/* Google signup button */}
              <motion.button
                ref={btnRef}
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={(e) => { handleRipple(e); handleGoogleSignup(); }}
                disabled={loading}
                className="relative w-full py-4 rounded-2xl font-bold text-white transition-all duration-300 disabled:opacity-50 overflow-hidden"
                style={{
                  background: 'linear-gradient(135deg, #FF6B6B, #FF8E53, #FFB347)',
                  backgroundSize: '200% auto',
                  boxShadow: '0 10px 30px rgba(255,107,107,0.3)',
                  transform: `translate(${btnMagnetic.x}px, ${btnMagnetic.y}px)`,
                }}
                animate={{
                  backgroundPosition: ['0% center', '100% center', '0% center'],
                }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                {/* Ripple effects */}
                {ripples.map((ripple) => (
                  <motion.span
                    key={ripple.id}
                    className="absolute bg-white/30 rounded-full"
                    initial={{ width: 0, height: 0, opacity: 1, x: ripple.x, y: ripple.y }}
                    animate={{ width: 300, height: 300, opacity: 0, x: ripple.x - 150, y: ripple.y - 150 }}
                    transition={{ duration: 0.6, ease: 'easeOut' }}
                  />
                ))}

                <div className="relative z-10 flex items-center justify-center gap-3">
                  {loading ? (
                    <motion.div
                      className="flex items-center gap-3"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                    >
                      <motion.span
                        animate={{ y: [0, -10, 0] }}
                        transition={{ duration: 0.8, repeat: Infinity, ease: 'easeInOut' }}
                      >
                        🚀
                      </motion.span>
                      <span>Creating your account...</span>
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
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-orange-200 to-transparent" />
                <span className="text-xs text-stone-400 font-medium">SECURED BY</span>
                <div className="flex-1 h-px bg-gradient-to-r from-transparent via-orange-200 to-transparent" />
              </motion.div>

              {/* Security badges */}
              <motion.div
                className="flex items-center justify-center gap-6 text-xs text-stone-500"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1 }}
              >
                {[
                  { icon: '🔒', label: 'Google Auth' },
                  { icon: '🛡️', label: 'Encrypted' },
                  { icon: '✅', label: 'Secure' },
                ].map((item, i) => (
                  <motion.div
                    key={item.label}
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 1.1 + i * 0.1, type: 'spring', stiffness: 300 }}
                    className="flex items-center gap-1.5 hover:scale-110 transition-transform cursor-default"
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                  </motion.div>
                ))}
              </motion.div>

              {/* Login link */}
              <motion.p
                className="text-center mt-8 text-sm text-stone-500"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 1.2 }}
              >
                Already have an account?{' '}
                <Link href="/login" className="text-orange-500 hover:text-orange-600 font-bold transition-colors relative group">
                  Sign in
                  <span className="absolute -bottom-0.5 left-0 w-0 h-0.5 bg-orange-500 group-hover:w-full transition-all duration-300" />
                </Link>
              </motion.p>
            </div>
          </motion.div>
        </motion.div>
      </motion.div>
    </div>
  );
}
