'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center gap-6">
      <div className="text-center">
        <div className="text-6xl mb-4">⚠️</div>
        <h2 className="text-2xl font-bold text-light-text dark:text-dark-text mb-2">
          Dashboard Error
        </h2>
        <p className="text-light-muted dark:text-dark-muted mb-6">{error.message}</p>
        <button
          onClick={reset}
          className="px-6 py-3 rounded-2xl text-white font-semibold"
          style={{ background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)' }}
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
