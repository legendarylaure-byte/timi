// Invariant: every status a visitor can filter by renders as a distinct,
// human-readable badge -- and none of them silently borrows another's colour.
//
// The bug this pins: archive/page.tsx had a `statusColors` map covering 9
// statuses but not `pending_review` or `blocked_review`, and then used
// `statusColors[v.status] || statusColors.generating` as its fallback. So a
// video the quality gate was deliberately holding rendered as a yellow
// "Generating" badge, i.e. the archive said "still working on it" for a video
// that was finished and waiting for a human. Same class of failure as the
// D38 dashboard/teal drift: a fallback that hides a mismatch.
import { STATUS_META, statusMeta, statusClasses, DEFAULT_STATUS_META, STATUS } from '@/lib/brand';

// The `<option>` values the archive status filter offers.
const FILTER_OPTIONS = [
  'uploaded', 'scheduled', 'generating', 'upload_failed', 'failed',
];

// Statuses the Python pipeline writes into `videos.status`.
const PIPELINE_STATUSES = [
  'generating', 'testing', 'uploaded', 'scheduled', 'upload_failed', 'failed',
  'blocked', 'blocked_virality', 'blocked_compliance',
];

describe('status vocabulary', () => {
  it('covers every status the archive filter offers', () => {
    for (const s of FILTER_OPTIONS) {
      expect(STATUS_META[s]).toBeDefined();
    }
  });

  it('covers every status the pipeline writes', () => {
    for (const s of PIPELINE_STATUSES) {
      expect(STATUS_META[s]).toBeDefined();
    }
  });

  // The actual defect. `videos.status` is "pending_review"; the sibling field
  // `videos.review_status` is "manual_review". Neither was in the map.
  it('covers pending_review and blocked_review', () => {
    expect(STATUS_META.pending_review).toBeDefined();
    expect(STATUS_META.blocked_review).toBeDefined();
  });

  it('a held video is not labelled generating', () => {
    expect(statusMeta('pending_review').label).not.toBe(statusMeta('generating').label);
    expect(statusClasses('pending_review')).not.toBe(statusClasses('generating'));
    expect(statusClasses('blocked_review')).not.toBe(statusClasses('generating'));
  });

  it('publishing and publishing-failed are different tones', () => {
    expect(statusClasses('uploaded')).not.toBe(statusClasses('upload_failed'));
    expect(statusClasses('uploaded')).not.toBe(statusClasses('failed'));
  });

  it('every tone maps to a defined colour set', () => {
    for (const s of Object.keys(STATUS_META)) {
      const tone = statusMeta(s).tone;
      expect(Object.keys(STATUS)).toContain(tone);
    }
  });

  it('no label leaks an internal enum', () => {
    for (const [key, meta] of Object.entries(STATUS_META)) {
      expect(meta.label).not.toBe(key);
      expect(meta.label).not.toContain('_');
      expect(meta.label.length).toBeGreaterThan(0);
    }
  });

  it('an unknown status degrades visibly instead of borrowing a colour', () => {
    // This is the fallback that hid the bug. It must not be "generating",
    // because "generating" is a claim about work in progress.
    const fallback = statusMeta('a_status_nobody_wrote_yet');
    expect(fallback).toEqual(DEFAULT_STATUS_META);
    expect(fallback.label).not.toBe('Generating');
  });

  it('handles null, undefined and empty without throwing', () => {
    for (const v of [null, undefined, '']) {
      expect(() => statusMeta(v)).not.toThrow();
      expect(statusMeta(v)).toEqual(DEFAULT_STATUS_META);
      expect(() => statusClasses(v)).not.toThrow();
    }
  });
});
