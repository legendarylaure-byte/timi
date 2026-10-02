/**
 * The composer queues a post asynchronously, so the only handle on an in-flight
 * publish is the intent id. It lives in React state, which a reload throws away:
 * refresh mid-post and the panel comes back empty with no hint that anything is
 * happening. The id is mirrored to localStorage and restored on mount.
 *
 * This is a source-level check on purpose. Mounting this page in jsdom needs
 * firebase, framer-motion and apiFetch stubbed, and the thing that actually
 * regresses here is somebody refactoring a localStorage call away -- which no
 * DOM assertion would notice. The three call sites are the contract.
 */
import { readFileSync } from 'fs';
import { join } from 'path';

const PAGE = join(process.cwd(), 'src/app/dashboard/publishing/page.tsx');
const src = readFileSync(PAGE, 'utf8');

/** Body of a function/method, so an assert cannot be satisfied by a sibling. */
function body(marker: string, lines = 24): string {
  const i = src.indexOf(marker);
  expect(i).toBeGreaterThan(-1);
  return src.slice(i, i + lines * 100);
}

describe('TikTok composer intent persistence', () => {
  it('queues the id to localStorage so a reload can find it', () => {
    const submit = body('const submitCompose = async ()');
    expect(submit).toMatch(
      /setCompIntentId\(data\.intent_id\)[\s\S]{0,200}localStorage\.setItem\(\s*COMPOSE_INTENT_KEY/
    );
  });

  it('restores an in-flight intent on mount instead of starting blank', () => {
    const mount = body('// Restore an in-flight intent on mount');
    expect(mount).toMatch(/localStorage\.getItem\(COMPOSE_INTENT_KEY\)/);
    expect(mount).toMatch(/setCompIntentId\(saved\)/);
  });

  it('clears the key once the post reaches a terminal state', () => {
    // Must be in the poll's terminal branch, not the queue path: a key left
    // behind would re-open a finished post as "in flight" on the next visit.
    const poll = body('// Poll intent status after queuing');
    const terminal = poll.match(/st === 'published'[\s\S]{0,600}/);
    expect(terminal).not.toBeNull();
    expect(terminal![0]).toMatch(/localStorage\.removeItem\(COMPOSE_INTENT_KEY\)/);
  });

  it('keeps the key when a status poll fails, so a blip cannot orphan a post', () => {
    const mount = body('// Restore an in-flight intent on mount');
    // The catch must not clear: losing the id on a transient network error is
    // the exact failure this persistence exists to prevent.
    const catchBlock = mount.match(/catch\(\(\) => \{[\s\S]{0,300}?\}\);/);
    expect(catchBlock).not.toBeNull();
    expect(catchBlock![0]).not.toMatch(/removeItem|setCompIntentId\(''\)/);
  });

  it('shows the duration even with no preview, since the length is required', () => {
    // Guideline 1c: users must understand whether the video will be accepted.
    // The readout used to live inside the preview conditional, so a video with
    // no playable preview showed no length at all.
    const readout = body('/* Length readout, required whether or not a preview plays. */');
    expect(readout).toMatch(/compDuration > 0/);
    expect(readout).toMatch(/no preview available/);
  });

  it('seeds duration from the persisted record before any preview loads', () => {
    const select = body('const selectComposeVideo = async (videoId: string)');
    expect(select).toMatch(/Number\(v\?\.duration\)/);
  });
});
