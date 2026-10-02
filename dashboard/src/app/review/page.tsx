'use client';

import { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { apiFetch } from '@/lib/api-fetch';

function ReviewContent() {
  const searchParams = useSearchParams();
  const [connected, setConnected] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get('demo_connected') === 'true') {
      setConnected(true);
    }
    const err = searchParams.get('error');
    if (err) setErrorMsg(err);
  }, [searchParams]);

  const startConnect = () => {
    window.location.href = '/api/auth/meta?action=connect&demo=1';
  };

  const publishTest = async () => {
    setPublishing(true);
    setResult(null);
    setErrorMsg(null);
    try {
      const res = await apiFetch('/api/review/publish', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        setResult({ ok: true, message: `Published successfully. Post ID: ${data.post_id}` });
      } else {
        setResult({ ok: false, message: data.error || 'Publish failed' });
      }
    } catch (e: any) {
      setResult({ ok: false, message: e.message || 'Network error' });
    } finally {
      setPublishing(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#050510] text-gray-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md space-y-5">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">Timi Video</h1>
          <p className="text-sm text-gray-400">Meta App Review - Permission Demo</p>
        </div>

        {errorMsg && (
          <div className="rounded-lg bg-dark-error/10 border border-dark-error/40 p-3 text-sm text-dark-error">
            Error: {errorMsg}
          </div>
        )}

        <div className="rounded-xl bg-white/5 border border-white/10 p-5 space-y-3">
          <h2 className="font-semibold">1. Connect your account</h2>
          <p className="text-sm text-gray-400">
            Click below to open the Facebook Login consent dialog. Approve it to demonstrate the
            authorization flow for the requested scopes.
          </p>
          <button
            onClick={startConnect}
            disabled={connected}
            className="w-full rounded-lg bg-[#0f5fbf] hover:bg-[#0b4d9c] disabled:opacity-50 py-2.5 font-semibold text-white transition-colors"
          >
            {connected ? 'Connected \u2713' : 'Connect Facebook'}
          </button>
        </div>

        <div className="rounded-xl bg-white/5 border border-white/10 p-5 space-y-3">
          <h2 className="font-semibold">2. Test publishing</h2>
          <p className="text-sm text-gray-400">
            Publishes a status to the linked Facebook Page using the app&apos;s authorized token,
            demonstrating the publish / manage-posts permission in use.
          </p>
          {/* Button fills are darkened from the brand hues, deliberately.
              White on Meta's #1877F2 is 4.2:1 and white on emerald-400
              (`dark-success`, 1.75:1) is unreadable, both short of the 4.5:1
              needed for 16px text. `dark-success` is a text token meant to sit
              ON dark, not to be a fill. A Meta reviewer reads this page, so
              legibility here is an approval concern, not just accessibility. */}
          <button
            onClick={publishTest}
            disabled={publishing}
            className="w-full rounded-lg bg-[#047857] hover:bg-[#065f46] disabled:opacity-50 py-2.5 font-semibold text-white transition-colors"
          >
            {publishing ? 'Publishing...' : 'Publish test post'}
          </button>
          {result && (
            <p className={`text-sm ${result.ok ? 'text-dark-success' : 'text-dark-error'}`}>
              {result.message}
            </p>
          )}
        </div>

        <p className="text-center text-xs text-gray-400">
          This is a restricted demo page for Meta App Review. It does not expose any account
          credentials or dashboard data.
        </p>
      </div>
    </main>
  );
}

export default function ReviewPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#050510] flex items-center justify-center text-gray-200">Loading...</div>}>
      <ReviewContent />
    </Suspense>
  );
}
