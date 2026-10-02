'use client';

import { useEffect, useState } from 'react';
import { auth } from '@/lib/firebase';
import { useGoToDashboard } from '@/lib/auth-nav';
import { onAuthStateChanged } from 'firebase/auth';
import { motion } from 'framer-motion';
import { AmbientBackground } from '@/components/ui/AmbientBackground';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import Image from 'next/image';
import Link from 'next/link';
import { BRAND_GRADIENT, CONTACT_EMAIL, COMPANY } from '@/lib/brand';
import {
  Bot, Play, TrendingUp, Music, Zap, CheckCircle,
  ArrowRight, Shield, Cpu
} from 'lucide-react';

// Agent count is 13 (agents/crew/*.py, excluding __init__). The old copy said
// 9 in two places, which is the kind of number nobody re-checks because it is
// only ever read, never computed.
const AGENT_COUNT = 13;
const PLATFORM_COUNT = 4;

const FEATURES = [
  { icon: Bot, title: `${AGENT_COUNT} specialist agents`, desc: 'Script, storyboard, voice, thumbnail, virality and publishing — each one reviewable on its own.' },
  { icon: Play, title: 'Real rendered video', desc: 'Stock footage, data-visualised diagrams and 3D scenes composed into a finished cut with burned captions.' },
  { icon: TrendingUp, title: `${PLATFORM_COUNT}-platform publishing`, desc: 'YouTube, TikTok, Instagram and Facebook from one pipeline, with per-platform metadata.' },
  { icon: Music, title: 'Voice and score', desc: 'Natural text-to-speech narration, phrase-timed captions, and a background bed mixed under the voice.' },
  { icon: Zap, title: 'News that is actually verified', desc: 'Headlines are checked against a fixed allowlist of real publishers before a script is written.' },
  { icon: CheckCircle, title: 'Gates you can see', desc: 'Quality, virality and review gates record why something was held, instead of failing silently.' },
];

// Honest numbers only. "500+ users" and "10K+ videos" were unsupportable and
// have been removed rather than softened.
const STATS = [
  { label: 'Specialist agents', value: String(AGENT_COUNT) },
  { label: 'Publish platforms', value: String(PLATFORM_COUNT) },
  { label: 'Dub languages ready', value: '3' },
  { label: 'Caption modes', value: 'Burned' },
];

const CTA_STYLE = {
  background: BRAND_GRADIENT,
  boxShadow: '0 8px 30px rgba(155, 77, 255, 0.35)',
} as const;

export default function Home() {
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

  const Cta = ({ label, className = '' }: { label: string; className?: string }) =>
    user ? (
      <button onClick={goToDashboard} className={className} style={CTA_STYLE}>{label}</button>
    ) : (
      <Link href="/signup" className={className} style={CTA_STYLE}>{label}</Link>
    );

  return (
    // This page has no PublicNavFooter -- it rolls its own nav -- so it owns its
    // canvas outright. It was `style={{ background: BRAND.canvas }}`, a
    // hardcoded dark, which is why the landing page rendered white-on-white
    // under a light OS preference: the themed <body> showed through and its
    // `text-white` had nothing light-on to sit against. Tokenised now, and it
    // is the one public page that must carry its own surface class rather than
    // inheriting one, which is why it is not in the shell check.
    <div className="min-h-screen relative overflow-hidden bg-light-bg dark:bg-dark-bg">
      <AmbientBackground variant="landing" />

      <nav className="relative z-40 flex items-center justify-between px-6 py-4 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <Image src="/logo.svg" alt="Vyom Ai Cloud" width={36} height={36} />
          <span className="font-display font-bold text-lg text-light-text dark:text-white">Vyom Ai Cloud</span>
        </div>
        <div className="hidden md:flex items-center gap-6 text-sm text-light-muted dark:text-dark-muted">
          <a href="#features" className="hover:text-light-text dark:hover:text-white transition-colors">Features</a>
          <a href="#how-it-works" className="hover:text-light-text dark:hover:text-white transition-colors">How It Works</a>
          <Link href="/about" className="hover:text-light-text dark:hover:text-white transition-colors">About</Link>
          <Link href="/faq" className="hover:text-light-text dark:hover:text-white transition-colors">FAQ</Link>
        </div>
        <div className="flex items-center gap-3">
          {!authChecked ? (
            <div className="px-5 py-2 rounded-xl bg-light-border dark:bg-white/10 animate-pulse" aria-hidden />
          ) : user ? (
            <button onClick={goToDashboard} className="px-5 py-2 rounded-xl font-semibold text-sm text-white transition-all duration-300" style={CTA_STYLE}>
              Go to Dashboard
            </button>
          ) : (
            <>
              <Link href="/login" className="px-4 py-2 rounded-xl text-sm text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white border border-light-border dark:border-white/10 dark:hover:border-white/20 transition-all">
                Sign In
              </Link>
              <Link href="/signup" className="px-5 py-2 rounded-xl font-semibold text-sm text-white transition-all duration-300" style={CTA_STYLE}>
                Get Started
              </Link>
            </>
          )}
          {/* This nav is hand-rolled, so it does not inherit one from
              PublicNavFooter the way /about, /faq, /privacy and /terms do. */}
          <ThemeToggle />
        </div>
      </nav>

      {/* Hero */}
      <section className="relative z-30 max-w-6xl mx-auto px-6 pt-20 pb-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, type: 'spring', stiffness: 100 }}
        >
          <div className="relative w-32 h-32 mx-auto mb-8">
            <Image src="/logo.svg" alt="Timi by Vyom Ai Cloud" fill className="object-contain drop-shadow-2xl" priority />
          </div>

          <h1 className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold mb-6 tracking-tight leading-tight">
            <span className="text-light-text dark:text-white">Timi</span>{' '}
            <span className="gradient-text">Video Automation</span>
            <br />
            {/* Full-strength `light-muted`/`dark-muted`, no opacity modifier.
                `text-light-text/70` measured 2.94:1 on `light-bg` and needs 3:1
                even at 72px bold, so it failed. The muted tokens measure 4.53:1
                and 7.02:1 and are already used by the paragraph below, so this
                also stops the two de-emphasis steps disagreeing. */}
            <span className="text-light-muted dark:text-dark-muted">by Vyom Ai Cloud</span>
          </h1>

          <p className="text-lg text-light-muted dark:text-dark-muted max-w-2xl mx-auto mb-4 leading-relaxed">
            From a verified headline to a published video across YouTube, TikTok,
            Instagram and Facebook — {AGENT_COUNT} specialist agents, one reviewable pipeline.
          </p>
          {/* No opacity modifier in EITHER namespace. `light-muted` is
              calibrated to 4.53:1 on `light-bg` and `dark-muted` to 7.02:1 on
              `dark-bg`, but both at FULL strength -- every step down fails AA
              (measured on light: /80 3.13, /70 2.64, /60 2.25, /50 1.93; on
              dark, /70 lands at 3.92). Dimming a colour that only just passes
              is what produced the 2.64:1 footer. */}
          <p className="text-sm text-light-muted dark:text-dark-muted mb-10">
            Built by {COMPANY.shortName}, Nepal.
          </p>

          <div className="flex items-center justify-center gap-4 flex-wrap">
            {!authChecked ? (
              <div className="px-8 py-4 rounded-2xl bg-light-border dark:bg-white/10 animate-pulse" aria-hidden />
            ) : user ? (
              <button
                onClick={goToDashboard}
                className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300 flex items-center gap-2"
                style={CTA_STYLE}
              >
                Go to Dashboard <ArrowRight className="w-5 h-5" />
              </button>
            ) : (
              <>
                <Cta
                  label="Get Started"
                  className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300 flex items-center gap-2"
                />
                <Link
                  href="/login"
                  className="px-8 py-4 rounded-2xl font-semibold text-light-muted dark:text-dark-muted text-lg border border-light-border dark:border-white/10 dark:hover:border-white/20 transition-all"
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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-px rounded-2xl overflow-hidden border border-light-border dark:border-white/5" style={{ background: 'color-mix(in srgb, currentColor 6%, transparent)' }}>
          {STATS.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="py-6 text-center bg-light-card dark:bg-[#0E0909]/80"
            >
              <div className="tabular font-display text-2xl font-bold">{stat.value}</div>
              <div className="text-xs text-light-muted dark:text-dark-muted mt-1">{stat.label}</div>
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
          className="font-display text-3xl sm:text-4xl font-bold text-center text-light-text dark:text-white mb-4"
        >
          Everything You Need
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-light-muted dark:text-dark-muted text-center mb-12 max-w-xl mx-auto"
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
              className="group relative p-6 rounded-2xl border border-light-border dark:border-white/5 bg-light-card dark:bg-white/[0.02] hover:bg-light-card/70 dark:hover:bg-white/[0.05] transition-all duration-300"
            >
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-4 bg-light-primary/15 dark:bg-[rgba(155,77,255,0.16)]">
                <feature.icon className="w-5 h-5 text-light-warning dark:text-dark-warning" />
              </div>
              <h3 className="font-display text-light-text dark:text-white font-bold mb-2">{feature.title}</h3>
              <p className="text-sm text-light-muted dark:text-dark-muted leading-relaxed">{feature.desc}</p>
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
          className="font-display text-3xl sm:text-4xl font-bold text-center text-light-text dark:text-white mb-4"
        >
          How It Works
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-light-muted dark:text-dark-muted text-center mb-12 max-w-xl mx-auto"
        >
          Set up once. Generate daily. Publish everywhere.
        </motion.p>

        <div className="grid sm:grid-cols-3 gap-8">
          {[
            { step: '01', title: 'Connect', desc: 'Link your YouTube, TikTok, Instagram, and Facebook accounts via OAuth.' },
            { step: '02', title: 'Configure', desc: 'Set your categories, languages, and the schedule you want to publish on.' },
            { step: '03', title: 'Automate', desc: 'Timi researches, scripts, renders and publishes — and records why it held anything.' },
          ].map((item, i) => (
            <motion.div
              key={item.step}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="text-center"
            >
              <div className="font-display w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-4 text-2xl font-bold bg-light-primary/15 dark:bg-[rgba(155,77,255,0.15)] text-light-warning dark:text-dark-warning">
                {item.step}
              </div>
              <h3 className="font-display text-light-text dark:text-white font-bold text-lg mb-2">{item.title}</h3>
              <p className="text-sm text-light-muted dark:text-dark-muted max-w-xs mx-auto">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Trust badges */}
      <section className="relative z-30 max-w-4xl mx-auto px-6 py-12">
        <div className="flex items-center justify-center gap-8 flex-wrap text-xs text-light-muted dark:text-dark-muted">
          <div className="flex items-center gap-2"><Shield className="w-4 h-4" /> Google sign-in</div>
          <div className="flex items-center gap-2"><Cpu className="w-4 h-4" /> Self-hosted option</div>
          <div className="flex items-center gap-2"><CheckCircle className="w-4 h-4" /> Allowlist-gated access</div>
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-30 max-w-3xl mx-auto px-6 py-16 text-center">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
        >
          <h2 className="font-display text-3xl sm:text-4xl font-bold text-light-text dark:text-white mb-4">
            Ready to Automate Your Content?
          </h2>
          <p className="text-light-muted dark:text-dark-muted mb-8 max-w-md mx-auto">
            Timi is built by {COMPANY.shortName} in Nepal. Access is invite-only —
            sign in to your account to continue.
          </p>
          {!authChecked ? (
            <div className="px-8 py-4 rounded-2xl bg-light-border dark:bg-white/10 animate-pulse" aria-hidden />
          ) : user ? (
            <button onClick={goToDashboard} className="px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300" style={CTA_STYLE}>
              Go to Dashboard
            </button>
          ) : (
            <Link href="/signup" className="inline-block px-8 py-4 rounded-2xl font-bold text-white text-lg transition-all duration-300" style={CTA_STYLE}>
              Get Started
            </Link>
          )}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-30 border-t border-light-border dark:border-white/5 py-10 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" width={24} height={24} />
            <span className="text-sm text-light-muted dark:text-dark-muted">
              © {new Date().getFullYear()} {COMPANY.legalName}. Timi is a {COMPANY.shortName} product.
            </span>
          </div>
          <div className="flex items-center gap-6 text-sm flex-wrap justify-center">
            <Link href="/about" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white transition-colors">About</Link>
            <Link href="/faq" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white transition-colors">FAQ</Link>
            <a href={`mailto:${CONTACT_EMAIL}`} className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white transition-colors">Contact</a>
            <Link href="/terms" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white transition-colors">Terms</Link>
            <Link href="/privacy" className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-white transition-colors">Privacy</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
