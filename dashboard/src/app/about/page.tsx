import type { Metadata } from 'next';
import PublicNavFooter from '@/components/PublicNavFooter';
import { Bot, Play, TrendingUp, Music, Zap, CheckCircle, Users, Globe, Shield, Sparkles } from 'lucide-react';

export const metadata: Metadata = {
  title: 'About — Vyom Ai Cloud',
  description: 'Learn about Vyom Ai Cloud, the AI-powered video automation platform for educational content creators.',
};

const AGENTS = [
  { icon: Bot, name: 'Scriptwriter', desc: 'Writes engaging video scripts with hooks, structure, and calls-to-action.' },
  { icon: Play, name: 'Video Generator', desc: 'Creates video clips using AI text-to-video, Blender 3D, and stock footage.' },
  { icon: Music, name: 'Voice Artist', desc: 'Generates natural voiceovers in 9 languages with TTS and SSML.' },
  { icon: Sparkles, name: 'Music Composer', desc: 'Produces AI-generated background music matched to content mood.' },
  { icon: TrendingUp, name: 'Trend Analyst', desc: 'Discovers trending topics and viral hooks for maximum reach.' },
  { icon: CheckCircle, name: 'Quality Reviewer', desc: 'Reviews scripts and storyboards before production begins.' },
  { icon: Zap, name: 'Thumbnail Artist', desc: 'Generates eye-catching thumbnails optimized for each platform.' },
  { icon: Users, name: 'Community Manager', desc: 'Manages audience engagement, comments, and community posts.' },
  { icon: Globe, name: 'Publisher', desc: 'Publishes to YouTube, TikTok, Instagram, and Facebook simultaneously.' },
];

export default function AboutPage() {
  return (
    <PublicNavFooter>
      <div className="max-w-4xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="text-center mb-16">
          <h1 className="text-4xl sm:text-5xl font-black text-white mb-4 tracking-tight">
            About Vyom Ai Cloud
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto leading-relaxed">
            Vyom Ai Cloud is an AI-powered video automation platform that helps educational content creators
            produce and publish videos across multiple social media platforms — hands-free.
          </p>
        </div>

        {/* What We Do */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">What We Do</h2>
          <div className="grid sm:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl border border-white/5 bg-white/[0.02]">
              <h3 className="text-white font-bold mb-2">For Creators</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                You connect your YouTube, TikTok, Instagram, and Facebook accounts once. Our 9 AI agents then work
                together to research trending topics, write scripts, generate videos, compose music, add voiceovers,
                and publish everything — automatically, every day.
              </p>
            </div>
            <div className="p-6 rounded-2xl border border-white/5 bg-white/[0.02]">
              <h3 className="text-white font-bold mb-2">For Educators</h3>
              <p className="text-sm text-gray-400 leading-relaxed">
                We specialize in educational and technology content. From coding tutorials to AI explainers,
                our pipeline produces content that teaches, engages, and grows your audience across every
                platform simultaneously.
              </p>
            </div>
          </div>
        </section>

        {/* How the Pipeline Works */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">How the Pipeline Works</h2>
          <div className="space-y-4">
            {[
              { step: '1', title: 'Topic Discovery', desc: 'AI scans trending topics across the web and selects the best fit for your content pillars and audience.' },
              { step: '2', title: 'Script Writing', desc: 'A dedicated scriptwriter agent writes an engaging script with hooks, structure, and calls-to-action.' },
              { step: '3', title: 'Storyboard & Review', desc: 'Scenes are planned and reviewed for quality before any video generation begins.' },
              { step: '4', title: 'Video Generation', desc: 'AI generates video clips using LTX text-to-video, Blender 3D renders, or intelligent stock footage composition.' },
              { step: '5', title: 'Voice & Music', desc: 'Natural TTS voiceovers are generated and mixed with AI-composed background music.' },
              { step: '6', title: 'Subtitle & Compositing', desc: 'Subtitles are auto-generated from voice timing, and all elements are composited into the final video.' },
              { step: '7', title: 'Quality Assurance', desc: 'Automated checks verify black frames, blur, freeze detection, and audio quality before publishing.' },
              { step: '8', title: 'Multi-Platform Publish', desc: 'The final video is published to YouTube, TikTok, Instagram, and Facebook with optimized titles, descriptions, and thumbnails.' },
            ].map((item) => (
              <div key={item.step} className="flex gap-4 items-start">
                <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center text-sm font-bold"
                  style={{ background: 'linear-gradient(135deg, rgba(255,105,105,0.2), rgba(200,0,54,0.2))', color: '#FF6969' }}>
                  {item.step}
                </div>
                <div>
                  <h3 className="text-white font-bold text-sm">{item.title}</h3>
                  <p className="text-sm text-gray-400">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 9 AI Agents */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Our 9 AI Agents</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {AGENTS.map((agent) => (
              <div key={agent.name} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-red-500/20 to-red-800/20 flex items-center justify-center mb-3">
                  <agent.icon className="w-4 h-4 text-red-300" />
                </div>
                <h3 className="text-white font-bold text-sm mb-1">{agent.name}</h3>
                <p className="text-xs text-gray-400 leading-relaxed">{agent.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Platforms */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Supported Platforms</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {['YouTube', 'TikTok', 'Instagram', 'Facebook'].map((platform) => (
              <div key={platform} className="p-4 rounded-xl border border-white/5 bg-white/[0.02] text-center">
                <p className="text-white font-semibold text-sm">{platform}</p>
              </div>
            ))}
          </div>
          <p className="text-sm text-gray-400 mt-4">
            Each platform is connected via official OAuth. Videos are published with optimized titles, descriptions,
            and thumbnails tailored to each platform&apos;s requirements.
          </p>
        </section>

        {/* Security */}
        <section className="mb-16">
          <h2 className="text-2xl font-bold text-white mb-6">Security &amp; Privacy</h2>
          <div className="grid sm:grid-cols-3 gap-4">
            {[
              { icon: Shield, title: 'OAuth Only', desc: 'We only use official OAuth flows. Your passwords are never stored.' },
              { icon: Shield, title: 'Encrypted Storage', desc: 'All tokens and data are encrypted at rest using Firebase Firestore.' },
              { icon: Shield, title: 'No Data Selling', desc: 'We never sell or share your personal data with third parties.' },
            ].map((item) => (
              <div key={item.title} className="p-5 rounded-2xl border border-white/5 bg-white/[0.02]">
                <item.icon className="w-5 h-5 text-gray-400 mb-2" />
                <h3 className="text-white font-bold text-sm mb-1">{item.title}</h3>
                <p className="text-xs text-gray-400">{item.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Contact */}
        <section className="text-center py-12 border-t border-white/5">
          <h2 className="text-2xl font-bold text-white mb-3">Get in Touch</h2>
          <p className="text-gray-400 mb-6">
            Questions about Vyom Ai Cloud? We&apos;d love to hear from you.
          </p>
          <a
            href="mailto:support@vyomai.cloud"
            className="inline-block px-6 py-3 rounded-xl font-semibold text-sm text-white transition-all duration-300"
            style={{
              background: 'linear-gradient(135deg, #FF6969, #C80036)',
              boxShadow: '0 4px 20px rgba(255,105,105,0.3)',
            }}
          >
            Contact Support
          </a>
        </section>
      </div>
    </PublicNavFooter>
  );
}
