import type { Metadata } from 'next';
import PublicNavFooter from '@/components/PublicNavFooter';

export const metadata: Metadata = {
  title: 'FAQ — Vyom Ai Cloud',
  description: 'Frequently asked questions about Vyom Ai Cloud, the AI-powered video automation platform.',
};

const FAQS = [
  {
    q: 'What is Vyom Ai Cloud?',
    a: 'Vyom Ai Cloud is an AI-powered video automation platform that generates, edits, and publishes educational technology videos to YouTube, TikTok, Instagram, and Facebook — all from a single pipeline. It uses 9 specialized AI agents that work together to handle everything from scriptwriting to publishing.',
  },
  {
    q: 'How does it work?',
    a: 'You connect your social media accounts once via OAuth. Our AI pipeline then runs on a schedule: it discovers trending topics, writes scripts, generates videos using AI (LTX text-to-video, Blender 3D, stock footage), adds voiceovers and music, composites subtitles, performs quality checks, and publishes to all connected platforms with optimized titles, descriptions, and thumbnails.',
  },
  {
    q: 'What platforms are supported?',
    a: 'Vyom Ai Cloud currently supports YouTube, TikTok, Instagram, and Facebook. Each platform is connected via official OAuth, and content is optimized for each platform\'s specific requirements (format, length, captions, etc.).',
  },
  {
    q: 'Is it free to use?',
    a: 'Yes, Vyom Ai Cloud is free to use. There are no subscription fees or hidden costs. You connect your own social media accounts and the platform handles content generation and publishing.',
  },
  {
    q: 'What kind of content does it create?',
    a: 'Vyom Ai Cloud specializes in educational and technology content — coding tutorials, AI explainers, tech news, and educational videos. The AI agents are tuned for informative, engaging content that teaches and educates viewers.',
  },
  {
    q: 'Do I need to provide video footage?',
    a: 'No. The AI generates all video content automatically. It uses LTX text-to-video for AI-generated clips, Blender for 3D renders and diagrams, and intelligent stock footage composition — all assembled into polished final videos.',
  },
  {
    q: 'Can I review content before it publishes?',
    a: 'Yes. Every script and storyboard goes through an AI quality review gate before video generation. You can also use the Scheduler to review and approve content before it goes live. The platform includes multiple quality gates (virality scoring, director review, content safety) to ensure high-quality output.',
  },
  {
    q: 'How does publishing work?',
    a: 'After video generation and quality checks, the Publisher agent uploads the final video to all connected platforms simultaneously. Each platform gets optimized titles, descriptions, tags, and thumbnails. YouTube also gets caption tracks. Publishing can be scheduled or immediate.',
  },
  {
    q: 'Is my data safe?',
    a: 'Yes. We use official OAuth flows — your passwords are never stored. All tokens and data are encrypted at rest using Firebase Firestore. We do not sell, trade, or share your personal data with third parties. You can revoke access at any time through each platform\'s settings.',
  },
  {
    q: 'Can I customize what the AI creates?',
    a: 'Yes. You can configure content categories, publishing schedules, voice preferences, and video style through the Dashboard Settings. The Scheduler also learns from your preferences and analytics to improve content selection over time.',
  },
  {
    q: 'What languages are supported?',
    a: 'The AI voiceover system supports 9 languages including English, Spanish, French, German, Japanese, Korean, Chinese, Portuguese, and Hindi. Content scripts are generated in English by default, with multi-language dubbing available for international reach.',
  },
  {
    q: 'How do I get started?',
    a: 'Simply sign up with your Google account, connect your social media platforms via OAuth, configure your content preferences, and the AI pipeline will start generating and publishing content on your schedule. The entire setup takes about 5 minutes.',
  },
];

export default function FAQPage() {
  return (
    <PublicNavFooter>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <div className="text-center mb-12">
          <h1 className="text-4xl sm:text-5xl font-black text-white mb-4 tracking-tight">
            Frequently Asked Questions
          </h1>
          <p className="text-lg text-gray-400 max-w-xl mx-auto">
            Everything you need to know about Vyom Ai Cloud.
          </p>
        </div>

        <div className="space-y-4">
          {FAQS.map((faq, i) => (
            <div key={i} className="p-6 rounded-2xl border border-white/5 bg-white/[0.02]">
              <h2 className="text-white font-bold mb-3">{faq.q}</h2>
              <p className="text-sm text-gray-400 leading-relaxed">{faq.a}</p>
            </div>
          ))}
        </div>

        <div className="text-center mt-16 py-12 border-t border-white/5">
          <h2 className="text-2xl font-bold text-white mb-3">Still have questions?</h2>
          <p className="text-gray-400 mb-6">
            Contact us directly and we&apos;ll get back to you as soon as possible.
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
        </div>
      </div>
    </PublicNavFooter>
  );
}
