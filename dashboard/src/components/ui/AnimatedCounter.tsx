'use client';

import { useEffect, useState } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

interface AnimatedCounterProps {
  value: number | string;
  duration?: number;
  prefix?: string;
  suffix?: string;
}

export function AnimatedCounter({ value, duration = 1.5, prefix = '', suffix = '' }: AnimatedCounterProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const numericValue = typeof value === 'string' ? parseFloat(value.replace(/[^0-9.-]/g, '')) || 0 : value;
  const springValue = useSpring(0, { stiffness: 100, damping: 30, duration: duration * 1000 });

  useEffect(() => {
    springValue.set(numericValue);
    const unsubscribe = springValue.on('change', (latest) => {
      setDisplayValue(Math.round(latest));
    });
    return () => unsubscribe();
  }, [numericValue, springValue]);

  return (
    <motion.span
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="tabular-nums"
    >
      {prefix}{displayValue.toLocaleString()}{suffix}
    </motion.span>
  );
}
