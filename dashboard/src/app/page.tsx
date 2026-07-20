'use client';

import { useEffect, useState } from 'react';
import { auth } from '@/lib/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';
import Link from 'next/link';
import {
  Bot, Play, TrendingUp, Music, Zap, CheckCircle,
  ArrowRight, Sparkles, Shield, Cpu
} from 'lucide-react';

const FEATURES = [
  { icon: Bot, title: '9 AI Agents', desc: 'Scriptwriting, video generation, voiceover, and publishing — all automated.' },
  { icon: Play, title: 'AI Video Generation', desc: 'Text-to-video with LTX, Blender 3D renders, and intelligent scene composition.' },
  { icon: TrendingUp, title: 'Multi-Platform Publishing', desc: 'YouTube, TikTok, Instagram, Facebook — one pipeline, all platforms.' },
  { icon: Music, title: 'AI Voice & Music', desc: 'Natural TTS voiceovers with 9 languages and AI-generated background music.' },
  { icon: Zap, title: 'Trend Discovery', desc: 'AI-powered topic research and hook optimization for maximum reach.' },
  { icon: CheckCircle, title: 'Fully Automated', desc: 'Schedule daily content. From script to published video, hands-free.' },
];

const STATS = [
  { label: 'Active Users', value: '500+' },
  { label: 'Videos Published', value: '10K+' },
  { label: 'Platforms Supported', value: '4' },
  { label: 'AI Agents', value: '9' },
];

export default function Home() {
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
      <div className="fixed top-4 right-4 z-50"><ThemeToggle /></div>

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
          <Image src="/logo.svg" alt="Vyom Ai Cloud" width={36} height={36} />
          <span className="text-white font-bold text-lg">Vyom Ai Cloud</span>
        </div>
        <div className="hidden md:flex items-center gap-8 text-sm text-gray-400">
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-white transition-colors">How It Works</a>
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

      {/* Hero */}
      <section className="relative z-30 max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, type: 'spring', stiffness: 100 }}
        >
          <motion.div
            className="relative w-32 h-24 mx-auto mb-8"
            animate={{ y: [0, -8, 0], rotate: [0, 2, -1, 0] }}
            transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
          >
            <Image src="/logo-vyomai.png" alt="Vyom Ai Cloud" fill className="object-contain drop-shadow-2xl" priority />
          </motion.div>

          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black mb-6 tracking-tight leading-tight">
            <span className="text-white">AI-Powered</span>{' '}
            <span
              style={{
                background: 'linear-gradient(135deg, #FF6969 0%, #C80036 50%, #FF6B6B 100%)',
                backgroundSize: '300% auto',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
              }}
            >
              Video Automation
            </span>
            <br />
            <span className="text-white/80">for Educational Creators</span>
          </h1>

          <p className="text-lg text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            From script to published video across YouTube, TikTok, Instagram, and Facebook —<br />
            all powered by 9 AI agents working together.
          </p>

          <div className="flex items-center justify-center gap-4 flex-wrap">
            {user ? (
              <button
                onClick={() => router.push('/dashboard')}
                className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300 flex items-center gap-2"
                style={{
                  background: 'linear-gradient(135deg, #FF6969, #C80036)',
                  boxShadow: '0 8px 30px rgba(255,105,105,0.35)',
                }}
              >
                Go to Dashboard <ArrowRight className="w-5 h-5" />
              </button>
            ) : (
              <>
                <Link
                  href="/signup"
                  className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300 flex items-center gap-2"
                  style={{
                    background: 'linear-gradient(135deg, #FF6969, #C80036)',
                    boxShadow: '0 8px 30px rgba(255,105,105,0.35)',
                  }}
                >
                  Get Started Free <Sparkles className="w-5 h-5" />
                </Link>
                <Link
                  href="/login"
                  className="px-8 py-4 rounded-2xl font-semibold text-gray-300 text-lg border border-white/10 hover:border-white/20 transition-all"
                >
                  Sign In
                </Link>
              </>
            )}
          </div>
        </motion.div>
      </section>

      {/* Stats bar */}
      <section className="relative z-30 max-w-4xl mx-auto px-6 pb-16">
        <div
          className="grid grid-cols-2 md:grid-cols-4 gap-px rounded-2xl overflow-hidden border border-white/5"
          style={{ background: 'rgba(255,255,255,0.05)' }}
        >
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="py-6 text-center bg-[#050510]/80"
            >
              <div className="text-2xl font-black text-white">{stat.value}</div>
              <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="relative z-30 max-w-6xl mx-auto px-6 py-16">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-3xl sm:text-4xl font-black text-center text-white mb-4"
        >
          Everything You Need
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-gray-400 text-center mb-12 max-w-xl mx-auto"
        >
          A complete content creation pipeline — from ideation to publication.
        </motion.p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((feature, i) => (
            <motion.div
              key={feature.title}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08 }}
              className="group relative p-6 rounded-2xl border border-white/5 bg-white/[0.02] hover:bg-white/[0.05] transition-all duration-300"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-500/20 to-red-800/20 flex items-center justify-center mb-4">
                <feature.icon className="w-5 h-5 text-red-300" />
              </div>
              <h3 className="text-white font-bold mb-2">{feature.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed">{feature.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="relative z-30 max-w-6xl mx-auto px-6 py-16">
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-3xl sm:text-4xl font-black text-center text-white mb-4"
        >
          How It Works
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-gray-400 text-center mb-12 max-w-xl mx-auto"
        >
          Set up once. Generate content daily. Publish everywhere.
        </motion.p>

        <div className="grid sm:grid-cols-3 gap-8">
          {[
            { step: '01', title: 'Connect', desc: 'Link your YouTube, TikTok, Instagram, and Facebook accounts via OAuth.' },
            { step: '02', title: 'Configure', desc: 'Set your content preferences, categories, and publishing schedule.' },
            { step: '03', title: 'Automate', desc: 'AI generates, edits, and publishes videos daily — hands-free.' },
          ].map((item, i) => (
            <motion.div
              key={item.step}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="text-center"
            >
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl font-black"
                style={{
                  background: 'linear-gradient(135deg, rgba(255,105,105,0.15), rgba(200,0,54,0.15))',
                  color: '#FF6969',
                }}
              >
                {item.step}
              </div>
              <h3 className="text-white font-bold text-lg mb-2">{item.title}</h3>
              <p className="text-sm text-gray-400 max-w-xs mx-auto">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Trust badges */}
      <section className="relative z-30 max-w-4xl mx-auto px-6 py-12">
        <div className="flex items-center justify-center gap-8 flex-wrap text-xs text-gray-500">
          <div className="flex items-center gap-2"><Shield className="w-4 h-4 text-gray-600" /> Google Auth</div>
          <div className="flex items-center gap-2"><Cpu className="w-4 h-4 text-gray-600" /> 100% Free</div>
          <div className="flex items-center gap-2"><CheckCircle className="w-4 h-4 text-gray-600" /> Encrypted</div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-30 max-w-3xl mx-auto px-6 py-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="text-3xl sm:text-4xl font-black text-white mb-4">
            Ready to Automate Your Content?
          </h2>
          <p className="text-gray-400 mb-8 max-w-md mx-auto">
            Join 500+ creators using Vyom Ai Cloud to publish daily without lifting a finger.
          </p>
          {user ? (
            <button
              onClick={() => router.push('/dashboard')}
              className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300"
              style={{
                background: 'linear-gradient(135deg, #FF6969, #C80036)',
                boxShadow: '0 8px 30px rgba(255,105,105,0.35)',
              }}
            >
              Go to Dashboard
            </button>
          ) : (
            <Link
              href="/signup"
              className="inline-block px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300"
              style={{
                background: 'linear-gradient(135deg, #FF6969, #C80036)',
                boxShadow: '0 8px 30px rgba(255,105,105,0.35)',
              }}
            >
              Get Started Free
            </Link>
          )}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-30 border-t border-white/5 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={24} height={24} />
            <span className="text-sm text-gray-500">© {new Date().getFullYear()} Vyom Ai Cloud. All rights reserved.</span>
          </div>
          <div className="flex items-center gap-6 text-sm">
            <Link href="/terms" className="text-gray-500 hover:text-gray-300 transition-colors">
              Terms of Service
            </Link>
            <Link href="/privacy" className="text-gray-500 hover:text-gray-300 transition-colors">
              Privacy Policy
            </Link>
            <a href="mailto:support@vyomai.cloud" className="text-gray-500 hover:text-gray-300 transition-colors">
              Contact
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
