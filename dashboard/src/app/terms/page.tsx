import type { Metadata } from 'next';
import Image from 'next/image';

export const metadata: Metadata = {
  title: 'Vyom Ai Cloud Terms of Service',
  description: 'Terms of Service for Vyom Ai Cloud (Timi)',
};

export default function TermsPage() {
  return (
    <main className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative w-16 h-16 mx-auto mb-6">
          <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-contain" />
        </div>
        <h1 className="text-3xl font-bold mb-8">Vyom Ai Cloud Terms of Service</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">Last updated: September 2, 2026</p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">1. Acceptance of Terms</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            By accessing or using the Vyom Ai Cloud service, website, or applications (&ldquo;Vyom Ai Cloud&rdquo;, &ldquo;Timi&rdquo;, &ldquo;the Service&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;), you agree to be bound by these Terms of Service. If you do not agree, do not use the Service.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">2. Description of Service</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            Vyom Ai Cloud (also known as Timi) is an AI-powered video automation platform that generates, edits, and publishes educational technology content to connected social media platforms including YouTube, TikTok, Instagram, and Facebook. The Service operates on your behalf only after you explicitly authorize each connected platform via OAuth.
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
          <h2 className="text-xl font-semibold mb-3">5a. TikTok Publishing Terms</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            By using the Service to publish content to TikTok, you agree to the following:
          </p>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li><strong>Ownership and rights:</strong> You confirm that you own or have all necessary rights,
            licenses, and permissions to the content you publish to TikTok, and that the content does not
            infringe the rights of any third party.</li>
            <li><strong>Privacy selection is manual:</strong> You must actively select the privacy level for each
            post. No default privacy level is preselected, and the Service posts only to the TikTok account you
            authorize via OAuth.</li>
            <li><strong>Music Usage Confirmation:</strong> By posting, you agree to TikTok&apos;s Music Usage
            Confirmation. You are responsible for ensuring any audio in your posts is used with permission.</li>
            <li><strong>Branded Content Policy:</strong> If you enable branded or commercial content disclosure,
            you agree to comply with TikTok&apos;s Branded Content Policy and to label such content accurately.</li>
            <li><strong>AI-generated content:</strong> You agree to comply with TikTok&apos;s policies on
            AI-generated content (AIGC), including labeling synthetic or AI-generated media where required.</li>
            <li><strong>Platform compliance:</strong> You agree to comply with TikTok&apos;s Terms of Service and
            Community Guidelines and acknowledge that TikTok may remove content or suspend your account for
            violations, for which we are not responsible.</li>
          </ul>
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
