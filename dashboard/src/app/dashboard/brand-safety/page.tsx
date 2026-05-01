'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, onSnapshot, doc, getDoc, setDoc, updateDoc, addDoc, deleteDoc } from 'firebase/firestore';
import { CONTENT_CATEGORIES } from '@/lib/constants';
import Image from 'next/image';

interface BrandReview {
  id: string;
  video_id: string;
  title: string;
  format: string;
  score: number;
  flags: string[];
  breakdown?: QualityBreakdown;
  feedback?: string;
  status: 'pending' | 'approved' | 'blocked';
  reviewed_at?: any;
  created_at: any;
}

interface QualityBreakdown {
  age_appropriateness: number;
  educational_value: number;
  engagement_potential: number;
  language_safety: number;
  creativity: number;
  pacing: number;
}

export default function BrandSafetyPage() {
  const [reviews, setReviews] = useState<BrandReview[]>([]);
  const [settings, setSettings] = useState({
    autoBlockThreshold: 50,
    requireReview: true,
    ageGroups: ['1-3', '4-6', '7-9'],
    strictness: 'moderate',
    forbiddenWords: ['violence', 'scary', 'death', 'kill', 'hurt', 'fight', 'war', 'blood', 'weapon', 'gun', 'bomb', 'death', 'die'],
  });
  const [newWord, setNewWord] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = onSnapshot(doc(db, 'settings', 'brand_safety'), (snap) => {
      if (snap.exists()) {
        setSettings((prev) => ({ ...prev, ...snap.data() }));
      }
      setLoading(false);
    });
    return () => unsub();
  }, []);

  useEffect(() => {
    const q = collection(db, 'brand_reviews');
    const unsub = onSnapshot(q, (snapshot) => {
      const items: BrandReview[] = [];
      snapshot.docs.forEach((d) => {
        items.push({ id: d.id, ...d.data() } as BrandReview);
      });
      items.sort((a, b) => (b.created_at?.toMillis?.() || 0) - (a.created_at?.toMillis?.() || 0));
      setReviews(items);
    });
    return () => unsub();
  }, []);

  const saveSettings = async (updates: Partial<typeof settings>) => {
    const merged = { ...settings, ...updates };
    setSettings(merged);
    try {
      await setDoc(doc(db, 'settings', 'brand_safety'), merged, { merge: true });
    } catch {}
  };

  const addWord = async () => {
    if (!newWord.trim()) return;
    const word = newWord.trim().toLowerCase();
    if (settings.forbiddenWords.includes(word)) return;
    await saveSettings({ forbiddenWords: [...settings.forbiddenWords, word] });
    setNewWord('');
  };

  const removeWord = async (word: string) => {
    await saveSettings({ forbiddenWords: settings.forbiddenWords.filter((w) => w !== word) });
  };

  const updateReview = async (reviewId: string, status: 'approved' | 'blocked') => {
    try {
      await updateDoc(doc(db, 'brand_reviews', reviewId), {
        status,
        reviewed_at: new Date().toISOString(),
      });
    } catch {}
  };

  const pendingReviews = reviews.filter((r) => r.status === 'pending');
  const approvedCount = reviews.filter((r) => r.status === 'approved').length;
  const blockedCount = reviews.filter((r) => r.status === 'blocked').length;

  const avgScore = reviews.length > 0
    ? Math.round(reviews.reduce((sum, r) => sum + r.score, 0) / reviews.length)
    : 0;

  const formatDate = (timestamp: any) => {
    if (!timestamp) return '';
    const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
    const diff = Math.floor((Date.now() - date.getTime()) / 1000);
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-emerald-400';
    if (score >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getScoreBarColor = (score: number) => {
    if (score >= 80) return 'bg-emerald-400';
    if (score >= 60) return 'bg-yellow-400';
    return 'bg-red-400';
  };

  const formatDimension = (key: string) => {
    const labels: Record<string, string> = {
      age_appropriateness: 'Age Appropriate',
      educational_value: 'Educational',
      engagement_potential: 'Engagement',
      language_safety: 'Language',
      creativity: 'Creativity',
      pacing: 'Pacing',
    };
    return labels[key] || key;
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl overflow-hidden relative">
            <Image src="/logo.svg" alt="Vyom Ai Cloud" fill className="object-cover" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Brand Safety</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Content moderation and age-appropriateness controls</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Avg Safety Score', value: `${avgScore}/100`, icon: '🛡️', color: avgScore >= 80 ? 'text-emerald-400' : avgScore >= 60 ? 'text-yellow-400' : 'text-red-400' },
          { label: 'Pending Review', value: pendingReviews.length.toString(), icon: '⏳', color: 'text-yellow-400' },
          { label: 'Approved', value: approvedCount.toString(), icon: '✅', color: 'text-emerald-400' },
          { label: 'Blocked', value: blockedCount.toString(), icon: '❌', color: 'text-red-400' },
        ].map((stat) => (
          <motion.div
            key={stat.label}
            className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5"
          >
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{stat.icon}</span>
              <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
            </div>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </motion.div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-strong rounded-2xl border border-light-border/30 dark:border-white/5 p-5">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Review Queue</h2>

          {pendingReviews.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-light-muted dark:text-dark-muted">
              <motion.div animate={{ y: [0, -8, 0] }} transition={{ duration: 2, repeat: Infinity }} className="text-3xl mb-3">
                🛡️
              </motion.div>
              <p className="text-sm font-medium">All clear!</p>
              <p className="text-xs mt-1">No content pending review</p>
            </div>
          ) : (
            <div className="space-y-3">
              {pendingReviews.map((review) => (
                <motion.div
                  key={review.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="p-4 rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="text-sm font-semibold text-light-text dark:text-dark-text">{review.title}</h3>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted">{review.video_id}</p>
                    </div>
                    <div className="text-right">
                      <p className={`text-lg font-bold ${getScoreColor(review.score)}`}>{review.score}</p>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted">quality</p>
                    </div>
                  </div>

                  <div className="w-full h-1.5 bg-light-border dark:bg-dark-border rounded-full overflow-hidden mb-3">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${review.score}%` }}
                      transition={{ duration: 0.8 }}
                      className={`h-full rounded-full ${getScoreBarColor(review.score)}`}
                    />
                  </div>

                  {review.breakdown && (
                    <div className="mb-3 p-3 rounded-lg bg-light-bg/30 dark:bg-dark-bg/30 border border-light-border/20 dark:border-white/5">
                      <p className="text-[10px] font-semibold text-light-muted dark:text-dark-muted mb-2 uppercase tracking-wider">Score Breakdown</p>
                      <div className="grid grid-cols-2 gap-2">
                        {Object.entries(review.breakdown).map(([key, val]) => (
                          <div key={key}>
                            <div className="flex justify-between mb-1">
                              <span className="text-[10px] text-light-muted dark:text-dark-muted">{formatDimension(key)}</span>
                              <span className="text-[10px] font-bold text-light-text dark:text-dark-text">{val}/100</span>
                            </div>
                            <div className="w-full h-1 bg-light-border/50 dark:bg-white/5 rounded-full overflow-hidden">
                              <motion.div
                                initial={{ width: 0 }}
                                animate={{ width: `${val}%` }}
                                transition={{ duration: 0.5 }}
                                className={`h-full rounded-full ${getScoreBarColor(val)}`}
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {review.feedback && (
                    <p className="text-[10px] text-light-muted dark:text-dark-muted mb-3 italic">&ldquo;{review.feedback}&rdquo;</p>
                  )}

                  {review.flags.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mb-3">
                      {review.flags.map((flag, i) => (
                        <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
                          ⚠️ {flag}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      onClick={() => updateReview(review.id, 'approved')}
                      className="flex-1 px-3 py-2 rounded-lg text-xs font-medium bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors"
                    >
                      ✅ Approve
                    </button>
                    <button
                      onClick={() => updateReview(review.id, 'blocked')}
                      className="flex-1 px-3 py-2 rounded-lg text-xs font-medium bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30 transition-colors"
                    >
                      ❌ Block
                    </button>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="glass-strong rounded-2xl border border-light-border/30 dark:border-white/5 p-5">
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Safety Settings</h2>

            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-light-text dark:text-dark-text">Auto-block threshold</label>
                  <span className="text-sm font-bold text-light-primary">{settings.autoBlockThreshold}</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={settings.autoBlockThreshold}
                  onChange={(e) => saveSettings({ autoBlockThreshold: Number(e.target.value) })}
                  className="w-full accent-light-primary"
                />
                <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">
                  Videos below this score are auto-blocked
                </p>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-light-text dark:text-dark-text">Manual review required</p>
                  <p className="text-[10px] text-light-muted dark:text-dark-muted">Flag content for human review</p>
                </div>
                <button
                  onClick={() => saveSettings({ requireReview: !settings.requireReview })}
                  className={`w-12 h-7 rounded-full transition-colors ${settings.requireReview ? 'bg-light-success' : 'bg-light-muted dark:bg-dark-muted'}`}
                >
                  <motion.div
                    className="w-5 h-5 rounded-full bg-white shadow-sm"
                    animate={{ x: settings.requireReview ? 20 : 2 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                </button>
              </div>

              <div>
                <label className="text-sm font-medium text-light-text dark:text-dark-text mb-2 block">Strictness level</label>
                <div className="flex gap-2">
                  {(['lenient', 'moderate', 'strict'] as const).map((level) => (
                    <button
                      key={level}
                      onClick={() => saveSettings({ strictness: level })}
                      className={`flex-1 px-3 py-2 rounded-lg text-xs font-medium capitalize transition-all ${
                        settings.strictness === level
                          ? 'bg-light-primary text-white'
                          : 'bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted'
                      }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm font-medium text-light-text dark:text-dark-text mb-2 block">Age groups</label>
                <div className="flex flex-wrap gap-2">
                  {['1-3', '4-6', '7-9'].map((age) => (
                    <button
                      key={age}
                      onClick={() => {
                        const groups = settings.ageGroups.includes(age)
                          ? settings.ageGroups.filter((a) => a !== age)
                          : [...settings.ageGroups, age];
                        saveSettings({ ageGroups: groups });
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                        settings.ageGroups.includes(age)
                          ? 'bg-light-secondary/20 text-light-secondary border border-light-secondary/30'
                          : 'bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted'
                      }`}
                    >
                      Age {age}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-strong rounded-2xl border border-light-border/30 dark:border-white/5 p-5">
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Blocked Words ({settings.forbiddenWords.length})</h2>

            <div className="flex flex-wrap gap-2 mb-4">
              {settings.forbiddenWords.map((word) => (
                <button
                  key={word}
                  onClick={() => removeWord(word)}
                  className="px-3 py-1.5 rounded-full text-xs font-medium bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                >
                  {word} ✕
                </button>
              ))}
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Add forbidden word..."
                value={newWord}
                onChange={(e) => setNewWord(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addWord()}
                className="flex-1 px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/50 dark:border-white/10 text-light-text dark:text-dark-text placeholder:text-light-muted dark:placeholder:text-dark-muted text-sm focus:outline-none focus:ring-2 focus:ring-light-primary/50"
              />
              <button
                onClick={addWord}
                className="px-4 py-2 rounded-xl text-sm font-medium bg-light-primary text-white hover:bg-light-primary/80 transition-colors"
              >
                Add
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
