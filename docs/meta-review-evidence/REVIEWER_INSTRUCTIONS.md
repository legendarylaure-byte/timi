# Reviewer Instructions — Copy-Paste Field Reference (Timi Video)

Fill these into the App Review → Reviewer Instructions / Platform Settings (Website) form.
Uses the **public /review demo page** path (Option A): the reviewer exercises the
Facebook Login consent flow + a publish test from a restricted public page, with **no
dashboard login and no exposure of secrets**.

---

## Platform
App Settings → Add Platform → **Website** → Site URL: `https://timi.vyomai.cloud`

---

## Field 1 — Where can we find the app?
```
https://timi.vyomai.cloud/review
```

## Field 2 — Provide instructions for accessing the app / testing
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

## Field 3 — Is Facebook Login integrated on this platform?
**Yes**

## Field 4 — Payment/membership access codes or test credentials
```
The app has no payment or membership requirement. Reviewers access the public demo page at https://timi.vyomai.cloud/review directly; no test credentials are required to review the Facebook Login consent flow and the publish function.
```

## Field 5 — Test user credentials
```
None required — the app is a single-operator dashboard. Reviewers use the public /review demo page, which triggers the app's Facebook Login consent dialog and demonstrates publishing with the app's authorized Page token. No dashboard login or test account is needed.
```

## Field 6 — App-store gift codes
```
Not applicable — this is a web app; there is no app-store download and no payment.
```

## Field 7 — Geo-blocking / geographic restrictions
```
Not applicable — the app is not restricted by geographic location, geo-blocking, or geo-fencing. It is accessible world-wide.
```

## Field 8 — In-app subscriptions / purchases codes
```
None — the app has no subscriptions, purchases, or paid features.
```

---

## Notes for the operator
- The `/review` page is intentionally **public** (outside the Firebase-gated `/dashboard` route) and is the only surface reviewers touch.
- The demo OAuth round-trip (`/api/auth/meta?action=connect&demo=1`) performs the token exchange for the consent-screen evidence but **does not persist** the resulting token, so the live pipeline's production `FACEBOOK_ACCESS_TOKEN` is never overwritten by a reviewer.
- The "Publish test post" button calls `/api/review/publish`, which uses the stored production Page token server-side and never returns the token to the browser. It posts a status to Page "VyomAi Cloud" demonstrating `pages_manage_posts` / `publish_video`.
- For the review to fully validate the flow, the app should be in **Live mode** so the Facebook Login consent presents outside Development mode. **Business verification (~48h) is the upstream gate.**
