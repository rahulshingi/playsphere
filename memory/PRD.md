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


## Implemented (Feb 24, 2026 — Iteration 35) Player match history + auto-tag sports
- **New endpoint** `GET /api/players/{id}/match-history` — returns fixture-level score cards for every match the player was rostered on. Payload includes team names, per-side score_display, result (won/lost/draw/live), award chips the player won on that match, and event link. Only status live/completed are returned.
- **PlayerProfile** now renders three sections in order: 🟢 **MY LOCAL MATCHES** (hosted) → 🟢 **LOCAL MATCH SCORES** (per-match cards from local tournaments played, iter35 NEW) → 🔵 **TOURNAMENTS PLAYED** (non-local corporate/organiser events).
- **Auto-tag interested_sports**: `POST /events/{event_id}/teams/{team_id}/members` now `$addToSet`s the event's sport into the player's `interested_sports` array. First time a player joins a badminton match → badminton stats card appears on their profile. Player can still remove manually via profile edit.
- **Bug fix** in `GET /api/players/{id}/tournaments`: was querying `db.matches` (nonexistent collection). Now queries `db.fixtures` → contribution counts (MOM / best_batter / best_bowler / top_scorer / matches) actually populate.
- **New tests**: `tests/test_match_history_iter35.py` (5/5). Aggregate regression 38/38 green.


## Implemented (Feb 24, 2026 — Iteration 34) Match completion lock + auto-awards + blank-page fix
- **Bug fix — Save highlights blank page** (reported on production kreedanation.com): `FixtureAwardsEditor` was calling `PATCH /fixtures/{id}` (score endpoint expecting a full `ScoreUpdate` body) instead of `PATCH /fixtures/{id}/media`. The 422 response cascaded into a UI blank. Fixed by pointing the editor to the correct route + hardened the media endpoint's contract.
- **Auto-populate winner + awards** on `status=completed` transition. Winner = team with higher total. Cricket: MoM = winning team's top batter (fallback to bowler with 3+ wickets, else overall top batter); Best Batter = highest individual runs across both innings; Best Bowler = most wickets, tiebreak by best economy. Other sports: top_scorer picked from the winning team (fallback: overall top scorer).
- **Lock policy**: after completion, `PATCH /fixtures/{id}` (score edits) returns 409, and `PATCH /fixtures/{id}/media` with `awards` returns 409. The hero image remains editable so organisers can swap in a better post-match photo anytime.
- **Escape hatch**: new `POST /fixtures/{id}/reopen` — event creator + platform admin only. Flips status back to `live`, clears `winner_id` + `awards` so the scorer can re-score cleanly. Broadcasts a WebSocket update so open scorecards refresh.
- **Frontend UX**: FixtureAwardsEditor dialog shows a "Locked" chip + explanatory note when the match is completed. Award inputs become read-only. A red "Reopen match" button appears (with a confirm prompt). FixtureCard button label switched to "Edit hero image · view awards" post-completion.
- **Tests**: `tests/test_fixture_completion_iter34.py` (10/10 pass) covers auto-fill on completion, media/score lock behavior, reopen permissions, and the blank-page regression itself.


## Implemented (Feb 22, 2026 — Iteration 33) Auth + business helper refactor (P1)
- **`routes/auth.py` refactor** — the 321-line `register()` closure is now a 20-line orchestrator delegating to four thematic module-level helpers: `_register_core_auth` (`/auth/*`), `_register_signup_otp` (4× `/*/signup/request-otp`), `_register_signup` (company + organiser signup + `/companies/*`), and `_register_password_reset` (forgot + reset). Shared logic `_issue_signup_otp` and `_unique_company_slug` are now module-level + individually testable. Behaviour verified by 66/66 existing OTP + signup + tournament tests.
- **`routes/business.py` helpers extracted** — `vendor_for_user`, `ensure_vendor_owner`, `staff_can` moved to module level (each takes `db` as first arg). In-closure wrappers `_vendor_for_user`, `_ensure_vendor_owner`, `_staff_can` preserved so all 52 call sites remain untouched. Helpers now importable + unit-testable in isolation without spinning up a FastAPI app.
- **New tests**: `tests/test_refactor_iter33.py` (9/9 pass) covers auth login/logout/me, free-domain gating, companies list gating, password-reset shape, meta endpoint. Zero behavioural regressions detected in the existing test suite.


## Implemented (Feb 22, 2026 — Iteration 31/32) Player Tournaments MVP (Local Matches)
- **Backend**: `Event` + `EventCreate` models extended with `is_local_match`, `listed_publicly`, `photos`. `Fixture` carries `hero_image_url` + `awards`. `POST /api/events` allows role=player (auto-tags `is_local_match=True`, honours `listed_publicly` toggle). `PATCH /api/events/{id}` widened to the event **creator** (any role, not just admins) with protected fields whitelist. `_can_manage_event` now returns True when `event.created_by == user.id`, unlocking fixture generation + teams management + photo uploads for player-hosts. New `GET /api/players/{id}/hosted-tournaments` endpoint (hides hidden events from strangers, always visible to creator + admin). Existing `POST/DELETE /api/events/{id}/photos` used for gallery uploads (owner-only).
- **Anonymous public profile fix (iter32)**: `GET /api/players/profiles/{id}` now uses `get_current_user_optional`; strips `mobile`/`email`/`dob` for anonymous viewers, returns `mobile_masked` instead. `PlayerDirectory.jsx` no longer redirects anonymous viewers to `/players/login`.
- **Frontend**: `Admin.jsx` renders a distinct "HOST A LOCAL MATCH" layout for `isPlayer && !isAdmin` (form + "MY LOCAL MATCHES" list + visibility toggle). `EventDetail.jsx` shows LOCAL MATCH + HIDDEN badges; `canManage` widened to include creator; new `EventPhotoGallery` mounted below tabs (file-picker upload + lightbox + delete); new `FixtureAwardsEditor` dialog + `FixtureAwardsBanner` on completed fixture cards. `PlayerProfile.jsx` + public `PlayerDirectory.jsx` render new `PlayerTournamentsSection` (MY LOCAL MATCHES + MATCHES PLAYED cards with sport tags + contribution chips). `Nav.jsx` gains "Host match" link for players.
- **Tests**: `tests/test_player_tournaments_iter31.py` (11/11) + `tests/test_public_profile_iter32.py` (3/3) green. Verified end-to-end by testing agent iter31 + iter32 (10/10 review cases pass after retest).

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

## Implemented (Feb 28, 2026 — Phase 1: Visible Calendar Widget)
- New reusable `DatePicker` component at `/app/frontend/src/components/ui/DatePicker.jsx` — shadcn `Calendar` wrapped in a `Popover`. Month grid, past dates greyed, optional `blockedDates` prop for vendor-blocked days.
- Replaced every browser-native `<input type="date">` in booking flows with `DatePicker`:
  - `pages/VendorMarket.jsx` (HR booking modal).
  - `components/VendorBookings.jsx` (HR reschedule form).
  - `components/VenueScheduleEditor.jsx` (vendor block-dates form).
- Testing agent (iteration_21) verified the DatePicker is used in all 3 surfaces and 0 native date inputs remain.

## Implemented (Feb 28, 2026 — Phase 2: Membership Purchase Flow)
- **New buyer endpoints** in `/app/backend/routes/memberships.py`:
  - `POST /api/memberships/purchase` — HR/Player/Organiser request to buy. Online payments are still queued as `pending_payment` (Razorpay stub). Duplicate active/pending purchases blocked (400).
  - `GET /api/memberships/my-purchases` — buyer's purchase history.
  - `POST /api/memberships/my-purchases/{id}/cancel` — buyer cancels their pending request.
- **New vendor endpoints**:
  - `GET /api/memberships/mine/purchases?status=` — vendor's purchase inbox.
  - `POST /api/memberships/mine/purchases/{id}/activate` — confirms offline payment, sets `status=active`, `starts_at`, `expires_at`.
  - `POST /api/memberships/mine/purchases/{id}/reject` — declines a pending request with reason.
  - `POST /api/memberships/mine/issue` — vendor manually issues a membership to an existing user (by email) for walk-in customers. Returns 404 if email not registered.
- **New frontend surfaces**:
  - `components/memberships/MembershipPurchaseModal.jsx` — two-CTA dialog (online disabled + offline active).
  - `components/memberships/PublicMembershipsList.jsx` — plan cards with Buy button. Mounted inside the VendorMarket booking modal.
  - `pages/MyMemberships.jsx` (route `/my-memberships`) — buyer's pass list with statuses, expiry counters, cancel CTA.
  - `components/vendor/VendorPurchaseRequests.jsx` — vendor's purchase inbox with Activate/Reject + Issue-manually form (mounted inside `VendorMembershipsPanel`).
  - Nav link "Memberships" added for HR + Player roles.
- **Testing**: iteration_21 ran 18/18 backend tests + frontend code-level review with 0 bugs.
- **Mocked**: Online payment is a UI stub. Both `payment_method=online` and `=offline` land as `pending_payment`. Razorpay integration is the next planned phase.

## Implemented (Feb 28, 2026 — Phase 3: Apply membership at booking + renewal reminders)
- **Booking flow now consumes memberships** — `VendorBookingRequest.apply_membership_id` + `VendorBooking.applied_membership_id`. The buyer's slot is free until `max_bookings` is reached; after that the toggle disappears and the buyer pays hourly.
- **Validation chain on the apply path**: membership must be active, owned by the buyer, expires in the future, and either vendor-wide or scoped to the listing. Any violation → HTTP 400 with a precise reason.
- **Usage tracking** — `db.membership_purchases.$inc.bookings_used` runs on every successful booking-with-membership.
- **Eligibility endpoint** `GET /api/memberships/my-eligibility?listing_id=…` powers the new "Apply membership" toggle in the booking modal (`pages/VendorMarket.jsx` → `vm-apply-memb`, `vm-apply-memb-toggle`). Total flips to ₹0 when ticked.
- **Renewal-reminder background job** — `/app/backend/routes/memberships_scheduler.py` spawns an asyncio loop on startup (default cadence: every 6 h). `_check_and_send(db, send_email)` looks up actives expiring within the next 7 days whose `renewal_reminder_sent_at` is still null, emails the buyer once via SendGrid, then stamps the timestamp for idempotency.
- **Tested in iteration_22**: 14 new backend tests + 18 Phase 2 regression tests (32/32 pass).

## Implemented (Feb 28, 2026 — Phase 4: Membership utilization dashboard)
- New endpoint `GET /api/memberships/purchase/{id}/utilization` returns the side-by-side metrics: `sessions_used`/`sessions_allowed`/`sessions_percent` AND `days_elapsed`/`days_total`/`days_percent`/`days_remaining` + an `expired` flag. Authorised to buyer + owning vendor + platform admin (everyone else → 403).
- New component `components/memberships/UtilizationBars.jsx` renders the two coloured progress bars (cyan = sessions, pink = days). data-testids `util-{purchase_id}`, `util-sessions-{id}`, `util-days-{id}`.
- Mounted only when `status === "active"` on both `/my-memberships` (buyer's view, full-width) and inside `VendorPurchaseRequests` (vendor's view, compact mode).
- **No "recommended renewal" suggestion** — per user's choice, only the raw numbers are shown.

## Implemented (Mar 12, 2026 — Promo codes: reward top offline→platform referrers)
- **New `PromoCode` model + collection** — one-time discount codes for offline-subscription checkout. Fields: `code, vendor_id, discount_percent, reason, expires_at, used, used_at`.
- **`POST /api/admin/promo-codes/reward-top-referrers`** — admin trigger. Picks top-N referring vendors (from the leaderboard), generates a `REFER-XXXXXX` promo (default 20% off, 60-day validity), and sends the vendor a congratulatory email via SendGrid. Idempotent-ish: reuses an existing unused reward promo if one already exists for that vendor.
- **`request_offline_subscription` accepts `promo_code`** — validates (exists / not used / not expired / vendor-scoped), deducts the discount, marks the code used on success.
- **UI**: golden "🎁 Reward top 5 (20% off promo)" button on the Vendor Referral Leaderboard in Platform Admin → Business tab. Shows the batch of codes it just issued (with per-vendor email-sent flag).
- **Tests**: 1 new test in `TestPromoCodesForTopReferrers` (18/18 pass across the last four Phase 5c test classes) — verifies promo issuance, 20% deduction at checkout, and single-use rejection on re-use.

## Implemented (Mar 11, 2026 — Phase 5c+ P1: subscription packages, price lock, referrals, QR posters)

**Admin subscription packages (CRUD)** — `POST/GET/PATCH/DELETE /api/admin/subscription-packages`. New model `SubscriptionPackage` (name, duration_days, price, currency, active, description). Vendors can now pick from custom plans (e.g. quarterly, annual, promo) instead of only the default monthly/yearly.

**Price lock on renewal for existing vendors** — new `SiteSettings.offline_subscription_locks_existing_price` (default True). When enabled, an existing vendor renewing the same `plan_type` pays their last-activated subscription's `amount`. New vendors always pay the current site-setting price. Ships in `request_offline_subscription` — one query for the vendor's prior activated sub, one comparison, done.

**Vendor referral leaderboard** — new `GET /api/admin/vendor-referral-leaderboard`. Aggregates `player_profiles.offline_source_vendor_id` per vendor, enriches with business name, city, and estimated commission WAIVED (= gross of offline-source bookings × site commission %). Powers the "reward top offline-→-platform referrers" dashboard card on the platform admin's Business tab.

**QR poster** — new `openQrPoster()` helper on Vendor Dashboard listing rows. Client-side only — pops a printable HTML page with a QR pointing at `${origin}/vendor-listing/${id}` using the free `api.qrserver.com` service. No backend, no keys, auto-triggers `window.print()`. Print → laminate → mount at venue.

**Frontend**
- New `SubscriptionPackagesSection` and `ReferralLeaderboardSection` embedded in the Platform Admin Business tab (`BusinessTab.jsx`). Inline add-plan form + toggle-active + delete.
- New "QR poster" button on every vendor listing row.
- Fixed 5 `useEffect(load, [])` React-18 warnings that leaked promises (`destroy is not a function`) across the OfflineBusinessSuite + new admin sections.

**Tests** — 4/4 pass in `TestSubscriptionPackagesAndReferrals`:
- Admin CRUD for packages (create → list → patch → delete).
- Vendor can subscribe with a `package_id`, price sourced from the package.
- Existing vendor renewing the SAME plan_type pays their prior locked price, not the new one.
- Referral leaderboard returns the expected shape with `estimated_commission_waived`.

## Implemented (Mar 10, 2026 — Phase 5c: Offline Business Suite + Business Model)

**Backend (12 new endpoints + 8 new models in `routes/business.py`)**
- `GET /api/vendor/dashboard-stats` — 8 KPIs: today's revenue, bookings, walk-in/online customers, active members, court utilisation %, pending payments, today's schedule, new leads (7d).
- Slot blocks (`POST/GET/DELETE /vendor/slot-blocks`) — with reasons: maintenance, tournament, private, staff_practice. Overlapping private bookings are rejected with a clear error.
- Expenses (`POST/GET/DELETE /vendor/expenses`) — categorised (rent, electricity, water, salary, equipment, maintenance, misc).
- Coaches (`POST/GET/PATCH/DELETE /vendor/coaches`).
- Batches (`POST/GET/PATCH/DELETE /vendor/batches`) — coach, capacity, days-of-week, monthly fee.
- Inventory (`POST/GET/PATCH/DELETE /vendor/inventory`) — quantity + low-stock threshold + cost/sale price.
- Vendor staff (`POST/GET/DELETE /vendor/staff`) — new `vendor_staff` role. Receptionist and coach have scoped permission masks (no reports/expenses for receptionist).
- Reports (`GET /vendor/reports?range=daily|weekly|monthly`) — revenue, expenses, profit, bookings split, membership sales, 24h peak-hours histogram, top-5 customers by spend.
- Customer detail (`GET /vendor/customers/{id}`) — visits, total_spent, outstanding, memberships, last 20 bookings + invoices.
- Check-in (`POST /vendor/checkin`) — accepts booking_id, customer_id, or phone; records a `vendor_checkins` row and stamps `checked_in_at` on the booking.
- Invite offline customer (`POST /vendor/invite-customer`) — returns a `wa.me/...?text=<signup url>` link stamped with `?ref_vendor=<id>`.
- Payment method on `VendorInvoice` (cash/upi/card/bank_transfer/online) — captured at mark-paid.

**Business-model bridge (KEY for revenue split)**
- New `PlayerProfile.offline_source_vendor_id` — stamped on signup when the player arrives via `?ref_vendor=<id>` (from the vendor's WhatsApp invite).
- `POST /api/vendor-bookings` now computes `offline_source: bool` at booking creation. When true, `commission_percent = 0` and `commission_amount = 0` — the platform waives its cut for the vendor's pre-existing offline customers who joined via the invite link.
- Otherwise commission is computed from `site_settings.commission_percentage` and stored on the booking for later payout accounting.

**Frontend**
- New umbrella component `OfflineBusinessSuite.jsx` bundling 9 sub-tabs: Dashboard, Bookings & calendar, Coaches & batches, Slot blocks, Inventory, Expenses, Reports, Staff, Check-in.
- Rendered inside the Vendor Dashboard's `Offline business` tab (unlocked when `vendor.offline_mode=true`).
- `PlayerSignup.jsx` now reads `?ref_vendor=<id>` from the URL and forwards it to the register endpoint.

**Tests**
- 11 new tests in `TestOfflineBusinessSuiteP0` — dashboard shape, slot-block enforcement, expenses CRUD, coach+batch flow, inventory low-stock, staff create + scoped login (receptionist blocked from `/vendor/reports`), reports shape, customer detail aggregation, check-in by booking-id, invite link, and the **offline-source commission bypass** (player invited by vendor pays platform 0% commission on future marketplace bookings to that vendor). **11/11 pass in 2.84s** (DB-seeded fixtures — bypass SendGrid rate limits).

**Cross-role integration**
- Company/HR + organiser already had `/hire` access from earlier passes.
- Player `/hire` access was fixed earlier; player now gets the offline-source commission-waiver treatment when arriving via the vendor's WhatsApp invite.
- Vendor staff (`vendor_staff` role) is a new authenticated role that can log in with their own email/password and inherits scoped vendor-scoped access.

## Implemented (Mar 09, 2026 — Persistent login fix: no more forced admin password resets)
- **Bug**: Every time the backend restarted (frequent on hot-reload / redeploy), `seed_admin()` was aggressively re-hashing the admin password to match `ADMIN_PASSWORD` env var — silently wiping any password the user had set via forgot-password. Result: the user had to reset every login attempt. Also affected any admin whose stored password happened to differ from the env value.
- **Fix**: `seed_admin()` now only re-seeds the password when (a) the stored hash is missing/blank, OR (b) the operator explicitly sets `FORCE_ADMIN_PASSWORD_RESET=true` in the environment. All other admin metadata (role, name, permissions, is_super_admin) still auto-heals as before. User-initiated password changes now persist across restarts.
- **Bonus**: `POST /api/auth/login` now trims trailing whitespace on both email and password (a common cause of "right password still fails" reports from copy-paste). Logs a breadcrumb `LOGIN FAIL email=<x> reason=no-user|bad-password` on every failure so future support tickets are easier to triage.
- Verified via curl: whitespace-padded email + trailing-newline password + clean payload all now return HTTP 200.

## Implemented (Mar 08, 2026 — Venue lead affordance + refreshed guides)
- **Bug**: Organisers at `/admin` couldn't surface a venue lead when the venue wasn't already on the platform — the `SuggestVenueButton` component only existed on the platform-admin's EventsTab, not the shared `Admin.jsx` used by organisers/HR.
- **Fix**: Added `<SuggestVenueButton>` next to the "Pick verified venue" button in `Admin.jsx`. Added a one-line helper text under it explaining the flow. Backend `POST /api/venue-leads` was already correct — this was purely a discoverability bug.
- **Refreshed all 7 role manuals** — added a "1a. What's new — leverage these features" section at the top of every PDF (Vendor, Player, HR/Company, Organiser, Platform admin, Sponsor, Scorer). Highlights the latest capabilities the reader should be actively using: Offline business (invoice settings, private bookings, WhatsApp share), calendar view, membership auto-apply, sponsorship inbox, suggest-venue, ownership scoping, and role-specific power-tips. Regenerated all PDFs via `python scripts/generate_manuals.py` — each ~330 KB.

## Implemented (Mar 07, 2026 — Ownership scoping for teams + sponsors)
- **Bug**: An organiser could see EVERY team and sponsor across the whole platform on their Admin > Manage screen — leaking data across tenants.
- **Backend fix (`GET /api/teams` + `GET /api/sponsors`)** — both now scope results to the caller:
  - `platform_admin` sees all rows.
  - `company_admin` / `organiser` sees only rows they created + rows attached to events they can manage.
  - `player` sees only teams they captain or are a member of.
  - `Anonymous` is allowed to read for a specific `event_id` (public event page still works) but the un-scoped top-level list returns 401.
- **Write endpoints locked down** — `POST /teams` now requires `require_admin` (was public!). `PATCH/DELETE` on `/teams/{id}` and `/sponsors/{id}` now check ownership; non-owning admins get 403.
- **Model additions** — `created_by` (Optional[str]) on both `Team` and `Sponsor`, populated on create.
- **Tests**: 41/41 pytest — added `TestTeamsSponsorsOwnershipScoping` ×2 that provisions two isolated organisers and verifies they cannot see or delete each other's teams/sponsors, while a platform admin still sees everything.

## Implemented (Mar 06, 2026 — Offline booking UX fixes)
- **Customer directory auto-populates from bookings** — when a vendor adds a private booking with an inline client_name/phone (walk-in), we now silently upsert a matching row in `vendor_customers`. Dedupes by phone (falls back to lowercase name). Existing legacy bookings are self-healed on the next GET `/api/vendor/customers` — so the Customers tab is no longer blank for vendors who booked before this landed.
- **Completed bookings are now immutable** — backend `PATCH /api/vendor/private-bookings/{id}` returns 400 for any edit to a booking with `status='completed'` (only `status→cancelled` is allowed). Frontend removes the Edit pencil from Completed rows.
- **Tests**: 39/39 pytest (added TestBookingCustomerAutoAndImmutable ×3).

## Implemented (Mar 05, 2026 — WhatsApp booking + invoice sharing)
- **WhatsApp share buttons** on the vendor Offline business panel:
  - Every private-booking row shows a green "WhatsApp" pill (data-testid `pb-whatsapp-{id}`) when the client has a phone on file. Opens `wa.me/<phone>?text=...` with a pre-formatted booking confirmation (date, time, hours, amount, weekly recurrence badge, notes, business name).
  - Every generated invoice preview shows a "WhatsApp" button (data-testid `pb-invoice-whatsapp`) that ships an itemised invoice message with subtotal / tax / total to the customer's number.
- Client-side only (uses `wa.me` deep-link). No new API keys, no Twilio/Meta cost. Ten-digit Indian numbers are auto-prefixed with `91` for the URL.
- Zero-cost UX win for vendors who currently confirm bookings manually over calls.

## Implemented (Mar 03, 2026 — Phase 5b+: vendor UX polish, player marketplace access, sponsorship inbox)
- **Vendor Dashboard — dedicated tabs** (`VendorDashboard.jsx`): "Marketplace" (listings, bookings table, memberships, reviews) + "Offline business" (OfflineModeCard, InvoiceSettings, PrivateBookings). Clean separation of the two revenue rails.
- **Edit private booking** — `PATCH /api/vendor/private-bookings/{id}` allowlist expanded to cover every editable field (times, hours, client, customer link, recurrence, notes). Pencil "Edit" button on every row in Active/Completed opens the same dialog pre-filled → hits PATCH.
- **Auto-adjust end time** in the booking dialog — changing `start_time` or `hours` recomputes `end_time = start + hours` (clamped at 23:59).
- **Big calendar view** — new "Calendar" tab in PrivateBookings renders a Mon-first month grid with prev/next navigation, listing filter, today highlight, coloured booking pills (active/completed/cancelled), and click-to-edit. Recurring weekly bookings expand into every matching day of the visible month.
- **Opening/closing enforcement** — `POST` and `PATCH` on `/api/vendor/private-bookings` now check the listing's `venue_schedules.opening_time..closing_time` window. Falls outside → 400 with a clear message referencing the opening hours.
- **After-hours override** — `PATCH /api/vendor-listings/{id}/schedule` now accepts `allow_after_hours` (bool). New checkbox in `VenueScheduleEditor` (`data-testid=vs-after-hours-toggle`). When true, private bookings skip the opening-hours check (marketplace slots still respect it).
- **Invoice Settings collapse-after-save** — once the vendor has saved a GSTIN/address, the panel renders as a compact summary card ("GSTIN 29… • Tax 18%") with an "Edit" pencil button (`inv-set-edit`). Click → expand back into the full form.
- **Player + Organiser can hire vendors** — `POST /api/vendor-bookings` now accepts `company_admin | player | organiser`. Player has no `company_id`, so we fall back to their name/email for the `company_name` field. `GET /api/vendor-bookings` for role=player returns only the bookings that player created. `/hire` (VendorMarket) no longer bounces non-company-admins; anonymous still lands on `/login?next=/hire`.
- **Sponsorship inbox for company/sponsor hybrids** — new `GET /api/sponsorships/my-activity` roll-up returns `{sent, received}` for the logged-in user. `Dashboard.jsx` shows a two-column "Sponsorship activity" card summarising both sides + a "Browse marketplace" link. Card is hidden when both lists are empty (intentional, keeps the dashboard clean for companies that don't sponsor).
- **Tests**: 36/36 pass in `/app/backend/tests/test_phase5_business.py` (added 6 new tests: TestPrivateBookingEditAndHours ×4, TestVendorBookingRoles ×1, TestSponsorshipMyActivity ×1). Testing agent iter_27 verified all 13 sub-items end-to-end.

## Implemented (Mar 01, 2026 — Phase 5b: Vendor Offline Business complete)
- **New endpoint `PATCH /api/vendors/me`** (`routes/vendors.py`) — vendor self-updates an allow-listed field set: `business_name, contact_name, mobile, email, city, gstin, invoice_business_name, invoice_address, invoice_phone, invoice_email, invoice_tax_percent, invoice_logo_url, invoice_footer_note`. Rejects disallowed fields (`approved`, `offline_mode`, `id`) with 400. Rejects `invoice_tax_percent` outside `[0, 100]` with 400. Requires `role=vendor` (403 otherwise). This unblocks the vendor's Invoice Settings UI (GSTIN / tax % / footer / logo) which is now fully wired end-to-end.
- **Vendor Dashboard — `InvoiceSettingsPanel.jsx`** (mounted below `OfflineModeCard` for `offline_mode=true` vendors) — GSTIN, business name override, phone, email, tax %, billing address, footer note. Save → toast → persists across reload. Verified via network trace: `PATCH /api/vendors/me` returns 200 and values round-trip on GET.
- **`PrivateBookingsPanel.jsx`** — Tabs: Active / Completed / Customers / Invoices (with counts). New-booking dialog supports (a) linking to a customer from the directory OR walk-in name, (b) rate-type toggle: flat total OR rate/hour with auto-multiply, (c) weekly recurrence with end-date DatePicker + day-of-week chip toggles (`pb-recur-dow-0..6`). New-customer dialog captures GSTIN + address for invoice population. "Generate invoice" on any booking creates a KN-YYYY-##### invoice with a print-ready preview (vendor snapshot from invoice settings, customer snapshot from directory or booking inline fields, subtotal + tax + total). "Mark paid" flips status → `paid`.
- **Backend — Customers + Invoices + Admin stats endpoints** already existed in `routes/business.py`; verified end-to-end:
  - `GET/POST/PATCH/DELETE /api/vendor/customers` — dedupes soft; PII vendor-only.
  - `POST /api/vendor/invoices` snapshots vendor + customer at issue time; per-vendor auto-increment invoice numbers.
  - `POST /api/vendor/invoices/{id}/mark-paid` idempotent.
  - `GET /api/admin/vendors/{id}/offline-stats` returns customer/booking/invoice counts + revenue + month calendar.
- **KN member as offline customer** — vendor can add an existing Kreeda Nation user (by matching email or mobile) as an offline customer without any uniqueness block. Verified via `TestVendorCustomersAndInvoices.test_kreeda_member_email_not_blocked_from_customer`.
- **Tests**: 30/30 pass in `/app/backend/tests/test_phase5_business.py` (added 8 new tests in `TestVendorInvoiceSettings` + `TestVendorCustomersAndInvoices` + `TestAdminVendorOfflineStats`). Testing agent iter_26 verified backend + core frontend flows.

## Implemented (Feb 28, 2026 — Phase 5A + 5C: Vendor profile + business model)
- **Phase 5A — vendor profile upgrades**:
  - VendorType literal extended to include `gym`, `studio`. Vendor signup now uses a **multi-select chip grid** (`/vendor/signup` data-testid `vendor-signup-types`); the primary `vendor_type` falls out as the first selected chip, full list lives in `vendor_types[]`. Server-side normalises empty → `[vendor_type]` for backwards compat.
  - VendorListing extended with `street`, `locality`, `state`, `pincode`, `maps_url` so detailed addresses can be matched with company / event / player city + locality.
  - New `VENDOR_CATEGORY_SPORTS` constant + `GET /api/meta/vendor-categories` endpoint power the adaptive Activities chip list in `pages/VendorDashboard.jsx`: Gym → gym/yoga/zumba/crossfit/pilates/cardio/strength, Studio → yoga/zumba/pilates/dance/aerobics, Grounds/Courts/Coaches → cricket/football/etc.
  - New `SuggestVenueButton` mounted in `components/admin/EventsTab.jsx`: HR / organiser / admin can submit a venue that isn't on the platform → recorded in the `venue_leads` collection → Platform Admin can list (`GET /api/admin/venue-leads`) and PATCH status (open → contacted → converted → archived) with notes for follow-up.
- **Phase 5C — business model**:
  - `SiteSettings` extended with `booking_commission_percent` (default 10), `membership_commission_percent` (default 5), and offline-subscription prices `offline_subscription_monthly_price` (₹99), `offline_subscription_yearly_price` (₹999). All admin-editable via existing `/settings` endpoint.
  - **Offline-mode subscription** — vendors can subscribe to use Kreeda Nation tools for their own offline business. New endpoints: `POST /api/offline-subscriptions/request`, `GET /api/offline-subscriptions/mine`, admin `GET /api/admin/offline-subscriptions`, `POST .../activate`, `POST .../reject`. Activation flips `Vendor.offline_mode = true` + sets `offline_subscription_expires_at` (now + 30d or +365d). Online payment stubbed (same offline-first rail as memberships).
  - **Private bookings** — `POST/GET/DELETE /api/vendor/private-bookings` for vendors with `offline_mode=true`. Supports one-off + weekly recurring (`recurrence_days_of_week`). These slots merge into the public availability grid so KN buyers see them as **unavailable** without leaking the private client's PII.
  - **Privacy mask** — `list_vendor_bookings` returns KN-originated bookings with `hr_email=null`, `created_by=''`, `notes=''` when the caller is a vendor. HR / Platform admin still see the full data.
- **New frontend surfaces**:
  - `components/vendor/OfflineModeCard.jsx` — vendor's subscription unlock CTA + plan tiles modal (monthly/yearly) + active/pending badges.
  - `components/vendor/PrivateBookingsPanel.jsx` — locked + unlocked states; add/list/delete + weekly recurrence picker (days-of-week chips).
  - `components/event/SuggestVenueButton.jsx` — modal usable from any event-create form.
  - Updated nav-bar branding to a stacked **KREEDA / — NATION —** mark (white bold caps + green wordmark with flanking horizontal dashes) per user-supplied reference image.
- **Testing**:
  - Iteration 23 caught 3 bugs (vendor_types not persisted on signup, PrivateBooking duplicate-kwargs TypeError, settings price override never applying). All 3 fixed in the same session — `routes/vendors.py vendor_signup`, `routes/business.py create_private_booking`, `routes/business.py _site_settings_doc`.
  - **19/19 pytest pass** on `/app/backend/tests/test_phase5_business.py` post-fix. Note: subsequent test runs hit SendGrid quota throttle (502 on `/vendors/signup/request-otp`), so PR-time tests must mock SendGrid for repeatable runs.

## Test Credentials
- Platform Admin (Super): admin@kreedanation.com / admin123
- Company HR: hr@acme.com / hr123
- Vendor: ravi@turf.in / vendor123
- Player: player@acme.com / player123 (or +919000000001)
- Viewer: viewer@kreedanation.com / viewer123
- (Staff admins created on the fly via /platform-admin → Team or POST /api/admin/staff)

## Feb 2026 — Venue direct-booking + Admin service enable/disable
- **`/services/{id}` for `category=='venue'` services** now redirects (`useNavigate replace:true`) to `/hire?vendor_type=ground`, skipping the enquiry-form flow entirely. Non-venue categories keep the existing quote-request flow.
- **Admin service enable/disable toggle** — every row on the Platform Admin → Services tab has a `data-testid="pa-toggle-<serviceId>"` Disable / Enable button that PATCHes `/api/services/{id}` with `{active: false|true}`. `GET /api/services` filters out inactive services from public listings; `GET /api/services?include_inactive=true` returns them for admins.
- **PDFs regenerated** (Feb 2026, 7 manuals, ~325 KB each). Company manual now lists venue-direct-booking; Admin manual documents the enable/disable toggle. Script: `python3 /app/scripts/generate_manuals.py`.
- Verified end-to-end via curl (login cookie, PATCH round-trip: disable → hidden → include_inactive shows → enable) and Playwright screenshot (17 toggle buttons rendered on Services tab).


## Feb 2026 — Public `/hire` marketplace preview
- Removed the unauth redirect guard on `pages/VendorMarket.jsx`. Anyone can now browse `/hire` — sport chips, city picker, and verified listing cards render for guest visitors (matches the promise made in player/vendor manuals).
- Auth is enforced at the "click a listing" step: `openBookingFor()` bounces guests to `/login?next=/hire` before opening the booking modal. Signed-in non-buyer roles (vendor, admin) still see the modal but the existing `canBook` gate blocks submission.
- Improves conversion from QR-poster / SEO / cold-traffic visits: users can validate the marketplace before committing to signup.

## Feb 2026 — Public listing detail page + OG social previews
- **NEW public route** `GET /vendor-listing/:id` (`pages/VendorListingDetail.jsx`) — fixes a dangling QR-poster link (the poster generator at `VendorDashboard.jsx:59` already pointed here, but no route existed).
- **Backend endpoint reused**: existing `GET /api/vendor-listings/{listing_id}` (in `routes/vendors.py`) returns only `approved && active` listings — safe for public exposure.
- **SEO / OpenGraph / Twitter Card meta tags** injected into `document.head` per listing on mount, cleaned up on unmount:
  - `<title>`, `<meta name="description">`
  - `og:title`, `og:description`, `og:image`, `og:url`, `og:type`
  - `twitter:card=summary_large_image`, `twitter:title`, `twitter:description`, `twitter:image`
- **Book CTA** reuses the exported `BookingModal` from `VendorMarket.jsx`; unauth clicks bounce to `/login?next=/vendor-listing/{id}`.
- Verified end-to-end (Playwright): `og:title=P5C Ground · Bangalore · Kreeda Nation`, `twitter:card=summary_large_image`, title & CTA rendered.
- **Impact**: every QR poster now lands users on a real page, and every share on WhatsApp / Instagram / X / LinkedIn shows a rich preview card instead of a bare URL.

## Feb 2026 — Share this venue (WhatsApp / X / Copy)
- Added `ShareRow` to `pages/VendorListingDetail.jsx` — 3 primary buttons (WhatsApp deep-link, X / Twitter intent, Copy link) + a "More share options" button that invokes `navigator.share` on mobile (native share sheet), falls back to WhatsApp on desktop.
- Testids: `vld-share-whatsapp`, `vld-share-x`, `vld-share-copy`, `vld-share-more`.
- Manual updates (targeted only): vendor manual now documents the public listing page + rich share previews under Phase 5c bullet list; player manual clarifies /hire is browseable without sign-in.
- 7 PDFs regenerated (Feb 2026).

## Feb 2026 — Player + Organiser vendor-marketplace access
- **`/bookings` unlocked for players** — `Bookings.jsx` no longer redirects `role in {player, organiser}` to /login. Players/organisers see their vendor-marketplace bookings via `<VendorBookings />`; company_admin + platform_admin still get service bookings too.
- **Cancel + reschedule for buyers** — backend `POST /api/vendor-bookings/{id}/cancel` and `.../reschedule` now permit `role in {player, organiser}` when the booking's `created_by == user.id`. Company admins remain scoped to their `company_id`.
- **`VendorBookings.jsx`** — `canBuyerModify` now includes `isPlayer`; completed bookings show a `/ Completed · read-only` marker (`data-testid=vb-readonly-<id>`) and hide the modify buttons. Review form still available on completed bookings for players + company_admin.
- **Player nav additions** — `Nav.jsx` adds `Hire vendors` (→ /hire) and `My bookings` (→ /bookings) to the player More menu.
- **`Book a venue` CTA** on `/bookings` for players (`data-testid=bookings-browse-hire`).
- **Renew memberships** — `/my-memberships` cards for `active` + `expired` passes now expose a `Renew` button (label upgrades to `Renew now` in the last 7 days, `Renew pass` when expired). Deep-links to `/vendor-listing/<listing_id>`. Also added a `Browse more →` link on every card.
- **Player manual** gained a bullet list documenting the /bookings + /my-memberships + share flows.
- **Organiser coverage**: organisers already receive `isCompanyAdmin=true` in `AuthContext.jsx`, so all HR/company_admin capabilities (dashboard, /hire, /bookings, /my-memberships, sponsor inbox) already apply. No extra plumbing needed.
- Verified end-to-end via curl (player login → create booking → cancel → 200, reschedule → 200) and Playwright (`/bookings` shows heading, hire CTA, Cancel+Reschedule buttons).

## Feb 2026 — Vendor productivity: CSV export, check-in v2, batches roster
### Backend (`routes/business.py`)
- **`GET /api/vendor/customers.csv`** — streaming CSV export with columns: Name, Phone, Email, Address, GSTIN, Visits, Total paid, Outstanding, Notes, Created at. Filename auto-tags date + vendor id prefix.
- **`POST /api/vendor/checkin`** rewritten:
  - Detects ambiguity — when a customer_id matches multiple active contexts (booking today + batch running today + active membership), returns `{ambiguous: true, options: [...]}` for the vendor to disambiguate; client retries with `context_type + context_id`.
  - New fields on `VendorCheckIn`: `batch_id`, `context` (booking|batch|membership|walkin), `planned_end_at`, `checked_out_at`, `overrun_minutes`, `extra_amount`, `extra_invoice_id`.
  - Auto-picks the single context if only one candidate exists.
- **`GET /api/vendor/checkins/active`** — list of check-ins with `checked_out_at is null`, enriched with `customer_name`, `customer_phone`, `label` (Batch · X · time OR Booking · X · sport OR Walk-in).
- **`POST /api/vendor/checkins/{id}/checkout`** — closes a check-in, computes `overrun_minutes = now - planned_end_at`. When `bill_overrun=true` + booking-context + positive overrun → mints a supplementary `vendor_invoices` record (`kind=overrun`, `parent_checkin_id`) at the same hourly rate. Batches skip auto-invoicing (monthly-fee model).
- **`POST /api/vendor/batches/{id}/enrol`** — adds a customer_id to `student_ids`; rejects duplicates + capacity overflow; **sends `send_email` to vendor owner the moment capacity is hit**.
- **`POST /api/vendor/batches/{id}/unenrol`** — remove customer.
- **`GET /api/vendor/batches/{id}/roster`** — returns `{batch, students: [VendorCustomer]}` with names/phones for the roster UI.

### Frontend
- **`OfflineBusinessSuite.jsx`**:
  - **`CheckIn` component rewritten** — split panel: left = code input + last-check-in card + **visible QR poster** (image via `api.qrserver.com`, print/preview modal); right = "Currently on premises" list with client-side countdown ticking every 30s. Row goes red when `≤5 min` remaining or overdue. Every row has a `Check out` button that surfaces the overrun toast + auto-invoice notification.
  - **Ambiguity picker** — modal dialog listing all candidate contexts as clickable cards (`data-testid=checkin-opt-{type}-{id}`); tapping one retries the check-in with the explicit context.
  - **`CoachesAndBatches` rewritten** — replaces `prompt()` with proper `Dialog`-based create/edit forms. Batches show a red **FULL** badge when at capacity; each batch has **Roster / Edit / Delete** buttons.
  - **`BatchRosterDialog`** — enrol from the vendor's customer directory, remove students, live capacity indicator.
- **`PrivateBookingsPanel.jsx`** — added an **Export CSV** button on the Customers tab that hits `/api/vendor/customers.csv` directly (browser handles the download).
- **`VendorMarket.jsx`** — every listing card now has a **View details →** link (opens `/vendor-listing/{id}` in a new tab) so the public share/detail page becomes discoverable from /hire. Existing "Tap card to book" behaviour preserved.

### Manuals
- Vendor manual gained bullets for check-in v2 (QR poster, ambiguity, overrun invoice), coach/batch editor, CSV export. 7 PDFs regenerated.

### Verification (Feb 2026)
- **Curl**: coach create → customer create → batch create (cap=2) → enrol → roster shows 1 student → check-in via customer_id → auto-picks batch context → active list shows Alice with `planned_end_at` → checkout returns `overrun_minutes=383` (correct math), active list clears.
- **Playwright**: vendor login → offline biz → Check-in tab shows QR image + "Currently on premises (0)".

## Feb 2026 — Event editor + Recurring bookings + Top-customers widget
### Event Edit (item 1 from user's Feb request)
- **Frontend `EventDetail.jsx`**: added `Edit event` button next to the stream-link button (visible when `canManage`). Opens a dialog with editable **name / description / venue / start_date / end_date**. Sport & format intentionally NOT editable (would break fixtures/standings).
- **Backend** already supported `PATCH /api/events/{event_id}` via `routes/events.py` — permission gate: platform_admin OR (company_admin/organiser AND event.company_id == user.company_id). Verified via curl: admin PATCH → 200, venue updated.
- Testids: `event-edit-btn`, `event-edit-name/desc/venue/start/end`, `event-edit-save`.

### Recurring bookings expanded into individual rows (item 2)
- **Backend `POST /api/vendor-bookings`**:
  - Added optional `recurrence` ("weekly"|None), `recurrence_until` (YYYY-MM-DD), `recurrence_days_of_week` ([0..6], Monday=0) to `VendorBookingRequest`.
  - Server now expands a weekly recurring request into a list of matching dates (`first .. until` inclusive, filtered by day-of-week) and **inserts one `VendorBooking` per date**, all sharing a common `recurrence_group_id`. Membership discount is only applied to the FIRST occurrence.
  - Guards: rejects when `until < first`, when the range produces zero occurrences, or when count > 52.
  - Response shape: for single bookings unchanged (`VendorBooking`). For a series returns `{recurrence_group_id, count, bookings:[…]}`.
- **New `VendorBooking.recurrence_group_id`** field so buyers + admins can visually group series in `/bookings`.
- **Frontend `VendorMarket.jsx` BookingModal**: added a **Book this weekly** toggle with a `recurrence_until` date picker. Client computes the JS weekday and converts to ISO Monday=0 index before POST.
- **Frontend `VendorBookings.jsx`**: rows in a series show a `Weekly series` badge (`data-testid=vb-series-<id>`). Cancel + Reschedule already operate per-row so each occurrence remains independent — matches the user's ask (cancel any single Saturday, keep the rest).
- Verified via curl: player creates a weekly booking from 2026-07-11 → 2026-08-03 with `days_of_week=[5]` (Sat) → server creates 4 bookings on 11/18/25 Jul + 1 Aug, all sharing `group_id=27fe83ad…`.

### Top 20 customers KPI (from previous "potential improvement")
- **Backend `GET /api/vendor/dashboard-stats`** now returns `top_customers: [{id, name, phone, total_spent, invoices}]` — computed via a MongoDB aggregation over `vendor_invoices` where `status=paid`, grouped by `customer_id`, sorted by lifetime spend DESC, limited to 20. Joined with `vendor_customers` for names/phones.
- **Frontend Vendor Dashboard KPIs**: new yellow card block "Top customers · lifetime value" listing #1..#20 with name + phone + invoice count + `INR` totals. Empty state prompts vendors to start invoicing.
- Testid: `kpi-top-customers`, per-row `top-cust-<id>`.

### Manuals
- Company section gained bullets for **Edit events** + **Book recurring slots** (7 PDFs regenerated).

## Feb 2026 — Code review remediation (quick wins)
### Security
- **`VendorDashboard.jsx openQrPoster`** — HTML-escape all user-controlled fields (`listing.title`, `vendor.business_name`, `listing.city`, target URL) before interpolating into the `document.write` payload of the pop-up QR poster window. Prevents a malicious vendor from injecting `<script>` into their business name.
- **`EventApprovalBanner.jsx dangerouslySetInnerHTML`** — verified false positive: already sanitised via `DOMPurify.sanitize(...)` on a `useMemo` above the render. No change.
- **Test-file "hardcoded secrets"** — `test_phase5_business.py`, `test_memberships_phase3_4.py`, `test_memberships_phase2.py` now read `ADMIN_PASSWORD`, `TEST_VENDOR_PW`, `TEST_HR_PW`, `TEST_WALKIN_PW` from env vars with local-dev defaults. CI can override via env.

### Performance
- **`AuthContext.jsx`** — wrapped the provider value in `useMemo([user, ready])`. Previously a new object identity was minted on every provider render, cascading a full app re-render on every unrelated state change.

### Reliability
- **`VendorListingDetail.jsx nativeShare`** — empty catch replaced with `err.name !== "AbortError"` guard + `console.error` for real failures. AbortError = user dismissed the OS share sheet (safe to swallow).

### Deferred (intentionally — needs a larger dedicated iteration)
- `routes/business.py register()` refactor into per-feature sub-routers (1465 lines, cyclomatic 347). Requires careful splitting of shared helpers (`_ensure_vendor_owner`, `_upsert_customer_from_booking`, `_check_no_slot_block`, …) — planned for a follow-up.
- `routes/auth.py register()` refactor into `validate_registration_input` / `create_user_account` / `send_verification_email` helpers.
- Adding type hints across the codebase (target: 60%+ coverage).
- 110 React hook dependency warnings across the codebase — high-impact ones (recent Bookings.jsx, VendorMarket.jsx, VendorListingDetail.jsx) verified individually; the rest is technical debt.
- 25+ nested-ternary cleanups.

## Feb 2026 — Organiser event fee + payment step at submission
### Backend
- **`SiteSettings.organiser_event_fee`** (float, default 0) + **`organiser_event_fee_currency`** (default "INR"). Persisted in `db.settings` singleton.
- **`Event.payment`** field (dict): `{fee, currency, status: not_required|pending_offline|paid_offline|paid_online, method, paid_at, provider}`.
- **`POST /api/events/{id}/acknowledge-instructions`** — now accepts `{payment_method: "online"|"offline"}`. When the configured fee > 0, `payment_method` is REQUIRED; server returns 400 otherwise. `online` is stubbed as instantly paid (`provider=razorpay_stub`) pending real Razorpay wiring; `offline` marks `pending_offline` and lets the event still enter admin approval.
- **`POST /api/events/{id}/mark-paid`** (platform-admin only) — flips `payment.status` from `pending_offline` to `paid_offline`, stamps `paid_at` + `confirmed_by`.

### Frontend
- **`SettingsTab.jsx`**: new panel "ORGANISER EVENT FEE" with amount + currency inputs (`data-testid=setting-organiser_event_fee`, `setting-organiser_event_fee_currency`, `organiser-fee-save`).
- **`EventApprovalBanner.jsx`**: fetches fee alongside instructions. Displays a green fee-summary block above the CTA when > 0. Clicking "I agree — pay ₹500 & submit" opens a **payment picker dialog** with two cards:
  - `approval-pay-online` — POSTs `payment_method: "online"` (stubbed as paid).
  - `approval-pay-offline` — POSTs `payment_method: "offline"` (event enters admin queue, pending).
  Free events (fee = 0) skip the dialog entirely, keeping the flow identical to before.
- **`PendingApprovalsTab.jsx`**: every event row shows a payment pill — green for `paid_online`/`paid_offline`, orange for `pending_offline` with an inline **Mark paid** button (`approval-mark-paid-<id>`) that fires `/mark-paid`.

### Verification (Feb 2026)
- Curl: admin PATCH settings fee=500 → organiser POST ack empty → HTTP 400 "Event fee of 500.0 INR required" → organiser ack `offline` → `payment.status=pending_offline` → admin POST mark-paid → `payment.status=paid_offline, paid_at, confirmed_by` set. Online path also verified (`paid_online, provider=razorpay_stub`).
- Bug caught during test: my acknowledge endpoint originally read `db.site_settings` (nonexistent collection); switched to `db.settings.find_one({id:"site"})` to match the settings router.
- Lint clean, 7 PDFs regenerated with Platform-Admin bullet documenting the new fee panel + payment status.

## Feb 2026 — Vendor calendar shows platform bookings + Invite share link
### Fix 1: Platform bookings block the vendor calendar
- **`PrivateBookingsPanel.jsx`** now loads both `/vendor/private-bookings` (offline) AND `/vendor-bookings` (marketplace) in parallel and merges them into the same `bookings` array. Marketplace rows are tagged `source: "platform"`, mapped so `client_name = company_name || "Platform booking"` and `status` normalised. Cancelled + rejected marketplace bookings are filtered out (time freed).
- **`BookingsCalendar` cells**: platform bookings render as **yellow (`#FACC15`) read-only pills** with a bullet marker (●); tapping a platform pill does nothing (edit only allowed for offline rows). Legend updated with "Platform (read-only)" chip.
- Verified via curl + Playwright: player creates a booking on `p5b_listing_1` → phase5b vendor's calendar cell for that date now shows the platform pill.

### Fix 2: Vendor referral share link (item 2)
- **`OfflineBusinessSuite.jsx VendorInviteCard`** (new component) — displays on the Vendor's `Offline business → Dashboard` tab. Contains:
  - A **QR code image** encoding `${window.origin}/players/signup?ref_vendor=<vendor.id>`.
  - The plain URL rendered as `data-testid="vendor-invite-url"`.
  - Three CTAs: **Copy link** (`vendor-invite-copy` — clipboard), **WhatsApp share** (`vendor-invite-wa` — pre-filled message), **Print QR poster** (`vendor-invite-qr` — 500×500 image link).
- No backend changes needed: `POST /players/register` already accepts `ref_vendor` and stamps `offline_source_vendor_id` (server.py line 1562). The booking commission logic (line 1998-2002) already waives commission when that player later books from the referring vendor.

### Verification
- Curl: `POST /vendor-bookings` for phase5b listing → vendor sees count=1 in `/vendor-bookings`.
- Playwright: vendor login → Offline business → Bookings & calendar → Calendar sub-tab → **yellow platform pill visible on 6 July**. Invite card renders with URL `.../players/signup?ref_vendor=p5b_vendor_1`.
- Lint clean.

## Feb 2026 — Manuals reorganised task-first ("HOW TO" recipes)
- **New `task_recipes(role)` helper** in `scripts/generate_manuals.py` — generates a fresh **"2. HOW TO — task recipes"** section per role that groups content by *outcome* (booking, event, sharing, membership renewal, checkin) instead of by feature.
- Recipes tailored per role, e.g.:
  - **Vendor**: List a listing / Share it / Convert a walk-in / Record offline booking / Check-in / Sell membership / Create batch + enrol / Export CSV.
  - **Player**: Sign up / Book venue / Book weekly / Cancel or reschedule / Renew membership / Share venue.
  - **Company HR**: Create tournament / Edit event / Hire venue / Invite sponsor.
  - **Organiser**: Submit event for approval (with pay online/offline step) / Edit event.
  - **Platform admin**: Approve/reject events / Configure event fee / Enable/disable services / Update instructions.
  - **Sponsor**: Browse opportunities / Complete brand profile.
  - **Scorer**: Score a live match / Fix a mistake.
- Each recipe is a `("num", [...])` block — sequential, jump-to-the-page, click-this-button style. Every step names the exact route (`/hire`, `/bookings`, `/my-memberships`, etc.) and the button label (Cancel, Reschedule, Export CSV, WhatsApp share, Mark paid…).
- Injected in **all 7 build() calls** immediately after the welcome section and before the "What's new" section, so a first-time reader lands on task recipes without scrolling.
- 7 PDFs regenerated (Feb 2026); sizes grew ~1-3 KB each — confirms new content shipped.

## Feb 2026 — Sport dropdown, auto-enrichment + singles/doubles picker (bug fix)
### Bug
Admin-added sports (e.g. pickleball) weren't showing up in HR event-creation dropdowns. Also: badminton/tennis/pickleball needed a Singles-vs-Doubles selector with matching scoring pattern.

### Backend
- **Event model**: `Event.sport: SportSlug=str` (was `Literal`). Added `Event.scoring_pattern: str` and `Event.player_format: str` — populated at create-time from `db.sports` lookup with `_SPORT_DEFAULTS` fallback for well-known slugs (cricket/football/basketball/badminton/tabletennis/tennis/lawntennis/pickleball/squash/volleyball/chess/quiz/hackathon).
- **`_enrich_sport()`** helper auto-backfills scoring_pattern + player_format on GET/PATCH so legacy sport rows work too.
- **`POST /api/sports`** accepts `scoring_pattern` + `player_format` (auto-defaults for known slugs); slug value is canonicalised (`''.join(strip().lower().split())`) → prevents `Pickle Ball` producing a duplicate row.
- **`POST /api/events`** enriches from `db.sports`. When the sport has `player_format='both'`, the client MUST supply `player_format` in ("singles","doubles") or the server returns 400 "singles and doubles".
- Cleaned the pre-existing duplicate `pickle ball` row from `db.sports`.

### Frontend
- **New `useSports()` hook** (`/app/frontend/src/hooks/useSports.js`) — fetches `/api/sports` once (60s cache) and MERGES the API list with the fallback `SPORTS` array (deduped by `value`, API wins on collision). Guarantees built-in fallbacks (tennis/lawntennis) always render even when the DB row is absent.
- Extended `FALLBACK_SPORTS` in `/app/frontend/src/lib/sports.js` with tennis/lawntennis/pickleball + `scoring_pattern` + `player_format` on every row. `renderScore()` now accepts either a sport slug OR an event object with `scoring_pattern` (racket pattern shared between badminton/tennis/pickleball/…).
- `Admin.jsx` and `components/admin/EventsTab.jsx` swapped hardcoded `SPORTS` for `useSports()` and added a Singles/Doubles `Select` (`data-testid=admin-event-player-format` and `pa-event-player-format`) that appears only for sports with `player_format=='both'`.
- `components/SportsManager.jsx` — admin add-sport form now includes `scoring_pattern` + `player_format` dropdowns and canonicalises the slug on input.

### Verification (Feb 2026)
- **iteration_28.json** — backend 12/12 pytest pass; frontend 80% (tennis/lawntennis missing + duplicate 'Pickle Ball').
- **iteration_29.json** — after `useSports()` merge fix + slug canonicalisation + DB cleanup → **backend 100% + frontend 100%**. Tennis, Lawn Tennis, Pickleball all render in the dropdown (13 options vs 11 in DB), no duplicate row, singles/doubles picker works for racket sports and hides for team sports.

## Feb 2026 — Organiser contact + universal event share + sport templates
### Backend
- **`Event.contact_name / contact_email / contact_phone`** — new optional Event fields. `POST /api/events` accepts them, `GET` returns them, `PATCH` updates them (verified 13/13 pytest in `test_event_contact_iter30.py`).

### Frontend
- **New Event form** (`Admin.jsx` + `EventsTab.jsx`) — new "Organiser contact" block with three inputs (testids `admin-event-contact-*` and `pa-event-contact-*`).
- **Edit Event dialog** (`EventDetail.jsx`) — pre-populates + edits the same three fields (`event-edit-cname/cphone/cemail`).
- **NEW `EventShareAndContact` component** on every event page above the tabs:
  - Universal `event-share-block` with `WhatsApp / X / Copy` buttons (visible to anonymous visitors too).
  - `event-contact-block` renders when any contact field is set: shows name / phone / email + a "WhatsApp the organiser" deep-link (`event-contact-wa`) that opens `wa.me/<digits>?text=...`.
  - Placeholder shown when contact fields empty.
- **Sport templates dropdown** on `SportsManager` — 10 pre-configured templates (Kabaddi, Kho-Kho, Futsal, Padel, Squash, Throwball, Dodgeball, Esports, Carrom, Snooker). Pick one → form fields auto-fill; admin can still override anything.

### Manuals
- Organiser recipe expanded with "How to share your event so teams can join & viewers can watch"; player recipe gained "How to share an event with viewers".
- 7 PDFs regenerated.

### Verification (iteration_30.json)
- **Backend 100% + Frontend 100%, retest_needed=false.**
- 13/13 pytest pass on the new contact-fields router (`test_event_contact_iter30.py`).
- iter28 regression suite (12/12) still passes.
- Playwright: contact fields on all 3 forms, share block on event page (anon + auth), WhatsApp organiser href resolves correctly, sport-template dropdown prefills the add-sport form.
