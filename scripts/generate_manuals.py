"""Generate PlaySphere PDF manuals for Vendors / Players / Companies / Platform Admin."""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem,
    Table, TableStyle, PageBreak,
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
    callout = ParagraphStyle("callout", parent=base, fontName="Helvetica-Bold",
                             fontSize=10.5, textColor=white, leading=14)
    return base, sub, h1, h2, h3, note, callout


def header_band(title, role_color, role_label):
    """A colored top band with role label."""
    t = Table([[role_label, title]], colWidths=[4.0 * cm, 14.0 * cm], rowHeights=[1.4 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), role_color),
        ("TEXTCOLOR", (0, 0), (0, 0), white),
        ("BACKGROUND", (1, 0), (1, 0), INK),
        ("TEXTCOLOR", (1, 0), (1, 0), white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, 0), 10),
        ("FONTSIZE", (1, 0), (1, 0), 14),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("ALIGN", (1, 0), (1, 0), "LEFT"),
        ("LEFTPADDING", (1, 0), (1, 0), 16),
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
    base, sub, h1, h2, h3, note, _ = styles()
    out = OUT_DIR / filename
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.6 * cm,
                            title=f"PlaySphere — {title}", author="PlaySphere")
    story = [
        header_band(title, role_color, role_label),
        Spacer(1, 0.5 * cm),
        Paragraph("PlaySphere", h1),
        Paragraph(tagline, sub),
        Paragraph("Where Teams Compete, Connect & Grow", note),
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
    story.append(Paragraph("Need help? Email <font color='#65A30D'><b>hello@playsphere.io</b></font> — we usually reply within one business day.", note))
    doc.build(story)
    print("wrote", out, "(", out.stat().st_size // 1024, "KB )")


# ---------- VENDOR MANUAL ----------
vendor_sections = [
    {"title": "1. Who this guide is for",
     "intro": "Anyone offering grounds, courts, coaching, refereeing, umpiring, training, photography or videography services for corporate tournaments. PlaySphere helps you reach HR teams across companies — your business identity stays private until you accept a booking.",
     "blocks": []},
    {"title": "2. Create your vendor account",
     "blocks": [
        ("num", [
            "Open <b>/vendor/signup</b> from the footer link <b>“Become a vendor”</b>.",
            "Fill in business name, contact name, city, mobile and a working email.",
            "Pick your <b>primary service type</b> (Ground / Court / Coach / Referee / Umpire / Trainer / Photographer / Videographer). You can still add listings of <b>any</b> other type later — this just sets the default.",
            "Choose a password and click <b>Create vendor account</b>.",
            "You are taken straight to <b>/vendor/dashboard</b>. A yellow <b>“PENDING APPROVAL”</b> chip is shown on your business banner until PlaySphere HQ verifies you.",
        ]),
        ("tip", "Tip — vendors are approved per business and per listing. Make sure your business details are accurate before adding listings; this speeds up approval. Once a listing is live, it carries a green <b>✓ Verified by PlaySphere</b> badge in the marketplace — instant trust signal for HR teams browsing /hire."),
    ]},
    {"title": "3. Add a listing (ground, court, coach, etc.)",
     "blocks": [
        ("num", [
            "On your dashboard click <b>+ New listing</b>.",
            "Pick what you’re listing in the <b>“What are you listing?”</b> dropdown. The form adapts to your choice.",
            "Enter title, description, city, price + currency (USD or INR) and price unit (per hour / per session / per match etc.).",
            "Grounds & courts: enter capacity and tick the sports the venue supports.",
            "Coaches, referees, umpires, trainers: tick the sports you specialise in.",
            "Upload 5–10 image URLs of the venue or your work. Vendors with rich photo sets convert ~3× better.",
            "Click <b>Save listing</b>. The listing appears in your dashboard with a <b>PENDING</b> tag until platform admin approves it.",
        ]),
        ("h3", "Multiple listings per account"),
        ("p", "One account can hold any number of listings of any type — e.g. two grounds in different parts of town, a coach service and a photographer package, all under one email. Each listing is reviewed independently."),
        ("warn", "If you change a listing’s type (e.g., a coach profile to a referee profile) it is sent back to PlaySphere HQ for re-approval before re-publishing."),
    ]},
    {"title": "4. Handle booking requests",
     "blocks": [
        ("p", "When a company books your listing it appears in the <b>Booking requests</b> table on your dashboard with status <b>PENDING</b>."),
        ("num", [
            "Review the requested date, start–end time and any notes from the HR team.",
            "Click <b>Confirm</b> or <b>Decline</b>. The HR team gets the new status instantly.",
            "Confirmed bookings remain visible in your dashboard for record keeping. Past bookings stay forever."
        ]),
        ("tip", "Your contact details are never exposed to the HR team in the marketplace. They only see your listing photos, price and city. Confirming a booking is how you both signal you’re ready to be put in touch."),
    ]},
    {"title": "5. Pricing & payouts",
     "blocks": [
        ("kv", [
            ["Currency", "USD or INR — set per listing"],
            ["Pricing model", "Flat price × price unit (per hour / per match / per session)"],
            ["Discounts", "Add seasonal pricing by editing each listing or duplicating with a different price"],
            ["Payments", "Handled offline between you and the HR team for now; PlaySphere Stripe checkout is on the roadmap"],
        ]),
    ]},
    {"title": "6. Common questions",
     "blocks": [
        ("h3", "How long does approval take?"),
        ("p", "Usually under 24 hours. You’ll see your listing go from PENDING → LIVE in the dashboard."),
        ("h3", "Can I temporarily hide a listing?"),
        ("p", "Yes — edit the listing and uncheck <b>Active</b>, or ask platform admin to “Unpublish”. Bookings already in flight are unaffected."),
        ("h3", "Can multiple staff log in to the same vendor account?"),
        ("p", "Today it’s one email per business. Team logins are on the roadmap — drop us a note if you need it sooner."),
    ]},
]

# ---------- PLAYER MANUAL ----------
player_sections = [
    {"title": "1. What you get with a player account",
     "intro": "Your PlaySphere profile is your <b>universal corporate-sports identity</b>. Even when you change companies, your stats, photos and Cric Heroes link travel with you.",
     "blocks": [
        ("bul", [
            "One profile, every tournament you ever play.",
            "Searchable by name, city, mobile — recruiters & captains can find you.",
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
    ]},
    {"title": "3. Complete your profile",
     "intro": "Profiles are heavily skewed toward cricket but work for any sport.",
     "blocks": [
        ("kv", [
            ["Photo", "Public profile picture URL"],
            ["City, DOB", "Where you’re based and your date of birth"],
            ["Playing role", "Batsman / Bowler / All-rounder / Wicket-keeper / Any"],
            ["Batting hand", "Right or Left"],
            ["Bowling style", "Right-arm-fast / spin / etc."],
            ["Jersey number", "Optional integer; shown on your card"],
            ["Height & weight", "Optional"],
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
        ("tip", "If your new employer isn’t on PlaySphere yet, you can stay on “Independent” until they onboard — your profile keeps working."),
    ]},
    {"title": "5. Find other players",
     "blocks": [
        ("num", [
            "Open <b>/players/profiles</b> from the nav (“Find players”).",
            "Search by name, city or partial mobile number.",
            "Click any card to view their full profile.",
            "Your own profile shows a <b>view counter</b> — it increments each time a <i>different</i> player visits you. Self-views don’t count, so refreshing your own page doesn’t inflate it.",
        ]),
    ]},
    {"title": "6. Getting added to a team",
     "blocks": [
        ("p", "When your HR team builds a tournament roster they’ll see your name in the company players list. You don’t need to do anything — make sure your role, jersey number and Cric Heroes link are filled so they know what to slot you as."),
        ("warn", "Tournament teams are managed by the HR account. If you joined the wrong company by mistake, fix it under /players/me — your roster card on existing teams stays where HR placed it."),
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
    ]},
    {"title": "2. Create a tournament",
     "blocks": [
        ("num", [
            "Click <b>+ New tournament</b> on /dashboard (or open <b>/admin</b>).",
            "Pick a sport (cricket, football, badminton, quiz, hackathon…) and a format — <b>Round-robin</b> or <b>Knockout</b>.",
            "Fill in name, description, venue and a banner image URL.",
            "Click <b>Create</b>. The event now lives at <b>/events/{id}</b> with public fixtures / standings / teams tabs.",
        ]),
        ("tip", "Mixing departments? Use clear team names like “Engineering Eagles” / “Sales Spartans” and set a distinct color — it makes the bracket and standings instantly readable."),
    ]},
    {"title": "3. Register teams & rosters",
     "blocks": [
        ("num", [
            "Open <b>/register-team</b>.",
            "Enter team name, department, captain and pick a colour.",
            "Pick the tournament from the Event dropdown (optional).",
            "Add players — type freeform, or click any chip in <b>“Pick from registered company players”</b> to auto-fill name & role.",
            "Click <b>Register team</b>.",
        ]),
        ("p", "The chip list only shows players who registered on PlaySphere and chose your company — so you never accidentally pull in someone from another company."),
    ]},
    {"title": "4. Generate fixtures & live-score",
     "blocks": [
        ("num", [
            "On the event page click <b>Generate fixtures</b>. Round-robin rotates pairings automatically; knockout builds the bracket with byes.",
            "On any fixture row click <b>Update score</b>. The sport-specific scorer opens (cricket overs/wickets, football goals, badminton sets, etc.).",
            "Toggle status to <b>LIVE</b> while play is on; Standings auto-update on completion. WebSocket broadcasts the score change to every open browser instantly — no refresh required.",
        ]),
    ]},
    {"title": "5. Hire services",
     "blocks": [
        ("h3", "Marketplace services"),
        ("p", "Open <b>/services</b> to browse the 17-service catalogue (Live YouTube streaming, Jerseys, Caps, Trophies with image picks, Custom Medals, Banners, Catering, DJ, Photography, Videography, Drone, Anchoring, First Aid, Match Officials, …). Click a card → fill the dynamic form → submit a quote request. Track status under <b>/bookings</b>."),
        ("h3", "Hire grounds, coaches, officials"),
        ("p", "Open <b>/hire</b> from the nav. Tabs cover Grounds, Courts, Coaches, Referees, Umpires, Trainers, Photographers and Videographers. Filter by city. Every visible card carries a green <b>✓ Verified</b> badge — only listings approved by PlaySphere HQ appear here. Click a listing → pick date, start & end time → <b>Request booking</b>. The vendor confirms or declines from their dashboard."),
        ("warn", "Vendor contact details are deliberately hidden from you until they confirm — this is how PlaySphere keeps the marketplace neutral. After confirmation we connect you over email."),
    ]},
    {"title": "6. Sponsors — now per-tournament",
     "blocks": [
        ("p", "Sponsors are managed at the <b>tournament</b> level, not site-wide. Open an event you own and switch to the <b>Sponsors</b> tab to add sponsors with tier (Title / Gold / Silver / Bronze), logo URL, website and description. Public visitors see those sponsors only on that event's page — keeping every sponsorship deal scoped to the event it funds."),
        ("tip", "Pitch sponsors on per-tournament packages: Title for one premium logo, Gold/Silver/Bronze tiers for graded exposure. Sponsors only appear on the events they sponsor — a clean ROI story for HQ."),
    ]},
    {"title": "7. Live updates",
     "blocks": [
        ("bul", [
            "Every event page shows a <b>LIVE STREAM ON</b> badge — score changes appear instantly via WebSocket.",
            "Knockout brackets propagate winners automatically as you complete matches.",
            "Standings recalc on every completed match (3 pts win, 1 pt draw).",
        ]),
    ]},
]

# ---------- PLATFORM ADMIN MANUAL ----------
admin_sections = [
    {"title": "1. Your role",
     "intro": "PlaySphere HQ — you curate the marketplace, approve vendors and listings, manage the service catalog, and oversee every company tournament.",
     "blocks": [
        ("kv", [
            ["Login", "admin@playsphere.com (default password admin123 — change on first login)"],
            ["Landing", "/platform-admin (Services / Companies / Bookings / Vendors / Listings / Settings)"],
            ["Cross-company visibility", "You can see every company’s events, teams, bookings"],
        ]),
    ]},
    {"title": "2. Curate the services catalog",
     "blocks": [
        ("num", [
            "On /platform-admin open the <b>Services</b> tab.",
            "Click <b>+ New service</b>. Enter name, category, currency (USD/INR), base price, price unit and a main image.",
            "Add <b>config fields</b> — these are the questions HR teams answer on the booking form (Number, Text, Textarea or Select with options).",
            "Add <b>variants</b> when relevant — e.g., Trophy designs, Medal finishes, Banner styles. Each variant has its own image and +/- price.",
            "Tick <b>Allow custom text</b> if HR should be able to enter an inscription, channel name, dietary note, etc.",
            "Click <b>Save service</b>. It appears in /services for every company instantly.",
        ]),
        ("tip", "Best practice: keep base price minimal and use variants for upgrades. The price preview in the HR booking form updates live as they select."),
    ]},
    {"title": "3. Approve vendors & listings",
     "blocks": [
        ("num", [
            "Open the <b>Vendors</b> tab to see every signed-up business with PENDING / APPROVED status.",
            "Click <b>Approve</b> to bring them on board (or <b>Revoke</b> to suspend).",
            "Open the <b>Listings</b> tab to approve individual listings — only approved + active listings appear in /hire.",
        ]),
        ("warn", "Listings that change vendor_type after creation drop back to PENDING automatically. Make a habit of re-reviewing them — the vendor may be repositioning their offering."),
    ]},
    {"title": "4. Companies & bookings overview",
     "blocks": [
        ("bul", [
            "<b>Companies</b> tab — every signed-up company with contact details and slug.",
            "<b>Bookings</b> tab — recent service bookings across all companies; jump to /bookings for the full table where you can update status (pending → approved → fulfilled).",
            "Vendor bookings — visible in /platform-admin under bookings overview; full lifecycle (pending / confirmed / declined / cancelled).",
        ]),
    ]},
    {"title": "5. Site settings, About page & branding",
     "blocks": [
        ("h3", "Social media (Settings tab)"),
        ("num", [
            "Open the <b>Settings</b> tab on /platform-admin.",
            "Paste the URLs for Facebook, Instagram, LinkedIn, Twitter and YouTube.",
            "Click <b>Save settings</b>. The footer renders an icon for every link you set, and hides icons for fields you leave blank.",
        ]),
        ("h3", "About page content (About page tab)"),
        ("num", [
            "Switch to the <b>About page</b> tab.",
            "Edit the company description, mission and vision text — these show up at <b>/about</b>.",
            "Add <b>Founders</b> and <b>Directors</b> entries with name, role, image URL, bio and LinkedIn link.",
            "Click <b>Save About page</b>. /about updates instantly across the site.",
        ]),
        ("tip", "The /about route is publicly accessible — no login required. It's the standard B2B credibility page; make sure the founders & mission copy is brand-aligned before launching marketing pushes."),
    ]},
    {"title": "6. Tournaments & cross-company rostering",
     "blocks": [
        ("p", "Platform admin can create tournaments directly on /platform-admin (or /admin). When you build a team via /register-team you can <b>pick from ALL registered players across every company</b> — not just one company's roster. Company admins only see their own company's players; this is intentional."),
        ("warn", "Pulling a player into a tournament does not change their company affiliation. Players retain their universal corporate-sports profile."),
    ]},
    {"title": "7. Sponsors are now per-tournament",
     "blocks": [
        ("p", "The global <b>/sponsors</b> page has been retired. Every event detail page now has a <b>Sponsors</b> tab where admins (platform or company) can add Title / Gold / Silver / Bronze sponsors with logos, website and description. Public visitors browsing an event see only that event's sponsors — making each sponsorship contract cleanly scoped."),
        ("bul", [
            "Per-tournament sponsor lists encourage tiered packages and repeat sponsorships.",
            "If a vendor is also a sponsor, they appear in both places — no double-counting.",
            "Removing a sponsor is non-destructive: the historical event card and bracket views remain.",
        ]),
    ]},
    {"title": "8. Operational tips",
     "blocks": [
        ("bul", [
            "Run weekly approval batches — group vendor + listing approvals for predictable SLAs.",
            "Audit currency mix — Indian customers expect INR; US/EU expect USD. Set the right default per service.",
            "Use the <b>✓ Verified</b> badge as a quality signal — it appears automatically on every approved listing in /hire (no manual flag needed).",
            "Keep the seed admin password rotation policy: change it after onboarding the real HQ team and remove the default.",
            "Regenerate manuals after major product changes — run <code>/app/scripts/generate_manuals.py</code>.",
        ]),
        ("warn", "Anything you do here affects every company on the platform. Test new services in a draft state (uncheck Active) before going live."),
    ]},
]


# Build all four
build("playsphere-vendor-manual.pdf", "VENDOR", PINK,
      "Vendor manual",
      "Everything you need to list grounds, courts, coaches and other on-ground services.",
      vendor_sections)

build("playsphere-player-manual.pdf", "PLAYER", CYAN,
      "Player manual",
      "Your portable corporate-sports profile — set it up once, carry it across employers.",
      player_sections)

build("playsphere-company-manual.pdf", "HR / COMPANY", LIME_D,
      "Company HR manual",
      "Run end-to-end internal tournaments and hire services from one dashboard.",
      company_sections)

build("playsphere-platform-admin-manual.pdf", "PLATFORM HQ", RED,
      "Platform admin manual",
      "Curate the marketplace, approve vendors, and oversee every company.",
      admin_sections)

print("ALL DONE")
