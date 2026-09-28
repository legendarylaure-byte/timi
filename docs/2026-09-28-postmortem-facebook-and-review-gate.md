# Postmortem: 2026-09-28 15:05 UTC run

Run: 15:05:00 → 16:55:08 UTC. 5/5 videos rendered, 5/5 reached YouTube.
Platforms: 19/20 uploads. YouTube/Instagram/TikTok flawless; both long-form
Facebook uploads failed.

## Why the review gate stays advisory (decision: keep 5/day)

The user asked whether a "score > 50 then publish" rule was worth having. It is
not, for three independent reasons:

1. **50 is already the floor.** All 59 scored videos in the last 60 are >= 50,
   minimum exactly 50. The block condition is `score < 50` — unreachable by
   construction.
2. **The score does not predict views.** Pearson r = **+0.089** over 138 paired
   videos (r^2 = 0.008). Mean views: score <70 → 30, score >=80 → 41. A
   score-55 short got 103 views, beating four separate 88s.
3. **The threshold gates nothing today.** `main.py:1770` / `:2388` only stop on
   `review_decision == "block"`. `"pending_review"` is a label, never a hold.
   All 9 `manual_review` videos published anyway (9/9, verified individually).

Three thresholds are ANDed, so changing one is not enough:
- LLM recommendation (`utils/quality_scorer.py:30-35`): approve >=70, review 55-69, block <55
- `AUTO_APPROVE_THRESHOLD` (`main.py:449`) = 80
- hard block floor (`utils/quality_scorer.py:419`) = `<50`, unreachable

Score distribution has a natural break at 78 → 82, so 80 sits in an empty gap.
`AUTO_APPROVE_THRESHOLD` stays at 80.

## The Sentry alert was our own logging, not a broken video

Sentry `98591abe117d4a61a8c44fc8234b3d3f`: auto-reply failed for
`ohKDktWuCfQ`, `commentThreads.list` → HTTP 403 `reason="commentsDisabled"`.

Verified against the Data API — all four of the run's videos are
`privacy=private`, `madeForKids=False`, `snippet.allowComments=None`. The
channel default has comments off. Not a token problem (the same token uploaded
all five videos). A separate pinned-comment POST returned 403 insufficient
permissions.

Three defects:

1. **The log lies.** `main.py:1997` and `:2617` discard
   `post_pinned_comment()`'s bool, then log `"Pinned comment + auto-reply set
   up"` unconditionally. Every run writes success into `activity_logs` while
   doing nothing.
2. **Wrong order.** Comments are posted at upload time, when the video is
   `private` with no comment thread. `publish_at` is already in scope at both
   call sites.
3. **Wrong severity.** `commentsDisabled` is an expected state, logged as
   `ERROR` — that is what raised the Sentry alert.

## Facebook: the resumable protocol was never implemented

Meta's `/page/videos` resumable upload is a three-phase protocol:

| Phase | Sends | Must return |
|---|---|---|
| `start` | `file_size` | `video_id`, `start_offset`, `end_offset`, `upload_session_id` |
| `transfer` | **`video_file_chunk`**, `start_offset` | next `start_offset`/`end_offset` |
| `finish` | `upload_session_id` | `success: true` |

The code sent one phase, with the wrong field name:

- `:818` sent `files={'source': f}` — the transfer field is `video_file_chunk`
- `finish` was never called, so the session was opened and abandoned
- `:843` read `chunk_body.get('id')` — the id comes from the **`start`** response

`1363030` is Meta reporting an unfinalised session, **not** slow bandwidth.
`Expecting value: line 1 column 1 (char 0)` is a non-JSON error body on a
request that was never going to succeed.

The fault line is the 50MB direct/resumable split: every success tonight was
<=24MB (direct), every failure >=55MB (resumable). `_compress_for_facebook`
worked fine — 393MB → 108MB, 220MB → 55MB, in ~65s.

Meta's own developer forum has reports of this upload breaking server-side for
days (May 2026), so correct code can still fail. Hence the live test post.

## CRF: 20 for longs, 17 for shorts

`composite_video` renders both formats, so a single literal change would hit
both. Only the two final encodes (`:1024`, `:1194`) become format-aware; the
seven per-scene encodes (`:137`-`:503`) stay at 17 because they are re-encoded
into the final pass, so their quality is transient.

Longs ~393MB → ~215MB, so TikTok sends 4 chunks instead of 7. Nothing displays
the master: all four platforms re-encode. `QA_BLUR_THRESHOLD` is Laplacian
sharpness and will not catch compression artifacts — the long master is the
exposure and it is not visually verified.

## What did NOT get fixed tonight

- Clip sizing still renders full source duration before trimming (wasted render
  time every run)
- Render-only runs still record as `upload_failed` instead of a distinct state
- First-content hook only applies when the scene is `render_type == "manim"`
- Scene-count enforcement, title caps, token-refresh race, held-story fallback,
  watermark on dubs, HTML logo, daily-volume guard
- Viral TikTok photo posts still need an R2 custom domain

## Verification discipline

Six false alarms were recorded during this investigation. The ones that cost
time: a grep returning nothing for `AUTO_PROPROVE_THRESHOLD` (it exists at
`main.py:449`); a "no compression logs" conclusion (they go to Firestore, not
stdout); and a broken size-to-outcome correlation query that mismatched files
and counted failures from other runs. Confirm the mechanism ran before
believing a result, in either direction.
