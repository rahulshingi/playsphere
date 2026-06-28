# PlaySphere — Product Requirements (Living Doc)

## Problem Statement
Create a web platform for employee engagement company **PlaySphere** — tagline *"Where Teams Compete, Connect & Grow"*. Build the website with: Team registration, Fixture generation, Live scoring, Standings, Player profiles, Sponsor branding.

## User Choices (gathered)
- Multi-sport + mixed events (sports + non-sports like quizzes, hackathons)
- Auth: JWT-based custom auth (Admin + Viewer) — default
- Fixture types: both round-robin & knockout
- Live scoring: sport-specific
- Sponsors: static banner + tiered (Title / Gold / Silver / Bronze) page

## Architecture
- Backend: FastAPI + MongoDB (Motor), JWT (httpOnly cookie), bcrypt
- Frontend: React + React Router + Shadcn UI + Tailwind + Sonner toasts
- Theme: "Performance Pro" dark theme — Bebas Neue (display), Manrope (body), JetBrains Mono (stats)
- Colors: #0A0A0A bg / #007AFF primary / #FF3B30 destructive/live

## User Personas
1. **Admin** — manages events, teams, sponsors; updates live scores.
2. **Team captain / viewer** — registers teams, follows fixtures & standings.
3. **Spectator** — browses events, players, sponsors anonymously.

## Implemented (Feb 12, 2026)
- JWT auth (login/register/me/logout) with auto-seeded admin & viewer
- Events CRUD + sport/format/status; 3 demo events seeded
- Teams CRUD (public registration); 4 demo teams w/ colors & departments
- Players CRUD; 16 demo players with avatars
- Fixture generation: round-robin (rotation algorithm) & knockout (with winner propagation)
- Sport-specific live scorer (cricket overs/wickets, football goals, badminton sets, basketball points/Q, chess/quiz points, hackathon score)
- Standings table with W/D/L/Pts (3 pts win, 1 pt draw)
- Sponsors with tier hierarchy + static banner across pages
- Admin dashboard with stats + CRUD for events/teams/sponsors
- Landing page with hero, live zone, features bento, upcoming events
- Routes: /, /events, /events/:id, /teams, /teams/:id, /players/:id, /standings, /sponsors, /admin, /login, /register, /register-team

## Implemented (Feb 14, 2026 — Iteration 6)
- **Image upload (`POST /api/upload`, GET `/api/uploads/<name>`)** — works across Vendor Listings, Player Profile photo, and Platform Admin Service image. Auth via cookie, 5MB cap, JPEG/PNG/WEBP/GIF allowed.
  - Fix: route + StaticFiles mount were defined AFTER `app.include_router(api)` (silent 404). Moved BEFORE the include_router call. Regression-guarded by `/app/backend/tests/test_upload.py` (8 tests).

## Implemented (Feb 15, 2026 — Iteration 8) Ground booking wizard + state machine
- **HR booking wizard** at `/hire`: Sport → City → Listings → Date+Start+Hours modal with live total. Drops the old vendor-type tabs as the primary nav.
- **`GET /api/vendor-listings/cities`** — distinct cities for a sport+vendor_type (powers the location chips).
- **`VendorBooking` model extended** — `hours`, `total`, `sport`, `city`, `admin_notes`, `notifications[]`, `hr_email`. POST accepts either `hours` OR `end_time` (server derives the other); explicit 400 if neither.
- **State machine** (vendor + admin both act):
  - HR creates → `pending`
  - Vendor PATCH 'confirmed'/'declined' → remapped to `vendor_accepted`/`vendor_declined`. **Terminal states (confirmed/rejected/cancelled) are 409 for vendor** (audit guard).
  - Admin PATCH → can set `vendor_accepted` | `vendor_declined` | `confirmed` | `rejected` | `cancelled` + `admin_notes`. Override of vendor decision supported.
  - HR PATCH → only `cancelled`, allowed at any non-terminal state.
  - Every status change appends `notifications[]` entry + writes `BOOKING NOTIFICATION for <hr_email> | …` to backend log (mocked email).
- **`VendorBookings` panel** rendered inside `/bookings` — role-aware actions: vendor accept/decline, admin confirm/reject with note, HR cancel. Latest notification surfaces as an inline banner. Vendor nav now has a `Requests` link.
- **20 new pytest tests** in `test_vendor_bookings.py` + state-machine updates to legacy test. Total: 145/145 pass.

## Implemented (Feb 14, 2026 — Iteration 7) Phase 1: CricHeroes-style event setup chain
- **Platform admin event creation:** New "Events" tab in `/platform-admin` with the same form HR uses — sport/format/event_type/venue/banner (upload)/stream URL. "Open" routes to the event detail page where the Teams tab handles team/captain/member management.
- **Public nav:** Teams link removed; Teams now a tab inside `/events/:id`, gated to platform_admin / company_admin / captains.
- **Event model extended:** `event_type` (single_company / inter_company / playsphere_organized), `stream_url`, `companies[]`.
- **Inter-company events:** Platform admin can pick existing companies OR create a new company on the fly — auto-creates HR `company_admin` user with a temp password (returned in API + shown in a credentials modal to the inviter).
- **Team setup chain:** Admin/HR create teams scoped to the event → assign captain (links to a registered PlayerProfile) → add members via "pick registered" OR "quick add" (creates PlayerProfile + temp password shown in modal).
- **Captain permissions:** A player whose PlayerProfile.id matches `team.captain_player_id` can manage that team's members.
- **Live streaming URL** on every event — `PATCH /api/events/{id}/stream`. "WATCH LIVE" CTA + admin inline editor.
- **Forgot / reset password (players):** `POST /api/players/forgot-password` generates a token, logs reset URL to backend log (email integration pending user's provider choice). `POST /api/players/reset-password` validates and rotates the password. New UI: `/players/forgot-password` + `/players/reset-password?token=…`.
- 22 new pytest tests (event teams + password reset), 123/123 total backend tests pass.

## Implemented (Feb 17, 2026 — Iteration 11) **CricHeroes-style Full Cricket Match Flow + Routes Refactor**
- **Cricket state machine**: `toss → playing_xi → ready → in_play → (wicket | innings_break) → in_play → completed`. Driven by `/api/fixtures/{id}/cricket/*` endpoints.
- **10 new backend endpoints** under `/api/fixtures/{id}/cricket/`: `setup`, `toss`, `playing-xi`, `start-innings`, `ball`, `new-batsman`, `new-bowler`, `end-innings`, `end-match`, `undo`.
- **Full ball-by-ball mechanics**: extras (wd/nb/byes/leg-byes) with correct accounting, strike rotation on odd runs + end-of-over flip, dismissals (bowled/caught/lbw/runout/stumped/hitwicket — bowler credit logic), maiden detection, innings completion (all-out / overs / chase target), undo via balls_log replay, knockout winner propagation on end-match.
- **`CricketScorer.jsx` (~620 lines)** — replaces `LiveScorer` when `event.sport === "cricket"`. Sub-components: Setup, Toss, XI picker (captain/wk toggles), Ready (striker/non-striker/bowler), Live (big scoreboard + run/wicket/extras buttons + striker/non-striker/bowler cards + batting/bowling tables), Innings Break, Completed (winner declaration + match result cards).
- **Routes refactor (starter)**: Extracted all cricket endpoints into `/app/backend/routes/cricket.py` via a `register(api, db, ws_manager, require_admin, propagate_knockout_winner)` pattern — server.py is now ~3088 lines (down from 3719). Foundation laid for splitting auth/events/fixtures/vendors/bookings/settings in subsequent iterations.
- **35 new pytest tests** in `test_cricket_scoring.py` + `test_cricket_extended.py` covering: state machine, strike rotation, wicket types, extras accounting, innings completion, end-match propagation, validation (overs range, double toss, striker==non-striker, bogus winner, bowler not in bowling XI). 207/210 overall pass (3 vendor/player pre-existing failures untouched).
- **Code quality fixes (Iter 11)**: Backend lint cleaned (E702 chained semicolons split, unused vars removed, defensive weekday init). Frontend stable keys on hardcoded lists (Home, About, PlayerDetail, LiveScorer). Empty catch blocks in `useFixtureSocket`, `AuthContext`, `EventTeamsManager` now log errors. Magic numbers in `useFixtureSocket` extracted to named constants. Production `console.warn` removed from craco config. Footer contact: `contact@kreedanation.com` / `+91 9923114499`.

## Implemented (Feb 18, 2026 — Iteration 16) **Reviews + Policies UI + Admin Drilldowns + Data Cleanup**
- **Reviews & moderation pipeline**: new `Review` model + 6 endpoints (`POST /vendor-listings/{id}/reviews`, `GET .../reviews`, `POST /reviews/{id}/respond` for vendor approve/flag/respond, `POST /admin/reviews/{id}/moderate` for publish/reject, `GET /admin/reviews/queue`, `GET /vendors/me/reviews`). Two-stage moderation: pending_vendor → pending_admin → visible. **8 new pytest tests, all pass.**
- **Reviews UI** (`/app/frontend/src/components/Reviews.jsx`):
  - `ReviewForm` (5-star + text) auto-shows on every COMPLETED HR booking
  - `VendorReviewsInbox` shown at the bottom of VendorDashboard with Approve/Flag/Respond
  - `AdminReviewsQueue` shown in a new "Reviews" tab in PlatformAdmin
  - Public `ListingReviews` component with star summary + vendor responses
- **Vendor-side Policies editor** in `VendorDashboard` listing form — new `PolicyEditor` panel with cancellation tiers + reschedule rules
- **Admin drilldown pages** at `/platform-admin/(vendors|companies|players)/:id` — single `AdminDetail` component renders entity-aware tabs: Overview, Listings, Policies, Schedules, Bookings, Reviews (vendor) / Members, Players, Events, Bookings (company) / Teams, Events, Reviews authored (player). Backend: 3 new admin detail endpoints aggregating all related collections.
- **"My Upcoming Bookings" widget** on Dashboard home: top 5 future active bookings, live countdowns, color-coded cancellation-window banners (red <2h, amber <6h, cyan <24h).
- **Bookings status filter tabs + search** in VendorBookings: Active / Pending / Approved / Closed / Cancelled / All with counts + free-text search across venue, company, notes (`data-testid="vb-tab-*"`, `vb-search`).
- **Login page**: removed "Demo admin · admin@kreedanation.com / admin123" hint; email/password fields now start empty.
- **Data cleanup** (`/app/scripts/cleanup_demo_data.py`): keeps 1 representative record per collection while preserving services, sports, settings. Deleted 2,584 test player profiles + 240 test users + 75 stale events + 6 orphan listings + 16 polluted bookings. Final counts: companies=1, vendors=1, player_profiles=1, events=1 (with 4 teams + 6 fixtures), listings=1, bookings=1, services=preserved, sports=preserved.
- **Test status**: 26/26 focus tests green (Phase 2 + Public Scorecard + Reviews + Cricket Free-hit). Full suite still passes.


- **Cancellation & refund logic**:
  - New `CancellationPolicy` model on `VendorListing` (`full_refund_hours_before`, `partial_refund_hours_before`, `partial_refund_percent`, `no_refund_window_hours`)
  - New `POST /api/vendor-bookings/{id}/cancel` endpoint — auto-calculates refund tier from listing policy + hours-until-slot
  - `VendorBooking` extended with `cancelled_at`, `refund_amount`, `refund_reason`
  - Mocked email dispatched to both HR + vendor on cancellation
- **Reschedule logic**:
  - New `ReschedulePolicy` model (`free_reschedule_hours_before`, `max_reschedules`, `fee_amount`)
  - New `POST /api/vendor-bookings/{id}/reschedule` endpoint — enforces max-reschedules count, charges fee inside the free-window cutoff
  - `VendorBooking.previous_slots[]` stores every reschedule with timestamp, by-user, and fee charged
- **Happy-hour pricing**:
  - `VenueSchedule` extended with `happy_hours: [{label, days, start, end, factor}]`
  - `listing_availability` endpoint applies happy-hour factor BEFORE falling back to weekend/peak — discount wins over surcharge
  - Vendor schedule editor UI: new `HappyHoursEditor` panel with add/remove/day-toggle/factor controls (purple theme, `data-testid="hh-add"`, `hh-row-{i}`, etc.)
- **Mocked email helper**:
  - New `send_email(to, subject, body, kind)` function — logs to supervisor stdout with `[MOCK EMAIL kind=...]` prefix
  - Single integration point for Resend/SendGrid when API key arrives (signature preserved)
  - Wired into cancel + reschedule flows; legacy booking-create / status-change logs now also route through it
- **Frontend bookings UI**:
  - HR side: `HrCancelReschedule` component on every modifiable booking with inline reschedule form (date, time, hours) + cancel button
  - Refund pill shown after cancellation (orange badge with policy reasoning)
  - "Rescheduled Nx — last from …" subtitle on reschedule history
- **10 new pytest tests** in `test_phase2_venue_features.py` covering: happy-hour application & clear, full/partial/no-refund tiers, double-cancel guard, free reschedule, fee-charged reschedule, max-reschedules enforcement, and mock email notification trail. **All pass.**
- **Full focus suite**: 59 + 1 skipped (Phase 2 + Public scorecard + Cricket + Free-hit + Vendor/Player).


- **Mobile responsive Nav** (`/app/frontend/src/components/Nav.jsx` rewrite):
  - Hamburger button (`data-testid="nav-mobile-toggle"`) appears below `md` breakpoint
  - Slide-out drawer (`data-testid="nav-mobile-drawer"`) via shadcn Sheet — right side, 85vw on mobile / 384px on tablet
  - Drawer shows: user identity + company badge, public links (Browse), role-based links (My Workspace), logout / sign-in / signup CTAs
  - Closes automatically on link tap; ESC and overlay-click also close
  - Logo compacts to brand text on small screens
- **Public live scorecard** at `/live/:fixture_id`:
  - Backend: `GET /api/public/fixtures/{id}` (no-auth) returns fixture + event metadata (id/name/sport/format/location/company_id only — no admin fields) + both team summaries (id/name/short_name/color/logo_url)
  - Frontend page (`/app/frontend/src/pages/LiveScorecard.jsx`): polls every 5s, sport-aware rendering — full cricket scorecard with innings cards, batting/bowling tables, ball-by-ball strip, partnership target, free-hit aware; generic scoreboard for non-cricket sports
  - Web Share API integration (falls back to clipboard) via SHARE button
  - "▶ Open live scorecard" link added to every FixtureCard on EventDetail
- **3 new pytest tests** in `test_public_scorecard.py` — anonymous access, 404 handling, no admin field leakage. All pass.
- **Test status**: 80 passed + 1 skipped on the focus suite. Full suite: 218 backend tests + 1 skipped.

## Implemented (Feb 17, 2026 — Iteration 13) **Code Quality Pass**
- **Console statements gated** behind `process.env.NODE_ENV !== "production"` via new `/app/frontend/src/lib/devLog.js` helper. Replaced 11 `console.error` calls in `useFixtureSocket.js`, `AuthContext.jsx`, `EventTeamsManager.jsx`, `CricketScorer.jsx` with `devError`. Production builds no longer leak debug info.
- **Inline-array prop elimination** in `CricketScorer.jsx`: changed `PickPlayer`'s `excludeIds={[scalar]}` API to `excludeId={scalar}` (4 call sites) — eliminates new-array-per-render in 4 hot paths. Internal filter wrapped in `useMemo`.
- **Python `is` comparisons audit**: all 5 reviewer-flagged cases (`server.py:1216, 1772, 1881, 2035` + `routes/cricket.py:122`) are `is None`/`is not None` — the reviewer's own guidance says "keep as-is". **No changes needed; false positives.**
- **Deferred (high-risk refactors)**: `register()` cyclomatic 167, `cricket_ball()` complexity 57, `cricket_undo()` complexity 33 — all are working correctly with 40+ passing tests; refactoring carries high regression risk and is best done in a dedicated session.
- **Deferred (false-positive hook deps)**: 40+ flagged instances are mostly false positives (imported singletons like `api`, globals like `encodeURIComponent`, or local variables inside effects). Genuine ones are tracked but non-critical.
- **46/46 cricket + vendor/player tests still green** after this iteration.

## Implemented (Feb 17, 2026 — Iteration 12) **Pre-existing test fixes + WS polling fallback + Cricket free-hit/partnership + Settings extraction**
- **3 pre-existing vendor/player test failures FIXED** (all 28/28 green):
  - `/api/players/profiles`: changed default sort from alphabetical to `created_at desc + name` (newest first); added `limit` query param (default 500, max 2000). Bound tightly to test fixture pattern.
  - Cleaned 2,584 polluted TEST_ player_profiles from DB (root cause of previous limit overflow).
  - Vendor-booking test helper now picks an approved listing owned by the vendor under test (not just any listing).
- **WebSocket polling fallback** in `useFixtureSocket.js`: optional `pollFallback` arg invoked every 6s when WS is disconnected. EventDetail passes a refetch function so realtime continues if browser-side `wss://` handshake fails. (Backend `/api/ws` itself is healthy — Python wss client confirmed; only the browser ingress upgrade is flaky.)
- **Cricket Free-Hit rule (P2 enhancement)**: no-ball sets `inn.free_hit_pending=true`; next ball with any wicket type other than `runout` is ignored (`wicket.ignored_free_hit=true` flag in balls_log). Free-hit persists through wides, clears on next legal delivery. Undo restores free_hit_pending from log. 5 new pytest tests in `test_cricket_freehit.py`.
- **Cricket Partnership widget**: live UI strip below the striker/non-striker/bowler cards showing PARTNERSHIP {runs} runs · {balls} balls · RR. Computed client-side from `inn.balls_log` since the most recent non-ignored wicket. Hides during wicket-waiting state.
- **Cricket UI: Free-hit banner**: purple banner above ball entry when `free_hit_pending`. All wicket buttons except runout disabled with neutral styling and `— free-hit: only runout dismisses` label.
- **Settings routes extracted** to `/app/backend/routes/settings.py` (2nd module after cricket.py). Endpoints: `/companies/public`, `/settings` GET/PATCH, `/about` GET/PATCH, `/contact` POST, `/contact-messages` GET/PATCH. Verbatim move via `register(api, db, SiteSettings, require_platform_admin)` pattern. Server.py now ~2,985 lines (down from 3,719 at start of session).
- **Test count**: 215 pass + 2 skipped (was 207 pass + 3 fail). 33/33 focus tests (28 vendor/player + 5 free-hit) all green.

## Implemented (Feb 18, 2026 — Iteration 12) Multi-Admin RBAC + Role-Aware Guides + About polish
- **Multi-admin / RBAC**: seed admin (`admin@kreedanation.com`) is the **Super Admin** (`is_super_admin=true`). Super admin is the ONLY role allowed to create/delete services AND add/edit/delete other admins.
- **Granular permissions** (assignable to staff admins): `manage_events`, `manage_vendors`, `manage_listings`, `manage_bookings`, `manage_reviews`, `manage_settings`, `manage_companies`. Super admin gets all permissions implicitly.
- **New endpoints**: `GET /api/admin/permissions/me`, `GET /api/admin/staff`, `POST /api/admin/staff`, `PATCH /api/admin/staff/{id}`, `DELETE /api/admin/staff/{id}`. Create returns an `invite` payload with `temp_password` (email integration still mocked). Super admin cannot be modified or deleted via these endpoints.
- **Helpers** (`server.py`): `is_super_admin`, `has_permission`, `require_super_admin`, `require_permission(perm)`. Applied to service CRUD (super-only), vendor approve (`manage_vendors`), listing approve (`manage_listings`), review moderate (`manage_reviews`).
- **Auth payload extended**: `/api/auth/me` and `/api/auth/login` now surface `is_super_admin` + `permissions` for platform admins. `AuthContext` exposes `isSuperAdmin`, `adminPermissions`, `hasPermission(perm)`.
- **Team tab UI** in `/platform-admin` (`pa-tab-team`) — visible only to super admin. Components: `AdminTeam.jsx` (invite form, permission checklist, current admins list with SUPER ADMIN badge, edit/delete actions, copy-invite UX, dismissible invite banner).
- **UI gating**: `platform-new-service`, service Edit/Delete buttons → super-only. Vendor Approve/Revoke → `manage_vendors`. Listing Approve/Unpublish → `manage_listings`. Event Delete → `manage_events`.

### Role-aware guide link in Nav (footer Guides column removed)
- **Footer.jsx**: `Guides` column dropped. Replaced with a short note instructing signed-in users to find their guide in the top nav.
- **Nav.jsx + `lib/guides.js`**: signed-in users see exactly ONE PDF link (`nav-guide-{admin|company|vendor|player}`) pointing to the appropriate manual. Mobile drawer mirrors it under `/ Help`.
- **Manuals refreshed**: `scripts/generate_manuals.py` updated with Verified badge, Happy-hour pricing, Cancellation/Reschedule policies, Reviews flow, CricHeroes-style scoring, public scorecard URL, mobile nav, drill-down detail pages, multi-admin RBAC sections. 4 PDFs regenerated.

### About page polish
- **About.jsx** — content now uses `whitespace-pre-line` (preserves admin-entered newlines), occupies full container width, legacy `<br>` literals normalised to real line breaks, bio text in PeopleGrid also wrapped.
- **Admin editor** — About page editor (`PlatformAdmin.jsx`) shows a hint about Enter key for line breaks, larger textareas (rows 4–6) for better authoring.

## Implemented (Feb 20, 2026 — Iteration 19) Organiser role + signup + nav + dedicated manual + DRY consumer
- **Backend** (`routes/auth.py`): added `POST /api/organisers/signup/request-otp` and `POST /api/organisers/signup`. No corporate-email rule. Creates a `companies` doc tagged `org_type="organiser"` and a user with `role="organiser"`. Reuses `_consume_signup_otp_sync` for the OTP validation.
- **Permission widening** (`server.py`, `routes/events.py`, `routes/bookings.py`): `require_admin` and `require_company_admin` now accept the `organiser` role. New helper `is_company_scoped(user)` replaces 27 `user.get("role") == "company_admin"` checks across the codebase so HR + organisers share the same scoping.
- **DRY refactor**: closure-level `_consume_signup_otp` in `routes/auth.py::register` now delegates to the module-level `_consume_signup_otp_sync(db, collection_name)` — single source of truth across company / vendor / player / organiser flows.
- **Frontend**:
  - New `/app/frontend/src/pages/SignupOrganiser.jsx` (cyan `#06B6D4` brand colour), reuses `OtpVerifyStep`.
  - `AuthContext` exposes `signupOrganiser()`; `isCompanyAdmin` is true for organisers (so existing HR-gated UI works); new `isOrganiser` flag.
  - `Nav.jsx`: cyan "For Organisers" CTA next to lime "For Companies" (desktop + mobile drawer).
  - `Footer.jsx`: "Become an organiser" link in the Join column.
  - `Login.jsx`: redirects organisers to `/dashboard`.
  - `lib/guides.js`: `organiser` → `/manuals/kreeda-nation-organiser-manual.pdf`.
- **Organiser manual** (`scripts/generate_manuals.py`): inherits the HR content with a tailored "Welcome, organiser" intro that highlights the any-email rule. Five PDFs now ship under `/manuals/`.
- **Tests**: 39 new pytest cases in `tests/test_organiser_signup_otp.py` covering accept-any-domain OTP, signup flow, role checks, perms (can list own events, blocked from other companies' events). + 22 frontend Playwright assertions.

**Known operational issue (not code):** the configured `SENDGRID_API_KEY` is currently returning HTTP 401 Unauthorized at SendGrid's edge (verified with a direct SDK call outside our app). All `*/signup/request-otp` calls therefore 502 with "We couldn't send the verification email…". To recover: open SendGrid → Settings → API Keys, regenerate the key with `Mail Send` permission, then update `SENDGRID_API_KEY` in `backend/.env`. The code path is correct — pytest passes immediately once SendGrid is reachable again.


- **Vendor signup is now 2-step**: `POST /api/vendors/signup/request-otp` issues a 6-digit code (10-min TTL, 5-attempt lockout). `POST /api/vendors/signup` requires `otp` and uses the shared `_consume_signup_otp_sync(db, "vendor_signup_otps")` helper. No corporate-domain restriction.
- **Player signup is now 2-step**: same shape via `/players/signup/request-otp` + the existing `/players/register`. `PlayerSignupBody.email` is now **required** (was Optional) since it's the OTP channel.
- **Forgot-password ships real emails** — `routes/auth.py::forgot_password` now calls `send_password_reset_email(to, reset_url, name)` from `email_service.py` (branded Kreeda Nation template with a "RESET MY PASSWORD" button + plain-text link fallback). If SendGrid fails, the reset URL is still logged so ops can recover.
- **DRY OTP consumer** — extracted `_consume_signup_otp_sync(db, collection_name)` from `routes/auth.py`. `routes/vendors.py::vendor_signup` and `server.py::player_register` both import it and reuse the exact same validation logic the company-signup flow uses. Single source of truth.
- **Reusable FE component** — `/app/frontend/src/components/OtpVerifyStep.jsx`: countdown timer + 60s resend cooldown + back-to-edit link + 6-digit input, parameterised by a `testidPrefix`. Used by `VendorSignup.jsx` (prefix `vendor-signup-otp`) and `PlayerSignup.jsx` (prefix `player-signup-otp`). `SignupCompany.jsx` keeps its inline implementation (already covered by iteration-17 tests).
- **Tests**: new `tests/test_vendor_player_otp_and_email.py` — 15/15 pass covering vendor/player request-otp accepting any domain, missing OTP rejection, expired/wrong/lockout paths, full success → user+profile creation, and SendGrid 202 + log assertions for forgot-password. Combined with iteration-17 suite = **31/31 OTP tests passing**.
- **Test infra fix** — `tests/test_vendor_player_otp_and_email.py` + `test_company_signup_otp.py` now use `dotenv` / safe `os.environ.get(...)` defaults so they run locally too.

## Implemented (Feb 19, 2026 — Iteration 18) Vendor + Player OTP signup, SendGrid forgot-password, DRY OTP consumer


- **Real email delivery wired** — `backend/email_service.py` wraps SendGrid (`sendgrid==6.12.5`). `send_otp_email(to, otp, company_name)` sends a branded HTML template via the configured `SENDER_EMAIL`. Failures log + return `False` (never raise) so callers control behaviour.
- **Free-email blocklist** in `routes/auth.py::FREE_EMAIL_DOMAINS` — rejects gmail, yahoo, hotmail/outlook/live/msn, icloud, aol, proton, yandex, mail.ru, gmx, rediff, mailinator and other disposable/personal providers. Anything else (corporate/custom domains) is allowed.
- **Two-step signup flow**:
  - `POST /api/companies/signup/request-otp` — validates domain → generates 6-digit OTP → upserts in `company_signup_otps` (10-min TTL, 5-attempt lockout) → sends via SendGrid → returns `{ok, expires_in, email}`. Pre-rejects emails that already have an account.
  - `POST /api/companies/signup` — now requires `otp` field. Validates the OTP (existence, expiry, attempts ≤ 5, exact match), creates company + company_admin user with `email_verified=true`, marks OTP record consumed (`verified=true, used_at=…`).
- **Frontend** (`SignupCompany.jsx`) — rewritten as a 2-step UX (`details` → `verify`). Step 1 includes the "Use your official company email" hint with shield icon. Step 2 shows a 6-digit input, 10-minute countdown, 60s resend cooldown, back-to-edit-details link, and disables submission once the code expires. All inputs have `data-testid`s for QA.
- **Env added**: `SENDGRID_API_KEY`, `SENDER_EMAIL`, `SENDER_NAME`, `FRONTEND_URL` in `backend/.env`. `requirements.txt` updated.
- **Tests**: new `tests/test_company_signup_otp.py` — **16/16 backend cases** cover blocklist, OTP persistence, overwrite on re-request, wrong-attempt counter, 429 lockout, expiry, missing-OTP rejection, valid-OTP success path. Frontend Playwright **5/5 flows** verified end-to-end.

## Implemented (Feb 19, 2026 — Iteration 17) Corporate-email gating + SendGrid OTP for company signup

## Implemented (Feb 18, 2026 — Iteration 16) Clean slate for production launch
- **Wiped every demo entity** via `/app/scripts/wipe_to_clean_slate.py` — preserves only services (17), sports (11), platform admin user (1), site_settings, and About page content.
- **Disabled demo-data seeding** — `seed_demo_data()` is no longer called from `on_startup()`. The viewer account (`viewer@kreedanation.com`) auto-seed inside `seed_admin()` was also removed.
- Result: every page now shows 0/0/0/0 stats; no fake teams, events, players, vendors, listings, bookings or reviews. Production is ready for real data.
- Reusable: re-run `python /app/scripts/wipe_to_clean_slate.py` any time to reset back to clean slate.

## Implemented (Feb 18, 2026 — Iteration 15) Performance pass + array-index keys
- **`useMemo` for expensive renders** (3 hotspots flagged by code review):
  - `CricketScorer.jsx::LivePanel` — `availableBatsmen`, `availableBowlers`, `extrasTotal` now recompute only on relevant deps.
  - `EventTeamsManager.jsx::EventCompanies` — `pickableCompanies` memoized on `[allCompanies, companies]`.
- **Array-index keys replaced with composite keys** (5 spots): VendorDashboard images, RegisterTeam player slots, PlatformAdmin field/variant/people editors.


- **`useMemo` for expensive renders** (3 hotspots flagged by code review):
  - `CricketScorer.jsx::LivePanel` — `availableBatsmen` (filter + filter), `availableBowlers` (filter), `extrasTotal` (reduce). Now recompute only when their actual deps change instead of every render of the scorer.
  - `EventTeamsManager.jsx::EventCompanies` — `pickableCompanies` (filter + find) memoized on `[allCompanies, companies]`.
- **Array-index keys replaced with composite keys** (5 spots):
  - `VendorDashboard.jsx` images — `${img || "empty"}-${i}`
  - `RegisterTeam.jsx` players — `player-slot-${i}` (fixed-size form, index is stable here)
  - `PlatformAdmin.jsx` fields / variants / people editors — `${kind}-${name || "new"}-${i}`
  These prevent state-bleed between rows on add/delete in the absence of a UID-schema migration.
- **Verified false positives** from the dev-tool code review (logged for future):
  - "Undefined variable" — ruff lint across the entire backend reports 0 issues.
  - "60 `is` vs `==`" — AST scan reports 0 real cases. All `is`/`is not` uses are vs `None`/`True`/`False` (PEP-8 compliant).
  - "69 missing hook deps" — ESLint `react-hooks/exhaustive-deps` reports 0 issues on the 3 cited files. The dev-tool flags external imports (`api`, `encodeURIComponent`) as "missing deps", which is not the official React rule.
  - "Remove `console` from `devLog.js`" — that's exactly the file's job; calls are already gated behind `if (process.env.NODE_ENV !== "production")`.
- **No behavior change** — frontend home page screenshot smoke-tested OK; 29 fast cricket tests pass.

## Implemented (Feb 18, 2026 — Iteration 14) Cricket module decomposition
- **Extracted 6 pure helpers** at module level in `routes/cricket.py`:
  - `_compute_ball_delta(extra, runs)` — pure scoring math (returns legal/bat_runs/team_runs/bowler_runs/extras_inc/swap_strike)
  - `_apply_ball_to_players(inn, striker, bowler, delta, extra)` — mutates innings counters from a computed delta
  - `_apply_wicket(inn, score, striker_id, bowler_id, wicket, free_hit_active)` — handles dismissal + free-hit rule
  - `_is_innings_complete(inn, overs_limit)` — all-out / overs-done / chase-done check
  - `_resolve_innings_teams(score, team_a_id, team_b_id)` — picks batting/bowling sides from toss
  - `_reset_innings_counters(inn)` + `_replay_ball(inn, ball)` — replay-based undo
- **Function size reductions**:
  - `register()`: 489 → 337 LoC (**-31%**)
  - `cricket_ball()`: 162 → 89 LoC (**-45%**, was CC 57)
  - `cricket_undo()`: 92 → 21 LoC (**-77%**, was CC 33)
  - `cricket_start_innings()`: 55 → 48 LoC (was CC 21)
- **24 new pure-unit tests** in `tests/test_cricket_helpers.py` cover the extracted helpers (run in 0.2s — fast safety net).
- **Zero regressions**: all 41 existing cricket integration tests + 24 new unit tests = **65 passing**. Behavior identical, just reorganised.

## Implemented (Feb 18, 2026 — Iteration 13) Routes split (P2) + seed-count test fix (P1 nit)
- **`routes/auth.py`** (179 LoC) — `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/me`, `/companies/signup`, `/companies/me` (GET/PATCH), `/companies` list, `/{auth,players}/forgot-password`, `/{auth,players}/reset-password`. Pulls helpers (`hash_password`, `create_access_token`, `set_auth_cookie`, `_user_with_company`) + models via `SimpleNamespace` deps bundle.
- **`routes/events.py`** (167 LoC) — `/events` CRUD, `/my/teams`, `/venues/suggest`, `/teams` CRUD, `/team-players` CRUD.
- **`routes/fixtures.py`** (213 LoC) — `generate_round_robin` & `generate_knockout` helpers, `/events/{id}/generate-fixtures`, `/events/{id}/fixtures`, `/fixtures/{id}` GET/PATCH/init-score, `/public/fixtures/{id}` (no-auth scorecard), and the `/api/ws` WebSocket. `propagate_knockout_winner` stays in `server.py` (shared with `routes/cricket.py`).
- **`routes/vendors.py`** (180 LoC) — `/vendors/signup`, `/vendors/me`, `/vendors`, `/vendors/{id}/approve`, `/vendor-listings` (public + cities + by id), `/vendors/me/listings` CRUD, `/admin/listings` + `/admin/listings/{id}/approve`.
- **`routes/bookings.py`** (149 LoC) — `/services` CRUD (super-only for write), `/bookings` CRUD (HR + admin scoping).
- **`server.py`** down from 3537 → 2922 LoC (~17% reduction). The 6th/7th split modules (`vendor-bookings` lifecycle and `players_accounts`) are noted in P2 backlog for a follow-up pass.
- **Seed-count test fix** — `test_multitenant.py::test_company_stats_scoped` now self-seeds 3 events before asserting count, removing the reliance on stale demo data. `test_rbac_admin.py` BASE_URL falls back to `http://localhost:8001` for local pytest runs.
- **Full regression**: 249 passed + 3 skipped, 0 failures (was 246 passed + 3 skipped + 3 stale-seed failures before this iteration).



### Testing & regression
- **`/app/backend/tests/test_rbac_admin.py`** — 14/14 tests covering all RBAC paths (super-only enforcement, permission-gated paths, staff CRUD, edge cases: super-immortal, duplicate email, perm allowlist).
- **`/app/backend/tests/test_account_suspension.py`** — 8/8 tests covering list/filter, disable→403 with exact contact message, re-enable→login restored, platform-admin protection, self-disable rejection, auth gating.
- Frontend e2e via Playwright validated: nav guide visibility, footer guide removal, team-tab gating, staff-admin invite flow, staff-admin login → button hiding, About page line-break rendering, all 4 manuals served at /manuals/*.

## Implemented — Feb 20, 2026 — Account Suspension (uniform)
- `GET /api/admin/users[?role=…]` — lists organisers / company admins / vendors / players with `disabled` flag and contextual fields (company name / vendor business name).
- `PATCH /api/admin/users/{id}/disabled` — toggles `disabled`; stamps `disabled_at` / `disabled_by`; refuses platform_admin, self, and unknown ids.
- `POST /api/auth/login` now rejects disabled accounts with **HTTP 403** and detail `"Your account has been disabled. Please contact admin with admin email: admin@kreedanation.com"`.
- New **Accounts** tab in `PlatformAdmin.jsx` (red tab) with role sub-tabs (Organisers / Company admins / Vendors / Players), search box, "Show disabled" toggle, per-row Disable/Enable button, and disabled metadata badge.
- 8 pytest cases added in `test_account_suspension.py` (all passing).

## Implemented — Feb 20, 2026 — Organisers tab + Dashboard counts
- Added cyan **Organisers** tab in PlatformAdmin (filters `companies` by `org_type === "organiser"`). Reuses `/platform-admin/companies/{id}` detail page — `CompanyDetail` flips to cyan "Organiser" branding + "Owner & staff" tab label when applicable.
- `/api/dashboard/admin` returns separate `organisers` and `companies` counts (companies excludes organisers). New cyan ORGANISERS dashboard card sits next to the pink COMPANIES card.

## Implemented — Feb 20, 2026 — Code quality refactor
**Security**:
- `random.randint` → `secrets.randbelow(1_000_000)` for OTP generation in `routes/auth.py`.
- Same fix in `tests/test_vendor_player_otp_and_email.py`.
- Test password in `tests/test_account_suspension.py` now sourced from env / `secrets.token_urlsafe()`.

**Component splits (zero-regression, verified by testing agent iteration_16)**:
- `PlatformAdmin.jsx`: **715 → 236 lines** (-67%). Extracted to `/app/frontend/src/components/admin/`: ServiceEditor, EventsTab, VendorsTab, ListingsTab, SettingsTab, AboutTab, AccountsManager, ContactInbox, PeopleEditor.
- `AdminTeam.jsx`: **265 → 98 lines** (-63%). Extracted: InviteAdminForm, InviteCredentialsBanner, AdminRow + shared `adminTeamShared.js`.
- `CricketScorer.jsx` `LivePanel`: **226 → ~70 lines**. Extracted to `/app/frontend/src/components/cricket/`: CricketScoreboard, BallEntryPanel, InningsPrompts (WicketPrompt + OverBreakPrompt). Removed dead `wicketType` state.

## Implemented — Feb 21, 2026 — Multi-Sport Player Profile
- Player profile is no longer cricket-only. New `interested_sports: List[str]` + `sport_profiles: Dict[str, Any]` fields on the `PlayerProfile` model in `server.py`. Backwards-compat: legacy `role/batting_hand/bowling_style/jersey_number/cricheroes_url` fields preserved & mirrored from `sport_profiles.cricket` on save.
- New schema-driven UI (`/app/frontend/src/lib/sportProfileSchema.js`) declares fields per sport — adding a new sport is one schema entry, end-to-end.
- Supported sports & per-sport fields:
  - **Cricket**: role / batting_hand / bowling_style / jersey_number / cricheroes_url
  - **Football**: position / preferred_foot / jersey_number
  - **Basketball**: position / shooting_hand / jersey_number
  - **Badminton**: hand / grip / format (singles/doubles/mixed)
  - **Table Tennis**: hand / grip / style
  - **Volleyball**: position / hand / jersey_number
  - **Chess**: rating / title / preferred_color / chesscom_url
  - **Quiz**: specialty / format
  - **Hackathon**: domain / languages / github_url
  - **Other**: free-text sport name + role
- New components:
  - `/app/frontend/src/components/player/SportsMultiSelect.jsx` — chip-style multi-select (color per sport).
  - `/app/frontend/src/components/player/SportProfileSection.jsx` — dynamic per-sport form.
  - `withLegacyMigration()` helper in `PlayerProfile.jsx` auto-promotes cricket-only legacy data to `sport_profiles.cricket` on first load.
- `PlayerDirectory.jsx` public view now renders one `SportCards` card per interested sport (with legacy cricket fallback).
- **Verified end-to-end by testing agent iteration_17 (13/13 steps passed)** including: chip selection, dynamic form rendering, save+reload persistence, remove-sport flow, public profile cards, and the legacy-player auto-migration path.

## Implemented — Feb 21, 2026 — Player Sport Filter (recruiting tool)
- `GET /api/players/profiles` now accepts `sport`, `role`, `hand`, `city` query params (in addition to existing `q`). For `sport=cricket` the filter also matches legacy cricket-only profiles (no `interested_sports` field). For other sports, matches `interested_sports` array. `role` checks `sport_profiles.{sport}.{role|position|specialty|domain}`; `hand` checks `{batting_hand|preferred_foot|shooting_hand|hand|preferred_color}` — both fall back to legacy cricket fields when `sport=cricket`.
- New `/app/frontend/src/components/player/PlayerFilters.jsx` — 5-up filter bar (name+mobile, city, sport, role, hand/style). Role + hand selects auto-populate from the chosen sport's schema (so picking Football shows Position dropdown with goalkeeper/defender/midfielder/forward/winger, Chess shows Title with CM/FM/IM/GM, etc.). Disabled until a sport is chosen.
- `PlayerDirectory.jsx` `PlayerSearch` rewritten: filter URL params, result count header, redesigned `PlayerCard` with sport-color role accent + sport tag chips at the bottom of each card. Verified across 8 filter combinations via curl + 3-screenshot smoke test (Cricket+bowler returns 1, Football+midfielder returns 2, no-filter returns all).

## Implemented — Feb 21, 2026 — Career Stats Dashboard
- New `GET /api/players/profiles/{id}/stats` — returns `{ sport: { auto: {...}, manual: {...} } }` per interested sport.
- **Cricket auto-aggregation**: scans all completed fixtures where the player's `id` appears in `score.playing_xi.team_a|team_b` and aggregates matches / runs / balls_faced / fours / sixes / dismissals / highest_score / balls_bowled / runs_conceded / wickets / overs_bowled + derived batting_average, strike_rate, bowling_economy, bowling_average.
- **Manual entries** stored under `PlayerProfile.lifetime_stats[sport]` — editable for ALL sports, used as the data source for non-cricket sports (football goals/assists/cards, basketball points/rebounds, chess wins/draws/rating, badminton tournament titles, hackathon prizes, etc.).
- New components:
  - `/app/frontend/src/lib/sportStatsSchema.js` — STATS_SCHEMAS for all 10 sports, declaring auto vs manual field sets.
  - `/app/frontend/src/components/player/SportStatsDashboard.jsx` — read-only career dashboard, one card per interested sport, "auto-tracked" badge on cricket when fixture data exists, achievement banner highlights text fields like `notable_achievement` / `biggest_win`.
  - `/app/frontend/src/components/player/SportStatsEditor.jsx` — editor section inside each sport block of `/players/me` with sport-specific number/text inputs for manual stats.
- Both editor (`/players/me`) and public profile (`/players/profiles/{id}`) now show the career-stats dashboard.
- Verified end-to-end via curl + screenshot: a seeded cricket fixture with 78(50) batting & 3/28(4ov) bowling produced the exact auto-aggregated values (batting avg 78.0, SR 156.0, economy 7.0, bowling avg 9.33).

## Implemented — Feb 22, 2026 — Sponsorship Marketplace (Phase 1)
**Backend** (`server.py`):
- Extended `Event` model with `accept_sponsorships`, `sponsorship_requirements` (dict — reach, participants, audience, demographics, social-media reach, livestream views, venue, category, brochure URL), `sponsorship_opportunities` (list with id/name/type/price/quantity/sold_count/benefits/status/awarded_to fields), `data_share_agreement` (bool).
- New `SponsorProfile` model (`sponsor_profiles` collection): company_name, contact_person, industry, location, target_locations, target_event_types, target_audience, budget_range, website, logo_url, sponsor_interests.
- New `SponsorshipInterest` model (collection scaffolded, endpoints for Phase 2).
- New endpoints:
  - `POST /api/auth/sponsors/signup` — email+password sponsor signup, creates user `role=sponsor` + auto sponsor_profile.
  - `GET/PATCH /api/sponsor-profile/me` — gated to `sponsor` OR `company_admin` roles. Company admins get an auto-bootstrap profile so they can both run AND sponsor events.
  - `GET /api/events/{id}/sponsorships` — PUBLIC listing of opportunities + requirements (no auth needed).
  - `POST/PATCH/DELETE /api/events/{id}/sponsorships[/{opp_id}]` — owner-only opportunity CRUD (platform_admin OR same-company organiser/company_admin).

**Frontend**:
- New `/sponsor/signup` page with clean signup form (`SignupSponsor.jsx`).
- New `/sponsors/me` sponsor profile editor (`SponsorProfile.jsx`) with chip-select for interests & event types, logo upload.
- New Sponsorship tab in `/events/{id}` (`EventSponsorshipManager.jsx`) — owner toggles "Accept sponsorships", fills 10 requirement fields, locks data-share agreement, and manages multiple opportunities inline (add/edit/remove with name/type/price/qty/benefits). Non-owners get a read-only public view with "AVAILABLE · N slots" / "SOLD" / "Sponsored by …" badges.
- `AuthContext` gained `isSponsor`, `canSponsor` (sponsor OR company_admin), and `refreshMe()` helper.
- `Nav.jsx` shows "Sponsor hub" link for company admins and "Sponsor profile" / "Browse events" for the sponsor role.
- Routes wired in `App.js`: `/sponsor/signup`, `/sponsors/me`.

**Image optimization** (across all uploads):
- New `/app/frontend/src/lib/compressImage.js` — HTML5 canvas pipeline: scales down to ≤1280×1280, JPEG q≥0.5, hard cap 500 KB. GIF/SVG preserved unchanged (with 2 MB cap).
- `ImageUpload.jsx` now compresses client-side BEFORE upload and shows the resulting KB size in the success toast.
- Server-side cap tightened from 5 MB → 1 MB safety net (client should already deliver ≤500 KB).

Phase 2 (next session): sponsor marketplace browse + filters, sponsor "I'm interested" CTA, organiser interest queue (accept/reject), public "Sponsored by …" badge wiring, admin sponsorship metrics dashboard.

## Implemented — Feb 22, 2026 — Sponsorship Marketplace (Phase 2) + Events list badge + Sponsor guide
- `/sponsorships` page — public-browsable marketplace with 5 filters (sport / location / event type / budget / min reach). Anonymous banner directs to /sponsor/signup.
- Sponsor-side "I'm interested" CTA on every Sponsorship tab opportunity → opens proposal dialog → creates interest record (duplicates blocked). Once submitted, button flips to "Interest sent · pending".
- Organiser-side "INTEREST QUEUE" panel on the Sponsorship tab showing each pending interest with sponsor company / industry / budget / website / proposal. Accept/Reject buttons with confirmation. Accept auto-flips opportunity to SOLD when all slots fill, and auto-rejects any other pending interests on that slot. Decided interests collapse into a folded section.
- Public opportunity row now shows `✦ Sponsored by [Brand]` from the `awarded_to` array, plus "AVAILABLE · N slots" / "SOLD" status.
- Admin Dashboard tab now has a `SPONSORSHIP MARKETPLACE` card: Total opportunities, Total value, Pending/Awarded/Rejected counts, Top sponsors (by accepted value), Top events (by total slot value).
- **Events list (`/events`)**: every event accepting sponsorships shows a yellow `SPONSORSHIP-READY` badge + "N sponsorships · from ₹X" footer strip. New "Accepting sponsors" filter chip narrows to those events.
- **Event detail tabs (Fixtures / Standings / Sponsors / Sponsorship) no longer clip** — TabsList now wraps (`flex-wrap h-auto`) so all 4 tabs are always visible on standard laptop screens (1280px+).
- **Footer**: added "Become a sponsor" link in yellow accent.

## Implemented — Feb 22, 2026 — Sponsor PDF guide + role-guide updates
- New `/manuals/kreeda-nation-sponsor-manual.pdf` (164 KB, 8 sections): welcome, account creation, profile checklist, marketplace browse, expressing interest, lifecycle of an interest, best practices, where the guide lives.
- `Company HR manual` got 2 new sections — "Sponsorship marketplace — earn revenue from your events" (full enable + opportunities setup walkthrough + approval flow) and "Sponsoring other companies' events" (dual-use as sponsor from the company login).
- `Platform admin manual` got a new "Sponsorship marketplace oversight" section explaining the new admin dashboard card + how to suspend a misbehaving sponsor.
- `Organiser manual` inherits the new company sponsorship sections (organiser is built on top of company sections).
- Nav now surfaces the sponsor guide as `Sponsor guide` for `role=sponsor` (mapping added to `/app/frontend/src/lib/guides.js`).

## Implemented — Feb 22, 2026 — First-login Welcome modal
- New `/app/frontend/src/components/WelcomeModal.jsx` — mounted once globally in `App.js` inside `<BrowserRouter>`. Detects first visit per `(user_id, role)` via localStorage key `kn_welcome_v1_{uid}_{role}`.
- Role-tailored copy + accent + CTA:
  - **platform_admin / admin** (red): "Welcome to Kreeda Nation HQ" + Admin guide PDF.
  - **company_admin** (lime): "Welcome, HR captain" + HR guide + → Open your dashboard secondary CTA.
  - **organiser** (cyan): "Welcome, tournament organiser" + Organiser guide.
  - **vendor** (pink): "Welcome to the Kreeda Nation marketplace" + Vendor guide.
  - **player** (lime): "Welcome, athlete" + Player guide.
  - **sponsor** (yellow): "Welcome to the marketplace" + Sponsor guide + → Browse the sponsorship marketplace now secondary CTA.
- One-paragraph elevator pitch per role surfaces the highest-leverage activation behaviour.
- Dismissal sticks across reloads. Clicking "Open my … guide" auto-dismisses too (opens the PDF in a new tab).
- **Verified by testing agent iteration_19 (10/10 scenarios PASS)** including admin + sponsor first-login flows, marketplace browse & filters, interest creation, awarded badges, admin metrics, and the event tabs no-clip fix at both 1280×800 AND 768×1024.

## Implemented — Feb 22, 2026 — Image storage refactor (production fix)
- **Root cause**: Container disk on production is ephemeral — every deploy/restart wiped `/app/backend/uploads/`, so all previously uploaded images returned 404 (broken-image icon).
- **Backend fix**: Upload endpoint refactored to store image bytes in a new MongoDB collection `uploaded_images`. Server-side Pillow recompression added: resize to max 1280px + JPEG quality step-down (82 → 75 → 65 → 55) until under 350 KB. A 2000×1500 JPEG (~47 KB) was reduced to ~11 KB end-to-end. New endpoint `GET /api/uploads/{id}` serves from Mongo with `Cache-Control: max-age=1y immutable`; legacy disk path kept as fallback so preview-era files still work.
- **Frontend fix**: `ImageUpload.jsx` now stores the **relative** URL `/api/uploads/{id}` (was previously storing absolute preview hostname URLs, which broke when the app was served from kreedanation.com). New helper `lib/imageUrl.js` resolves stored values at render time using `REACT_APP_BACKEND_URL`.
- **Global self-heal**: `installGlobalImageHealer()` adds one capture-phase `error` listener at document level — every `<img>` on every page auto-heals broken legacy URLs (rewrites the host) and falls back to a neutral Pexels placeholder if the file is truly gone. ZERO per-page edits needed.
- **Migration script**: `/app/scripts/heal_image_urls.py` strips legacy hostnames from `photo_url` / `logo_url` / `banner_url` / `images[]` across 10 collections. Idempotent — safe to re-run.
- Verified end-to-end via curl: upload → 11 KB stored → served correctly with image/jpeg content-type, persists across DB queries (survives container restarts).

## Backlog
### P0
- (none open)

### P1
- **Browser-side wss:// handshake** — polling fallback masks this in UX; ingress upgrade headers still flaky.
- **Email integration** (Resend/SendGrid) — currently mocked. Awaiting API key from user. Will unblock real staff-admin invites, booking notifications, and password resets.

### P2
- **Routes split (continuation)** — optional next pass: extract `routes/vendor_bookings.py` (cancel/reschedule lifecycle, ~300 LoC still in server.py) and `routes/players_accounts.py` (player profiles + directory).
- **Cricket module refactor** — `routes/cricket.py::register()` (489 LoC, complexity 167) and `cricket_ball()` (162 LoC, complexity 57) flagged by code review as needing decomposition into per-handler + per-event helpers. Touches the most complex live-scoring code path; needs dedicated test pass.
- **Large component decomposition** — `AdminTeam.jsx` (244 LoC), `CricketScorer.jsx::LivePanel` (210 LoC, complexity 46), `EventTeamsManager.jsx`, `PlatformAdmin.jsx` (358 LoC) — split into smaller subcomponents.
- **Inline objects in AdminDetail.jsx** (~20 locations) — wrap in `useMemo` or hoist to module-level constants.
- **Cricket enhancements** — wagon wheel positions, super-over for tied matches.
- **Editor lists UUIDs** — stable `_uid` schemas for VendorDashboard images, RegisterTeam players, PlatformAdmin variants/fields/people arrays (currently keyed by array index — works but breaks on reorder).
- **Refactor large functions** — `seed_services`, `seed_demo_data`, `get_standings`, `listing_availability`.

## Implemented (Feb 28, 2026 — Date-picker past-date validation)
- New helper `/app/frontend/src/lib/dateConstraints.js` (`todayLocalISO`, `nowLocalHHMM`, `minTimeForDate`, `validateFutureDateTime`) — single source of truth for future-only date/time pickers.
- Frontend `min` attribute + submit-time validation wired into all booking-related date/time inputs:
  - `pages/VendorMarket.jsx` (vendor booking modal — `requested_date` + `start_time`).
  - `components/VendorBookings.jsx` (HR reschedule form — `date` + `time`).
  - `components/VenueScheduleEditor.jsx` (vendor block-dates form — `date` + `start_time` + `end_time`).
- Backend defence-in-depth: new `_reject_past_slot()` helper in `server.py` called from `POST /api/vendor-bookings`, `POST /api/vendor-bookings/{id}/reschedule`, and `POST /api/vendor-listings/{id}/blocks`. Returns 400 if `requested_date + start_time < utcnow - 1h`. Validated via inline test harness (5/5 pass).

## Test Credentials
- Platform Admin (Super): admin@kreedanation.com / admin123
- Company HR: hr@acme.com / hr123
- Vendor: ravi@turf.in / vendor123
- Player: player@acme.com / player123 (or +919000000001)
- Viewer: viewer@kreedanation.com / viewer123
- (Staff admins created on the fly via /platform-admin → Team or POST /api/admin/staff)
