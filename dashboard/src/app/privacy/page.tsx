import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Vyom Ai Cloud Privacy Policy',
  description: 'Privacy Policy for Vyom Ai Cloud (Timi)',
};

export default function PrivacyPage() {
  return (
    <main className="min-h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 py-16 px-4">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-8">Vyom Ai Cloud Privacy Policy</h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-8">Last updated: July 4, 2026</p>

        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-3">1. Information We Collect</h2>
          <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-3">
            We collect only the information necessary to operate the Service:
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
            Your data is stored securely using:
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
            We do not sell, trade, or share your personal data with third parties except:
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
            For privacy-related inquiries: privacy@vyomai.cloud
          </p>
        </section>
      </div>
    </main>
  );
}
