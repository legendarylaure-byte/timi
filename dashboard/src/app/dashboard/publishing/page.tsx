'use client';

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { db } from '@/lib/firebase';
import { collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore';
import Image from 'next/image';
import { apiFetch } from '@/lib/api-fetch';

interface PlatformConfig {
  id: string;
  name: string;
  icon: string;
  color: string;
  connected: boolean;
  followers: number;
  videosPublished: number;
  lastPublished?: any;
  scope?: string;
  autoPublish: boolean;
  bestTime: string;
  scheduleEnabled: boolean;
  maxShortsPerDay: number;
  maxLongPerDay: number;
}

// The one handle on a queued post. Kept in localStorage so a reload mid-publish
// resumes polling instead of forgetting the post exists.
const COMPOSE_INTENT_KEY = 'tiktok.composer.intentId';

export default function PublishingPage() {
  const PRIVACY_LABELS: Record<string, string> = {
    PUBLIC_TO_EVERYONE: 'Public',
    MUTUAL_FOLLOW_FRIENDS: 'Mutual follow / friends',
    FOLLOWER_OF_CREATOR: 'Followers only',
    SELF_ONLY: 'Only me',
  };
  const compPrivacyLabel = (opt: any) => {
    if (typeof opt === 'string') return PRIVACY_LABELS[opt] || opt;
    const raw = opt?.level || opt?.privacy_level || opt?.value || opt?.id || '';
    return PRIVACY_LABELS[raw] || opt?.display_name || opt?.label || raw || '';
  };
  const compComplianceText = () => {
    const branded = compBrandToggle && compBrandContent;
    const base = 'By posting, you agree to TikTok\'s';
    return branded
      ? `${base} Branded Content Policy and Music Usage Confirmation.`
      : `${base} Music Usage Confirmation.`;
  };
const [platforms, setPlatforms] = useState<PlatformConfig[]>([]);
    const [loading, setLoading] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState<string | null>(null);

  // TikTok composer state
  const [availableVideos, setAvailableVideos] = useState<any[]>([]);
  const [privacyOptions, setPrivacyOptions] = useState<any[]>([]);
  const [compTitle, setCompTitle] = useState('');
  const [compVideo, setCompVideo] = useState('');
  const [compPrivacy, setCompPrivacy] = useState('');
  const [compComment, setCompComment] = useState(false);
  const [compDuet, setCompDuet] = useState(false);
  const [compStitch, setCompStitch] = useState(false);
  const [compSubmitting, setCompSubmitting] = useState(false);
  const [compOptionsLoading, setCompOptionsLoading] = useState(false);
  const [compCreator, setCompCreator] = useState<any>(null);
  const [compPreviewUrl, setCompPreviewUrl] = useState('');
  const [compDuration, setCompDuration] = useState(0);
  const [compBrandToggle, setCompBrandToggle] = useState(false);
  const [compBrandOrganic, setCompBrandOrganic] = useState(false);
  const [compBrandContent, setCompBrandContent] = useState(false);
  const compBrandDisabled = compBrandToggle && !compBrandOrganic && !compBrandContent;
  const [compConsent, setCompConsent] = useState(false);
  const [compIntentId, setCompIntentId] = useState('');
  const [compIntent, setCompIntent] = useState<any>(null);
  const [compMsgs, setCompMsgs] = useState<string[]>([]);
  const [compUploading, setCompUploading] = useState(false);
  const [compUploadProgress, setCompUploadProgress] = useState(0);
  const [userRole, setUserRole] = useState<'owner' | 'reviewer'>('owner');

  useEffect(() => {
    apiFetch('/api/auth', { method: 'POST' })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { if (d?.role) setUserRole(d.role === 'reviewer' ? 'reviewer' : 'owner'); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiFetch('/api/platform-settings')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((d) => { if (!cancelled && d.platforms) setPlatforms(d.platforms as PlatformConfig[]); })
      .catch((e) => { console.error('[Publishing] platform_settings:', e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

useEffect(() => {
      const unsub = onSnapshot(
      query(collection(db, 'videos'), orderBy('created_at', 'desc'), limit(50)),
      (snap) => {
        const list = snap.docs.map(d => ({ id: d.id, ...d.data() }));
        setAvailableVideos(list.filter((v: any) => v?.status !== 'published'));
      },
      (error) => console.error('[Publishing] load videos:', error)
    );
    return () => unsub();
  }, []);

  // Load TikTok creator info on mount (guideline 1: latest creator info when rendering Post page).
  useEffect(() => {
    loadComposerOptions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const compPushMsg = (m: string) => setCompMsgs((p) => [...p.slice(-2), m]);

  const loadComposerOptions = async () => {
    setCompOptionsLoading(true);
    try {
      const res = await apiFetch('/api/tiktok/composer/options');
      const data = await res.json();
      if (data.success) {
        setPrivacyOptions(Array.isArray(data.privacy_level_options) ? data.privacy_level_options : []);
        setCompCreator({
          nickname: data.creator_nickname || '',
          username: data.creator_username || '',
          avatar_url: data.creator_avatar_url || '',
          max_duration: Number(data.max_video_post_duration_sec) || 0,
          comment_disabled: !!data.comment_disabled,
          duet_disabled: !!data.duet_disabled,
          stitch_disabled: !!data.stitch_disabled,
        });
      } else {
        setCompCreator(null);
        compPushMsg(`TikTok options unavailable: ${data.error}`);
      }
    } catch (e: any) {
      setCompCreator(null);
      compPushMsg(`TikTok options unavailable: ${e.message}`);
    } finally {
      setCompOptionsLoading(false);
    }
  };

  // Resolve + preview the selected video; read its duration (guideline 1c + 5a).
  const selectComposeVideo = async (videoId: string) => {
    setCompVideo(videoId);
    setCompPreviewUrl('');
    setCompDuration(0);
    if (!videoId) return;
    const v = availableVideos.find((x: any) => (x.video_id || x.id) === videoId);
    // Seed from the persisted Firestore duration so guideline 1c still shows a
    // length (and the max check still bites) when there is no preview to measure.
    // onLoadedMetadata below refines this with the real media length.
    const recorded = Number(v?.duration) || 0;
    if (recorded > 0) {
      setCompDuration(recorded);
      if (compCreator?.max_duration && recorded > compCreator.max_duration) {
        compPushMsg(`Duration ${Math.round(recorded)}s exceeds TikTok max ${compCreator.max_duration}s — publishing blocked.`);
      }
    }
    let src = v?.video_url || v?.youtube_url || '';
    const r2Key = v?.r2_key || '';
    if (!src && r2Key) {
      const res = await apiFetch(`/api/storage/sign?key=${encodeURIComponent(r2Key)}`);
      const data = await res.json();
      if (!data.success) {
        compPushMsg(`Preview unavailable: ${data.error}`);
        return;
      }
      src = data.url;
    }
    if (!src) {
      compPushMsg('No preview media found for this video (render not in R2). You can still queue it — the pipeline publishes the local file.');
      return;
    }
    setCompPreviewUrl(src);
  };

  const submitCompose = async () => {
    if (!compVideo) return alert('Select a video to publish.');
    if (!compTitle.trim()) return alert('Enter a title.');
    if (!compPrivacy) return alert('Select a privacy level (required — no default).');
    if (compCreator?.max_duration && compDuration > compCreator.max_duration)
      return alert(`This video (${Math.round(compDuration)}s) exceeds the TikTok max post duration (${compCreator.max_duration}s).`);
    if (compBrandToggle && !compBrandOrganic && !compBrandContent)
      return alert('You need to indicate if your content promotes yourself, a third party, or both.');
    if (compBrandContent && compPrivacy === 'SELF_ONLY')
      return alert('Branded content visibility cannot be set to private. Choose Public or followers.');
    if (!compConsent) return alert('Confirm the consent declaration to continue.');
    setCompSubmitting(true);
    try {
      const res = await apiFetch('/api/tiktok/composer/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          video_id: compVideo,
          title: compTitle.trim(),
          format: 'shorts',
          privacy_level: compPrivacy,
          comment_disabled: !compComment,
          duet_disabled: !compDuet,
          stitch_disabled: !compStitch,
          brand_organic: compBrandToggle && compBrandOrganic,
          brand_content: compBrandToggle && compBrandContent,
          express_consent: compConsent,
          music_usage_confirmed: compConsent,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setCompIntentId(data.intent_id);
        localStorage.setItem(COMPOSE_INTENT_KEY, data.intent_id);
        setCompIntent({ status: 'queued' });
        compPushMsg(`Queued (${data.intent_id}). Posting may take a few minutes to be visible on TikTok.`);
        setCompTitle(''); setCompVideo(''); setCompPrivacy(''); setCompComment(false); setCompDuet(false); setCompStitch(false);
        setCompBrandToggle(false); setCompBrandOrganic(false); setCompBrandContent(false); setCompConsent(false);
        setCompPreviewUrl(''); setCompDuration(0);
      } else {
        compPushMsg(`Failed to queue TikTok post: ${data.error}`);
      }
    } catch (e: any) {
      compPushMsg(`Failed to queue TikTok post: ${e.message}`);
    } finally {
      setCompSubmitting(false);
    }
  };

  // Restore an in-flight intent on mount, then immediately resolve it rather than
  // leaving the panel blank until the first 10s tick.
  useEffect(() => {
    const saved = localStorage.getItem(COMPOSE_INTENT_KEY);
    if (!saved) return;
    setCompIntentId(saved);
    apiFetch(`/api/tiktok/composer/status/${saved}`)
      .then((r) => r.json())
      .then((d) => {
        if (!d.success) return;
        setCompIntent(d);
        if (d.status === 'published' || d.status === 'failed') {
          localStorage.removeItem(COMPOSE_INTENT_KEY);
          setCompIntentId('');
        }
      })
      .catch(() => {
        // Keep the id: a transient network blip should not orphan a real post.
      });
  }, []);

  // Poll intent status after queuing (guideline 5e: users understand post status).
  // The id is persisted so a reload resumes tracking. Without this, refreshing the
  // page mid-post silently dropped the only handle on a post that is still in
  // flight -- the queue is asynchronous, so the reload window is not small.
  useEffect(() => {
    if (!compIntentId) return;
    const timer = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/tiktok/composer/status/${compIntentId}`);
        const data = await res.json();
        if (data.success) {
          const st = data.status || 'unknown';
          setCompIntent(data);
          if (st === 'published' || st === 'failed') {
            clearInterval(timer);
            localStorage.removeItem(COMPOSE_INTENT_KEY);
            compPushMsg(st === 'published' ? `Published: ${data.url || data.publish_id || 'TikTok'}` : `Failed: ${data.error || st}`);
          }
        }
      } catch (e: any) {
        compPushMsg(`Status poll error: ${e.message}`);
      }
    }, 10000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compIntentId]);

  const totalFollowers = platforms.reduce((s, p) => s + p.followers, 0);
  const totalPublished = platforms.reduce((s, p) => s + (Number(p.videosPublished) || 0), 0);
const connectedCount = platforms.filter(p => p.connected).length;

  const OAUTH_URLS: Record<string, string> = {
    tiktok: '/api/auth/tiktok?action=connect',
    youtube: '/api/auth/youtube?action=connect',
    facebook: '/api/auth/meta?action=connect',
    instagram: '/api/auth/meta?action=connect',
  };

  const formatFollowers = (n?: number) => {
    if (typeof n !== 'number' || Number.isNaN(n)) return '0';
    return n >= 1000000 ? (n / 1000000).toFixed(1) + 'M' : n >= 1000 ? (n / 1000).toFixed(1) + 'K' : n.toString();
  };

  const savePlatformSetting = async (platformId: string, updated: any) => {
    try {
      const res = await apiFetch(`/api/platform-settings/${platformId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
      if (!res.ok) throw new Error('Failed to save');
    } catch (e) {
      console.error('Failed to save platform setting:', e);
    }
  };

  const toggleConnection = async (platformId: string) => {
    const platform = platforms.find(p => p.id === platformId);
    if (!platform) return;

    if (!platform.connected) {
      const oauthUrl = OAUTH_URLS[platformId];
      if (oauthUrl) {
        window.location.href = oauthUrl;
        return;
      }
      const updated = { ...platform, connected: true };
      await savePlatformSetting(platformId, updated);
    } else {
      if (!confirm(`Disconnect ${platform.name}? OAuth tokens will be removed.`)) return;
      const updated = {
        ...platform,
        connected: false,
        access_token: '',
        refresh_token: '',
        open_id: '',
      };
      await savePlatformSetting(platformId, updated);
    }
  };

  const toggleAutoPublish = async (platformId: string) => {
    const platform = platforms.find(p => p.id === platformId);
    if (!platform) return;
    const updated = { ...platform, autoPublish: !platform.autoPublish };
    await savePlatformSetting(platformId, updated);
  };

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center gap-4 mb-2">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-green-500/20 to-emerald-500/20 flex items-center justify-center">
            <span className="text-2xl">📤</span>
          </div>
          <div>
            <h1 className="text-3xl font-bold text-light-text dark:text-dark-text">Multi-Platform Publishing</h1>
            <p className="text-light-muted dark:text-dark-muted mt-1">Manage uploads across YouTube, TikTok, Instagram & Facebook</p>
          </div>
        </div>
      </motion.div>

      {userRole === 'reviewer' ? (
        <div className="rounded-2xl glass-strong border border-blue-500/30 p-6">
          <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-1">Reviewer Access</h2>
          <p className="text-xs text-light-muted dark:text-dark-muted">
            You are signed in with a reviewer account. Only the TikTok composer and its publish-status flow are available to this role. Platform connection status, analytics, and admin controls are hidden.
          </p>
        </div>
      ) : (
      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'Connected Platforms', value: `${connectedCount}/${platforms.length}`, icon: '🔗', color: 'text-emerald-400' },
          { label: 'Total Followers', value: formatFollowers(totalFollowers), icon: '👥', color: 'text-blue-400' },
{ label: 'Videos Published', value: totalPublished.toString(), icon: '🎬', color: 'text-purple-400' },
          ].map(stat => (
          <motion.div key={stat.label} className="p-4 rounded-xl glass-strong border border-light-border/30 dark:border-white/5">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{stat.icon}</span>
              <p className="text-xs text-light-muted dark:text-dark-muted">{stat.label}</p>
            </div>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </motion.div>
        ))}
      </div>

      {/* TikTok Review Access */}
      <div className="rounded-2xl glass-strong border border-purple-500/30 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-1">TikTok Review Access</h2>
        <p className="text-xs text-light-muted dark:text-dark-muted mb-4">
          Provided for TikTok Direct Post audit reviewers. Log in below to test the live posting flow end-to-end.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="rounded-xl bg-purple-500/5 border border-purple-500/20 p-4">
            <p className="text-xs font-semibold text-light-muted dark:text-dark-muted mb-2">Reviewer credentials</p>
            <div className="space-y-1 text-sm text-light-text dark:text-dark-text">
              <p><span className="text-light-muted dark:text-dark-muted">Email:</span> <code className="text-purple-400">reviewer@vyomai.cloud</code></p>
              <p><span className="text-light-muted dark:text-dark-muted">Sign in:</span> use the <strong>&ldquo;Sign in with Email&rdquo;</strong> field on the login page</p>
            </div>
          </div>
          <div className="rounded-xl bg-light-bg/50 dark:bg-dark-bg/50 border border-light-border/30 dark:border-white/5 p-4">
            <p className="text-xs font-semibold text-light-muted dark:text-dark-muted mb-2">How to test posting to TikTok</p>
            <ol className="list-decimal pl-4 space-y-1 text-xs text-light-text dark:text-dark-text">
              <li>Sign in as reviewer, then connect a TikTok account below (Connect → TikTok).</li>
              <li>Open the <strong>Compose TikTok Post</strong> card on this page.</li>
              <li>Pick a video (preview + duration shown), enter a title, then select a privacy level (no default).</li>
              <li>Review interaction toggles, commercial content disclosure, and the consent declaration.</li>
              <li>Confirm consent and hit <strong>Queue TikTok Post</strong> — the status panel tracks publishing.</li>
              <li>The post publishes to the connected TikTok account within ~5 minutes.</li>
            </ol>
          </div>
        </div>
      </div>

      {/* Platform Cards */}
      {platforms.length === 0 ? (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-12 text-center">
          <div className="text-5xl mb-4">📤</div>
          <h3 className="text-lg font-bold text-light-text dark:text-dark-text mb-2">No Platforms Connected</h3>
          <p className="text-sm text-light-muted dark:text-dark-muted max-w-md mx-auto">
            Connect your YouTube, TikTok, Instagram, or Facebook accounts to start publishing videos automatically.
          </p>
        </motion.div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {platforms.map((platform, i) => (
          <motion.div
            key={platform.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className={`rounded-2xl glass-strong border overflow-hidden transition-all cursor-pointer ${
              selectedPlatform === platform.id ? 'border-2' : 'border-light-border/30 dark:border-white/5'
            }`}
            style={selectedPlatform === platform.id ? { borderColor: platform.color } : {}}
            onClick={() => setSelectedPlatform(selectedPlatform === platform.id ? null : platform.id)}
          >
            {/* Platform Header */}
            <div className="p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-xl flex items-center justify-center text-2xl" style={{ background: `${platform.color}20` }}>
                    {platform.icon}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-light-text dark:text-dark-text">{platform.name}</h3>
                    <p className="text-xs text-light-muted dark:text-dark-muted">{formatFollowers(platform.followers)} followers</p>
                    {platform.connected && platform.scope && (
                      <p className="text-[10px] text-light-muted dark:text-dark-muted break-all">scopes: {platform.scope}</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <StatusPill connected={platform.connected} />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Published</p>
                  <p className="text-lg font-bold text-light-text dark:text-dark-text">{platform.videosPublished}</p>
                </div>
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Shorts/Day</p>
                  <p className="text-lg font-bold text-light-text dark:text-dark-text">{platform.maxShortsPerDay}</p>
                </div>
                <div className="p-2 rounded-lg bg-light-bg/50 dark:bg-dark-bg/50 text-center">
                  <p className="text-xs text-light-muted dark:text-dark-muted">Best Time</p>
                  <p className="text-sm font-bold text-light-text dark:text-dark-text">{platform.bestTime}</p>
                </div>
              </div>

              <div className="flex gap-2 mt-4">
                <button
                  onClick={(e) => { e.stopPropagation(); toggleConnection(platform.id); }}
                  className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                    platform.connected
                      ? 'bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30'
                      : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 hover:bg-emerald-500/30'
                  }`}
                >
                  {platform.connected ? 'Disconnect' : 'Connect'}
                </button>
                {platform.connected && (
                  <button
                    onClick={(e) => { e.stopPropagation(); toggleAutoPublish(platform.id); }}
                    className={`flex-1 py-2 rounded-lg text-xs font-medium transition-colors ${
                      platform.autoPublish
                        ? 'bg-purple-500/20 text-purple-400 border border-purple-500/30'
                        : 'bg-light-border/50 dark:bg-dark-border/50 text-light-muted dark:text-dark-muted'
                    }`}
                  >
                    Auto: {platform.autoPublish ? 'ON' : 'OFF'}
                  </button>
                )}
              </div>
            </div>

            {/* Expanded Details */}
            <AnimatePresence>
              {selectedPlatform === platform.id && (
                <motion.div
                  key="details"
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className="overflow-hidden"
                >
                  <div className="px-5 pb-5 pt-0 border-t border-light-border/30 dark:border-white/5">
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Schedule enabled</span>
                        <span className={`text-xs font-bold ${platform.scheduleEnabled ? 'text-emerald-400' : 'text-light-muted dark:text-dark-muted'}`}>
                          {platform.scheduleEnabled ? 'Yes' : 'No'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Long form per day</span>
                        <span className="text-sm font-bold text-light-text dark:text-dark-text">{platform.maxLongPerDay}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-light-muted dark:text-dark-muted">Last published</span>
                        <span className="text-sm font-bold text-light-text dark:text-dark-text">
                          {platform.lastPublished ? formatTimeAgo(platform.lastPublished) : 'Never'}
                        </span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </div>
      )}

      )}

{/* TikTok Composer */}
      <div className="rounded-2xl glass-strong border border-light-border/30 dark:border-white/5 p-6">
        <h2 className="text-lg font-bold text-light-text dark:text-dark-text mb-1">Compose TikTok Post</h2>
        <p className="text-xs text-light-muted dark:text-dark-muted mb-4">
          Manually publish a recently rendered video to TikTok. A privacy level is <span className="font-semibold text-light-primary">required</span> — no default is preselected. Comments/Duet/Stitch default to off.
        </p>

        {/* Creator banner (guideline 1a) */}
        {compOptionsLoading && (
          <div className="text-xs text-light-muted dark:text-dark-muted mb-3">Loading TikTok creator info…</div>
        )}
        {!compOptionsLoading && compCreator && (
          <div className="flex items-center gap-3 mb-4 p-3 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5">
            {compCreator.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={compCreator.avatar_url} alt={compCreator.nickname} className="w-10 h-10 rounded-full object-cover" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400 font-bold">
                {(compCreator.nickname || 'T')[0]}
              </div>
            )}
            <div>
              <p className="text-sm font-semibold text-light-text dark:text-dark-text">{compCreator.nickname}</p>
              <p className="text-xs text-light-muted dark:text-dark-muted">
                Posting to @{compCreator.username || compCreator.nickname}.{' '}
                {compCreator.max_duration ? `Max video: ${compCreator.max_duration}s.` : ''}
              </p>
            </div>
          </div>
        )}
        {!compOptionsLoading && !compCreator && (
          <div className="text-xs text-amber-500 mb-3">
            TikTok creator info unavailable — connect a TikTok account first.
            <button onClick={loadComposerOptions} className="ml-2 underline">Retry</button>
          </div>
        )}

        <div className="space-y-3">
          <div>
            <label className="text-xs font-medium text-light-muted dark:text-dark-muted block mb-1">Video (unpublished renders)</label>
            <select
              value={compVideo}
              onChange={(e) => selectComposeVideo(e.target.value)}
              className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 text-sm text-light-text dark:text-dark-text outline-none focus:border-light-primary/50"
            >
              <option value="">Select a video…</option>
              {availableVideos.map((v: any) => (
                <option key={v.video_id || v.id} value={v.video_id || v.id}>
                  {v.title || v.video_id || v.id} ({v.format || 'shorts'}){v.status ? ` — ${v.status}` : ''}
                </option>
              ))}
            </select>
            <div className="flex flex-wrap gap-2 mt-2">
              {availableVideos.map((v: any) => (
                <button
                  key={v.video_id || v.id}
                  onClick={() => selectComposeVideo(v.video_id || v.id)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium border ${
                    compVideo === (v.video_id || v.id)
                      ? 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                      : 'bg-light-bg dark:bg-dark-bg border-light-border/30 dark:border-white/5 text-light-muted dark:text-dark-muted'
                  }`}
                >
                  {(v.title || v.video_id || v.id).slice(0, 24)}
                </button>
              ))}
            </div>
          </div>

          {/* Manual upload shortcut for reviewers */}
          <div>
            <label className="text-xs font-medium text-light-muted dark:text-dark-muted block mb-1">Upload a video file to R2</label>
            <input
              type="file"
              accept="video/*"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setCompUploading(true);
                setCompUploadProgress(15);
                const _fake = setInterval(() => { setCompUploadProgress(p => Math.min(p + 15, 90)); }, 200);
                try {
                  const form = new FormData();
                  form.append('file', file);
                  form.append('format', 'shorts');
                  const res = await apiFetch('/api/tiktok/composer/upload', { method: 'POST', body: form });
                  const data = await res.json();
                  clearInterval(_fake);
                  setCompUploadProgress(100);
                  if (data.success) {
                    setCompVideo(data.video_id);
                    setAvailableVideos(p => [{ video_id: data.video_id, title: file.name, format: 'shorts', status: 'uploaded', r2_key: data.r2_key }, ...p]);
                    compPushMsg('Uploaded: ' + data.video_id);
                  } else {
                    compPushMsg('Upload failed: ' + (data.error || 'unknown'));
                  }
                } catch (err: any) {
                  compPushMsg('Upload failed: ' + err.message);
                } finally {
                  clearInterval(_fake);
                  setCompUploading(false);
                  setTimeout(() => setCompUploadProgress(0), 1500);
                }
              }}
              className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 text-sm text-light-text dark:text-dark-text"
            />
            {compUploading && (
              <div className="mt-2 w-full h-2 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                <div className="h-full bg-light-primary dark:bg-dark-primary transition-all duration-200" style={{ width: `${compUploadProgress}%` }} />
              </div>
            )}
          </div>

          {/* Content preview (guideline 5a) */}
          {compPreviewUrl && (
            <div>
              <div className="rounded-xl overflow-hidden bg-black">
                {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
                <video
                  src={compPreviewUrl}
                  controls
                  className="w-full max-h-56 object-contain"
                  onLoadedMetadata={(e) => {
                    const d = (e.target as HTMLVideoElement).duration || 0;
                    if (d > 0) setCompDuration(d);
                    const dur = d > 0 ? d : compDuration;
                    if (compCreator?.max_duration && dur > compCreator.max_duration) {
                      compPushMsg(`Duration ${Math.round(dur)}s exceeds TikTok max ${compCreator.max_duration}s — publishing blocked.`);
                    }
                  }}
                />
              </div>
              <p className="text-[10px] text-light-muted dark:text-dark-muted mt-1">
                Preview shows watermarked version — clean file (no watermark) will be posted to TikTok.
              </p>
            </div>
          )}

          {/* Length readout, required whether or not a preview plays. */}
          {compDuration > 0 && (
            <div className="rounded-xl border border-light-border dark:border-dark-border px-3 py-1.5 text-[11px] text-light-muted dark:text-dark-muted">
              Duration: {Math.round(compDuration)}s
              {compCreator?.max_duration > 0 && ` / max ${compCreator.max_duration}s`} —
              {compCreator?.max_duration > 0 && compDuration > compCreator.max_duration ? (
                <span className="text-red-500 font-semibold"> too long, publishing blocked</span>
              ) : (
                <span className="text-light-success font-semibold"> OK</span>
              )}
              {!compPreviewUrl && (
                <span> (from pipeline record — no preview available)</span>
              )}
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-light-muted dark:text-dark-muted block mb-1">
              Caption (this is the post title — include your hashtags here)
            </label>
            {/* A textarea, not an input: on TikTok the title IS the caption, and a
                caption carrying hashtags is multi-line by nature. maxLength is
                enforced by the browser in UTF-16 code units, which is the same
                unit TikTok's 2200 limit uses, so the two cannot disagree. */}
            <textarea
              value={compTitle}
              onChange={(e) => setCompTitle(e.target.value)}
              maxLength={2200}
              rows={4}
              placeholder="Write the caption and add #hashtags…"
              className="w-full px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 text-sm text-light-text dark:text-dark-text placeholder-light-muted dark:placeholder-dark-muted outline-none focus:border-light-primary/50 resize-y"
            />
            {/* JS strings ARE UTF-16, so `.length` is already the unit TikTok and
                maxLength both use. Do not "fix" this to [...s].length -- that
                counts code points and would under-report an emoji-heavy caption. */}
            <div className="mt-1 text-right text-[11px] tabular-nums text-light-muted dark:text-dark-muted">
              {compTitle.length} / 2200
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-light-muted dark:text-dark-muted block mb-1">Privacy level (no default — select one)</label>
            <div className="flex gap-2">
              <select
                value={compPrivacy}
                onChange={(e) => {
                  const val = e.target.value;
                  setCompPrivacy(val);
                  if (compBrandToggle && compBrandContent && val === 'SELF_ONLY') {
                    compPushMsg('Branded content visibility cannot be set to private. Choose Public or followers.');
                  }
                }}
                className="flex-1 px-3 py-2 rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 text-sm text-light-text dark:text-dark-text outline-none focus:border-light-primary/50"
              >
                <option value="">Select privacy…</option>
                {privacyOptions.map((opt: any) => {
                  const val = typeof opt === 'string' ? opt : (opt?.level || opt?.privacy_level || opt?.value || '');
                  const label = compPrivacyLabel(opt);
                  const blocked = compBrandToggle && compBrandContent && val === 'SELF_ONLY';
                  return val ? <option key={val} value={val} disabled={!!blocked}>{label}{blocked ? ' (blocked for branded content)' : ''}</option> : null;
                })}
              </select>
              <button
                onClick={loadComposerOptions}
                disabled={compOptionsLoading}
                className="px-3 py-2 rounded-xl text-xs font-medium bg-purple-500/20 text-purple-400 border border-purple-500/30 hover:bg-purple-500/30 disabled:opacity-50"
              >
                {compOptionsLoading ? 'Loading…' : 'Reload options'}
              </button>
            </div>
          </div>

          <div className="space-y-2 pt-1">
            {[
              { label: 'Allow comments', state: compComment, setter: setCompComment, locked: !!compCreator?.comment_disabled },
              { label: 'Allow duet', state: compDuet, setter: setCompDuet, locked: !!compCreator?.duet_disabled },
              { label: 'Allow stitch', state: compStitch, setter: setCompStitch, locked: !!compCreator?.stitch_disabled },
            ].map((t) => (
              <div key={t.label} className="flex items-center justify-between">
                <span className={`text-sm ${t.locked ? 'text-light-muted/60 dark:text-dark-muted/60' : 'text-light-text dark:text-dark-text'}`}>
                  {t.label}{t.locked ? ' (disabled in TikTok settings)' : ''}
                </span>
                <button
                  onClick={() => { if (!t.locked) t.setter(!t.state); }}
                  disabled={t.locked}
                  className={`w-10 h-6 rounded-full transition-colors ${t.state ? 'bg-light-success' : 'bg-light-border dark:bg-dark-border'} ${t.locked ? 'opacity-40 cursor-not-allowed' : ''}`}
                >
                  <motion.div
                    className="w-5 h-5 rounded-full bg-white shadow-sm"
                    animate={{ x: t.state ? 18 : 2 }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                </button>
              </div>
            ))}
          </div>

          {/* Commercial content disclosure (guideline 3) */}
          <div className="rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 p-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-light-text dark:text-dark-text">Commercial content disclosure</span>
              <button
                onClick={() => { setCompBrandToggle(!compBrandToggle); if (!compBrandToggle) { setCompBrandOrganic(false); setCompBrandContent(false); } }}
                className={`w-10 h-6 rounded-full transition-colors ${compBrandToggle ? 'bg-light-success' : 'bg-light-border dark:bg-dark-border'}`}
              >
                <motion.div
                  className="w-5 h-5 rounded-full bg-white shadow-sm"
                  animate={{ x: compBrandToggle ? 18 : 2 }}
                  transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                />
              </button>
            </div>
            {compBrandToggle && (
              <div className="mt-3 space-y-2">
                <label className="flex items-start gap-2 cursor-pointer">
                  <input type="checkbox" checked={compBrandOrganic} onChange={(e) => setCompBrandOrganic(e.target.checked)} className="mt-0.5 accent-teal-500" />
                  <span className="text-sm text-light-text dark:text-dark-text">
                    Your brand — <span className="text-xs text-light-muted dark:text-dark-muted">&quot;Your photo/video will be labeled as &apos;Promotional content&apos;&quot;.</span>
                  </span>
                </label>
                <label className="flex items-start gap-2 cursor-pointer">
                  <input type="checkbox" checked={compBrandContent} onChange={(e) => setCompBrandContent(e.target.checked)} className="mt-0.5 accent-teal-500" />
                  <span className="text-sm text-light-text dark:text-dark-text">
                    Branded content — <span className="text-xs text-light-muted dark:text-dark-muted">&quot;Your photo/video will be labeled as &apos;Paid partnership&apos;&quot;.</span>
                  </span>
                </label>
                {compBrandToggle && !compBrandOrganic && !compBrandContent && (
                  <p className="text-xs text-amber-500">You need to indicate if your content promotes yourself, a third party, or both.</p>
                )}
                {compBrandToggle && compBrandOrganic && compBrandContent && (
                  <p className="text-xs text-light-muted dark:text-dark-muted">&quot;Your photo/video will be labeled as &apos;Paid partnership&apos;&quot;.</p>
                )}
              </div>
            )}
          </div>

          {/* Compliance + consent (guideline 4 + 5c) */}
          <div className="rounded-xl bg-light-bg dark:bg-dark-bg border border-light-border/30 dark:border-white/5 p-3">
            <label className="flex items-start gap-2 cursor-pointer">
              <input type="checkbox" checked={compConsent} onChange={(e) => setCompConsent(e.target.checked)} className="mt-0.5 accent-teal-500" />
              <span className="text-sm text-light-text dark:text-dark-text">
                I understand this video will be published to my TikTok account. {compComplianceText()} Posting may take a few minutes to be visible.
              </span>
            </label>
          </div>

          {compMsgs.map((m, i) => (
            <p key={i} className="text-xs text-light-muted dark:text-dark-muted">{m}</p>
          ))}

          {/* Status panel (guideline 5e) */}
          {compIntent && (
            <div className="rounded-xl p-3 border border-light-border/30 dark:border-white/5 bg-light-bg dark:bg-dark-bg">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-light-text dark:text-dark-text">Publish status</span>
                <span className={`text-xs font-bold ${compIntent.status === 'published' ? 'text-light-success' : compIntent.status === 'failed' ? 'text-red-500' : 'text-purple-400'}`}>
                  {compIntent.status}
                </span>
              </div>
              {compIntent.status !== 'published' && compIntent.status !== 'failed' && compIntent.status !== 'limit_reached' && (
                <p className="text-xs text-light-muted dark:text-dark-muted mt-1">Processing — this may take a few minutes to appear on TikTok.</p>
              )}
              {compIntent.status === 'limit_reached' && (
                <p className="text-xs text-amber-500 mt-1">You&apos;ve hit today&apos;s posting limit — try again later.</p>
              )}
              {compIntent.status === 'published' && compIntent.url && (
                <a href={compIntent.url} target="_blank" rel="noreferrer" className="text-xs text-light-primary underline mt-1 block break-all">
                  {compIntent.url}
                </a>
              )}
              {compIntent.error && compIntent.status !== 'limit_reached' && <p className="text-xs text-red-500 mt-1 break-all">{compIntent.error}</p>}
            </div>
          )}

          <button
            onClick={submitCompose}
            disabled={compSubmitting || compBrandDisabled || (!!compCreator?.max_duration && compDuration > compCreator.max_duration)}
            className="w-full py-3 rounded-2xl text-white font-semibold text-sm bg-gradient-to-r from-light-primary to-purple-600 hover:shadow-lg transition-shadow disabled:opacity-50"
            title={compBrandDisabled ? 'You need to indicate if your content promotes yourself, a third party, or both.' : undefined}
          >
            {compSubmitting ? 'Queuing…' : 'Queue TikTok Post'}
          </button>
        </div>
      </div>
    </div>
  );
}

function StatusPill({ connected }: { connected: boolean }) {
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-bold ${
      connected ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'
    }`}>
      {connected ? '● Connected' : '○ Disconnected'}
    </span>
  );
}

function formatTimeAgo(timestamp: any) {
  if (!timestamp) return 'Never';
  const date = timestamp.toDate ? timestamp.toDate() : new Date(timestamp);
  const diff = Math.floor((Date.now() - date.getTime()) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
