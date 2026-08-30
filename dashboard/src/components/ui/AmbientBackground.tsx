'use client';

interface AmbientBackgroundProps {
  variant?: 'dashboard' | 'landing';
  className?: string;
}

export function AmbientBackground({ variant = 'dashboard', className = '' }: AmbientBackgroundProps) {
  const scene = variant === 'landing' ? 'dark-scene' : 'dark-scene';
  return (
    <div aria-hidden="true" className={`ambient-scene ${scene} fixed inset-0 -z-10 overflow-hidden pointer-events-none ${className}`}>
      <div className="ambient-orb-lg w-[42rem] h-[42rem] -top-40 -left-40" style={{ background: 'radial-gradient(circle, rgba(236,19,62,0.55), transparent 70%)' }} />
      <div className="ambient-orb-lg w-[40rem] h-[40rem] -bottom-48 -right-32" style={{ background: 'radial-gradient(circle, rgba(78,205,196,0.45), transparent 70%)' }} />
      <div className="ambient-orb w-72 h-72 top-1/3 left-2/3" style={{ background: 'radial-gradient(circle, rgba(244,113,139,0.5), transparent 70%)', animationDelay: '-8s' }} />
      <div className="ambient-orb-sm w-44 h-44 top-24 right-1/4" style={{ background: 'radial-gradient(circle, rgba(212,184,150,0.4), transparent 70%)', animationDelay: '-4s' }} />
      <div className="ambient-orb-sm w-40 h-40 bottom-24 left-1/3" style={{ background: 'radial-gradient(circle, rgba(78,205,196,0.4), transparent 70%)', animationDelay: '-12s' }} />
    </div>
  );
}
