import type { Metadata } from 'next';
import Image from 'next/image';

export const metadata: Metadata = {
  title: 'Vyom Ai Cloud Privacy Policy',
  description: 'Privacy Policy for Vyom Ai Cloud (Timi)',
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative w-16 h-16 mx-auto mb-6">
          <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-contain" />
        </div>
        <h1 className="text-3xl font-bold mb-8">Vyom Ai Cloud Privacy Policy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">Last updated: September 2, 2026</p>

        <section className="mb-8">
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            This Privacy Policy explains how <strong>Vyom Ai Cloud</strong> (&ldquo;Timi&rdquo;, &ldquo;we&rdquo;, &ldquo;us&rdquo;, &ldquo;our&rdquo;) collects, uses, and protects your information when you use the Vyom Ai Cloud service, website, and applications (collectively, the &ldquo;Service&rdquo;). By accessing or using the Vyom Ai Cloud service, you agree to the collection and use of information in accordance with this policy.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">1. Information We Collect</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            Vyom Ai Cloud collects only the information necessary to operate the Service:
          </p>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li><strong>OAuth Tokens:</strong> Access and refresh tokens for YouTube, TikTok, Instagram, and Facebook, obtained only after your explicit authorization.</li>
            <li><strong>Channel/Profile Info:</strong> Basic profile information (channel name, profile image, subscriber/follower counts) from connected platforms.</li>
            <li><strong>Video Metadata:</strong> Titles, descriptions, thumbnails, and performance metrics of videos published through the Service.</li>
            <li><strong>Usage Data:</strong> Pipeline execution logs, error reports, and feature usage statistics for improving the Service.</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">2. How We Use Your Information</h2>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li>To publish content to your connected social media platforms.</li>
            <li>To generate analytics and insights about your published content.</li>
            <li>To improve and maintain the Service.</li>
            <li>To communicate with you about Service updates and issues.</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">3. Data Storage & Security</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            Vyom Ai Cloud stores your data securely using:
          </p>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li><strong>Firebase Firestore:</strong> Encrypted at rest and in transit for operational data.</li>
            <li><strong>Cloudflare R2:</strong> Encrypted object storage for video files.</li>
            <li><strong>Sentry:</strong> Error reporting (no personal data intentionally collected).</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">4. Data Sharing</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            Vyom Ai Cloud does not sell, trade, or share your personal data with third parties except:
          </p>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li>As required by platform APIs (e.g., sending videos to YouTube/TikTok via their APIs).</li>
            <li>If required by law or to protect our legal rights.</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">5. Third-Party Services</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            The Service integrates with: Google (YouTube), TikTok, Meta (Instagram/Facebook), 
            Groq, Ollama, Google Gemini, Cloudflare R2, Firebase (Google), and Sentry. 
            Each service has its own privacy policy governing data handling.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">5a. Posting to TikTok</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            Vyom Ai Cloud uses TikTok&apos;s Content Posting API (Login Kit and Content Posting API, scopes
            <code className="text-teal-600 dark:text-teal-400"> user.info.basic</code>, <code className="text-teal-600 dark:text-teal-400">video.upload</code>, and <code className="text-teal-600 dark:text-teal-400">video.publish</code>) to publish
            videos to a TikTok account only after you explicitly authorize that account via TikTok&apos;s OAuth
            consent screen. The Service posts <strong>only to the TikTok account you connect and authorize</strong>,
            and it never posts to third-party accounts.
          </p>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            <strong>Privacy selection is made by you for each post:</strong> when composing a post, the Service
            retrieves the available privacy options directly from TikTok (<code className="text-teal-600 dark:text-teal-400">privacy_level_options</code>)
            and presents them to you to choose from. There is <strong>no default privacy level preselected</strong>;
            you must actively choose the visibility of every post. The Service honors and sends exactly the privacy
            level you select to TikTok and does not override your choice.
          </p>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            <strong>What data is sent to TikTok:</strong> when you publish, the Service transmits the video file and
            the metadata you provide (title/caption, your selected privacy level, and your chosen comment, duet, and
            stitch settings) to TikTok via its API for posting. This transmission occurs only after you explicitly
            confirm the post. Your TikTok access token is used solely to authenticate these posting requests and is
            stored securely; it can be revoked at any time from your TikTok account settings.
          </p>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            <strong>AI-generated content disclosure:</strong> where a video published through the Service contains
            AI-generated or synthetic content, we disclose this in accordance with TikTok&apos;s AI-generated content
            guidelines. You are responsible for ensuring the content you publish complies with TikTok&apos;s Terms of
            Service and Community Guidelines.
          </p>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            <strong>Consent declaration:</strong> before publishing to TikTok, the Service displays the consent
            declaration required by TikTok, including <em>&ldquo;By posting, you agree to TikTok&apos;s Music Usage
            Confirmation&rdquo;</em>. You confirm the post only after reviewing this declaration.
          </p>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            <strong>Limited retention:</strong> SSID access and posting metadata are used only to operate the
            Service and are not retained longer than necessary. You can disconnect your TikTok account from the
            dashboard at any time, which revokes the Service&apos;s ability to post on your behalf.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">6. Your Rights</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            Depending on your jurisdiction, you may have the right to:
          </p>
          <ul className="list-disc pl-6 text-gray-700 dark:text-gray-300 leading-relaxed space-y-2">
            <li>Access, correct, or delete your personal data.</li>
            <li>Withdraw consent for OAuth access at any time (via each platform&apos;s settings).</li>
            <li>Request a copy of your data in a portable format.</li>
          </ul>
        </section>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">7. Contact</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
            For privacy-related inquiries about the Vyom Ai Cloud app, contact us at: privacy@vyomai.cloud
          </p>
        </section>
      </div>
    </main>
  );
}
