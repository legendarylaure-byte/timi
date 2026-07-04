import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Terms of Service — Vyom Ai Cloud',
  description: 'Terms of Service for Vyom Ai Cloud (Timi)',
};

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Terms of Service</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">Last updated: July 4, 2026</p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            By accessing or using Vyom Ai Cloud (&ldquo;Timi&rdquo;, &ldquo;the Service&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;), 
            you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">2. Description of Service</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            Timi is an AI-powered video automation platform that generates, edits, and publishes 
            educational technology content to connected social media platforms including YouTube, TikTok, 
            Instagram, and Facebook. The Service operates on your behalf only after you explicitly 
            authorize each connected platform via OAuth.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">3. User Responsibilities</h2>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li>You are responsible for all content published through the Service.</li>
            <li>You must comply with each platform&apos;s terms of service and community guidelines.</li>
            <li>You must not use the Service for illegal, harmful, or deceptive purposes.</li>
            <li>You are responsible for maintaining the confidentiality of your API keys and credentials.</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">4. Data & Privacy</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            Our handling of your data is governed by our Privacy Policy. We store only the data 
            necessary to operate the Service, including OAuth tokens, video metadata, and publishing 
            history. We do not sell your data.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">5. Limitation of Liability</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            The Service is provided &ldquo;as is&rdquo; without warranties of any kind. We are not liable 
            for any damages arising from your use of the Service, including but not limited to content 
            removal, account suspension, or platform policy violations by third-party platforms.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">6. Changes to Terms</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            We reserve the right to modify these terms at any time. Continued use of the Service 
            after changes constitutes acceptance of the new terms.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">7. Contact</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            For questions about these terms, contact us at support@vyomai.cloud.
          </p>
        </section>
      </div>
    </main>
  );
}
