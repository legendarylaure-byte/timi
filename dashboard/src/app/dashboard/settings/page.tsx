'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { db } from '@/lib/firebase';
import { doc, updateDoc, getDoc, setDoc, collection, onSnapshot } from 'firebase/firestore';
import { useToast } from '@/components/ui/Toast';
import { GradientCard } from '@/components/ui/GradientCard';
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
  const [notifWarning, setNotifWarning] = useState(true);
  const [notifError, setNotifError] = useState(true);
  const [notifInfo, setNotifInfo] = useState(true);
  const [desktopNotifs, setDesktopNotifs] = useState(false);

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
    const unsub = onSnapshot(collection(db, 'platform_settings'), (snap) => {
      const connections: Record<string, { connected: boolean; followers: number }> = {};
      snap.forEach(doc => {
        const d = doc.data();
        connections[doc.id] = {
          connected: d.connected || false,
          followers: d.followers || 0,
        };
      });
      setPlatformConnections(connections);
    });
    return () => unsub();
  }, []);

  const toggleTheme = () => {
    const next = theme === 'light' ? 'dark' : 'light';
    document.documentElement.classList.toggle('dark', next === 'dark');
    localStorage.setItem('theme', next);
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
      await setDoc(doc(db, 'settings', 'general'), {
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
      }, { merge: true });
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
              onClick={() => {
                document.documentElement.classList.remove('dark');
                localStorage.setItem('theme', 'light');
                setTheme('light');
              }}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                theme === 'light'
                  ? 'bg-light-primary text-white'
                  : 'bg-light-border dark:bg-dark-border text-light-muted dark:text-dark-muted'
              }`}
            >
              ☀️ Light
            </button>
            <button
              onClick={() => {
                document.documentElement.classList.add('dark');
                localStorage.setItem('theme', 'dark');
                setTheme('dark');
              }}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                theme === 'dark'
                  ? 'bg-light-secondary text-white'
                  : 'bg-light-border dark:bg-dark-border text-light-muted dark:text-dark-muted'
              }`}
            >
              🌙 Dark
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
                  ? 'text-white'
                  : 'bg-light-border dark:bg-dark-border text-light-muted dark:text-dark-muted'
              }`}
              style={selectedCategories.includes(cat.name) ? { background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)' } : {}}
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
                <span className={`text-xs px-3 py-1 rounded-full ${
                  isConnected
                    ? 'bg-emerald-500/20 text-emerald-400'
                    : 'bg-light-warning/20 text-light-warning'
                }`}>
                  {isConnected ? 'Connected' : 'Not Connected'}
                </span>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-light-muted dark:text-dark-muted mt-4">Connect your social media accounts from the Publishing page</p>
      </GradientCard>

      {/* Save Button */}
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => handleSave('All')}
        className="w-full py-4 rounded-2xl text-white font-semibold text-lg"
        style={{ background: 'linear-gradient(135deg, #FF4D6D, #7C3AED)' }}
      >
        Save All Settings
      </motion.button>
        </>
      )}
    </div>
  );
}
