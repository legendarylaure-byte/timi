# Meta App Review — Final Submission Package (Timi Video)

App: **Timi Video** — App ID `1623305175831341`
Destination accounts: Facebook Page **VyomAi Cloud** (`1295177777016744`) + linked Instagram Business Account (`17841437566807299`)
Reviewed test evidence: see `docs/meta-review-evidence/INDEX.html`

---

## App overview paragraph (paste at top of submission)

> "Timi Video is a single-operator content pipeline that generates and publishes educational technology videos to the developer's own YouTube, Facebook Page, and linked Instagram business account. It is not a multi-user product. Videos are pre-rendered and uploaded only as the Page/account admin via the Graph API. The app collects no user data and only acts on the developer-owned accounts."

---

## Permissions to submit (7 — advanced access)

Submit these **7** together. Remove from the submission any of: `instagram_business_basic`, `instagram_business_manage_messages`, `instagram_manage_comments`, `pages_messaging`, and anything not in this list.

### 1. instagram_content_publish
> **Describe how your app uses this permission or feature:**
> Timi Video publishes pre-rendered educational-technology videos to the Instagram business account that is linked to the developer's own Facebook Page "VyomAi Cloud". This permission allows the app to create and publish Reels/video posts to that single business account as the account admin. The app never posts to, reads, or interacts with any third-party Instagram account.
>
> **Required API test call (done):** `POST /17841437566807299/media` → media container ID `18093030908252227`, status `FINISHED`. Read-back `GET /{ig}/media` confirmed the published Reels.

### 2. pages_manage_posts
> **Describe how your app uses this permission or feature:**
> This permission lets the app create and publish video posts on the developer's own Facebook Page "VyomAi Cloud". The automated pipeline prepares the video file and uploads it as a Page post. The app only manages the developer-owned Page's content; it does not create posts for, or affect, any other user's Page.
>
> **Required API test call (done):** `POST /1295177777016744/videos` → video `1595237155297003` published.

### 3. pages_show_list
> **Describe how your app uses this permission or feature:**
> The app calls `GET /me/accounts` to list the Pages that the authenticated developer/admin manages, in order to select the correct destination Page ("VyomAi Cloud") for publishing. It returns only the Page IDs and names owned by the app operator. No user data is collected or stored.
>
> **Test call (done):** `GET /me/accounts` returned Page `1295177777016744` ("VyomAi Cloud").

### 4. publish_video
> **Describe how your app uses this permission or feature:**
> The app publishes pre-rendered, fully-compiled educational-technology videos to the developer-owned Facebook Page via the Graph API video upload endpoint. It is a one-way publisher that uploads on behalf of the Page admin only. It does not publish to other users' Pages and does not read user data.
>
> **Required API test call (done):** `POST /1295177777016744/videos` → video `1595237155297003` published.

### 5. pages_read_engagement
> **Describe how your app uses this permission or feature:**
> The app reads read-only engagement metrics (views, likes, comments) on the videos it has published to the developer's own Page, so the operator can measure content performance for the channel. This is read-only on the developer-owned Page only; no private user data is accessed.
>
> **Required API test call (done):** `GET /1295177777016744/posts?fields=id,message,created_time,insights...` returned the test post.

### 6. public_profile
> **Describe how your app uses this permission or feature:**
> Standard identity scope used during login to confirm the app developer/admin's Facebook identity and obtain their numeric user ID. It is used only to authenticate the single operator of the app and is not used to read data about other users.

### 7. instagram_basic
> **Describe how your app uses this permission or feature:**
> The app reads the basic profile of the developer's own Instagram business account (username, account ID) to verify the correct destination account for publishing videos. It is limited to the linked business account owned by the operator; no follower data or content is accessed.
>
> **Required API test call (done):** `GET /me/accounts?fields=instagram_business_account{id,username}` resolved the linked IG account `17841437566807299`.

---

## Dependency pairs (must all be present together)
- `instagram_content_publish` → requires `instagram_basic` ✓
- `pages_manage_posts` → requires `pages_show_list` + `pages_read_engagement` ✓
- `pages_read_engagement` → requires `pages_show_list` ✓

---

## Screencast steps (record ~60–90s, screen only)

Use the **existing live artifacts** so nothing new needs publishing for the demo:

1. Open the dashboard → **Run Pipeline** flow (or pipeline logs) showing the automated publish steps.
2. Show the Graph API log lines: page upload → `1595237155297003`; IG media → `18093030908252227`.
3. Open the Facebook Page (VyomAi Cloud) → show the live "API Test Upload" video post.
4. Open the Instagram business account → show the matching Reel / the account's Reels feed.
5. Close by showing a `publish_urls` doc containing both `facebook` and `instagram` URLs (from a real pipeline run).

That single recording demonstrates all 6 screencast-required permissions (`public_profile` needs none).

---

## Required API test calls — checklist (all already performed, evidence saved)
- [x] `instagram_basic` — `GET /me/accounts` (evidence `api/01_*.json`)
- [x] `pages_read_engagement` — `GET /{page}/posts` (evidence `api/02_*.json`)
- [x] `pages_manage_posts` + `publish_video` — `POST /{page}/videos` (evidence `api/03_*.json`) → video `1595237155297003`
- [x] `instagram_content_publish` — `POST /{ig}/media` (evidence `api/04_*.json`) → `18093030908252227` FINISHED + read-back `api/05_*.json`

---

## Test video location (this Mac)
- **Source file:** `/Users/Ai Mark/timi/agents/output/long-20260903-n3_long.mp4`
  (H.264, 1920×1080, 17 s, 29 MB)
- **R2-hosted copy used as the IG Reel `video_url`:**
  https://c28748eef382795e7a2d2982224b1aa8.r2.cloudflarestorage.com/vyom-ai-videos/meta_appreview/test-verification.mp4
  (presigned, 1-hour window — expires; regenerate via the R2 helper when needed)

---

## After approval
1. Flip the app from **Development → Live**.
2. Tokens remain durable; the code's `fb_exchange_token` auto-refresh keeps them renewed.
3. No code changes needed — the pipeline already uses `FACEBOOK_ACCESS_TOKEN` for both FB and IG.

---

## Reviewer Instructions — complete copy-paste block (public /review demo page, Option A)

**Platform to add in App Settings → Add Platform:** check **Website** → Site URL `https://timi.vyomai.cloud`.

**Where can we find the app?**
```
https://timi.vyomai.cloud/review
```

**Provide instructions for accessing the app / testing:**
```
The app is a web dashboard at https://timi.vyomai.cloud. It is a single-operator tool that generates and publishes educational-technology videos to the developer's own content accounts (a Facebook Page "VyomAi Cloud" and its linked Instagram business account).

A dedicated public demo page is provided for reviewers at https://timi.vyomai.cloud/review — no account signup or dashboard login is required.

How to test (end-to-end):
1. Open https://timi.vyomai.cloud/review in a browser.
2. Step 1 "Connect your account": click "Connect Facebook". The browser opens the Facebook Login consent dialog for the Timi Video app, listing the requested scopes: instagram_content_publish, instagram_basic, pages_manage_posts, pages_read_engagement, pages_show_list, and public_profile. Approve the consent.
3. The page returns to the /review demo page and shows "Connected".
4. Step 2 "Test publishing": click "Publish test post". The app publishes a status to the linked Facebook Page using the app's authorized token and returns the new post ID.

This demonstrates the OAuth/consent flow and the data-usage of the requested publishing permissions without granting access to the operator's internal dashboard or any stored credentials.
```

**Is Facebook Login integrated on this platform?** → **Yes**

**Payment/membership access codes or test credentials:**
```
The app has no payment or membership requirement. Reviewers access the public demo page at https://timi.vyomai.cloud/review directly; no test credentials are required to review the Facebook Login consent flow and the publish function.
```

**Test user credentials:**
```
None required — the app is a single-operator dashboard. Reviewers use the public /review demo page, which triggers the app's Facebook Login consent dialog and demonstrates publishing with the app's authorized Page token. No dashboard login or test account is needed.
```

**App-store gift codes (payment required to download):**
```
Not applicable — this is a web app; there is no app-store download and no payment.
```

**Geo-blocking / geographic restrictions:**
```
Not applicable — the app is not restricted by geographic location, geo-blocking, or geo-fencing. It is accessible world-wide.
```

**In-app subscriptions / purchases codes:**
```
None — the app has no subscriptions, purchases, or paid features.
```

---

## How the reviewer demo works (implementation notes)
- **Public `/review` page** (`dashboard/src/app/review/page.tsx`) — outside the Firebase-gated `/dashboard` route, so reviewers need no dashboard login and see no secrets.
- **Demo OAuth** (`/api/auth/meta?action=connect&demo=1`): the callback performs the token exchange for consent-screen evidence but **skips persistence** (`state` prefixed `demo-`), so the live production `FACEBOOK_ACCESS_TOKEN` in Firestore `env_vars` is never overwritten by a reviewer.
- **Publish test** (`/api/review/publish` POST): reads the stored production Page token server-side, posts a status to Page "VyomAi Cloud", returns the post ID — token never reaches the browser.

## Auth hardening shipped alongside (protects the operator dashboard)
- Added server-side `verifyAuth` (Firebase ID token via `Bearer`) to previously-open sensitive routes: `api/env-vars` (GET), `api/env-vars/[key]` (PUT), `api/settings` (PUT), `api/platform-settings/[id]` (PUT), `api/pipeline/reset` (POST), `api/pipeline-triggers` (POST).
- Updated the matching client callers to send the `Authorization: Bearer <idToken>` header.
- OAuth callbacks and public endpoints (`auth/*/callback`, `webhook`, `health`, `/review`, `/api/review/publish`) intentionally remain unauthenticated by design.
