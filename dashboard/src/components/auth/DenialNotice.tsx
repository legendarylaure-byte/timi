'use client';

import { motion } from 'framer-motion';
import { Mail } from 'lucide-react';
import { CONTACT_EMAIL, BRAND, COMPANY } from '@/lib/brand';
import { DENIAL_HEADLINE } from '@/lib/auth-errors';

/**
 * The one place a definitive allowlist denial is rendered.
 *
 * Login and signup both hit it, and both previously inlined a red <p> with a
 * technical sentence. Two consequences: the friendly copy had to be written
 * twice (and was), and a genuine 401/500 looked identical to "you are not
 * allowed", which is the exact confusion this whole module exists to remove.
 *
 * The caller decides which kind of failure it is; this component only ever
 * renders the denial, so contact copy can never appear next to a real error.
 */
export default function DenialNotice({ detail }: { detail: string }) {
  return (
    <motion.div
      // Honour the OS setting rather than animating regardless: this is an
      // error state, and motion adds nothing to it.
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      role="alert"
      aria-live="polite"
      className="rounded-2xl border border-violet-500/40 bg-violet-500/10 p-4 text-left"
    >
      <div className="flex items-start gap-3">
        <div
          aria-hidden
          className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
          style={{ background: 'rgba(155,77,255,0.18)' }}
        >
          <Mail className="h-4 w-4" style={{ color: BRAND.lightOrange }} />
        </div>

        <div className="min-w-0">
          <p className="font-display text-sm font-semibold text-white">
            {DENIAL_HEADLINE}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-white/75">{detail}</p>
          <p className="mt-2 text-xs text-white/50">
            Access to Timi is managed by {COMPANY.shortName}.
          </p>
        </div>
      </div>
    </motion.div>
  );
}

/** A mailto link with the same copy, for pages that want the address separate. */
export function ContactLink({ className = '' }: { className?: string }) {
  return (
    <a
      href={`mailto:${CONTACT_EMAIL}`}
      className={`underline underline-offset-4 hover:text-white transition-colors ${className}`}
    >
      {CONTACT_EMAIL}
    </a>
  );
}
