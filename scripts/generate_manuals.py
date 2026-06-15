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
        "or <b>/players/forgot-password</b> for player accounts.", note))
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

build("kreeda-nation-platform-admin-manual.pdf", "PLATFORM HQ", RED,
      "Platform admin manual",
      "Curate the marketplace, approve vendors, and oversee every company.",
      admin_sections)

print("ALL DONE")
