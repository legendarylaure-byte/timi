'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { doc, updateDoc, getDoc, setDoc, collection, onSnapshot } from 'firebase/firestore';
import { useToast } from '@/components/ui/Toast';
import { GradientCard } from '@/components/ui/GradientCard';
import { toggleTheme as toggleAppTheme } from '@/lib/theme';
import { DAILY_QUOTA, CONTENT_CATEGORIES, PLATFORMS } from '@/lib/constants';

export default function SettingsPage() {
  const { addToast } = useToast();
  const [notifications, setNotifications] = useState(true);
  const [autoUpload, setAutoUpload] = useState(true);
  const [shortsPerDay, setShortsPerDay] = useState(DAILY_QUOTA.shorts);
  const [longPerDay, setLongPerDay] = useState(DAILY_QUOTA.long);
  const [selectedCategories, setSelectedCategories] = useState<string[]>(CONTENT_CATEGORIES.map(c => c.name));
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const [loading, setLoading] = useState(true);
  const [platformConnections, setPlatformConnections] = useState<Record<string, { connected: boolean; followers: number }>>({});
  const [notifSuccess, setNotifSuccess] = useState(true);
  const [envOpen, setEnvOpen] = useState(false);
  const [envSearch, setEnvSearch] = useState('');
  const [envVars, setEnvVars] = useState<Record<string, { value: string; updated_at: string }>>({});
  const [envLoading, setEnvLoading] = useState(false);
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [editingEnvKey, setEditingEnvKey] = useState<string | null>(null);
  const [editingEnvValue, setEditingEnvValue] = useState('');
  const [notifWarning, setNotifWarning] = useState(true);
  const [notifError, setNotifError] = useState(true);
  const [notifInfo, setNotifInfo] = useState(true);
  const [desktopNotifs, setDesktopNotifs] = useState(false);

  const OAUTH_URLS: Record<string, string> = {
    tiktok: '/api/auth/tiktok?action=connect',
    youtube: '/api/auth/youtube?action=connect',
    facebook: '/api/auth/meta?action=connect',
    instagram: '/api/auth/meta?action=connect',
  };

  const ENV_GROUPS: Record<string, string[]> = {
    'Meta (Facebook & Instagram)': ['FACEBOOK_APP_ID', 'FACEBOOK_APP_SECRET', 'FACEBOOK_ACCESS_TOKEN', 'FACEBOOK_PAGE_ID', 'INSTAGRAM_ACCOUNT_ID'],
    YouTube: ['YOUTUBE_CLIENT_ID', 'YOUTUBE_CLIENT_SECRET', 'YOUTUBE_API_KEY'],
    TikTok: ['TIKTOK_CLIENT_KEY', 'TIKTOK_CLIENT_SECRET', 'TIKTOK_ACCESS_TOKEN', 'TIKTOK_OPEN_ID', 'TIKTOK_REFRESH_TOKEN'],
    'Google Cloud': ['GOOGLE_APPLICATION_CREDENTIALS'],
    'AI / LLM': ['GEMINI_API_KEY', 'GROQ_API_KEY'],
    Other: [
      'PEXELS_API_KEY',
      'PIXABAY_API_KEY',
      'TELEGRAM_BOT_TOKEN',
      'SENTRY_DSN',
      'CLOUDFLARE_R2_ACCESS_KEY_ID',
      'CLOUDFLARE_R2_SECRET_ACCESS_KEY',
      'CLOUDFLARE_R2_BUCKET_NAME',
      'CLOUDFLARE_R2_ACCOUNT_ID',
      'CLOUDFLARE_R2_PUBLIC_URL',
      'VERCEL_TOKEN',
    ],
  };

  function maskValue(val: string) {
    if (!val) return '(empty)';
    if (val.length <= 8) return '*'.repeat(val.length);
    return val.slice(0, 4) + '*'.repeat(Math.min(val.length - 8, 32)) + val.slice(-4);
  }

  const loadEnvVars = async () => {
    setEnvLoading(true);
    try {
      const res = await fetch('/api/env-vars');
      const data = await res.json();
      if (data.success) {
        setEnvVars(data.vars);
      }
    } catch (err) {
      console.error('Failed to load env vars:', err);
    } finally {
      setEnvLoading(false);
    }
  };

  useEffect(() => {
    if (envOpen) {
      loadEnvVars();
    }
  }, [envOpen]);

  const togglePlatformConnection = async (platformId: string, currentConnected: boolean, platformName: string) => {
    if (!currentConnected) {
      const oauthUrl = OAUTH_URLS[platformId];
      if (oauthUrl) {
        window.location.href = oauthUrl;
        return;
      }
      // Fallback: platforms without OAuth (connect directly)
      try {
        await fetch(`/api/platform-settings/${platformId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ connected: true }),
        });
        addToast(`${platformName} connected`, 'success');
      } catch (e) {
        console.error('Failed to connect:', e);
        addToast(`Failed to connect ${platformName}`, 'error');
      }
      return;
    } else {
      if (!confirm(`Disconnect ${platformName}? OAuth tokens will be removed.`)) return;
      try {
        await fetch(`/api/platform-settings/${platformId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ connected: false, access_token: '', refresh_token: '', open_id: '' }),
        });
      } catch (e) {
        console.error('Failed to disconnect:', e);
      }
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem('theme') as 'light' | 'dark';
    if (saved) setTheme(saved);
  }, []);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const snap = await getDoc(doc(db, 'settings', 'general'));
        if (snap.exists()) {
          const data = snap.data();
          if (data.notifications !== undefined) setNotifications(data.notifications);
          if (data.autoUpload !== undefined) setAutoUpload(data.autoUpload);
          if (data.shortsPerDay !== undefined) setShortsPerDay(data.shortsPerDay);
          if (data.longPerDay !== undefined) setLongPerDay(data.longPerDay);
          if (data.selectedCategories !== undefined) setSelectedCategories(data.selectedCategories);
          if (data.notifSuccess !== undefined) setNotifSuccess(data.notifSuccess);
          if (data.notifWarning !== undefined) setNotifWarning(data.notifWarning);
          if (data.notifError !== undefined) setNotifError(data.notifError);
          if (data.notifInfo !== undefined) setNotifInfo(data.notifInfo);
          if (data.desktopNotifs !== undefined) setDesktopNotifs(data.desktopNotifs);
        }
      } catch (error) {
        console.error('Failed to load settings:', error);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  useEffect(() => {
    const unsub = onSnapshot(collection(db, 'platform_settings'),
      (snap) => {
        const connections: Record<string, { connected: boolean; followers: number }> = {};
        snap.forEach(doc => {
          const d = doc.data();
          connections[doc.id] = {
            connected: d.connected || false,
            followers: d.followers || 0,
          };
        });
        setPlatformConnections(connections);
      },
      (error) => {
        console.error('[Settings] platform_settings:', error);
      }
    );
    return () => unsub();
  }, []);

  const toggleTheme = () => {
    const next = toggleAppTheme();
    setTheme(next);
    addToast(`Switched to ${next} mode`, 'info');
  };

  const toggleCategory = (cat: string) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleSave = async (section: string) => {
    try {
      const res = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          notifications,
          autoUpload,
          shortsPerDay,
          longPerDay,
          selectedCategories,
          notifSuccess,
          notifWarning,
          notifError,
          notifInfo,
          desktopNotifs,
          updatedAt: new Date().toISOString(),
        }),
      });
      if (!res.ok) throw new Error('Failed to save');
      addToast(`${section} settings saved`, 'success');
    } catch (error) {
      addToast('Failed to save settings', 'error');
    }
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Settings</h1>
        <p className="text-light-muted dark:text-dark-muted mt-1">Configure your content automation preferences</p>
      </motion.div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <div className="w-8 h-8 border-2 border-light-primary border-t-transparent rounded-full animate-spin" />
        </div>
      ) : (
        <>

      {/* Appearance */}
      <GradientCard gradient="primary">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Appearance</h2>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-light-text dark:text-dark-text">Theme</p>
            <p className="text-sm text-light-muted dark:text-dark-muted">Switch between light and dark mode</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={toggleTheme}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                theme === 'light'
                  ? 'bg-light-primary text-white'
                  : 'bg-light-border dark:bg-dark-border text-light-muted dark:text-dark-muted'
              }`}
            >
              {theme === 'light' ? '☀️ Light' : '🌙 Dark'}
            </button>
          </div>
        </div>
      </GradientCard>

      {/* Content Schedule */}
      <GradientCard gradient="warm">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Content Schedule</h2>

        <div className="space-y-6">
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="font-medium text-light-text dark:text-dark-text">Shorts per day</label>
              <span className="text-sm font-bold gradient-text">{shortsPerDay} videos</span>
            </div>
            <input
              type="range"
              min="0"
              max="5"
              value={shortsPerDay}
              onChange={(e) => setShortsPerDay(Number(e.target.value))}
              className="w-full accent-light-primary"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="font-medium text-light-text dark:text-dark-text">Long form videos per day</label>
              <span className="text-sm font-bold gradient-text">{longPerDay} videos</span>
            </div>
            <input
              type="range"
              min="0"
              max="4"
              value={longPerDay}
              onChange={(e) => setLongPerDay(Number(e.target.value))}
              className="w-full accent-light-secondary"
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-light-text dark:text-dark-text">Auto-upload</p>
              <p className="text-sm text-light-muted dark:text-dark-muted">Automatically upload videos to channels</p>
            </div>
            <button
              onClick={() => setAutoUpload(!autoUpload)}
              className={`w-12 h-7 rounded-full transition-colors ${autoUpload ? 'bg-light-success' : 'bg-light-border dark:bg-dark-border'}`}
            >
              <motion.div
                className="w-5 h-5 rounded-full bg-white shadow-sm"
                animate={{ x: autoUpload ? 20 : 2 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
          </div>
        </div>
      </GradientCard>

      {/* Content Categories */}
      <GradientCard gradient="cool">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Content Categories</h2>
        <div className="flex flex-wrap gap-2">
          {CONTENT_CATEGORIES.map((cat) => (
            <button
              key={cat.name}
              onClick={() => toggleCategory(cat.name)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                 selectedCategories.includes(cat.name)
                   ? 'text-white bg-gradient-to-r from-light-primary to-purple-600'
                   : 'bg-light-border dark:bg-dark-border text-light-muted dark:text-dark-muted'
               }`}
            >
              {cat.name}
            </button>
          ))}
        </div>
      </GradientCard>

      {/* Notifications */}
      <GradientCard gradient="success">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Notifications</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-light-text dark:text-dark-text">Telegram Notifications</p>
              <p className="text-sm text-light-muted dark:text-dark-muted">Receive alerts and updates on Telegram</p>
            </div>
            <button
              onClick={() => setNotifications(!notifications)}
              className={`w-12 h-7 rounded-full transition-colors ${notifications ? 'bg-light-success' : 'bg-light-border dark:bg-dark-border'}`}
            >
              <motion.div
                className="w-5 h-5 rounded-full bg-white shadow-sm"
                animate={{ x: notifications ? 20 : 2 }}
                transition={{ type: 'spring', stiffness: 500, damping: 30 }}
              />
            </button>
          </div>

          <div className="border-t border-light-border/30 dark:border-white/5 pt-4">
            <p className="text-sm font-medium text-light-text dark:text-dark-text mb-3">Notification Types</p>
            <div className="space-y-3">
              {[
                { label: 'Success alerts', desc: 'Video uploaded, task completed', state: notifSuccess, setter: setNotifSuccess, icon: '✅', color: 'bg-emerald-500/20' },
                { label: 'Warnings', desc: 'Rate limits, agent paused', state: notifWarning, setter: setNotifWarning, icon: '⚠️', color: 'bg-yellow-500/20' },
                { label: 'Errors', desc: 'Upload failures, API errors', state: notifError, setter: setNotifError, icon: '❌', color: 'bg-red-500/20' },
                { label: 'Info updates', desc: 'Agent started, daily summary', state: notifInfo, setter: setNotifInfo, icon: 'ℹ️', color: 'bg-blue-500/20' },
              ].map((item) => (
                <div key={item.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm ${item.color}`}>
                      {item.icon}
                    </span>
                    <div>
                      <p className="text-sm font-medium text-light-text dark:text-dark-text">{item.label}</p>
                      <p className="text-[10px] text-light-muted dark:text-dark-muted">{item.desc}</p>
                    </div>
                  </div>
                  <button
                    onClick={() => item.setter(!item.state)}
                    className={`w-10 h-6 rounded-full transition-all duration-200 ${
                      item.state ? 'bg-light-success' : 'bg-light-muted dark:bg-dark-muted'
                    }`}
                  >
                    <motion.div
                      className="w-5 h-5 rounded-full bg-white shadow-sm"
                      animate={{ x: item.state ? 18 : 2 }}
                      transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                    />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="border-t border-light-border/30 dark:border-white/5 pt-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-light-text dark:text-dark-text">Desktop Notifications</p>
                <p className="text-sm text-light-muted dark:text-dark-muted">Browser push notifications</p>
              </div>
              <button
                onClick={() => setDesktopNotifs(!desktopNotifs)}
                className={`w-12 h-7 rounded-full transition-colors ${desktopNotifs ? 'bg-light-success' : 'bg-light-border dark:bg-dark-border'}`}
              >
                <motion.div
                  className="w-5 h-5 rounded-full bg-white shadow-sm"
                  animate={{ x: desktopNotifs ? 20 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              </button>
            </div>
          </div>
        </div>
      </GradientCard>

      {/* Connected Channels */}
      <GradientCard gradient="info">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-4">Connected Channels</h2>
        <div className="space-y-3">
          {Object.entries(PLATFORMS).map(([key, platform]) => {
            const conn = platformConnections[key.toLowerCase()];
            const isConnected = conn?.connected || false;
            const followers = conn?.followers || 0;
            const iconMap: Record<string, string> = {
              YOUTUBE: '▶️',
              TIKTOK: '🎵',
              INSTAGRAM: '📸',
              FACEBOOK: '👥',
            };
            return (
              <div key={key} className="flex items-center justify-between p-3 rounded-xl bg-light-bg dark:bg-dark-bg/50">
                <div className="flex items-center gap-3">
                  <span className="text-lg">{iconMap[key] || '🔗'}</span>
                  <span className="text-sm font-medium text-light-text dark:text-dark-text">{platform.name}</span>
                  {isConnected && followers > 0 && (
                    <span className="text-xs text-light-muted dark:text-dark-muted">{followers.toLocaleString()} followers</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-3 py-1 rounded-full ${
                    isConnected
                      ? 'bg-emerald-500/20 text-emerald-400'
                      : 'bg-light-warning/20 text-light-warning'
                  }`}>
                    {isConnected ? 'Connected' : 'Not Connected'}
                  </span>
                  <button
                    onClick={() => togglePlatformConnection(key.toLowerCase(), isConnected, platform.name)}
                    className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                      isConnected
                        ? 'bg-red-500/20 text-red-400 border-red-500/30 hover:bg-red-500/30'
                        : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/30'
                    }`}
                  >
                    {isConnected ? 'Disconnect' : 'Connect'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-light-muted dark:text-dark-muted mt-4">Manage connections or start publishing from the Publishing page</p>
      </GradientCard>

      {/* Environment Variables */}
      <GradientCard gradient="info">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-bold text-light-text dark:text-dark-text">Environment Variables</h2>
            <p className="text-sm text-light-muted dark:text-dark-muted">Manage runtime secrets and API keys</p>
          </div>
          <button
            onClick={() => setEnvOpen(!envOpen)}
            className="text-light-muted dark:text-dark-muted hover:text-light-text dark:hover:text-dark-text transition-colors"
          >
            <span className={`inline-block transition-transform ${envOpen ? 'rotate-180' : ''}`}>▾</span>
          </button>
        </div>

        {envOpen && (
          <div className="space-y-3">
            <div className="relative mb-4">
              <input
                type="text"
                placeholder="Search tokens..."
                value={envSearch}
                onChange={(e) => setEnvSearch(e.target.value)}
                className="w-full px-4 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 text-sm text-light-text dark:text-dark-text placeholder-light-muted dark:placeholder-dark-muted outline-none focus:border-light-primary/50"
              />
            </div>

            {envLoading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-6 h-6 border-2 border-light-primary border-t-transparent rounded-full animate-spin" />
              </div>
            ) : (
              Object.entries(ENV_GROUPS).map(([groupName, groupKeys]) => {
                const visibleKeys = groupKeys.filter(k =>
                  k.toLowerCase().includes(envSearch.toLowerCase()) ||
                  groupName.toLowerCase().includes(envSearch.toLowerCase())
                );
                if (visibleKeys.length === 0) return null;
                return (
                  <div key={groupName}>
                    <p className="text-xs font-bold text-light-muted dark:text-dark-muted uppercase tracking-wider mb-2">
                      {groupName}
                    </p>
                    <div className="space-y-2 mb-4">
                      {visibleKeys.map((key) => {
                        const entry = envVars[key];
                        const val = entry?.value ?? '';
                        const isEditing = editingEnvKey === key;
                        const editVal = editingEnvValue;
                        return (
                          <div key={key} className="flex items-center gap-2 p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50">
                            <span className="text-xs font-mono font-bold text-light-text dark:text-dark-text w-1/3 truncate" title={key}>
                              {key}
                            </span>
                            <div className="flex-1 flex items-center gap-2">
                              {isEditing ? (
                                <input
                                  type="text"
                                  value={editVal}
                                  onChange={(e) => setEditingEnvValue(e.target.value)}
                                  className="flex-1 px-2 py-1 rounded-lg bg-light-bg dark:bg-dark-bg border border-light-primary/50 text-xs font-mono text-light-text dark:text-dark-text outline-none"
                                  autoFocus
                                />
                              ) : (
                                <span className="text-xs font-mono text-light-muted dark:text-dark-muted truncate">
                                  {revealedKeys.has(key) ? val : maskValue(val)}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => {
                                  if (revealedKeys.has(key)) revealedKeys.delete(key);
                                  else revealedKeys.add(key);
                                  setRevealedKeys(new Set(revealedKeys));
                                }}
                                className="p-1 rounded hover:bg-light-border/30 dark:hover:bg-dark-border/30 text-xs"
                                title={revealedKeys.has(key) ? 'Hide' : 'Show'}
                              >
                                {revealedKeys.has(key) ? '🙈' : '👁️'}
                              </button>
                              {isEditing ? (
                                <>
                                  <button
                                    onClick={async () => {
                                      if (!editVal.trim()) return;
                                      try {
                                        const res = await fetch(`/api/env-vars/${key}`, {
                                          method: 'PUT',
                                          headers: { 'Content-Type': 'application/json' },
                                          body: JSON.stringify({ value: editVal.trim() }),
                                        });
                                        const data = await res.json();
                                        if (data.success) {
                                          addToast(`${key} updated`, 'success');
                                          setEditingEnvKey(null);
                                          setEditingEnvValue('');
                                          loadEnvVars();
                                        } else {
                                          addToast(`Failed: ${data.error}`, 'error');
                                        }
                                      } catch {
                                        addToast('Failed to save token', 'error');
                                      }
                                    }}
                                    className="p-1 rounded hover:bg-emerald-500/20 text-emerald-400 text-xs"
                                    title="Save"
                                  >
                                    ✓
                                  </button>
                                  <button
                                    onClick={() => { setEditingEnvKey(null); setEditingEnvValue(''); }}
                                    className="p-1 rounded hover:bg-red-500/20 text-red-400 text-xs"
                                    title="Cancel"
                                  >
                                    ✕
                                  </button>
                                </>
                              ) : (
                                <button
                                  onClick={() => { setEditingEnvKey(key); setEditingEnvValue(val); }}
                                  className="p-1 rounded hover:bg-light-border/30 dark:hover:bg-dark-border/30 text-xs"
                                  title="Edit"
                                >
                                  ✏️
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </GradientCard>

      {/* Save Button */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => handleSave('All')}
        className="w-full py-4 rounded-2xl text-white font-semibold text-lg bg-gradient-to-r from-light-primary to-purple-600 hover:shadow-lg transition-shadow"
      >
        Save All Settings
      </motion.button>
        </>
      )}
    </div>
  );
}
