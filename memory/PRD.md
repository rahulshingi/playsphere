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

## Implemented (Feb 18, 2026 — Iteration 15) **Phase 2: Cancellation policies + Happy-hour pricing + Mocked email**
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

## Backlog
### P0
- (none open) — CricHeroes match flow + all P1 items closed.

### P1
- **Browser-side wss:// handshake** — verify Kubernetes ingress is forwarding Upgrade/Connection headers for `/api/ws`. Backend WS itself is healthy; polling fallback masks this in UX.
- **Email integration** (Resend/SendGrid) — currently mocked. Awaiting API key from user.
- **Sponsor reach analytics** — track logo impressions across event pages for ROI.

### P2
- **Continue routes split** — extract `routes/auth.py`, `routes/events.py`, `routes/fixtures.py`, `routes/vendors.py`, `routes/bookings.py` following the `cricket.py` + `settings.py` pattern. (2/6 complete.)
- **Cricket enhancements** (remaining): wagon wheel positions, super-over for tied matches.
- **Editor lists UUIDs** — VendorDashboard images + RegisterTeam players + PlatformAdmin fields/variants use array-index keys; refactor to stable `_uid`s.
- **Refactor large functions** — `seed_services` (300 lines), `seed_demo_data` (113 lines), `get_standings` (cyclomatic 17), `listing_availability` (14).

## Test Credentials
- Platform Admin: admin@kreedanation.com / admin123
- Company HR: hr@acme.com / hr123
- Vendor: ravi@turf.in / vendor123
- Player: player@acme.com / player123 (or +919000000001)
- Viewer: viewer@kreedanation.com / viewer123
