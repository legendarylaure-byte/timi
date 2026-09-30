'use client';

import { useRouter } from 'next/navigation';
import { auth } from '@/lib/firebase';
import { isAllowedUser } from '@/lib/api-fetch';

/**
 * Land on /dashboard, or on the page that explains why you can't.
 *
 * The auth check happens at CLICK time, not render time. The landing page
 * decides which button to show from a cached auth state that is briefly null
 * on first paint, so a render-time check routes people on stale information.
 *
 * Signed in but not on the allowlist -> signed out and told why, rather than
 * dropped into a dashboard where every panel 403s.
 */
export function useGoToDashboard() {
  const router = useRouter();
  return async () => {
    if (!auth.currentUser) {
      router.push('/login?next=/dashboard');
      return;
    }
    if (!(await isAllowedUser())) {
      await auth.signOut();
      router.push('/login?error=not_allowed');
      return;
    }
    router.push('/dashboard');
  };
}

/**
 * Only same-site paths. `?next=` is attacker-supplied, so `//evil.com` and
 * `https://evil.com` would otherwise turn this into an open redirect.
 */
export function safeNext(value: string | null): string {
  return value && value.startsWith('/') && !value.startsWith('//') ? value : '/dashboard';
}
