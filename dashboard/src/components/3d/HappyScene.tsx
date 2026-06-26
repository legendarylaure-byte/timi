'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';

interface CodeSymbol {
  id: number;
  x: number;
  symbol: string;
  size: number;
  duration: number;
  delay: number;
  color: string;
}

interface NodePoint {
  id: number;
  x: number;
  y: number;
  size: number;
  delay: number;
}

export function HappyScene() {
  const [symbols, setSymbols] = useState<CodeSymbol[]>([]);
  const [nodes, setNodes] = useState<NodePoint[]>([]);

  useEffect(() => {
    const codeSymbols = ['{', '}', '<', '>', '[', ']', '/', '=', '&&', '||', '=>', '()', '...', '/*', '*/'];
    const colors = ['#ec133e', '#bd0f32', '#f4718b', '#6B7280', '#2563EB', '#059669', '#D97706'];
    setSymbols(
      Array.from({ length: 20 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        symbol: codeSymbols[i % codeSymbols.length],
        size: 12 + Math.random() * 14,
        duration: 4 + Math.random() * 6,
        delay: Math.random() * 3,
        color: colors[i % colors.length],
      }))
    );
    setNodes(
      Array.from({ length: 12 }, (_, i) => ({
        id: i,
        x: Math.random() * 100,
        y: 10 + Math.random() * 80,
        size: 4 + Math.random() * 6,
        delay: Math.random() * 2,
      }))
    );
  }, []);

  return (
    <div className="w-full h-64 sm:h-72 md:h-80 lg:h-96 rounded-2xl overflow-hidden relative" style={{
      background: 'linear-gradient(135deg, #1a1a1a 0%, #210309 30%, #2d0a10 60%, #1a1a1a 100%)',
    }}>
      {/* Grid overlay */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: 'linear-gradient(#ec133e 1px, transparent 1px), linear-gradient(90deg, #ec133e 1px, transparent 1px)',
        backgroundSize: '40px 40px',
      }} />

      {/* Neural network connections */}
      <svg className="absolute inset-0 w-full h-full opacity-20">
        {nodes.map((a, i) =>
          nodes.slice(i + 1).map((b, j) => (
            <line
              key={`conn-${i}-${j}`}
              x1={`${a.x}%`}
              y1={`${a.y}%`}
              x2={`${b.x}%`}
              y2={`${b.y}%`}
              stroke="#ec133e"
              strokeWidth="0.5"
              opacity={0.3 + Math.sin(i + j) * 0.2}
            />
          ))
        )}
      </svg>

      {/* Neural nodes */}
      {nodes.map((node) => (
        <motion.div
          key={`node-${node.id}`}
          className="absolute rounded-full"
          style={{
            left: `${node.x}%`,
            top: `${node.y}%`,
            width: node.size,
            height: node.size,
            background: '#ec133e',
            boxShadow: '0 0 8px #ec133e80',
          }}
          animate={{
            scale: [1, 1.5, 1],
            opacity: [0.4, 0.8, 0.4],
          }}
          transition={{ duration: 3, repeat: Infinity, delay: node.delay, ease: 'easeInOut' }}
        />
      ))}

      {/* Floating code symbols */}
      {symbols.map((s) => (
        <motion.div
          key={`sym-${s.id}`}
          className="absolute font-mono font-bold"
          style={{
            left: `${s.x}%`,
            fontSize: s.size,
            color: s.color,
            opacity: 0.15,
          }}
          animate={{
            y: [0, -60, 0],
            opacity: [0.08, 0.25, 0.08],
            rotate: [-5, 5, -5],
          }}
          transition={{ duration: s.duration, repeat: Infinity, delay: s.delay, ease: 'easeInOut' }}
        >
          {s.symbol}
        </motion.div>
      ))}

      {/* Terminal cursor blink */}
      <motion.div
        className="absolute font-mono text-xs"
        style={{ left: '8%', bottom: '12%', color: '#10B981', opacity: 0.3 }}
      >
        <motion.span
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 1, repeat: Infinity }}
        >
          _
        </motion.span>
        <span className="ml-1">/workspace/agents</span>
      </motion.div>

      {/* Scrolling hex line */}
      <motion.div
        className="absolute font-mono text-[10px] tracking-widest"
        style={{ right: '6%', top: '15%', color: '#f4718b', opacity: 0.15 }}
        animate={{ y: [0, -30, 0] }}
        transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
      >
        0x7C 0xA3 0xF1 0x4D 0x9E 0x2B
      </motion.div>

      {/* Data flow bar */}
      <motion.div
        className="absolute bottom-0 left-0 right-0 h-0.5"
        style={{ background: 'linear-gradient(90deg, transparent, #ec133e, #bd0f32, transparent)' }}
        animate={{ x: ['-100%', '100%'] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
      />
    </div>
  );
}
