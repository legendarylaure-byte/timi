import { db } from './firebase';
import { doc, getDoc } from 'firebase/firestore';

export interface PlatformThresholds {
  youtube: { subs: number; watchHours: number; shortsViews: number };
  tiktok: { followers: number; views: number };
  instagram: { followers: number; watchMins: number };
}

export const DEFAULT_THRESHOLDS: PlatformThresholds = {
  youtube: { subs: 1000, watchHours: 4000, shortsViews: 10_000_000 },
  tiktok: { followers: 10_000, views: 100_000 },
  instagram: { followers: 10_000, watchMins: 60_000 },
};

let cachedThresholds: PlatformThresholds | null = null;

export async function getThresholds(): Promise<PlatformThresholds> {
  if (cachedThresholds) return cachedThresholds;
  try {
    const snap = await getDoc(doc(db, 'config', 'thresholds'));
    if (snap.exists()) {
      const data = snap.data();
      cachedThresholds = {
        youtube: {
          subs: data.youtube?.subs ?? DEFAULT_THRESHOLDS.youtube.subs,
          watchHours: data.youtube?.watchHours ?? DEFAULT_THRESHOLDS.youtube.watchHours,
          shortsViews: data.youtube?.shortsViews ?? DEFAULT_THRESHOLDS.youtube.shortsViews,
        },
        tiktok: {
          followers: data.tiktok?.followers ?? DEFAULT_THRESHOLDS.tiktok.followers,
          views: data.tiktok?.views ?? DEFAULT_THRESHOLDS.tiktok.views,
        },
        instagram: {
          followers: data.instagram?.followers ?? DEFAULT_THRESHOLDS.instagram.followers,
          watchMins: data.instagram?.watchMins ?? DEFAULT_THRESHOLDS.instagram.watchMins,
        },
      };
      return cachedThresholds;
    }
  } catch {
    // Firestore unavailable — use defaults
  }
  return DEFAULT_THRESHOLDS;
}

export function resetThresholdsCache() {
  cachedThresholds = null;
}
