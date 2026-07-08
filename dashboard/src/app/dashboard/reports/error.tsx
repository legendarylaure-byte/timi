'use client';

import { useEffect } from 'react';

export default function ReportsError({ error, reset }: { error: Error; reset: () => void }) {
  useEffect(() => { console.error('[REPORTS]', error); }, [error]);

  return (
    <div className="flex flex-col items-center justify-center py-20">
      <div className="text-4xl mb-4">📊</div>
      <h2 className="text-xl font-bold text-light-text dark:text-dark-text mb-2">Reports Unavailable</h2>
      <p className="text-light-muted dark:text-dark-muted text-sm mb-6 max-w-md text-center">
        {error.message || 'Failed to load report data. The pipeline may still be collecting data.'}
      </p>
      <button onClick={reset} className="btn-primary px-6 py-2 rounded-xl text-sm">
        Try Again
      </button>
    </div>
  );
}
