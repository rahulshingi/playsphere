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

## Backlog
### P0
- (none open) — MVP complete & tested (31/31 backend, all critical UI flows pass)

### P1
- WebSocket-based real-time score push (currently fetch-on-demand)
- Per-player stats (goals, MoM, etc.) aggregated from match events
- Match-level player participation & substitutions
- Tighten CORS to explicit origins; brute-force lockout on /auth/login

### P2
- Email/Slack notifications for fixture & result updates
- Photo gallery & match highlights upload (object storage)
- Achievements/badges, season MVP, social shareable cards
- Payments for paid tournaments (Stripe) or sponsor billing

## Test Credentials
- Admin: admin@playsphere.com / admin123
- Viewer: viewer@playsphere.com / viewer123
