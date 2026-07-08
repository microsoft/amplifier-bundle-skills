---
name: msgraph-integration-patterns
description: >
  Hard-won patterns for probing, building, troubleshooting, and iterating against
  Microsoft Graph API endpoints -- especially from a browser SPA using delegated
  MSAL.js auth calling Graph directly with no backend (lessons generalize to any
  Graph integration). Covers the throwaway-probe-file methodology for de-risking
  before building, OData/query quirks, permission and admin-consent sequencing,
  recordings/transcripts access patterns (SharePoint REST, not Graph), CSP
  requirements for a pure-browser SPA, retry/pagination/backoff patterns, and the
  MSAL/EasyAuth auth-redirect-loop debugging saga. Use when integrating with
  Microsoft Graph, Teams APIs, MSAL.js, or EasyAuth; when hitting an unexpected
  Graph error (400/403/429), a silent missing-scope failure, an auth redirect
  loop, or a CSP violation that only appears in production; or when deciding how
  to validate a new Graph capability before committing it to a codebase.
model_role: coding
allowed-tools: [read_file, write_file, edit_file, bash, web_fetch]
---

# Microsoft Graph Integration Patterns

Hard-won lessons from building a Teams-data SPA (chats, channel threads,
recordings/transcripts) against Microsoft Graph with delegated MSAL.js auth.
Real evidence throughout -- not generic API advice.

## 0. The one practice that pays for everything else: probe before you build

Before writing any TypeScript/app code against a new Graph capability, write a
**throwaway, standalone HTML file** with zero build tooling:

```html
<script type="module">
  import { PublicClientApplication } from "https://esm.sh/@azure/msal-browser";
  // hardcode the real client id -- client ids are not secrets
  const pca = new PublicClientApplication({ auth: { clientId: "...", authority: "..." } });
  // real interactive login, then a raw fetch() to the EXACT endpoint/query
  // render BOTH a summary AND the raw JSON of the first result --
  // the raw JSON is "proof of shape," including undocumented-feeling fields
  // like a replies[] array under $expand
</script>
```

This decouples two different risks: "does this scope/endpoint even return what
I expect" (cheap, interactive, real credentials, zero build step) from "is my
app's abstraction correct." A wrong assumption about Graph's actual behavior
gets caught in seconds instead of after a full feature is built on it. **Delete
the probe once you have the answer** -- never commit or ship it.

Treat admin-consent lead time as a hard roadmap gate: confirm consent is
available for a scope *before* starting the feature that needs it, not as a
mid-feature surprise. Run genuine investigation spikes (not ad hoc debugging)
for open questions, and record the negative result permanently (a commit
message, a design-doc line) so nobody re-tries a dead end later without
knowing why it failed.

## 1. OData / query quirks

- `$top` can be **rejected on specific sub-endpoints** even when it works on
  the parent -- e.g. allowed on `/me/chats` and `/{chat}/messages`, but
  `/me/chats/{id}/members` throws `Query option 'Top' is not allowed`. Don't
  assume a query option that works on one endpoint works on its neighbors.
- `$expand=replies` is the only way to get thread replies inline on channel
  messages: `/teams/{teamId}/channels/{channelId}/messages?$top=50&$expand=replies`.
  There's no server-side "last activity" sort for threads -- compute
  `max(root.createdDateTime, all replies.createdDateTime)` client-side.
- **No `$filter` on chat-message dates.** Page newest-first, stop once you hit
  your `since` boundary or run out of messages, filter client-side. This
  pattern recurs everywhere Graph lacks a date filter (recordings windowing,
  etc.) -- assume no server-side date filter until proven otherwise.
- `@odata.nextLink` is an **absolute URL** -- pass it straight to `fetch()`,
  don't re-prefix it with your base URL.
- `$count` support is **not universal** across endpoints (e.g. transcript
  endpoints don't support it) -- declare per-source capabilities and adapt
  UI/warnings rather than assuming uniform support.
- Resource IDs aren't always interchangeable even when they look similar --
  e.g. Teams chat IDs are MRIs starting with `19:`; passing an Exchange/Outlook
  item ID (`AAMk...`) to a chat endpoint returns `400 "Invalid MRI, should
  start with digits and colon"`. Validate ID shape client-side before firing
  the request.

## 2. Permissions & consent

- **Split app registrations by trust boundary.** One app for auth-gate/login
  scopes only (`openid`, `profile`, `email`); a separate app for the actual
  Graph content scopes. A leaked login credential then can't pivot to content
  access.
- **Grow scopes incrementally, tied to feature order**, and be willing to
  *drop* scopes a prior approach needed once you replace that approach (e.g.
  dropping calendar/online-meetings scopes entirely once a chat-based
  discovery method replaced the calendar-based one -- see §3).
- **Transcript access needs a *different* API resource's permission** --
  `Sites.Read.All` under "Office 365 SharePoint Online" is not the same grant
  as Microsoft Graph's own `Sites.Read.All`, and backs a *different* bearer
  token (`https://{spHost}/.default`).
- **Fingerprint consent errors and degrade gracefully, don't retry-loop.**
  Match `/AADSTS65001|invalid_grant|InteractionRequiredAuthError/i` against the
  error; on match for an optional feature, set a session-scoped flag that
  suppresses further attempts for the rest of the page session (self-heals on
  reload once the scope is granted) instead of spamming retries or the
  console.
- **Nested-group and mail-enabled-group gotchas** (general Entra knowledge):
  `AADSTS50105` fires when a role assignment flows through a *nested*
  subgroup (must be a direct member for app-role assignment); a
  mail-enabled security group silently fails to emit the `roles` claim even
  though the portal shows the assignment as successful (recreate as a pure
  security group); the `groups` claim is replaced by
  `_claim_names`/`_claim_sources` once a user is in 200+ groups (resolving
  needs an OBO call with a client secret -- generally blocked for pure SPAs,
  so prefer app roles over group claims when overage is possible).

## 3. Recordings / transcripts -- the hardest-won findings

- **`/me/onlineMeetings` transcript/recording endpoints are a confirmed dead
  end for "recordings I can access" -- they only work for meetings the
  signed-in user organized.** `getAllTranscripts()`/`getAllRecordings()`
  enforce `userId == organizerId`; the `meetingOrganizerUserId=null` "get all"
  syntax doesn't work at v1.0 or beta (both 400); passing your own oid returns
  412 "not supported in delegated context." `/search/query` for
  `filetype:mp4` returns 0 results under delegated auth.
- **The working alternative: walk `/me/chats` messages and read
  `eventDetail[\"@odata.type\"] === \"#microsoft.graph.callRecordingEventMessageDetail\"`
  directly out of the message payload.** This surfaces recordings regardless
  of who organized the meeting, including recordings in another user's
  OneDrive. Cross-join participants from sibling `callEndedEventMessageDetail`
  events by shared `callId`, falling back to plain chat membership when no
  `callEnded` event exists (ad-hoc 1:1 calls never emit one).
- **The real access boundary is SharePoint ACL on the recording file, not
  meeting organizer.** The "organizer-only" gate is an artifact of the
  `/me/onlineMeetings` API specifically -- not a real data limit. This
  reframing is the core insight: chat-membership access ≠ organizer access,
  and Graph's *official* transcript API enforces the wrong boundary.
- **Transcript retrieval is SharePoint REST v2.1, not Graph:**
  1. `GET /shares/{shareId}/driveItem` (Graph, `Files.Read.All`) to resolve
     `driveId`/`itemId` from a sharing URL. `shareId = "u!" + base64url(url)`,
     strip `=` padding.
  2. `GET https://{spHost}/_api/v2.1/drives/{driveId}/items/{itemId}?select=name,media/transcripts&$expand=media/transcripts`
     -- **Graph does not expose `media/transcripts`**; this is a separate
     SharePoint-resource bearer token (`https://{spHost}/.default`), not the
     Graph token.
  3. Rewrite `temporaryDownloadUrl` to `/streamContent?is=1&applymediaedits=false`
     to get raw VTT.
  4. Try with the bearer token first, fall back to unauthenticated fetch on
     401 (a hosted SPA needs the SP token; a browser extension could ride
     cookies but a hosted app can't).
- **Cross-tenant recordings are a typed non-error.** `/shares/{id}/driveItem`
  returns `400 "Invalid hostname for this tenancy"` when the file lives in
  another org's SharePoint -- give this its own error type so callers can
  count/label it, not treat it as a bug.
- **Shallow pagination silently drops data.** A naive top-50 scan dropped 11
  of 38 recordings in a 30-day window. Deep-scan each in-window container
  until you pass the window edge or hit a page cap; if the cap fires first,
  flag the result `truncated: true` and say so loudly in the UI -- never
  silently incomplete.
- **Validate defensive assumptions empirically before keeping them.** A
  padded date-window buffer (in case a container's "last updated" timestamp
  was stale) was later disproven with a full-scan oracle across hundreds of
  containers -- the timestamp was always current, the buffer was pure
  overhead. Removing it cut the scan size substantially.
- **Different environments/tenant rings can use different SharePoint
  hostname patterns.** If your app runs across multiple tenants or
  environments (production, staging, internal test rings), verify the
  actual SharePoint hostname per environment rather than assuming one
  wildcard covers all -- each distinct host pattern needs its own
  CSP/allowlist entry.

## 4. CSP for a pure-browser SPA calling Graph directly

Built up incrementally -- **every addition was driven by a production-only
failure the local dev server never surfaced**, since CSP is browser-enforced,
not dev-server-enforced:

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
connect-src 'self' https://login.microsoftonline.com https://graph.microsoft.com
  https://*.sharepoint.com;
frame-src 'self' https://login.microsoftonline.com https://identity.{n}.azurestaticapps.net;
img-src 'self' data:; font-src 'self'; object-src 'none'; base-uri 'self';
frame-ancestors 'none'; form-action 'self'
```

- `style-src 'unsafe-inline'` -- dynamic inline styles, invisible until prod.
- `connect-src *.sharepoint.com` -- OneDrive AppFolder sync + transcript
  downloads share one wildcard (add further host patterns per environment,
  see §3's last point).
- `frame-src` entries were added to support an `ssoSilent` hidden-iframe
  approach that was **later ripped out entirely** (§6) -- left in place as
  harmless once no longer load-bearing. **Lesson: a CSP entry added for one
  strategy can outlive that strategy** -- don't assume every entry still has
  a live purpose; don't be surprised when removing a CSP entry breaks nothing.

## 5. Rate limiting / retry / pagination

- **Retry only `429, 502, 503, 504`.** Everything else (400/401/403/404…)
  throws immediately with the (truncated) response body in the error -- never
  blind-retry a client error.
- **429:** honor `Retry-After` (seconds), clamp to a sane max (~60s) against a
  misbehaving value.
- **502/503/504:** exponential backoff + jitter when no `Retry-After` (e.g.
  ~1s doubling, capped ~30s, random jitter to avoid thundering-herd retries).
- **Cap at ~5 attempts**, then throw loud with status + attempt count +
  truncated body.
- **Refresh the token on every retry**, not just once -- a long paginated
  scan across hundreds of items shouldn't die to a token that expired
  mid-scan.
- **Bounded concurrency pool (e.g. 4 workers) for bulk enumeration**, not
  unbounded `Promise.all` over hundreds of items -- bounds throttling risk.
- Start with **observability-only** for rate limiting (log/capture 429s and
  scope failures as a signal) rather than building custom retry dashboards
  before you know if you even need them.

## 6. MSAL.js / EasyAuth -- the auth-loop debugging saga

This was the single most-iterated area. Presented as a sequence because the
sequence *is* the lesson: **four plausible-looking root causes in a row were
wrong**, and each "fix" that didn't work still taught something.

1. **Wrong-ish:** assumed CSP `frame-src` was too strict for MSAL's hidden
   `ssoSilent` iframe returning to the app's own origin. Added `'self'` to
   `frame-src`. Loop persisted.
2. **Still incomplete:** the iframe also needed the platform's own identity
   host in `frame-src` to ride an existing session cookie. Added it. Loop
   persisted.
3. **The CSP fixes were a red herring.** Real cause: modern browsers block
   third-party session cookies in same-frame contexts, *and* the identity
   provider refuses to render its login page in an iframe at all
   (`X-Frame-Options: deny`) -- unfixable from the app side. **Fix:** remove
   the iframe-based silent-SSO bridge entirely, fall through to a full
   top-level redirect login (no iframe, so `X-Frame-Options` doesn't apply).
   Accepted UX cost: one click instead of a broken zero-click bridge.
4. **Loop persisted even without the iframe.** Actual root cause: the
   platform's own catch-all "require auth on every route" rule intercepted
   MSAL's own redirect-return navigation (which carries the auth code in a
   URL fragment) and stripped the fragment before MSAL could read it -- so
   MSAL never established a session. **Fix:** add an anonymous callback route
   (e.g. `/auth-callback`) *above* the catch-all auth rule; point
   `redirectUri` at it; only navigate into the app after
   `handleRedirectPromise()` resolves an account. Confirmed by checking the
   console showed **zero CSP violations** during the failure -- proof it was
   never a CSP problem, which is what fixes 1-2 had assumed.
5. **Write the decision + dead-ends down permanently** once solved, so a
   future session with a similar symptom doesn't re-litigate the same wrong
   hypothesis (CSP) again.
6. A related but distinct bug: an un-awaited "try silent login" call at
   module top-level blocked first paint for the iframe's multi-second
   timeout -- a white-screen bug, not a loop. Fix: make it non-blocking with
   a visible "Signing in..." placeholder.

**Net architecture:** no iframe-based silent SSO. On load: init →
`handleRedirectPromise()` → if on the callback route with an account now
set, client-side redirect to `/` → else reuse a cached account if present
→ else show a sign-in button that does a full top-level redirect login.
**Per-Graph-call fallback is separate:** try silent token acquisition first;
on failure, redirect interactively for that scope set and let the navigation
handle it -- don't try to recover in place.

**Deployed-vs-local config drift is its own bug class:** when two different
env vars can each answer "which app is this" (e.g. one injected by your
deploy platform, one injected by your build tool), get the **precedence
order** right and know which one actually carries your full scope set --
getting it backwards silently breaks a *specific* feature only in the
deployed build, invisible in local dev where only one var is set. Test the
newest feature specifically against the deployed build, not just locally.

## 7. Other gotchas

- **Sibling resource types (chats vs. channels) can have materially
  different Graph surfaces and scope requirements** even though they feel
  like the same product area to a user -- investigate each independently,
  don't assume parity.
- **Client-side date-range windowing is the default assumption**, not the
  exception -- "page newest-first, stop once a whole page is provably older
  than your window" beats hoping for a `$filter` that doesn't exist.
- **A 403 on one item in a bulk enumeration should be a typed, silent
  "no access" for that item** -- pattern-match 403/forbidden/access-denied
  and convert to a skip or a labeled UI state, so one inaccessible item
  doesn't abort enumeration of everything else.
- **Synthesize your own composite/stable ID** when Graph doesn't provide one
  spanning a hierarchy (e.g. `teamId::channelId`, or `callId::filename` when
  one call can produce multiple recording files).
- **Re-evaluate narrow "selected files" scopes against broad ones once admin
  consent removes the security argument for going narrow** -- the narrower
  scope's interactive picker can add UX friction with no remaining benefit.
- **Graph itself won't merge concurrent writes to shared state.** Use
  conditional writes (ETags/`If-Match`) on any shared blob you sync through
  Graph-backed storage, and handle `412 Precondition Failed` with a
  re-read-and-merge (set-union for additive fields, last-write-wins per key
  for scalars).
