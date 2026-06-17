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

## Backlog
### P0
- (none open) — Cricket flow complete & tested end-to-end.

### P1
- **Realtime via WebSocket** — `wss://.../api/ws` handshake fails through Kubernetes ingress. UI still refreshes via API on each action, but second-admin concurrent scoring won't propagate live until ingress is fixed.
- **Email integration** (Resend/SendGrid) — currently mocked. Awaiting API key from user. Used for: password reset, booking notifications.
- **Sponsor reach analytics** — track logo impressions across event pages for ROI.
- **Vendor/player test fixes** — 3 pre-existing failures in `test_vendor_player_settings.py` (profile list mobile mask, view count increment, booking flow). Not cricket-related; investigate separately.

### P2
- **Continue routes split** — extract `routes/auth.py`, `routes/events.py`, `routes/fixtures.py`, `routes/vendors.py`, `routes/bookings.py`, `routes/settings.py` following the cricket pattern.
- **Editor lists UUIDs** — VendorDashboard images + RegisterTeam players + PlatformAdmin fields/variants use array-index keys; refactor to stable `_uid`s (requires DB migration for vendor listings).
- **Refactor large functions** — `seed_services` (300 lines), `seed_demo_data` (113 lines), `get_standings` (cyclomatic 17), `listing_availability` (14).
- **Cricket enhancements**: Wagon wheel positions, partnership tracking widget, fall-of-wickets list, free-hit handling after no-ball, super over for tied limited-overs matches.

## Test Credentials
- Platform Admin: admin@kreedanation.com / admin123
- Company HR: hr@acme.com / hr123
- Vendor: ravi@turf.in / vendor123
- Player: player@acme.com / player123 (or +919000000001)
- Viewer: viewer@kreedanation.com / viewer123
