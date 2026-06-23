"""Generate Kreeda Nation PDF manuals for Vendors / Players / Companies / Platform Admin."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    Table, TableStyle, PageBreak, Image,
)
from reportlab.lib.enums import TA_LEFT

LIME = HexColor("#84CC16")
LIME_D = HexColor("#65A30D")
INK = HexColor("#0a0a0a")
GREY = HexColor("#525252")
PINK = HexColor("#EC4899")
CYAN = HexColor("#06B6D4")
RED = HexColor("#FF3B30")
LINE = HexColor("#d4d4d4")

OUT_DIR = Path("/app/frontend/public/manuals")
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOGO_PATH = Path("/app/frontend/public/kreeda-mark.png")


def styles():
    ss = getSampleStyleSheet()
    base = ParagraphStyle("base", parent=ss["BodyText"], fontName="Helvetica",
                          fontSize=10.5, leading=15, textColor=INK, alignment=TA_LEFT)
    h1 = ParagraphStyle("h1", parent=base, fontName="Helvetica-Bold",
                        fontSize=26, leading=30, spaceBefore=0, spaceAfter=6, textColor=INK)
    sub = ParagraphStyle("sub", parent=base, fontName="Helvetica",
                         fontSize=10, leading=14, textColor=GREY, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=base, fontName="Helvetica-Bold",
                        fontSize=14, leading=18, spaceBefore=14, spaceAfter=6, textColor=LIME_D)
    h3 = ParagraphStyle("h3", parent=base, fontName="Helvetica-Bold",
                        fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4, textColor=INK)
    note = ParagraphStyle("note", parent=base, fontName="Helvetica-Oblique",
                          fontSize=9.5, textColor=GREY)
    return base, sub, h1, h2, h3, note


def header_band(title, role_color, role_label):
    logo_cell = Image(str(LOGO_PATH), width=1.2 * cm, height=1.2 * cm) if LOGO_PATH.exists() else ""
    t = Table([[logo_cell, role_label, title]],
              colWidths=[1.6 * cm, 3.4 * cm, 13.0 * cm], rowHeights=[1.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), INK),
        ("BACKGROUND", (1, 0), (1, 0), role_color),
        ("TEXTCOLOR", (1, 0), (1, 0), white),
        ("BACKGROUND", (2, 0), (2, 0), INK),
        ("TEXTCOLOR", (2, 0), (2, 0), white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, 0), (1, 0), 10),
        ("FONTSIZE", (2, 0), (2, 0), 14),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "LEFT"),
        ("LEFTPADDING", (2, 0), (2, 0), 16),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def bullets(items, base):
    return ListFlowable(
        [ListItem(Paragraph(x, base), leftIndent=12, bulletColor=LIME) for x in items],
        bulletType="bullet", start="•", leftIndent=18, bulletFontSize=10,
    )


def numbered(items, base):
    return ListFlowable(
        [ListItem(Paragraph(x, base), leftIndent=12, bulletColor=LIME_D) for x in items],
        bulletType="1", leftIndent=22, bulletFontSize=10,
    )


def kv_table(rows, col_widths=(6 * cm, 11 * cm)):
    t = Table(rows, colWidths=list(col_widths))
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), HexColor("#fafafa")),
        ("TEXTCOLOR", (0, 0), (0, -1), GREY),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def callout_box(text, color, base):
    t = Table([[Paragraph(text, ParagraphStyle("c", parent=base, textColor=white, fontName="Helvetica-Bold", fontSize=10, leading=13))]],
              colWidths=[17 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def build(filename, role_label, role_color, title, tagline, sections):
    base, sub, h1, h2, h3, note = styles()
    out = OUT_DIR / filename
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.6 * cm,
                            title=f"Kreeda Nation — {title}", author="Kreeda Nation")
    story = [
        header_band(title, role_color, role_label),
        Spacer(1, 0.5 * cm),
        Paragraph("Kreeda Nation", h1),
        Paragraph(tagline, sub),
        Paragraph("Where Teams Compete, Connect &amp; Grow", note),
        Spacer(1, 0.5 * cm),
    ]
    for sec in sections:
        story.append(Paragraph(sec["title"], h2))
        if sec.get("intro"):
            story.append(Paragraph(sec["intro"], base))
            story.append(Spacer(1, 0.2 * cm))
        for block in sec.get("blocks", []):
            kind = block[0]
            if kind == "h3":
                story.append(Paragraph(block[1], h3))
            elif kind == "p":
                story.append(Paragraph(block[1], base))
                story.append(Spacer(1, 0.15 * cm))
            elif kind == "num":
                story.append(numbered(block[1], base))
                story.append(Spacer(1, 0.2 * cm))
            elif kind == "bul":
                story.append(bullets(block[1], base))
                story.append(Spacer(1, 0.2 * cm))
            elif kind == "kv":
                story.append(kv_table(block[1]))
                story.append(Spacer(1, 0.2 * cm))
            elif kind == "tip":
                story.append(callout_box(block[1], LIME_D, base))
                story.append(Spacer(1, 0.2 * cm))
            elif kind == "warn":
                story.append(callout_box(block[1], RED, base))
                story.append(Spacer(1, 0.2 * cm))
            elif kind == "pb":
                story.append(PageBreak())
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        "Need help? Email <font color='#65A30D'><b>hello@kreedanation.io</b></font> — "
        "we usually reply within one business day. "
        "Forgot your password? Visit <b>/forgot-password</b> (works for HR, vendors and admins) "
        "or <b>/players/forgot-password</b> for player accounts. "
        "Tip: once you sign in, this guide is one click away from the <b>top navigation bar</b> — "
        "no need to dig through the footer.", note))
    doc.build(story)
    print("wrote", out, "(", out.stat().st_size // 1024, "KB )")


# ---------- VENDOR MANUAL ----------
vendor_sections = [
    {"title": "1. Who this guide is for",
     "intro": "Anyone offering grounds, courts, coaching, refereeing, umpiring, training, photography or videography services for corporate tournaments. Kreeda Nation helps you reach HR teams across companies — your business identity stays private until a booking is confirmed by both you and Kreeda Nation HQ.",
     "blocks": []},
    {"title": "2. Create your vendor account",
     "blocks": [
        ("num", [
            "Open <b>/vendor/signup</b> from the footer link <b>“Become a vendor”</b>.",
            "Fill in business name, contact name, city, mobile and a working email.",
            "Pick your <b>primary service type</b> (Ground / Court / Coach / Referee / Umpire / Trainer / Photographer / Videographer). You can still add listings of <b>any</b> other type later — this just sets the default.",
            "Choose a password and click <b>Create vendor account</b>.",
            "You are taken to <b>/vendor/dashboard</b>. A yellow <b>“PENDING APPROVAL”</b> chip is shown on your business banner until Kreeda Nation HQ verifies you.",
        ]),
        ("tip", "Approved? A green <b>✓ Verified by Kreeda Nation</b> badge appears on every live listing in the marketplace — instant trust signal for HR teams browsing /hire."),
        ("h3", "Forgot password"),
        ("p", "Open <b>/forgot-password</b>, enter your registered email and submit. A reset link (valid 1 hour) is sent. Set a new password and sign in again. Same flow works for HR and admin accounts."),
    ]},
    {"title": "3. Add a listing (ground, court, coach, etc.)",
     "blocks": [
        ("num", [
            "On your dashboard click <b>+ New listing</b>.",
            "Pick what you’re listing in the <b>“What are you listing?”</b> dropdown. The form adapts to your choice.",
            "Enter title, description, city, price + currency (USD or INR) and price unit (per hour / per session / per match).",
            "Grounds &amp; courts: enter capacity and tick the sports the venue supports.",
            "Coaches, referees, umpires, trainers: tick the sports you specialise in.",
            "<b>Upload images directly</b> — each image slot lets you either paste an image URL or click <b>Upload</b> to pick a file from your computer (JPEG / PNG / WEBP / GIF, up to 5 MB). 5–10 photos convert ~3× better.",
            "Click <b>Save listing</b>. The listing appears in your dashboard with a <b>PENDING</b> tag until Kreeda Nation HQ approves it.",
        ]),
        ("h3", "Multiple listings per account"),
        ("p", "One account can hold any number of listings of any type — e.g. two grounds in different parts of town, a coach service and a photographer package, all under one email. Each listing is reviewed independently."),
        ("warn", "If you change a listing’s type (e.g., a coach profile to a referee profile) it is sent back to Kreeda Nation HQ for re-approval before re-publishing."),
    ]},
    {"title": "4. Handle booking requests (new dual-approval flow)",
     "blocks": [
        ("p", "When an HR team books your listing it appears on your dashboard <i>and</i> at <b>/bookings</b> (a new <b>Requests</b> link in the nav). Status starts as <b>Awaiting vendor</b>."),
        ("num", [
            "Review the venue, requested date, start time and total <b>hours</b> the HR team picked. Notes from HR appear below.",
            "Click <b>Accept</b> or <b>Decline</b>. Status changes to <b>Vendor accepted</b> or <b>Vendor declined</b>. Kreeda Nation HQ is notified.",
            "An admin then finalises: <b>Confirmed by Kreeda Nation</b> or <b>Rejected by Kreeda Nation</b>. The admin can override your decision in either direction.",
            "Once a booking is in a final state (Confirmed / Rejected / Cancelled) you cannot re-touch it — only admin can. This is intentional to protect the audit trail.",
        ]),
        ("tip", "Every status change appends to a <b>notifications</b> log on the booking — both you and the HR team see the most recent message and who made it. Email notifications are coming soon; right now the log is in-app + backend logs."),
    ]},
    {"title": "5. Pricing &amp; payouts",
     "blocks": [
        ("kv", [
            ["Currency", "USD or INR — set per listing"],
            ["Pricing model", "Flat price × price unit (per hour / per match / per session)"],
            ["Total on booking", "HR picks date + start time + hours; we compute total = price × hours"],
            ["Discounts", "Add seasonal pricing by editing each listing"],
            ["Payments", "Handled offline between you and the HR team for now; Stripe checkout is on the roadmap"],
        ]),
    ]},
    {"title": "6. Common questions",
     "blocks": [
        ("h3", "How long does approval take?"),
        ("p", "Usually under 24 hours. You’ll see your listing go from PENDING → LIVE in the dashboard."),
        ("h3", "Can I temporarily hide a listing?"),
        ("p", "Yes — edit the listing and uncheck <b>Active</b>, or ask Kreeda Nation HQ to “Unpublish”. Bookings already in flight are unaffected."),
        ("h3", "Can multiple staff log in to the same vendor account?"),
        ("p", "Today it’s one email per business. Team logins are on the roadmap."),
    ]},
    {"title": "7. Verified vendor badge",
     "blocks": [
        ("p", "Once Kreeda Nation HQ approves your business AND you've collected at least one published review, a green <b>✓ Verified</b> badge appears on every live listing in /hire. Vendors with the badge convert ~2× better than unbadged ones — it tells HR teams a real human has played at your venue."),
        ("tip", "Want the badge faster? After a confirmed booking, ask the HR team to leave a quick review from <b>/bookings → Past → Leave review</b>. You can also encourage them in person."),
    ]},
    {"title": "8. Happy-hour pricing &amp; venue schedules",
     "blocks": [
        ("p", "Ground / court listings support <b>Venue schedules</b> for slot-based bookings. Open a listing → <b>Schedule</b> tab to:"),
        ("bul", [
            "Add weekly availability windows (Mon–Sun, start / end time, slot length).",
            "Set <b>Happy-hour pricing</b> — different price during off-peak hours (e.g., 50% off 11:00–15:00 weekdays).",
            "Block specific dates (maintenance, weather, private events).",
        ]),
        ("tip", "Happy-hour discounts are calculated automatically when HR picks a start time that falls inside your happy-hour window — they see the discounted total live."),
    ]},
    {"title": "9. Cancellation &amp; reschedule policies",
     "blocks": [
        ("p", "Each listing has its own <b>Policy editor</b> (Edit listing → <b>Policies</b> section). You decide:"),
        ("kv", [
            ["Cancel window", "How many hours before slot start can HR cancel for free / partial / no refund."],
            ["Reschedule window", "Until how close to slot start HR can reschedule to another date."],
            ["Free reschedules", "Number of free reschedules per booking. After that you can charge a fee."],
        ]),
        ("warn", "Once an HR cancels or reschedules, the system honours <b>your</b> policy — no need to negotiate every time. Final amount and refund are computed automatically and shown in the booking timeline."),
    ]},
    {"title": "10. Reviews — your reputation engine",
     "blocks": [
        ("p", "After every confirmed booking, the HR team can leave a 1–5★ review on <b>/bookings → Past</b>. Reviews flow through a two-step approval pipeline:"),
        ("num", [
            "<b>You see it first</b> at <b>/vendor/dashboard → Reviews</b>. Approve to send to HQ, or flag if it is abusive / off-topic.",
            "Kreeda Nation HQ publishes the review on your public listing OR rejects it if flagged.",
        ]),
        ("tip", "Your aggregate rating (average ★ + count) is shown on every marketplace listing once you have ≥1 published review — the same number that powers the Verified badge eligibility."),
    ]},
    {"title": "11. What's new — approval emails &amp; rejection reasons",
     "intro": "Kreeda Nation HQ approval decisions now arrive in your inbox automatically. No need to log in to check status.",
     "blocks": [
        ("h3", "Vendor account approval"),
        ("p", "When HQ approves your vendor business, you get an email titled <b>“Your vendor account has been approved”</b> with a one-click button to your dashboard. If HQ rejects with a reason, the email includes that reason verbatim so you know exactly what to fix before resubmitting."),
        ("h3", "Listing approval"),
        ("p", "Each listing is reviewed independently. You'll receive a separate email per listing — <b>“Your listing ‘&lt;title&gt;’ has been approved”</b> or rejected with the admin's note. Edit the listing in your dashboard and it goes back into the queue."),
        ("tip", "If a rejection email never arrives, check spam and add <b>admin@kreedanation.com</b> to your safe-senders list."),
    ]},
]

# ---------- PLAYER MANUAL ----------
player_sections = [
    {"title": "1. What you get with a player account",
     "intro": "Your Kreeda Nation profile is your <b>universal corporate-sports identity</b>. Even when you change companies, your stats, photos and Cric Heroes link travel with you.",
     "blocks": [
        ("bul", [
            "One profile, every tournament you ever play.",
            "Searchable by name, city, mobile — recruiters &amp; captains can find you.",
            "Profile view counter shows how often other players check you out.",
            "Link your <b>Cric Heroes</b> profile so detailed match stats are one click away.",
        ]),
    ]},
    {"title": "2. Sign up",
     "blocks": [
        ("num", [
            "Open <b>/players/signup</b> from the footer link <b>“Player account”</b>.",
            "Enter your full name, mobile number, password.",
            "Pick your current company from the dropdown. If your company isn’t listed yet, ask your HR team to onboard at /signup-company first.",
            "Click <b>Create player account</b> — you land straight in your profile editor at /players/me.",
        ]),
        ("tip", "Your mobile number is your login ID. It’s only fully visible to you — other users see “•••• 1234” unless they’re you."),
        ("h3", "Already added by an HR / captain"),
        ("p", "If your HR team or a team captain quick-added you, you’ll receive (or be shown) a temporary password along with a login email like <code>player_+91xxxxxxxxxx@players.playsphere.app</code>. Sign in at <b>/players/login</b>, then open <b>/players/me</b> to set a real email + change the password."),
        ("h3", "Forgot password"),
        ("p", "Open <b>/players/forgot-password</b>, enter the email on your profile. We send a reset link valid for 1 hour. Land on <b>/players/reset-password?token=…</b>, set a new password and sign in."),
    ]},
    {"title": "3. Complete your profile",
     "intro": "Profiles are heavily skewed toward cricket but work for any sport.",
     "blocks": [
        ("kv", [
            ["Photo", "Click <b>Upload</b> or paste a public image URL"],
            ["Email", "Add a real email so you can use forgot-password if needed"],
            ["City, DOB", "Where you’re based and your date of birth"],
            ["Playing role", "Batsman / Bowler / All-rounder / Wicket-keeper / Any"],
            ["Batting hand", "Right or Left"],
            ["Bowling style", "Right-arm-fast / spin / etc."],
            ["Jersey number", "Optional integer; shown on your card"],
            ["Height &amp; weight", "Optional"],
            ["Cric Heroes link", "Paste your cricheroes.com profile URL — appears as a button on your public page"],
            ["Bio", "A short pitch about yourself"],
        ]),
    ]},
    {"title": "4. Changing company",
     "blocks": [
        ("p", "Your profile is portable. When you switch jobs:"),
        ("num", [
            "Open <b>/players/me</b>.",
            "Use the <b>Company</b> dropdown and pick your new employer.",
            "Click <b>Save profile</b>. Your stats, history, photo and Cric Heroes link all stay; only your company badge updates.",
        ]),
        ("tip", "If your new employer isn’t on Kreeda Nation yet, you can stay on “Independent” until they onboard — your profile keeps working."),
    ]},
    {"title": "5. Find other players",
     "blocks": [
        ("num", [
            "Open <b>/players/profiles</b> from the nav (“Find players”).",
            "Search by name, city or partial mobile number.",
            "Click any card to view their full profile.",
            "Your own profile shows a <b>view counter</b> — it increments only when a <i>different</i> player visits you.",
        ]),
    ]},
    {"title": "6. Joining a team (captain or HR add)",
     "blocks": [
        ("p", "Teams are now event-scoped. When an HR team or platform admin creates a tournament they:"),
        ("num", [
            "Create teams inside the event.",
            "Assign a <b>captain</b> — that’s a registered player profile.",
            "Add members — they can pick you from the registered roster, or quick-add you (which creates a profile + sends you credentials).",
        ]),
        ("p", "If you’re a <b>captain</b>, the event’s Teams tab is visible to you and you can add members to <i>your</i> team — same Pick / Quick-add options HR sees."),
        ("warn", "Tournament teams are managed by HR / captain. If you joined the wrong company by mistake, fix it under /players/me — your roster card on existing teams stays where HR placed it."),
    ]},
    {"title": "7. Watching matches live",
     "blocks": [
        ("p", "Every fixture in a live tournament has a <b>public scorecard URL</b> — <b>/live/&lt;fixture_id&gt;</b>. Share it with friends and family who don't have Kreeda Nation accounts; they'll see ball-by-ball updates streaming in real time without needing to log in."),
        ("bul", [
            "Click the fixture row in any event → the public Scorecard link is shown.",
            "Cricket matches use a <b>CricHeroes-style</b> live view: toss, playing XI, batting/bowling cards, partnerships and free-hit indicators.",
            "Score updates push instantly via WebSocket, with REST polling as a fallback — no manual refresh needed.",
        ]),
        ("tip", "If the tournament organiser added a YouTube/Twitch stream URL, a red <b>WATCH LIVE</b> button appears at the top of the event page."),
    ]},
    {"title": "8. Mobile experience",
     "blocks": [
        ("p", "Kreeda Nation is fully mobile-responsive. On phones / tablets the top-right <b>hamburger</b> icon opens a slide-in menu with every page you can access. Your player guide is always one tap away in the same menu under <i>Help</i>."),
    ]},
]

# ---------- COMPANY (HR) MANUAL ----------
company_sections = [
    {"title": "1. Onboard your company",
     "intro": "60-second setup. Your data, tournaments and team rosters are completely isolated from every other company on the platform.",
     "blocks": [
        ("num", [
            "Open <b>/signup-company</b> (header CTA “For Companies”).",
            "Enter your company name, admin name, phone and a work email.",
            "Choose a password (≥6 chars) and click <b>Create company account</b>.",
            "You are taken to <b>/dashboard</b>. From here you can launch tournaments, hire services and review bookings.",
        ]),
        ("h3", "Auto-onboarded by Kreeda Nation HQ"),
        ("p", "If Kreeda Nation HQ added your company to an inter-company tournament, your HR email + a temporary password are shared with you out-of-band (and in admin's confirmation modal). Sign in at <b>/login</b>, then change your password from /dashboard. Use <b>/forgot-password</b> any time you need a reset link."),
    ]},
    {"title": "2. Create a tournament",
     "blocks": [
        ("num", [
            "Click <b>+ New tournament</b> on /dashboard (or open <b>/admin</b>).",
            "Pick a sport (cricket, football, badminton, quiz, hackathon…) and a format — <b>Round-robin</b> or <b>Knockout</b>.",
            "Fill in name, description, venue and (optionally) a banner image URL.",
            "Paste a <b>Live stream URL</b> (YouTube, Twitch, any platform) — every event visitor sees a “WATCH LIVE” button. You can edit it anytime from the event page.",
            "Click <b>Create</b>. The event now lives at <b>/events/{id}</b> with public Fixtures / Standings / Teams tabs.",
        ]),
        ("tip", "Use clear team names like “Engineering Eagles” / “Sales Spartans” and set a distinct colour — it makes the bracket and standings instantly readable."),
    ]},
    {"title": "3. Set up teams &amp; captains (new event-scoped flow)",
     "blocks": [
        ("p", "Open your event → switch to the <b>Teams</b> tab (visible to HR, admin and captains). The legacy /teams page is no longer in the public nav."),
        ("num", [
            "Click <b>NEW TEAM</b>. Enter team name, optional department, colour. Submit.",
            "On the new team card, click <b>Assign captain</b> and pick from the registered players list. The captain is auto-added to the roster.",
            "Click <b>Add player</b> on the team card. Two modes:",
            "<b>Pick registered</b> — choose anyone in the global player directory.",
            "<b>Quick add</b> — enter name + mobile + (optional) email. We create a player profile and show you a one-time temporary password to share. The player can change it on first login.",
            "Remove a player anytime with the trash icon. Removing the captain clears that slot.",
        ]),
        ("warn", "Captains can add &amp; remove players on <i>their</i> team. They cannot create new teams. HR or admin still own the team list."),
    ]},
    {"title": "4. Generate fixtures &amp; live-score",
     "blocks": [
        ("num", [
            "On the event page click <b>Generate fixtures</b>. Round-robin rotates pairings automatically; knockout builds the bracket with byes.",
            "On any fixture row click <b>Update score</b>. The sport-specific scorer opens (cricket overs/wickets, football goals, badminton sets, etc.).",
            "Toggle status to <b>LIVE</b> while play is on; Standings auto-update on completion. WebSocket broadcasts the score change to every open browser instantly.",
            "Spectators with the live-stream URL click <b>WATCH LIVE</b> from the event header to jump to your YouTube/Twitch feed.",
        ]),
    ]},
    {"title": "5. Hire services and book grounds",
     "blocks": [
        ("h3", "Marketplace services (custom jerseys, trophies, catering, …)"),
        ("p", "Open <b>/services</b> for the 17-service catalogue. Fill the dynamic form, submit a request. Track under <b>/bookings</b>."),
        ("h3", "Book a ground / coach / referee (new wizard)"),
        ("p", "Open <b>/hire</b>. It’s now a guided wizard:"),
        ("num", [
            "<b>Step 1</b> — Pick the category (Grounds / Courts / Coaches / Referees …).",
            "<b>Step 2</b> — Pick the sport / surface (Cricket, Football, Tennis …).",
            "<b>Step 3</b> — Pick the city. Only cities with verified vendors for your sport appear.",
            "<b>Step 4</b> — Pick a venue card. The booking modal shows the price/hour and lets you choose date + start time + total <b>hours</b>. Total is computed live.",
            "Click <b>Send request</b>. You land on <b>/bookings</b> where your booking shows status <b>Awaiting vendor</b>.",
        ]),
        ("tip", "Vendor accepts/declines first → Kreeda Nation HQ confirms or overrides. Every status change is visible on your booking card with the latest message + author. You can <b>Cancel request</b> any time before the booking is finalised."),
        ("warn", "Vendor contact details stay hidden until Kreeda Nation confirms — we keep the marketplace neutral. After confirmation we connect you with the vendor."),
    ]},
    {"title": "6. Sponsors — per-tournament",
     "blocks": [
        ("p", "Sponsors are managed at the <b>tournament</b> level. Open an event you own and switch to the <b>Sponsors</b> tab to add sponsors with tier (Title / Gold / Silver / Bronze), logo, website and description. Public visitors see those sponsors only on that event's page."),
        ("tip", "Pitch sponsors on per-tournament packages: Title for a premium logo, Gold/Silver/Bronze tiers for graded exposure."),
    ]},
    {"title": "7. Live updates",
     "blocks": [
        ("bul", [
            "Every event with a stream URL shows a red <b>WATCH LIVE</b> CTA in the header.",
            "Score changes propagate via WebSocket — no refresh needed for spectators.",
            "Knockout brackets propagate winners automatically as you complete matches.",
            "Standings recalc on every completed match (3 pts win, 1 pt draw).",
        ]),
    ]},
    {"title": "8. CricHeroes-style cricket scoring",
     "blocks": [
        ("p", "Open any cricket fixture → <b>Update score</b> to launch the rich live scorer. The flow matches what your captains see on apps like CricHeroes, so the learning curve is near-zero:"),
        ("num", [
            "<b>Toss</b> — pick which team won and whether they chose to bat or bowl. The scorer auto-sets the batting / bowling sides.",
            "<b>Playing XI</b> — choose the 11 players from each team. Required before the first ball.",
            "<b>Striker / non-striker / bowler</b> — pick before the first delivery; the scorer rotates strike automatically on odd-run balls and end-of-over events.",
            "<b>Ball by ball</b> — runs, wides, no-balls (with free-hit auto-flag), byes, leg-byes, wickets (caught/bowled/run-out etc.). Partnerships, overs, current run-rate and required rate all update live.",
            "<b>Undo</b> any ball if you mis-tapped. The system recomputes batting / bowling cards and partnership widget instantly.",
        ]),
        ("tip", "Share <b>/live/&lt;fixture_id&gt;</b> with spectators who don't have an account — they get the same live scorecard with no login required."),
    ]},
    {"title": "9. Manage existing bookings (cancel / reschedule)",
     "blocks": [
        ("p", "Open <b>/bookings</b> → click any active booking. Depending on the vendor's policy you'll see:"),
        ("bul", [
            "<b>Cancel request</b> — free / partial refund / no refund based on hours-to-slot and the vendor's cancellation policy. The refund amount is computed live.",
            "<b>Reschedule</b> — pick a new date + start time. Free reschedules are tracked per booking; once exhausted, the vendor's reschedule fee applies.",
            "Every action writes a <b>notification</b> entry visible to you, the vendor and HQ — full audit trail.",
        ]),
        ("warn", "After a booking enters a final state (Confirmed, Rejected or Cancelled) only Kreeda Nation HQ can touch it. This protects everyone's audit log."),
    ]},
    {"title": "10. Upcoming bookings widget &amp; dashboard",
     "blocks": [
        ("p", "Your <b>/dashboard</b> shows an <b>Upcoming bookings</b> widget pinned at the top — the next 5 confirmed / pending slots across all your venues, with date, vendor and total. Click any card to jump straight into the booking detail."),
        ("tip", "Look at the dashboard daily — vendor accept / decline actions surface here before email is wired up."),
    ]},
    {"title": "11. Sponsorship marketplace — earn revenue from your events",
     "intro": "Open any event you run to its <b>Sponsorship</b> tab to enable the marketplace. Brands can then discover, browse and request the slots you list — Kreeda Nation handles discovery, you handle approvals.",
     "blocks": [
        ("num", [
            "Open <b>/events/{event}</b> → click <b>Sponsorship</b> tab.",
            "Tick <b>Accept sponsorships</b>. Fill in expected reach, expected participants, target audience, demographics, social-media reach, livestream views, venue, event category and (optionally) a brochure URL — these power the sponsor browse filters.",
            "Tick the <b>data-share agreement</b> checkbox at the bottom — required before your listing goes live.",
            "Click <b>Save sponsorship settings</b>.",
            "Add opportunities below — name, type, price, quantity, benefits. Common bundles: <i>Title</i> (qty 1, top price), <i>Associate</i> (qty 3-5), <i>Best Batsman / Bowler</i>, <i>Streaming</i>, <i>Boundary Branding</i> (qty 5+).",
        ]),
        ("tip", "Sponsors browse the marketplace at <b>/sponsorships</b> with filters by sport, location, budget, audience size, event type. The lower your minimum price, the wider your reach — Boundary slots are great entry points."),
        ("h3", "Approving a sponsor"),
        ("p", "When a sponsor clicks <b>I'm interested</b> on one of your slots, an entry appears in your <b>Interest queue</b> at the top of the Sponsorship tab with their company, industry, budget range, website &amp; proposal. Click <b>Accept</b> to award the slot (it auto-marks SOLD when all slots fill) or <b>Reject</b>."),
        ("h3", "When a slot is sold"),
        ("p", "The opportunity flips to <b>SOLD</b> and a <b>✦ Sponsored by [Brand]</b> badge is added to the public listing. Any other still-pending interests on that slot are auto-rejected. The badge surfaces wherever the event is shown — Events list, public event page, and the public sponsorships endpoint."),
    ]},
    {"title": "12. Sponsoring other companies' events",
     "blocks": [
        ("p", "Your company login can also <b>sponsor</b> other organisers' events — no separate account needed. Open the <b>Sponsor hub</b> link in your top nav. There you'll find your sponsor profile (industry, budget range, interests, target locations) and a link to browse all sponsorship-ready events at <b>/sponsorships</b>."),
        ("tip", "Fill out your sponsor profile fully — organisers see your industry, budget range and website on every interest you submit, which dramatically improves your acceptance rate."),
    ]},
    {"title": "13. Where to find your guide",
     "blocks": [
        ("p", "Once signed in, this HR manual is always available from the <b>top navigation</b> — look for <b>HR guide</b> next to your menu items. The footer no longer carries role guides; we surface only the one relevant to your account so you never have to wonder which PDF to open."),
    ]},
    {"title": "14. What's new — scorers, fixture lock &amp; marketplace clarity",
     "intro": "Recent product updates that change day-to-day operations for HR teams running tournaments.",
     "blocks": [
        ("h3", "Invite a match scorer"),
        ("p", "On any event you own → open the <b>Scorers</b> tab. Enter a scorer's email, pick scope (<b>All fixtures</b> or <b>Specific fixtures</b>) and send. If they aren't on Kreeda Nation yet, we auto-create a lightweight <i>scorer</i> account and email them login credentials. The temp password is also surfaced inline once for manual sharing."),
        ("bul", [
            "Scorers can update live scores ONLY for the events / matches you assign — they cannot edit your event, generate fixtures, or access scoring of other tournaments.",
            "They land at <b>/scorer/dashboard</b> after login showing every assigned event and fixture.",
            "Remove a scorer anytime with the trash icon on their row.",
        ]),
        ("h3", "Fixture lock"),
        ("p", "Once any fixture moves out of <b>Scheduled</b> (i.e. the tournament has started), the <b>Generate fixtures</b> button is automatically disabled and reads <b>Fixtures locked</b>. This protects live and completed match scores from being wiped by an accidental regenerate."),
        ("h3", "Cross-company permission scoping"),
        ("p", "HRs of other companies can no longer touch your event. The <b>Generate fixtures</b> button, the score-update controls, and the scorer-invite UI are all hidden for anyone outside your company. The backend also enforces this (returns 403)."),
        ("h3", "Sponsors tab — direct vs marketplace"),
        ("p", "If your event uses the Sponsorship marketplace, awarded sponsors are merged into the same <b>Sponsors</b> tab as manually-added ones. A filter row above the cards lets visitors flip between <b>All</b>, <b>Direct</b> and <b>Via marketplace</b> — useful when you want to highlight organic marketplace pull versus pre-negotiated partners."),
    ]},
]

# ---------- PLATFORM ADMIN MANUAL ----------
admin_sections = [
    {"title": "1. Your role",
     "intro": "Kreeda Nation HQ — you curate the marketplace, approve vendors and listings, manage the service catalog, organise platform-wide tournaments, and oversee every company.",
     "blocks": [
        ("kv", [
            ["Login", "admin@kreedanation.com (default password admin123 — change on first login)"],
            ["Landing", "/platform-admin (Services / Events / Companies / Bookings / Vendors / Listings / Settings)"],
            ["Cross-company visibility", "You can see every company’s events, teams, bookings"],
            ["Forgot password", "/forgot-password (works for HR, vendor, admin)"],
        ]),
    ]},
    {"title": "2. Create &amp; run Kreeda Nation tournaments",
     "blocks": [
        ("p", "Use <b>/platform-admin → Events tab</b> to organise platform-wide tournaments (single-company demos, PlaySphere-organised meets, or large <b>inter-company</b> events)."),
        ("num", [
            "Click <b>+ New event</b>. Set name, sport, format, venue, banner (upload or URL) and a live stream URL.",
            "Pick the <b>Event type</b>: <b>Single company</b>, <b>Inter-company</b>, or <b>Kreeda Nation organised</b>.",
            "Click <b>Open</b> on the event row → Teams tab → set up teams just like an HR would.",
        ]),
        ("h3", "Inter-company tournaments"),
        ("p", "On an inter-company event, the Teams tab shows a <b>PARTICIPATING COMPANIES</b> section. Two options:"),
        ("num", [
            "<b>Pick existing</b> — select a registered company. They’re added to the event.",
            "<b>Create new company</b> — enter company name, HR contact name and HR email. Kreeda Nation auto-creates the Company + HR account with a temporary password. The modal shows the credentials so you can share them directly with the HR contact.",
            "HRs then log in and add their teams + players for that event.",
        ]),
        ("warn", "When admin adds players via Quick-add, the temporary login email + password are surfaced in a credentials modal. Copy and share securely. Email integration is on the roadmap; for now you forward credentials manually."),
    ]},
    {"title": "3. Curate the services catalog",
     "blocks": [
        ("num", [
            "On /platform-admin open the <b>Services</b> tab.",
            "Click <b>+ New service</b>. Enter name, category, currency (USD/INR), base price, price unit and a main image (upload or URL).",
            "Add <b>config fields</b> — the questions HR teams answer on the booking form.",
            "Add <b>variants</b> for upgrades — each with its own image and +/- price.",
            "Tick <b>Allow custom text</b> if HR should be able to enter an inscription/channel name/dietary note.",
            "Click <b>Save service</b>. It appears in /services for every company instantly.",
        ]),
    ]},
    {"title": "4. Approve vendors &amp; listings",
     "blocks": [
        ("num", [
            "Open the <b>Vendors</b> tab to see every signed-up business with PENDING / APPROVED status.",
            "Click <b>Approve</b> to bring them on board (or <b>Revoke</b> to suspend).",
            "Open the <b>Listings</b> tab to approve individual listings — only approved + active listings appear in /hire.",
        ]),
        ("warn", "Listings that change vendor_type after creation drop back to PENDING automatically. Re-review them — the vendor may be repositioning their offering."),
    ]},
    {"title": "5. Ground &amp; service bookings (dual-approval workflow)",
     "blocks": [
        ("p", "Open <b>/bookings</b>. You see every ground/service request across the platform. The new vendor-bookings panel shows status, hours, total, the latest notification message and which role made it."),
        ("h3", "Lifecycle"),
        ("kv", [
            ["pending", "HR just submitted — vendor hasn’t acted yet."],
            ["vendor_accepted", "Vendor agreed — you (admin) need to confirm to finalise."],
            ["vendor_declined", "Vendor declined — you can still override and confirm if needed."],
            ["confirmed", "Final state set by admin — both parties are notified."],
            ["rejected", "Final state set by admin — HR is notified."],
            ["cancelled", "HR cancelled their request before final state."],
        ]),
        ("num", [
            "Open the booking row, click <b>Confirm / Reject</b>.",
            "(Optional) Type an <b>admin note</b> — visible to both HR and vendor.",
            "Click <b>Confirm</b> or <b>Reject</b>. A status_change entry is appended to the booking’s notifications log + a <b>BOOKING NOTIFICATION</b> line is written to backend logs.",
        ]),
        ("warn", "Email notifications are <b>not yet wired</b>. Once a provider key (Resend / SendGrid) is configured, every status change automatically emails HR + vendor. For now, the in-app banner + backend log act as the audit trail."),
    ]},
    {"title": "6. Companies &amp; settings",
     "blocks": [
        ("bul", [
            "<b>Companies</b> tab — every signed-up company with contact details and slug.",
            "<b>Bookings</b> tab — recent service bookings across all companies.",
            "<b>Settings</b> tab — social media URLs for the footer (Facebook, Instagram, LinkedIn, Twitter, YouTube).",
            "<b>About page</b> tab — edit company description, mission, vision, founders &amp; directors. Updates /about live.",
        ]),
    ]},
    {"title": "7. Cross-company rostering &amp; sponsors",
     "blocks": [
        ("p", "When you build a team via /register-team (or inside any event you own) you can <b>pick from ALL registered players across every company</b> — not just one company's roster. Company admins only see their own company's players."),
        ("p", "Sponsors are per-tournament. Open an event → Sponsors tab → add Title/Gold/Silver/Bronze with logo, website and description. Public visitors browsing an event see only that event's sponsors."),
        ("warn", "Pulling a player into a tournament does not change their company affiliation. Players retain their universal corporate-sports profile."),
    ]},
    {"title": "8. Operational tips",
     "blocks": [
        ("bul", [
            "Run weekly approval batches — group vendor + listing approvals for predictable SLAs.",
            "Audit currency mix — Indian customers expect INR; US/EU expect USD. Set the right default per service.",
            "Use the <b>✓ Verified</b> badge as a quality signal — it appears automatically on every approved listing in /hire.",
            "Rotate the seed admin password after onboarding the real HQ team.",
            "Regenerate manuals after major product changes — run <code>python /app/scripts/generate_manuals.py</code>.",
        ]),
        ("warn", "Anything you do here affects every company on the platform. Test new services in a draft state (uncheck Active) before going live."),
    ]},
    {"title": "9. Multi-admin &amp; permissions (super admin only)",
     "intro": "The seed account (admin@kreedanation.com) is the <b>Super Admin</b>. Only the super admin can add or remove other admins, create / delete services, and manage users at the platform level. Staff admins receive scoped permissions for day-to-day work.",
     "blocks": [
        ("h3", "Granular permissions available"),
        ("kv", [
            ["manage_events", "Create &amp; delete platform-organised tournaments."],
            ["manage_vendors", "Approve / revoke vendor businesses."],
            ["manage_listings", "Approve listings so they appear in /hire."],
            ["manage_bookings", "Confirm or reject ground / coach bookings."],
            ["manage_reviews", "Moderate the review queue (publish / reject)."],
            ["manage_settings", "Edit site settings &amp; the public About page."],
            ["manage_companies", "Manage company accounts."],
        ]),
        ("h3", "Invite a staff admin"),
        ("num", [
            "Open <b>/platform-admin → Team</b> tab (visible only to the super admin).",
            "Enter email, name and a temporary password (≥ 6 chars).",
            "Tick the permissions you want them to have. Leave blank for read-only access.",
            "Click <b>Create admin</b>. A one-time invite panel appears with the login URL + temp password — copy and share securely.",
        ]),
        ("h3", "Edit or remove a staff admin"),
        ("bul", [
            "On the Team tab, click <b>Edit</b> on any staff admin row to add / remove permissions or update their name.",
            "Click the trash icon to revoke access — they're signed out on their next request.",
            "You cannot edit or delete the super admin from the UI; rotate it from the env / DB if needed.",
        ]),
        ("warn", "Service add / delete and admin add / delete are reserved for the super admin — UI buttons are hidden from staff admins automatically, and the backend rejects unauthorised calls with 403."),
    ]},
    {"title": "10. Drill-down detail pages",
     "blocks": [
        ("p", "Three click-through pages help HQ inspect every actor without leaving /platform-admin:"),
        ("kv", [
            ["/platform-admin/vendors/{id}", "Vendor + owner login + every listing, schedule, booking, and review attached to that vendor."],
            ["/platform-admin/companies/{id}", "Company + HR contact + their events + roster + bookings + spend summary."],
            ["/platform-admin/players/{id}", "Player profile, masked mobile, event history, current teams and profile view count."],
        ]),
        ("tip", "Use these pages when a vendor or HR raises a support ticket — you get the full context in one screen."),
    ]},
    {"title": "11. Review moderation &amp; custom sports",
     "blocks": [
        ("h3", "Review moderation queue"),
        ("p", "The <b>Reviews</b> tab on /platform-admin shows every review the vendor approved (waiting for HQ publish) plus anything flagged. Publish to make it visible on the listing, or reject with an internal note."),
        ("h3", "Custom sports CRUD"),
        ("p", "The <b>Sports</b> tab lets you add / edit / remove the sports list that powers every dropdown in the platform (events, vendor listings, player profiles). Add quirky internal favourites like “Esports — Valorant” or “Padel” without a code change."),
    ]},
    {"title": "12. Sponsorship marketplace oversight",
     "intro": "The <b>SPONSORSHIP MARKETPLACE</b> card on your Dashboard tab gives you a live read on every sponsorship deal flowing through Kreeda Nation.",
     "blocks": [
        ("kv", [
            ["Total opportunities", "Sum of every available slot across all events with the marketplace enabled."],
            ["Total value", "Total slot count × asking price — the gross GMV at offer."],
            ["Pending / Awarded / Rejected", "Interest workflow counters — pending is your call-to-action: chase the organiser if they're sitting on offers too long."],
            ["Top sponsors", "Ranked by accepted GMV — these brands are your best repeat-revenue prospects."],
            ["Top events", "Ranked by total slot value — these organisers carry the heaviest book; protect them."],
        ]),
        ("tip", "Click <b>Browse marketplace</b> at the top-right of the card to open <b>/sponsorships</b> exactly as a sponsor sees it — useful for QA and giving demo walkthroughs."),
        ("h3", "Suspending a misbehaving sponsor"),
        ("p", "Open the <b>Accounts</b> tab → pick the <b>Vendors</b> chip → filter by 'sponsor' (or use search). Disabled sponsors get the same canned message at login as any other suspended account."),
    ]},
    {"title": "13. Where guides live now",
     "blocks": [
        ("p", "The footer no longer lists all four manuals — it cluttered the experience for logged-out visitors. Instead each signed-in user sees only <b>their</b> guide as a link in the top nav (HR sees HR guide, vendors see vendor guide, etc.). This admin manual appears as <b>Admin guide</b> when you sign in."),
    ]},
    {"title": "14. What's new — approvals, scorers &amp; inbox cleanup",
     "intro": "Major workflow updates the platform admin needs to know.",
     "blocks": [
        ("h3", "Organiser event approvals queue"),
        ("p", "A new <b>Approvals (n)</b> tab appears between Events and Sports on your platform-admin tabs. It shows every event that an independent <i>organiser</i> created and acknowledged the platform instructions for. From here you can:"),
        ("bul", [
            "<b>Approve &amp; publish</b> — the event becomes public, the organiser is emailed a confirmation with a one-click link to open the event.",
            "<b>Reject…</b> — write a reason in the inline textarea, click <b>Confirm rejection + email</b>. The organiser receives an email with your reason verbatim and can edit + resubmit.",
            "<b>Open</b> — jumps to the public event page so you can review teams, dates, sponsorships before deciding.",
        ]),
        ("warn", "HR / company events skip this workflow and are public immediately. Only independent <i>organiser</i> accounts hit the approval queue."),
        ("h3", "Customise the instructions organisers must acknowledge"),
        ("p", "Open <b>Settings</b> tab → scroll to <b>ORGANISER EVENT INSTRUCTIONS</b>. Edit the rich-text block with your latest fair-play, sponsorship and policy rules. Organisers see this verbatim inside the acknowledgement modal on every new event they create."),
        ("h3", "Vendor / listing approvals now send emails"),
        ("p", "Approvals tab actions on the <b>Vendors</b> and <b>Listings</b> tabs now auto-email the vendor:"),
        ("kv", [
            ["Approve", "Sends a green confirmation email with a dashboard link. Always fires."],
            ["Reject", "New red button beside Approve. Opens an inline reason textarea — vendor receives the reason via email."],
            ["Revoke / Unpublish", "Silent toggle for an already-approved item — no email, used for temporary pauses."],
        ]),
        ("h3", "Scorer invitations"),
        ("p", "Organisers / HRs can now invite match scorers from any event's <b>Scorers</b> tab. Invitees get an email with login credentials and can only update scores for the events / fixtures they're assigned to. As platform admin, you can see every scorer in the database under <b>Accounts</b> tab → role <i>scorer</i> filter."),
        ("h3", "Contact inbox — archive &amp; delete"),
        ("p", "The Settings page contact inbox now supports an Inbox / Archive toggle. Once a message is marked as <b>read</b>, you can <b>Archive</b> it to clear it from the active inbox (Restore brings it back) or <b>Delete</b> it permanently. The delete button is disabled while a message is still unread, to prevent accidental loss of unanswered enquiries."),
        ("h3", "Sponsors per event — direct vs marketplace"),
        ("p", "Awarded marketplace sponsors and manually-added sponsors are now merged into a single Sponsors tab on every event, deduplicated by name. The tab badge counts both. A filter row lets visitors see <b>All / Direct / Via marketplace</b>."),
    ]},
]


# Build all four
build("kreeda-nation-vendor-manual.pdf", "VENDOR", PINK,
      "Vendor manual",
      "Everything you need to list grounds, courts, coaches and other on-ground services.",
      vendor_sections)

build("kreeda-nation-player-manual.pdf", "PLAYER", CYAN,
      "Player manual",
      "Your portable corporate-sports profile — set it up once, carry it across employers.",
      player_sections)

build("kreeda-nation-company-manual.pdf", "HR / COMPANY", LIME_D,
      "Company HR manual",
      "Run end-to-end internal tournaments and hire services from one dashboard.",
      company_sections)

# Organisers share the company workflow but onboard as independent brands.
# Build them a dedicated PDF that emphasises that distinction.
organiser_intro_sections = [
    {"title": "1. Welcome, organiser",
     "intro": "Kreeda Nation gives independent tournament organisers the same power tools the corporate HR teams use — minus the corporate-domain requirement.",
     "blocks": [
        ("p", "Sign up at <b>/signup-organiser</b> with <i>any</i> email — Gmail, Yahoo, Outlook or a custom domain all work. We verify it with a 6-digit code (sent right away from <b>admin@kreedanation.com</b>) before creating the workspace."),
        ("kv", [
            ["Email", "Any provider — public or branded."],
            ["Phone", "Optional, helps vendors / players reach you fast."],
            ["Brand name", "Shown publicly on event pages, fixtures and scorecards."],
        ]),
        ("tip", "Once signed in you'll land on <b>/dashboard</b> — same powerful layout HR teams use. Your <b>Organiser guide</b> link is always one click away in the top nav."),
    ]},
    {"title": "1a. The event approval workflow (organiser-only)",
     "intro": "Every event you create on Kreeda Nation goes through a lightweight admin review before becoming public. This protects audience quality across the platform — and it's quick.",
     "blocks": [
        ("h3", "The lifecycle"),
        ("num", [
            "<b>You create the event</b> at <b>/dashboard → + New tournament</b>. It is saved as a private draft with the status <b>“Pending your acknowledgement”</b>. It does NOT appear on the public events page yet.",
            "<b>Open the event</b> to read the platform's tournament instructions (set by Kreeda Nation HQ). They cover fair-play, eligibility, sponsorship and content policies you must follow.",
            "<b>Click the yellow <i>I agree &amp; submit for approval</i></b> button on the banner. The event moves to <b>“Awaiting platform admin approval”</b>.",
            "<b>Wait briefly</b> — Kreeda Nation HQ typically reviews within a few business hours. You'll receive an <b>approval email</b> when they're done.",
            "<b>If approved</b>: the event goes public, all tabs unlock, and the normal flow continues — add teams, generate fixtures, invite scorers, list sponsorships, etc.",
            "<b>If rejected</b>: the email includes the admin's reason. Open the event, edit the details based on the feedback (dates, venue, sponsorship terms, etc.), and click <b>Resubmit for approval</b> — back to step 4.",
        ]),
        ("h3", "What about HR / corporate events?"),
        ("p", "Events created under a corporate <b>HR account</b> do NOT need approval — they go live immediately. Approval is only required for events created by independent organisers."),
        ("warn", "Editing an event while it's pending is fine and recommended — fix issues before submitting. Once approved, the event is public; major changes (sport, venue, dates) should be communicated to participants via the description or your own channels."),
    ]},
] + company_sections[1:]

build("kreeda-nation-organiser-manual.pdf", "ORGANISER", "#06B6D4",
      "Organiser manual",
      "Run open tournaments, book vendors, score matches live — without needing a company.",
      organiser_intro_sections)


build("kreeda-nation-platform-admin-manual.pdf", "PLATFORM HQ", RED,
      "Platform admin manual",
      "Curate the marketplace, approve vendors, and oversee every company.",
      admin_sections)

# ---------- SPONSOR MANUAL ----------
GOLD = HexColor("#FACC15")
sponsor_sections = [
    {"title": "1. Welcome, sponsor",
     "intro": "Kreeda Nation gives your brand direct access to engaged corporate-sports audiences — across cricket, football, badminton, hackathons and family-day events run by India's top employers and independent organisers.",
     "blocks": [
        ("kv", [
            ["You discover events", "Filter by sport, location, budget, audience size — surface only events that match your brand goals."],
            ["You express interest", "One-click 'I'm interested' on any sponsorship slot. Organisers review your profile + proposal."],
            ["You sponsor", "When the organiser accepts, your brand is locked in. Your name appears as the official sponsor on every public surface of the event."],
            ["No fees, no bidding", "Kreeda Nation runs the marketplace for free. Payment terms are between you and the organiser — we capture the relationship, not the cash."],
        ]),
    ]},
    {"title": "2. Create your sponsor account",
     "blocks": [
        ("num", [
            "Open <b>/sponsor/signup</b> (the <b>“Become a sponsor”</b> link in the footer goes here directly).",
            "Fill in company name, contact person, work email and a password (min 6 chars).",
            "Click <b>Create sponsor account</b> — you're signed in and dropped straight on <b>/sponsors/me</b>.",
        ]),
        ("tip", "Already running a company on Kreeda Nation? You don't need a second account — open the <b>Sponsor hub</b> link in your top nav and we auto-create a sponsor profile mirrored to your company. You can sponsor events from the same login."),
    ]},
    {"title": "3. Complete your sponsor profile",
     "intro": "Filling this out is the single best thing you can do for acceptance rates — organisers see every field on every interest you submit.",
     "blocks": [
        ("kv", [
            ["Company name + contact person", "Used on the interest queue and the public 'Sponsored by ABC Realty' badge."],
            ["Industry", "Pre-filters opportunities the organiser thinks fit your brand."],
            ["Location + Target locations", "Helps organisers gauge geographic alignment with their venue / audience."],
            ["Budget range", "Free-text like '₹10,000 – ₹5,00,000'. Organisers use this to triage applications."],
            ["Sponsor interests", "Multi-select chips — Cricket, Football, Corporate Sports, Family Day, Sports Day, etc."],
            ["Target event types", "Single-company, inter-company, family-day, sports-day — broadens or narrows browse results."],
            ["Website + Logo", "Logo appears next to your name once an opportunity is awarded; website is one click away from the organiser's queue."],
        ]),
        ("warn", "Without a logo or website, your interest still works — but acceptance rates drop sharply. Spend 5 minutes filling these in."),
    ]},
    {"title": "4. Browse the marketplace",
     "blocks": [
        ("p", "Open <b>/sponsorships</b> from the top nav. Anonymous users can browse but cannot apply — sign in or sign up to express interest."),
        ("h3", "Filters available"),
        ("kv", [
            ["Sport", "Cricket, Football, Badminton, etc. — same list as the events page."],
            ["Location", "Case-insensitive match against event venue + sponsorship venue_location."],
            ["Event type", "single_company / inter_company / playsphere_organized."],
            ["Budget", "Five buckets from ≤ ₹10,000 to ≤ ₹5,00,000. Shows events that have AT LEAST one open slot at-or-below your cap."],
            ["Min reach", "Filter by the expected_reach the organiser entered."],
        ]),
        ("tip", "Each event card shows the min price across its slots, how many slots are open vs taken, expected reach &amp; livestream views. Use this to shortlist before clicking through."),
    ]},
    {"title": "5. Express interest",
     "blocks": [
        ("num", [
            "Click into any event card → <b>Sponsorship</b> tab.",
            "Each slot card shows the current status: <b>AVAILABLE · N slots</b> or <b>SOLD</b> with the winning sponsor name.",
            "Click <b>I'm interested</b> on the slot you want. A short dialog opens.",
            "Optionally write a <b>proposal message</b> — explain why this slot matches your brand goals. Organisers tell us this dramatically improves acceptance.",
            "Click <b>Send interest</b>. The button on that slot flips to <b>Interest sent · pending</b>.",
        ]),
        ("warn", "You can only submit ONE pending interest per slot per sponsor account — duplicate clicks are blocked with a clear error message. If you change your mind, contact the organiser directly."),
    ]},
    {"title": "6. What happens next",
     "blocks": [
        ("kv", [
            ["Organiser sees your interest", "It lands at the top of their Sponsorship tab as a card showing your company, industry, budget range, website &amp; proposal."],
            ["Organiser accepts", "The opportunity is awarded to you — its status flips to SOLD if it was the last slot, and a public <b>✦ Sponsored by [Your brand]</b> badge appears on the event listing, the public sponsorships endpoint, the Events list, and inside the event page itself."],
            ["Organiser rejects", "Your interest moves to the 'Decided' section of their queue. You can apply for other slots on the same event."],
            ["Slot fills via someone else", "If all slots for that opportunity sell out before your interest is decided, your application is auto-rejected with a note."],
        ]),
        ("tip", "Right now we surface decisions in-app. Email notifications are on the roadmap — check <b>/sponsors/me</b> (your hub) for updates until they ship."),
    ]},
    {"title": "7. Best practices",
     "blocks": [
        ("bul", [
            "<b>Lead with the smallest slot first.</b> Boundary branding (qty 5+, lowest price) lets you test the audience before committing to Title-level spend.",
            "<b>Specific proposal beats generic one.</b> Mention the venue, the expected audience, and ONE concrete thing your brand will activate on-ground.",
            "<b>Refresh your interests list</b> via the <b>Sponsor hub</b> page weekly to see decisions.",
            "<b>Keep your sponsor interests up-to-date</b> — organisers can soon filter their reach-out list by your chip selection.",
        ]),
    ]},
    {"title": "8. Where to find this guide",
     "blocks": [
        ("p", "Once signed in as a sponsor, this manual is one click away from your <b>top navigation</b> as <b>Sponsor guide</b>. The footer always carries the <b>Become a sponsor</b> link for new users."),
    ]},
    {"title": "9. What's new — chip-input locations &amp; brand visibility",
     "blocks": [
        ("h3", "Target locations are now chip-based"),
        ("p", "Open <b>/sponsors/me</b> → <b>Target locations</b>. Type a city and press <b>Enter</b> or <b>,</b> to add it as a chip. Click <b>×</b> on any chip to remove. Backspace on an empty input removes the last chip. Duplicates are auto-blocked. Replaces the comma-string field which silently dropped trailing characters."),
        ("h3", "Awarded sponsors visible in the event's Sponsors tab"),
        ("p", "When an organiser accepts your interest, your brand now also appears in the event's main <b>Sponsors</b> tab — not just under Sponsorship. Visitors can flip a filter to view <b>All / Direct / Via marketplace</b>, so brands like yours that came in through the marketplace get explicit credit on the public surface."),
        ("tip", "Make sure your logo is uploaded and your website is set on your sponsor profile. The Sponsors tab pulls both onto the public card the moment your interest is accepted."),
    ]},
]

build("kreeda-nation-sponsor-manual.pdf", "SPONSOR", GOLD,
      "Sponsor manual",
      "Discover sponsorship-ready tournaments, apply to slots in one click, get your brand on every public surface.",
      sponsor_sections)

# ---------- SCORER MANUAL ----------
scorer_sections = [
    {"title": "1. What you do on Kreeda Nation",
     "intro": "You are a match scorer — invited by a tournament organiser to keep the live score for one or more matches.",
     "blocks": [
        ("bul", [
            "You see only the events and fixtures the organiser explicitly assigned you to.",
            "You cannot create events, generate fixtures, manage teams, or score matches you weren't invited to — by design.",
            "Your live updates broadcast instantly to anyone watching the public scorecard (no refresh needed).",
        ]),
    ]},
    {"title": "2. Your invitation &amp; first login",
     "blocks": [
        ("num", [
            "An organiser invites you by email from inside their event's <b>Scorers</b> tab. You receive a branded email with your login credentials (email + temporary password).",
            "Click the <b>SIGN IN TO SCORE</b> button in the email — it lands you on the Kreeda Nation login page.",
            "Sign in with your email + the temp password.",
            "You are taken directly to <b>/scorer/dashboard</b>.",
        ]),
        ("tip", "Didn't get the email? Check spam, then ask the organiser to share the temp password they see inline on the Scorers tab when they invited you."),
        ("h3", "Change your password"),
        ("p", "Open your profile menu in the top-right and pick <b>Reset password</b> — or use <b>/forgot-password</b> any time."),
    ]},
    {"title": "3. The scorer console (/scorer/dashboard)",
     "intro": "Your home screen. Every event you've been assigned to is listed here, with the specific fixtures you can score.",
     "blocks": [
        ("kv", [
            ["Event card", "Sport, venue, start date and your scope (All fixtures or N specific fixtures)."],
            ["Open event →", "Jumps to the public event page. The Fixtures tab shows the same matches you can score with the <b>Update score</b> button visible only on yours."],
            ["Fixture chips", "Each fixture shows match number, round, status (Scheduled / Live / Completed) and a pencil icon to jump to the scoring panel."],
        ]),
    ]},
    {"title": "4. Score a match",
     "blocks": [
        ("num", [
            "From /scorer/dashboard click any event card → <b>Open event →</b>.",
            "Switch to the <b>Fixtures</b> tab. The matches you're allowed to score have a <b>Update score</b> button.",
            "Click <b>Update score</b> to launch the sport-specific scorer (cricket: toss + playing XI + ball-by-ball; football: goals; badminton: sets; etc.).",
            "Updates push instantly to all live spectators via WebSocket.",
        ]),
        ("tip", "For cricket — set the toss, pick the playing XI, then pick striker / non-striker / bowler before the first ball. The system rotates strike automatically on odd-run balls and end-of-over events. Use the <b>Undo</b> button if you mis-tap a ball."),
        ("warn", "You cannot score a fixture that isn't on your assignment list — the Update score button won't show and the backend rejects unauthorised attempts."),
    ]},
    {"title": "5. Frequently asked",
     "blocks": [
        ("h3", "Can I be assigned to multiple events at once?"),
        ("p", "Yes — every event with at least one assigned fixture for you appears on your dashboard."),
        ("h3", "What if I no longer want to score?"),
        ("p", "Ask the organiser to remove you from their event's Scorers tab — they have a trash icon next to your row. Your account stays; only the assignment is revoked."),
        ("h3", "Can the organiser change my scope after inviting?"),
        ("p", "Today they need to remove and re-invite. Scope-edit-in-place is on the roadmap."),
    ]},
    {"title": "6. Where to find this guide",
     "blocks": [
        ("p", "Once signed in as a scorer, this manual is one click away from your top nav as <b>Scorer guide</b>."),
    ]},
]

build("kreeda-nation-scorer-manual.pdf", "SCORER", CYAN,
      "Scorer manual",
      "Keep live scores for the matches you've been invited to — nothing more, nothing less.",
      scorer_sections)

print("ALL DONE")
