'use client';

export default function DashboardSectionError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-12 text-center">
      <span className="text-4xl mb-4 block">⚠️</span>
      <h2 className="text-xl font-bold text-light-text dark:text-dark-text mb-2">Something went wrong</h2>
      <p className="text-light-muted dark:text-dark-muted mb-4 max-w-md mx-auto">
        {error.message || 'An unexpected error occurred in this section.'}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 text-white text-sm font-medium hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
