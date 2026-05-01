'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface Sphere {
  id: number;
  x: number;
  color: string;
  size: number;
  duration: number;
  delay: number;
  amplitude: number;
}

interface Star {
  id: number;
  x: number;
  y: number;
  color: string;
  size: number;
  duration: number;
  delay: number;
}

interface Sparkle {
  id: number;
  x: number;
  size: number;
  duration: number;
  delay: number;
}

export function HappyScene() {
  const [spheres, setSpheres] = useState<Sphere[]>([]);
  const [stars, setStars] = useState<Star[]>([]);
  const [sparkles, setSparkles] = useState<Sparkle[]>([]);

  useEffect(() => {
    const agentColors = ['#FF4D6D', '#7C3AED', '#FBBF24', '#10B981', '#3B82F6', '#F59E0B', '#A78BFA', '#60A5FA', '#34D399'];
    setSpheres(
      Array.from({ length: 9 }, (_, i) => ({
        id: i,
        x: 10 + i * 10,
        color: agentColors[i],
        size: 12 + Math.random() * 8,
        duration: 1.5 + Math.random() * 1,
        delay: i * 0.15,
        amplitude: 20 + Math.random() * 15,
      }))
    );

    setStars(
      Array.from({ length: 15 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        y: 10 + Math.random() * 60,
        color: ['#FBBF24', '#FF4D6D', '#7C3AED', '#3B82F6', '#10B981'][i % 5],
        size: 3 + Math.random() * 4,
        duration: 2 + Math.random() * 3,
        delay: Math.random() * 2,
      }))
    );

    setSparkles(
      Array.from({ length: 25 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        size: 2 + Math.random() * 3,
        duration: 3 + Math.random() * 4,
        delay: Math.random() * 3,
      }))
    );
  }, []);

  return (
    <div className="w-full h-64 sm:h-72 md:h-80 lg:h-96 rounded-2xl overflow-hidden relative" style={{
      background: 'linear-gradient(135deg, #FFFBF5 0%, #FFF7ED 30%, #FEF3C7 60%, #FFFBF5 100%)',
    }}>
      {/* Animated gradient overlay */}
      <div className="absolute inset-0 aurora-bg opacity-10" />

      {/* Sun */}
      <motion.div
        className="absolute left-1/2 -translate-x-1/2"
        style={{ top: '15%' }}
        animate={{ y: [0, -8, 0], scale: [1, 1.03, 1] }}
        transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut' }}
      >
        {/* Sun glow */}
        <motion.div
          className="absolute inset-0 rounded-full blur-xl"
          style={{ width: 80, height: 80, marginLeft: -10, marginTop: -10 }}
          animate={{ opacity: [0.3, 0.5, 0.3] }}
          transition={{ duration: 2, repeat: Infinity }}
        />
        {/* Sun body */}
        <div className="relative w-16 h-16 rounded-full" style={{ background: 'radial-gradient(circle at 35% 35%, #FDE68A, #FBBF24, #F59E0B)' }}>
          {/* Eyes */}
          <div className="absolute w-2 h-2 rounded-full bg-gray-800" style={{ top: '35%', left: '30%' }} />
          <div className="absolute w-2 h-2 rounded-full bg-gray-800" style={{ top: '35%', right: '30%' }} />
          {/* Eye shine */}
          <div className="absolute w-1 h-1 rounded-full bg-white" style={{ top: '32%', left: '33%' }} />
          <div className="absolute w-1 h-1 rounded-full bg-white" style={{ top: '32%', right: '33%' }} />
          {/* Smile */}
          <div className="absolute w-5 h-2.5 rounded-b-full border-b-2 border-transparent" style={{ top: '55%', left: '50%', transform: 'translateX(-50%)', borderBottomColor: '#FF4D6D' }} />
          {/* Cheeks */}
          <div className="absolute w-3 h-2 rounded-full bg-rose-400/30" style={{ top: '50%', left: '12%' }} />
          <div className="absolute w-3 h-2 rounded-full bg-rose-400/30" style={{ top: '50%', right: '12%' }} />
        </div>
        {/* Rays */}
        {Array.from({ length: 8 }).map((_, i) => {
          const angle = (i / 8) * 360;
          return (
            <motion.div
              key={i}
              className="absolute w-1 rounded-full"
              style={{
                height: 10,
                background: '#FBBF24',
                top: '50%',
                left: '50%',
                transformOrigin: 'center center',
                transform: `rotate(${angle}deg) translateY(-40px)`,
              }}
              animate={{ opacity: [0.4, 0.8, 0.4], height: [8, 12, 8] }}
              transition={{ duration: 2, repeat: Infinity, delay: i * 0.25 }}
            />
          );
        })}
      </motion.div>

      {/* Rainbow Arc */}
      <div className="absolute left-1/2 -translate-x-1/2 opacity-30" style={{ top: '5%', width: 200, height: 100 }}>
        {['#FF4D6D', '#F59E0B', '#FBBF24', '#10B981', '#3B82F6', '#7C3AED'].map((color, i) => (
          <motion.div
            key={i}
            className="absolute rounded-full border-2"
            style={{
              width: 200 - i * 12,
              height: 100 - i * 6,
              left: i * 6,
              top: i * 3,
              borderColor: color,
              borderRadius: '50% 50% 0 0',
              borderBottom: 'none',
            }}
            animate={{ scaleY: [1, 1.02, 1] }}
            transition={{ duration: 3 + i * 0.2, repeat: Infinity }}
          />
        ))}
      </div>

      {/* Twinkling Stars */}
      {stars.map((star) => (
        <motion.div
          key={`star-${star.id}`}
          className="absolute"
          style={{
            left: `${star.x}%`,
            top: `${star.y}%`,
            width: star.size,
            height: star.size,
          }}
        >
          <motion.div
            className="w-full h-full rounded-full"
            style={{ background: star.color }}
            animate={{ scale: [0.5, 1.5, 0.5], opacity: [0.3, 1, 0.3] }}
            transition={{ duration: star.duration, repeat: Infinity, delay: star.delay }}
          />
        </motion.div>
      ))}

      {/* Rising Sparkles */}
      {sparkles.map((s) => (
        <motion.div
          key={`sparkle-${s.id}`}
          className="absolute rounded-full"
          style={{
            left: `${s.x}%`,
            width: s.size,
            height: s.size,
            background: '#FBBF24',
          }}
          animate={{
            y: [0, -200],
            opacity: [0, 0.6, 0],
            x: [0, Math.sin(s.id) * 20, 0],
          }}
          transition={{ duration: s.duration, repeat: Infinity, delay: s.delay, ease: 'easeOut' }}
        />
      ))}

      {/* Bouncing Agent Spheres */}
      {spheres.map((sphere) => (
        <motion.div
          key={`sphere-${sphere.id}`}
          className="absolute rounded-full"
          style={{
            left: `${sphere.x}%`,
            width: sphere.size,
            height: sphere.size,
            background: `radial-gradient(circle at 35% 35%, white, ${sphere.color})`,
            boxShadow: `0 4px 12px ${sphere.color}40`,
            bottom: '15%',
          }}
          animate={{
            y: [0, -sphere.amplitude, 0],
          }}
          transition={{
            duration: sphere.duration,
            repeat: Infinity,
            delay: sphere.delay,
            ease: 'easeInOut',
          }}
        />
      ))}

      {/* Drifting Clouds */}
      {[0, 1, 2].map((i) => (
        <motion.div
          key={`cloud-${i}`}
          className="absolute flex gap-1"
          style={{ top: `${25 + i * 15}%` }}
          initial={{ x: -120 }}
          animate={{ x: 'calc(100% + 120px)' }}
          transition={{ duration: 15 + i * 8, repeat: Infinity, ease: 'linear', delay: i * 4 }}
        >
          {[0, 1, 2, 3].map((j) => (
            <div
              key={j}
              className="rounded-full bg-white/60"
              style={{
                width: 20 + j * 8,
                height: 12 + j * 4,
              }}
            />
          ))}
        </motion.div>
      ))}

      {/* Floating Music Notes */}
      {['♪', '♫', '♬', '♩'].map((note, i) => (
        <motion.div
          key={`note-${i}`}
          className="absolute text-2xl font-bold"
          style={{
            left: `${20 + i * 18}%`,
            color: ['#FF4D6D', '#7C3AED', '#3B82F6', '#10B981'][i],
            opacity: 0.4,
          }}
          animate={{
            y: [0, -40, 0],
            x: [0, 15, 0],
            rotate: [-10, 10, -10],
            opacity: [0.2, 0.5, 0.2],
          }}
          transition={{ duration: 3 + i, repeat: Infinity, delay: i * 0.8, ease: 'easeInOut' }}
        >
          {note}
        </motion.div>
      ))}
    </div>
  );
}
