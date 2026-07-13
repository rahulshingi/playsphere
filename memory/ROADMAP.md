# Kreeda Nation — Roadmap

Prioritized backlog. Updated Jul 13, 2026.

## P0 — Next up
- **Razorpay integration** for memberships, event bookings, venue rentals. Awaiting user's Razorpay Key ID + Secret. Playbook via `integration_playbook_expert_v2`.
- **Dashboard shell rollout — remaining roles**. Apply the new dark-theme `DashboardShell` (currently on `/platform-admin/overview` + `/vendor/overview`) to HR, Organiser, Player, Sponsor dashboards.

## P1 — Near term
- **Financial & utilization CSV export** for vendor/admin — natural extension of `/api/admin/bookings-analytics`. Backend endpoint should stream `text/csv` with the same shape as the JSON payload; frontend adds a "Download CSV" button per analytics tab.
- **Equipment rentals & Value-Added Services (VAS)** for vendors — new listing sub-category with per-item pricing + inventory count.
- **Customer trust score** on player profiles — auto-lower on repeated no-shows; flag to vendors during booking confirmation.

## P2 — Quality of life
- **Split PRD.md** into PRD.md (personas + core requirements, static) + CHANGELOG.md (append-only iteration log) + ROADMAP.md (this file). PRD.md currently exceeds 900 lines.
- **Move `window.confirm` in remaining call sites to shadcn AlertDialog** — one instance in the UnifiedBookingsTable no-show flow is done (Feb 28, 2026); audit other call sites.
- **Range filter labels** across the app should use "Last N days" wording rather than "This week / This month" (fixed in UnifiedBookingsTable; check BookingsAnalyticsTab + others).
- **Backend type-hint coverage** — currently ~0% in tests/, low in routes/. Add `mypy` in CI.
- **Refactor `/app/backend/server.py`** (4900+ lines) into topic-organised modules under `backend/models/` and `backend/routes/`.
- **Rate-limit sweep** — booking_lifecycle now caches sweep timestamp per collection (60s throttle) but under high QPS on the same collection, the throttle is best-effort — consider a Redis lock if this becomes hot.

## P3 — Nice to have
- **WelcomeModal escape / backdrop dismissal** ✅ done Feb 28, 2026. Should keep this pattern (backdrop click + ESC) as a convention for every full-screen modal.
- **Sport-specific onboarding hints** — quiz walkthrough shown to new players / HR / organiser once (via WelcomeModal registered pattern).
- **Bracket recap PNG poster** — when an event completes, auto-compose an Instagram-story PNG with final bracket + Top 3 teams + MoM/Top Scorer awards + event sponsors' logos. Uses existing canvas share-card pipeline in `lib/shareBracketImage.js`.
- **Auto refund on event cancel** — when an organiser cancels a paid event, notify registered teams + auto-refund Razorpay payments once Razorpay keys are wired.

## Completed (rolling summary — see PRD.md for detail)
- ✅ Iter 49 (Jul 13, 2026): **Commission invoices + overtime billing + booking reopen**. New `commission_invoices` collection auto-materialised from completed platform bookings. Vendor sees pending/paid dues + reminder banner. Admin gets a dedicated "Commissions" tab with per-vendor rollup, single-invoice reminders, bulk reminders (`/admin/commission-invoices/send-reminders-bulk`), and mark-paid action (emails via SendGrid). New "Complete" flow captures `actual_end_time` → auto-computes overtime minutes (rounded to vendor's block: 15/30/60), overtime amount = hours × listing rate × `overtime_charge_multiplier` (vendor-configurable), and overtime commission = OT amount × commission %. Reopen action reverses wrongly-expired/cancelled bookings for both `private_bookings` and `vendor_bookings`. Membership panel restructured into Plans / Active customers / Requests tabs with a click-to-detail drawer. Offline-mode tab now shows a plain **Offline bookings** list (in addition to KPIs) with per-row Complete/No-show/Reopen. `top_customers` fix — Top customers now aggregate paid invoices + fulfilled offline + completed online bookings (was empty for vendors without formal invoices). PlatformAdmin reverted from DashboardShell to classic Nav+Footer for the user's preferred layout.
- ✅ Iter 48 (Jul 13, 2026): Dashboard nav fix + register-role picker + demo vendor seed.
- ✅ Iter 44 (Feb 27, 2026): Per-vendor commission (`max(pct, flat)`), admin bookings analytics, unified vendor bookings table, show-up tracking, 4-hour auto-expire (throttled sweep).
- ✅ Iter 43 (Feb 27, 2026): 7-item UX batch fix (past-slot filter, sport images, event dates, cancel event, anonymous /hire calendar, mobile-number signup, rotating homepage hero).
- ✅ Iter 43 (Feb 26, 2026): Dynamic Sports Config Phase 5 + Bracket View + share-bracket PNG.
- ✅ Iter 42 (Feb 26, 2026): Dynamic Sports Config Phase 3 + Phase 4 (team roles, match metadata, Swiss + Double-Elimination fixtures).
- ✅ Iter 41 (Feb 24, 2026): Pretty share URLs + Phase 2 Sport Config.
- ✅ Iter 40 (Feb 22, 2026): Player Tournaments MVP (local matches), auth by email OR mobile, HR `also_player` opt-in.
