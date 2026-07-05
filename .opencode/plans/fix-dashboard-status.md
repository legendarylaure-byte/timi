# Plan: Fix Dashboard Status Indicators

Dashboard URL: https://timi.vyomai.cloud (Vercel)
Dashboard root: `/Users/Ai Mark/timi/dashboard/`

## Current Problems

| Status | Shows | Root Cause | Depends On |
|--------|-------|------------|------------|
| Firebase | Disconnected | `FIREBASE_SERVICE_ACCOUNT_KEY` missing from Vercel env vars | Vercel config |
| Agents | Unknown | Cascading from Firebase failure | Firebase fix |
| Docker | Offline | Expected — no Docker daemon on Vercel serverless | (expected) |
| Storage | Not configured | `CLOUDFLARE_R2_*` env vars missing | Optional R2 setup |
| Next Upload | 11:45 AM NPT | Works fine (client-side calculation) | None |

---

## Fix 1: Firebase — Add service account key to Vercel

**Not a code change** — requires updating Vercel project environment variables.

The Firebase Admin SDK (`dashboard/src/lib/firebase-admin.ts`) needs `FIREBASE_SERVICE_ACCOUNT_KEY` (base64-encoded service account JSON) to authenticate. This value already exists in `dashboard/.env.local` but is not deployed to Vercel.

**Action required (in Vercel dashboard):**
1. Go to https://vercel.com → Project "timi" → Settings → Environment Variables
2. Add `FIREBASE_SERVICE_ACCOUNT_KEY` with the same base64 value from `.env.local`
3. Add to "Production" and "Preview" environments
4. Redeploy or wait for next deployment

**Alternative (code change):** The `/api/firebase` route could be made more resilient — instead of crashing on missing credentials, return a clear "not configured" status. This way the dashboard doesn't show "Disconnected" as an error state when it's just not configured properly. But the root fix is still adding the env var.

---

## Fix 2: Docker — Show "N/A (cloud)" instead of "Offline"

**Code change in** `dashboard/src/components/status/GlobalStatusBar.tsx` (lines 373-421):

Currently when Docker is unavailable, it shows `status: 'error'` with value `"Offline"`. Since Docker will NEVER work on Vercel serverless, this is a misleading error state.

**Change:** Detect cloud deployment (check `window.location.hostname` for `vyomai.cloud` or `vercel.app`) or simply change the fallback display to show `"N/A (cloud)"` with `status: 'warn'` (not error).

An even simpler approach: the `/api/docker` endpoint could detect it's running on Vercel (`process.env.VERCEL === '1'`) and return a specific `reason: "vercel_serverless"` flag. The frontend could then show "N/A (cloud)" with a neutral icon instead of a red error dot.

---

## Fix 3: Storage — Optional, depends on R2 usage

**Action required (in Vercel dashboard):** If Cloudflare R2 storage is needed, add these env vars:
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_R2_ACCESS_KEY_ID`
- `CLOUDFLARE_R2_SECRET_ACCESS_KEY`
- `CLOUDFLARE_R2_BUCKET`

**If R2 is not needed:** The "Not configured" warning is benign. Can either leave it or add a graceful "Storage not in use" display.

---

## Fix 4: Agents — Auto-fixes when Firebase connects

No code change needed. The `/api/agents` and `/api/health` endpoints read from Firestore's `agent_status` collection. Once Firebase is connected (Fix 1), agents will show their real status from Firestore.

Optionally, the dashboard could cache the last known agent state locally so it doesn't show "Unknown" during brief Firestore outages.

---

## Implementation Order

| Step | What | Type | Effort |
|------|------|------|--------|
| 1 | Add `FIREBASE_SERVICE_ACCOUNT_KEY` to Vercel env vars | Config (Vercel UI) | 2 min |
| 2 | Graceful Docker "N/A (cloud)" display | Code (GlobalStatusBar.tsx) | 15 min |
| 3 | (Optional) Graceful Storage "not in use" display | Code (GlobalStatusBar.tsx) | 10 min |
| 4 | Verify all statuses after deployment | Testing | 5 min |

**Critical path:** Step 1 alone fixes Firebase + Agents. Steps 2-3 are cosmetic improvements.

---

## Files to Modify

| File | Change |
|------|--------|
| `dashboard/src/app/api/docker/route.ts` | Add Vercel detection → return `reason: "vercel"` |
| `dashboard/src/components/status/GlobalStatusBar.tsx` | Show "N/A (cloud)" instead of "Offline" for Docker on Vercel |
| (Optional) `dashboard/src/components/status/SystemStatusWidgets.tsx` | Same grace for Docker + Firebase status widgets |
