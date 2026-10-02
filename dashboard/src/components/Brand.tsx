'use client';

import Image from 'next/image';
import Link from 'next/link';
import { COMPANY, BRAND_GRADIENT } from '@/lib/brand';

export function BrandLogo({ size = 36 }: { size?: number }) {
  return (
    <Image
      src="/logo.svg"
      alt={`${COMPANY.shortName} logo`}
      width={size}
      height={size}
      priority={size >= 128}
    />
  );
}

/**
 * The shared wordmark. It keeps "Vyom Ai Cloud" above "Timi" so login matches
 * the requested co-branding ("Vyom Ai Cloud above Timi on login"), without
 * duplicating the gradient/title in every page.
 */
export function BrandWordmark({
  withByline = false,
  withProductLine = false,
  className = '',
}: {
  withByline?: boolean;
  withProductLine?: boolean;
  className?: string;
}) {
  return (
    <div className={`flex flex-col items-center lg:items-start ${className}`}>
      <Link href="/" className="flex flex-col items-center lg:items-start group">
        <span className="font-display text-sm uppercase tracking-[0.18em] text-white/60 group-hover:text-white/70 transition-colors">
          {COMPANY.shortName}
        </span>
        <h1
          className="font-display text-5xl sm:text-6xl lg:text-7xl font-bold tracking-tight leading-[0.95]"
          style={{
            background: BRAND_GRADIENT,
            backgroundSize: '200% auto',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            animation: 'shimmer 3s ease-in-out infinite',
          }}
        >
          Timi
        </h1>
      </Link>

      {withByline && (
        <p className="mt-2 text-sm text-white/60">
          Built by {COMPANY.shortName}, Nepal
        </p>
      )}
      {withProductLine && (
        <p className="mt-1 text-xs text-white/50">
          Timi is a {COMPANY.shortName} product
        </p>
      )}
    </div>
  );
}

/**
 * Small co-brand strip used in shells/footers where "Timi is a Vyom Ai Cloud
 * product" must be explicit.
 */
export function BrandCoProduct({ className = '' }: { className?: string }) {
  return (
    <span className={`text-xs text-white/50 ${className}`}>
      Timi is a {COMPANY.shortName} product
    </span>
  );
}
