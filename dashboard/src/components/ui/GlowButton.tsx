'use client';

import { motion, MotionProps } from 'framer-motion';
import { ReactNode } from 'react';

interface GlowButtonProps {
  children: ReactNode;
  variant?: 'primary' | 'secondary' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
}

const variants: Record<string, string> = {
  primary: 'from-light-primary to-light-secondary text-white',
  secondary: 'from-light-secondary to-light-info text-white',
  ghost: 'bg-transparent text-light-text dark:text-dark-text hover:bg-light-primary/10 dark:hover:bg-light-primary/20',
};

const sizes: Record<string, string> = {
  sm: 'px-4 py-2 text-sm rounded-xl',
  md: 'px-6 py-3 text-base rounded-2xl',
  lg: 'px-8 py-4 text-lg rounded-2xl',
};

export function GlowButton({ children, variant = 'primary', size = 'md', isLoading = false, disabled, onClick, className = '' }: GlowButtonProps) {
  const isGhost = variant === 'ghost';

  const motionProps: MotionProps = {
    whileHover: !disabled && !isLoading ? { scale: 1.02 } : undefined,
    whileTap: !disabled && !isLoading ? { scale: 0.98 } : undefined,
  };

  return (
    <motion.button
      {...motionProps}
      disabled={disabled || isLoading}
      onClick={onClick}
      className={`relative font-semibold transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${sizes[size]} ${className} ${
        isGhost
          ? variants.ghost
          : `${variants[variant]} overflow-hidden`
      }`}
    >
      {!isGhost && !disabled && (
        <div className="absolute inset-0 bg-gradient-to-r from-light-primary via-light-accent to-light-secondary opacity-0 group-hover:opacity-100 transition-opacity blur-xl" />
      )}
      <div className="relative flex items-center justify-center gap-2">
        {isLoading ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            className="w-5 h-5 border-2 border-white border-t-transparent rounded-full"
          />
        ) : (
          children
        )}
      </div>
    </motion.button>
  );
}
