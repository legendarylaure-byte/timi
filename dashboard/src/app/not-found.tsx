import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 bg-light-bg dark:bg-dark-bg">
      <div className="text-center">
        <div className="text-8xl font-black gradient-text mb-4">404</div>
        <h1 className="text-2xl font-bold text-light-text dark:text-dark-text mb-2">Page Not Found</h1>
        <p className="text-light-muted dark:text-dark-muted mb-6">The page you&apos;re looking for doesn&apos;t exist.</p>
        <Link
          href="/dashboard"
          className="px-6 py-3 rounded-2xl text-white font-semibold inline-block"
          style={{ background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)' }}
        >
          Back to Dashboard
        </Link>
      </div>
    </div>
  );
}
