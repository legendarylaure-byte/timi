'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { auth } from '@/lib/firebase';

const CHARACTERS = ['pixel', 'nova', 'ziggy', 'boop', 'sprout'];
const BACKGROUNDS = [
  'gradient_sky', 'gradient_forest', 'gradient_ocean', 'gradient_space',
  'gradient_sunset', 'gradient_night', 'gradient_garden', 'gradient_classroom',
  'gradient_bedroom', 'gradient_underwater',
];
const ANIMATIONS = ['bounce', 'float', 'wave', 'grow', 'wiggle', 'slide_in', 'twinkle', 'spin', 'glide', 'dance', 'squish', 'sway', 'none'];
const EFFECTS = ['none', 'sparkle', 'fade_in', 'fade_out', 'rainbow_burst', 'star_rain'];
const TRANSITIONS = ['cut', 'fade', 'dissolve', 'slide_left', 'slide_right'];
const MOODS = ['happy', 'calm', 'adventure', 'dreamy', 'playful', 'exciting'];
const FORMATS = ['shorts', 'long'] as const;
const CHAR_EMOJIS: Record<string, string> = {
  pixel: '🤖', nova: '⭐', ziggy: '🌈', boop: '🔵', sprout: '🌱',
};

export default function PreviewPage() {
  const [format, setFormat] = useState<'shorts' | 'long'>('shorts');
  const [bg, setBg] = useState('gradient_sky');
  const [character, setCharacter] = useState('pixel');
  const [pose, setPose] = useState('idle');
  const [expression, setExpression] = useState('neutral');
  const [animation, setAnimation] = useState('float');
  const [overlayText, setOverlayText] = useState('Hello!');
  const [textStyle, setTextStyle] = useState('title');
  const [effect, setEffect] = useState('sparkle');
  const [mood, setMood] = useState('happy');
  const [preview, setPreview] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const renderPreview = async () => {
    setLoading(true);
    setError('');
    setPreview(null);
    try {
      const token = auth.currentUser ? await auth.currentUser.getIdToken() : '';
      const scene = {
        background: bg,
        duration: 6.0,
        characters: [{
          name: character, pose, expression, animation, x: 0.5, y: 0.55,
        }],
        text: overlayText ? [{
          text: overlayText,
          style: textStyle,
          position: textStyle === 'title' ? 'center' : 'bottom',
        }] : [],
        effects: [effect],
        transition: 'cut',
        camera: { zoom: 1.0, pan_x: 0, pan_y: 0 },
        music_mood: mood,
      };

      const res = await fetch('/api/preview/scene', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ scene, format_type: format }),
      });
      const data = await res.json();
      if (data.success) setPreview(data.image);
      else setError(data.error || 'Preview generation failed');
    } catch (e: any) {
      setError(e.message || 'Failed to generate preview');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-purple-500/20 to-blue-500/20 flex items-center justify-center">
            <span className="text-2xl">🎨</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Scene Preview</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Design and preview animated scenes before publishing</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-4">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-5">
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Scene Config</h2>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Format</label>
                <div className="flex gap-2">
                  {FORMATS.map(f => (
                    <button key={f} onClick={() => setFormat(f)}
                      className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${
                        format === f
                          ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                          : 'bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/10 text-light-muted dark:text-dark-muted'
                      }`}>{f}</button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Background</label>
                <select value={bg} onChange={e => setBg(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                  {BACKGROUNDS.map(b => <option key={b} value={b}>{b.replace('gradient_', '')}</option>)}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Character</label>
                <div className="flex gap-1 flex-wrap">
                  {CHARACTERS.map(c => (
                    <button key={c} onClick={() => setCharacter(c)}
                      className={`px-2.5 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        character === c
                          ? 'bg-gradient-to-r from-purple-500 to-blue-500 text-white'
                          : 'bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/10 text-light-muted dark:text-dark-muted'
                      }`}>
                      {CHAR_EMOJIS[c]} {c}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Animation</label>
                  <select value={animation} onChange={e => setAnimation(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                    {ANIMATIONS.map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Effect</label>
                  <select value={effect} onChange={e => setEffect(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                    {EFFECTS.map(e => <option key={e} value={e}>{e}</option>)}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Text Overlay</label>
                <input type="text" value={overlayText} onChange={e => setOverlayText(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50" />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Text Style</label>
                  <select value={textStyle} onChange={e => setTextStyle(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                    <option value="title">Title</option>
                    <option value="emphasis">Emphasis</option>
                    <option value="dialogue">Dialogue</option>
                    <option value="narration">Narration</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-light-muted dark:text-dark-muted mb-1">Mood</label>
                  <select value={mood} onChange={e => setMood(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border dark:border-white/10 text-light-text dark:text-dark-text text-xs focus:outline-none focus:ring-2 focus:ring-purple-500/50">
                    {MOODS.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
              </div>
            </div>

            <button
              onClick={renderPreview}
              disabled={loading}
              className="mt-4 w-full py-3 rounded-xl bg-gradient-to-r from-purple-500 to-blue-500 text-white font-semibold text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
            >
              {loading ? 'Rendering...' : 'Render Preview'}
            </button>
          </motion.div>
        </div>

        <div className="lg:col-span-2">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
            className="relative rounded-2xl overflow-hidden glass-strong border border-light-border/50 dark:border-white/10 p-6 min-h-[400px] flex items-center justify-center">
            {loading ? (
              <div className="text-center">
                <div className="w-10 h-10 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin mx-auto mb-3" />
                <p className="text-sm text-light-muted dark:text-dark-muted">Rendering scene...</p>
              </div>
            ) : preview ? (
              <div className="text-center space-y-3">
                <img src={`data:image/png;base64,${preview}`} alt="Scene preview"
                  className="max-w-full max-h-[500px] rounded-xl shadow-2xl mx-auto"
                  style={{ aspectRatio: format === 'shorts' ? '9/16' : '16/9', objectFit: 'cover' }} />
                <p className="text-xs text-light-muted dark:text-dark-muted">Rendered in {format === 'shorts' ? '9:16' : '16:9'} format</p>
              </div>
            ) : error ? (
              <div className="text-center">
                <p className="text-red-400 text-sm mb-2">{error}</p>
                <p className="text-xs text-light-muted dark:text-dark-muted">Check that the animation engine is properly configured</p>
              </div>
            ) : (
              <div className="text-center">
                <span className="text-5xl mb-4 block">🎨</span>
                <p className="text-light-muted dark:text-dark-muted">Configure a scene on the left and click Render Preview</p>
              </div>
            )}
          </motion.div>
        </div>
      </div>
    </div>
  );
}
