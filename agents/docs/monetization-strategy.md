# Monetization Strategy — Data-Backed Path to YPP

**Status:** working doc (2026-08-29) · **Channel:** Legendary Laure · **Owner:** pipeline operator

## Where we stand (honest baseline)
Real channel analytics as of 2026-08-29 (live API):
- 388 videos published
- 12 subscribers
- 4,425 lifetime views
- ~4,341 views + 717 watch-minutes (~11.9 hours) in the last 365 days
- ~12 net subs/yr

YouTube Partner Program (YPP, monetization) requires **either**:
- 1,000 subs + 4,000 public watch-hours in 12 months, **or**
- 1,000 subs + 10M public Shorts views in 90 days.

Watch-time shortfall vs the 4,000-hr target: **~3,988 hrs (~336×)**. Raw output volume has
not worked and will not close this gap. Monetizable watch-time is the real constraint.

## Why volume alone failed
- 388 videos but ~12 watch-hours/yr → sub-1s average retention per video; no one watches.
- Audience-retention curves are fetched but were never fed back into content (biggest
  missed lever). This is now wired (see Retention item below).
- Repetition: daily scheduler was returning the same static monthly topic set with a
  no-op dedup → audiences see the same hook/video repeatedly, driving down retention.
- Blurry/AI-tell renders, double subtitle tracks, voice≠subtitle mismatches suppressed
  watch retention and CTR.

## The strategy: balanced dual-track (approved)
Stop trying to brute-force watch-hours with long-volume or reach with short-volume.
Run two complementary tracks, steered by measured retention/CTR feedback:

1. **Freshwater Shorts → reach + subscriber acquisition (the growth engine)**
   - High-volume, always-fresh, non-repeating topics (real dedup now enforced).
   - Subtitle correctness + TRUE 9:16 (not letterboxed center-crop) so mobile viewers stay.
   - Hook-led, narration-led visuals. Subscriber CTA at the end of every Short.
   - Swap to **Best Video for New Viewers / Suggested** placement; double down on
     Shorts that exceed the channel's median retention.

2. **Fewer, better Longs → monetizable watch-hours (the revenue engine)**
   - Cut long volume; make each one a flagship deep-dive (single running example,
     non-technical audience, 15-20+ scenes, every scene visually coupled to narration).
   - Longs get soft CC (not burned) so text is clean, and a LIKE CTA + end screens.
   - Before producing a long, force a potential-hold check; if the plan's hook/quality
     gate fails, skip rather than publish a dud.

Both tracks are driven by two feedback loops that were dead and are now live:
- **Retention loop:** pull `audienceWatchRatio` curves, find the drop-off point, feed it
  back into hook/pacing/scene-duration tuning so the next video holds viewers longer.
- **A/B loop:** title variants are scored (`pick_best_title`) and A/B-run (`TitleTester`),
  thumbnails are score-picked (`pick_best_thumbnail`) — stop shipping blind title[0].

## Priorities (in order)
1. **Retention > reach.** One video that holds 60%+ to the end is worth more than ten that
   lose everyone in 3 seconds. Pipeline now gates on retention-aware quality checks.
2. **Correctness > volume.** Fixed: subtitle=voice, single caption track, narration-led
   visuals, non-technical scripts (16+), real topic dedup.
3. **10M Shorts views is the faster YPP door** (vs the 4,000 watch-hours that would need
   ~336× the current rate). Shorts should be the primary growth instrument for now;
   Longs build the monetizable audience once retention is proven.

## Guardrails / anti-goals
- Do NOT keep cranking out Longs just to hit a daily count when retention is poor.
- Do NOT re-publish the same topic within a 30-day window (dedup enforced now).
- Only enable monetization-affecting claims (drama, revenue numbers) when factually grounded.

## When to revisit
Rerun the honest analytics snapshot every ~30 days. The lever to watch is **average view
duration** and **subs gained per 100 Shorts views** — if neither moves within two cycles,
the content model itself needs rethinking, not more volume.
