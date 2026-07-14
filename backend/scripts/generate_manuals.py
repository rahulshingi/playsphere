"""Generate branded PDF manuals for every user role on Kreeda Nation.

Run:
    python /app/backend/scripts/generate_manuals.py

Output: /app/frontend/public/manuals/kreeda-nation-{role}-manual.pdf (7 files).

Style: dark cover page with brand mark, section headings in Kreeda accent
colors (#84CC16 · #06B6D4 · #EC4899 · #F59E0B · #FACC15 · #FF3B30), body in
light gray on white for readability. Text-first with 1–3 screenshots per
manual (pulled from /app/backend/scripts/manuals_screenshots/ if present).

Each manual re-uses the same MANUAL constant → single source of truth.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak,
    Table, TableStyle, ListFlowable, ListItem, KeepTogether,
)
from reportlab.pdfgen import canvas

# ─────────────────────────── Paths ───────────────────────────
ROOT = Path("/app")
LOGO = ROOT / "frontend/public/kreeda-mark.png"
OUT  = ROOT / "frontend/public/manuals"
SHOTS = ROOT / "backend/scripts/manuals_screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# ─────────────────────────── Style ───────────────────────────
BRAND_LIME  = colors.HexColor("#84CC16")
BRAND_CYAN  = colors.HexColor("#06B6D4")
BRAND_PINK  = colors.HexColor("#EC4899")
BRAND_AMBER = colors.HexColor("#F59E0B")
BRAND_GOLD  = colors.HexColor("#FACC15")
BRAND_RED   = colors.HexColor("#FF3B30")
DARK        = colors.HexColor("#0a0a0a")
GRAY_MID    = colors.HexColor("#4b5563")
GRAY_LIGHT  = colors.HexColor("#e5e7eb")
GRAY_SOFT   = colors.HexColor("#f9fafb")

styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica",
                     fontSize=10, leading=15, textColor=colors.HexColor("#1f2937"),
                     spaceAfter=4)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8.5, textColor=GRAY_MID)
H1 = ParagraphStyle("h1", parent=BODY, fontName="Helvetica-Bold", fontSize=18,
                    leading=22, textColor=DARK, spaceBefore=6, spaceAfter=8)
H2 = ParagraphStyle("h2", parent=BODY, fontName="Helvetica-Bold", fontSize=13,
                    leading=17, textColor=DARK, spaceBefore=10, spaceAfter=5)
H3 = ParagraphStyle("h3", parent=BODY, fontName="Helvetica-Bold", fontSize=11,
                    leading=15, textColor=colors.HexColor("#374151"),
                    spaceBefore=6, spaceAfter=3)
TAG = ParagraphStyle("tag", parent=BODY, fontName="Helvetica-Bold", fontSize=8,
                     textColor=BRAND_CYAN, leading=10, spaceAfter=4)
CODE = ParagraphStyle("code", parent=BODY, fontName="Courier", fontSize=9,
                      textColor=colors.HexColor("#1f2937"),
                      backColor=GRAY_SOFT, borderColor=GRAY_LIGHT, borderWidth=0.5,
                      borderPadding=6, leading=13, spaceBefore=4, spaceAfter=6)
TIP  = ParagraphStyle("tip", parent=BODY, textColor=colors.HexColor("#065f46"),
                      backColor=colors.HexColor("#d1fae5"),
                      borderColor=colors.HexColor("#10b981"), borderWidth=0.6,
                      borderPadding=8, leading=15, spaceBefore=6, spaceAfter=8)
WARN = ParagraphStyle("warn", parent=BODY, textColor=colors.HexColor("#7c2d12"),
                      backColor=colors.HexColor("#fed7aa"),
                      borderColor=colors.HexColor("#ea580c"), borderWidth=0.6,
                      borderPadding=8, leading=15, spaceBefore=6, spaceAfter=8)


# ─────────────────────────── Cover page painter ───────────────────────────

def draw_cover(canvas_, doc, role_meta: dict):
    """Dark cover page — brand mark on left, role wordmark on right."""
    w, h = A4
    c = canvas_
    c.saveState()
    # Full black background
    c.setFillColor(DARK)
    c.rect(0, 0, w, h, stroke=0, fill=1)
    # Colored accent stripe
    c.setFillColor(colors.HexColor(role_meta["accent"]))
    c.rect(0, h - 12*mm, w, 4*mm, stroke=0, fill=1)
    # Logo
    if LOGO.exists():
        try:
            c.drawImage(str(LOGO), 25*mm, h - 55*mm, width=25*mm, height=25*mm,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass
    # Brand text
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(60*mm, h - 42*mm, "KREEDA NATION")
    c.setFillColor(colors.HexColor("#9ca3af"))
    c.setFont("Helvetica", 9)
    c.drawString(60*mm, h - 48*mm, "Where Teams Compete, Connect & Grow")

    # Role tag
    c.setFillColor(colors.HexColor(role_meta["accent"]))
    c.setFont("Helvetica-Bold", 10)
    c.drawString(25*mm, h - 110*mm, "/ " + role_meta["tag"])

    # Big role title
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 44)
    c.drawString(25*mm, h - 130*mm, role_meta["title"])

    c.setFillColor(colors.HexColor("#9ca3af"))
    c.setFont("Helvetica", 12)
    c.drawString(25*mm, h - 145*mm, role_meta["subtitle"])

    # Version + platform URL at the bottom
    c.setFillColor(colors.HexColor("#6b7280"))
    c.setFont("Helvetica", 8)
    c.drawString(25*mm, 20*mm, "Feb 2026 · Version 3.0 · Corporate Services + Invoicing edition")
    c.drawString(25*mm, 15*mm, "kreedanation.com  ·  contact@kreedanation.com")
    c.restoreState()


def make_footer(role_meta):
    def _footer(canvas_, doc):
        # Skip cover page (page 1) — cover handled by draw_cover via first onFirstPage.
        if doc.page == 1:
            return
        canvas_.saveState()
        w, _h = A4
        canvas_.setFillColor(GRAY_MID)
        canvas_.setFont("Helvetica", 8)
        canvas_.drawString(20*mm, 12*mm,
                          f"Kreeda Nation · {role_meta['title']} manual")
        canvas_.drawRightString(w - 20*mm, 12*mm, f"Page {doc.page}")
        canvas_.setStrokeColor(GRAY_LIGHT)
        canvas_.line(20*mm, 15*mm, w - 20*mm, 15*mm)
        canvas_.restoreState()
    return _footer


# ─────────────────────────── Content builders ───────────────────────────

def para(text): return Paragraph(text, BODY)
def h1(text): return Paragraph(text, H1)
def h2(text): return Paragraph(text, H2)
def h3(text): return Paragraph(text, H3)
def tag(text): return Paragraph("/ " + text, TAG)
def small(text): return Paragraph(text, SMALL)
def code(text): return Paragraph(text.replace(" ", "&nbsp;").replace("\n", "<br/>"), CODE)
def tip(text): return Paragraph("<b>💡 Tip.</b> " + text, TIP)
def warn(text): return Paragraph("<b>⚠ Heads up.</b> " + text, WARN)

def bullets(items):
    return ListFlowable(
        [ListItem(Paragraph(t, BODY), leftIndent=8) for t in items],
        bulletType="bullet", start="•", bulletColor=BRAND_CYAN,
        leftIndent=14, bulletFontSize=9,
    )

def numbered(items):
    return ListFlowable(
        [ListItem(Paragraph(t, BODY), leftIndent=8) for t in items],
        bulletType="1", bulletColor=BRAND_LIME,
        leftIndent=16, bulletFontSize=9, bulletFormat="%s.",
    )

def screenshot(name, caption=""):
    """Embed a screenshot if it exists — otherwise render a placeholder box."""
    path = SHOTS / name
    if path.exists():
        # Match native 1440×900 aspect (1.6:1) — draw at 170×106.25mm.
        img = Image(str(path), width=170*mm, height=106*mm, kind="proportional")
        img.hAlign = "CENTER"
        elements = [img]
    else:
        # Placeholder outline so the manual still layouts fine before shots are taken
        tbl = Table([[""]], colWidths=[170*mm], rowHeights=[65*mm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GRAY_SOFT),
            ("BOX", (0, 0), (-1, -1), 0.6, GRAY_LIGHT),
        ]))
        elements = [tbl]
    if caption:
        elements.append(small(f"<i>Figure: {caption}</i>"))
    elements.append(Spacer(1, 5*mm))
    return KeepTogether(elements)


def section_divider(color):
    tbl = Table([[""]], colWidths=[170*mm], rowHeights=[3])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(color)),
    ]))
    return tbl


# ─────────────────────────── Manuals: role content ───────────────────────────

def build_admin():
    role = {"tag": "Platform Admin", "title": "ADMIN GUIDE", "accent": "#FF3B30",
            "subtitle": "Master control over Kreeda Nation HQ."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("You run the platform."),
        para("As <b>Platform Admin</b> you configure catalogs, review incoming "
             "requests, keep vendors accountable, and unlock the whole revenue "
             "engine of Kreeda Nation. This guide walks through every tab of "
             "<b>/platform-admin</b> and highlights the flows that ship revenue."),
        tip("Super Admin? You additionally see the <b>Team</b> tab to invite "
            "staff admins with scoped permissions (manage_events / manage_vendors "
            "/ manage_listings / manage_reviews / manage_settings / manage_companies)."),

        section_divider("#FF3B30"), Spacer(1, 4*mm),
        tag("1 · Dashboard"),
        h2("Dashboard & analytics"),
        para("Landing view when you log in — KPI donuts for bookings, revenue, "
             "events, ecosystem. Click any donut to drill into the underlying tab "
             "(bookings → Bookings, revenue → Business, etc.)."),
        bullets([
            "<b>Bookings</b> — today/last-7/last-30/all-time counts by status",
            "<b>Revenue</b> — platform ₹ + offline ₹ + commissions owed",
            "<b>Events</b> — public/pending approval",
            "<b>Ecosystem</b> — vendors / companies / players",
        ]),
        screenshot("admin-dashboard.png", "Platform Admin dashboard with KPI donuts."),

        tag("2 · Corporate Services (RFQ engine)"),
        h2("Corporate Services workspace"),
        para("Six sub-tabs consolidated under one meta-tab:"),
        bullets([
            "<b>RFQs</b> — inbox of HR/Organiser requests. Click a row to build a cost sheet, compose quotations, and chat with HR",
            "<b>Service Vendors</b> — internal procurement ledger (contacts, rate cards, preferred flag). Never surfaced to HR",
            "<b>Packages</b> — HR-facing tiered offerings composed from services + add-ons",
            "<b>Categories · Services · Add-ons</b> — the building blocks",
        ]),
        h3("Handling an RFQ end-to-end"),
        numbered([
            "New RFQ arrives → click <b>Start review</b> to move it to <i>under_review</i>",
            "The <b>Cost Sheet</b> auto-seeds one line per selected service/add-on. Click <b>Auto-pick</b> for each service and the system assigns the top-ranked vendor (city match → preferred → lowest rate)",
            "Edit qty / unit rate as needed → <b>Save cost sheet</b>",
            "In <b>Quotation Builder</b>, choose per-line pricing: <b>Markup %</b> (default 25%) or <b>Fixed ₹</b>. Set discount / tax / valid-until",
            "Click <b>Create draft</b> — a versioned quote (v1, v2, …) appears in history",
            "Click <b>Send to HR</b> → HR receives a sanitised copy (never sees internal cost or margin)",
            "HR either <b>Accepts</b> (RFQ → Approved, invoice auto-generated) or <b>Rejects with a reason</b> (RFQ → Negotiation; you can chat and send v2)",
            "Once accepted, use the <b>Invoice</b> panel to Download PDF, create a Razorpay pay-link, or Mark paid",
        ]),
        warn("Pricing privacy is a hard contract. Anything you save inside a "
             "cost sheet, or margin %, or gross margin — never reaches HR. HR "
             "only sees the final selling total, tax and total after you click "
             "<b>Send to HR</b>."),
        screenshot("admin-rfq-detail.png", "RFQ detail with cost sheet, quotation builder and invoice panel."),

        tag("3 · Events & Approvals"),
        h2("Events lifecycle"),
        bullets([
            "<b>Events</b> tab — create, edit, delete events across all companies. Assign participating companies, upload banners, manage sponsors",
            "<b>Approvals</b> tab — organiser-created events land here as <i>pending_organiser_ack</i>. Approve to make public, reject with a reason (organiser resubmits after edits)",
            "<b>Sports</b> tab — configure sports registered on the platform (name, icon, scoring config)",
        ]),

        tag("4 · Vendors, Listings, Bookings"),
        h2("Vendor management"),
        bullets([
            "<b>Vendors</b> — approve/reject vendor signups, see their business type, city, offline_mode flag",
            "<b>Listings</b> — moderate every vendor listing (turf, court, coach, equipment)",
            "<b>Bookings</b> — analytics across all vendor bookings, filter by status and date",
            "<b>Commissions</b> — per-booking commission dues, mark paid, send reminders",
        ]),

        tag("5 · Business & Companies"),
        h2("Corporate accounts"),
        bullets([
            "<b>Companies</b> — HR/corporate signups",
            "<b>Organisers</b> — independent tournament organisers",
            "<b>Business</b> — sponsorship marketplace queue, deal negotiations",
            "<b>Users</b> — global user directory across all roles",
        ]),

        tag("6 · Settings, About, Reviews"),
        h2("Platform configuration"),
        bullets([
            "<b>Settings</b> — social URLs, contact info, commission %s, offline subscription pricing",
            "<b>About page</b> — the public /about page content",
            "<b>Reviews</b> — moderate flagged/pending reviews",
            "<b>Accounts</b> — deactivate/delete misbehaving accounts",
            "<b>Team</b> (super admin only) — invite staff admins, assign permissions",
        ]),
    ]
    return role, story


def build_company():
    role = {"tag": "Company / HR", "title": "HR PLAYBOOK", "accent": "#06B6D4",
            "subtitle": "Book employee engagement events in three clicks."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("Employee engagement made effortless."),
        para("You&rsquo;re the <b>HR / Company Admin</b>. Kreeda Nation gives you "
             "curated packages, a smart RFQ workflow, and one-click booking of "
             "sports venues — everything you need to run team offsites, wellness "
             "programs and inter-team tournaments."),
        tip("Prefer to explore first? Head to <b>Home → Corporate Services</b> "
            "to browse packages without submitting anything."),

        section_divider("#06B6D4"), Spacer(1, 4*mm),
        tag("1 · Sign in"),
        h2("Signing in"),
        numbered([
            "Visit <b>/signup-company</b> to onboard your company",
            "Confirm your email via the link sent to your inbox",
            "Sign in at <b>/login</b> — or use <b>Sign in with Google</b> for one-tap access",
            "Land on your <b>Dashboard</b> with quick shortcuts to bookings, RFQs, memberships",
        ]),

        tag("2 · Corporate Services"),
        h2("The RFQ flow"),
        para("<b>Corporate Services</b> is where you request custom events — sports "
             "days, yoga sessions, tournaments, wellness weeks. Browse packages "
             "grouped by category, customise, submit."),
        h3("Submitting a request"),
        numbered([
            "Open <b>Home → Corporate Services</b>",
            "Pick a category tile (Yoga, Inter-Team Tournament, etc.)",
            "Choose a tier (<b>Starter · Standard · Premium</b>)",
            "Click <b>Customise this package</b>",
            "Uncheck services you don&rsquo;t need, add optional add-ons with quantities",
            "Fill event details: date, time, city, venue, players, spectators, budget hint",
            "Submit — status flips to <b>Submitted</b> in your <b>My Requests</b> page",
        ]),
        h3("What happens next"),
        bullets([
            "Admin marks it <b>Under Review</b> and prepares a quotation",
            "You receive an email once the quote is ready and status flips to <b>Quoted</b>",
            "Open the RFQ → review line-by-line pricing → <b>Accept</b> or <b>Reject with a reason</b>",
            "Once you accept, an <b>Invoice</b> panel appears with <b>Download PDF</b> + <b>Pay now</b> (Razorpay)",
            "You can chat with admin at any time after the first quote arrives — negotiate freely",
        ]),
        screenshot("hr-rfq-detail.png", "HR RFQ detail with quotation, invoice and chat panel."),

        warn("Pricing stays hidden until admin clicks <b>Send</b>. You&rsquo;ll "
             "never see internal cost or margin — only the final priced quotation."),

        tag("3 · Book a venue"),
        h2("Marketplace bookings"),
        bullets([
            "Open <b>/hire</b> for the vendor marketplace",
            "Filter by city, sport, listing type (turf / court / coach)",
            "Click a listing to see availability, pick a slot, pay online (Razorpay) or offline (vendor confirms)",
            "Track everything under <b>Bookings</b>",
        ]),

        tag("4 · Universal player profiles"),
        h2("Linking your team"),
        para("Players who sign up with a corporate-domain email are auto-linked "
             "to your company. Head to <b>Players → Directory</b>, filter by your "
             "company, and see everyone under one roof."),

        tag("5 · Memberships"),
        h2("Subscriptions"),
        bullets([
            "Some vendors offer monthly / yearly memberships",
            "Purchase during the venue-booking modal or from <b>My Memberships</b>",
            "Pay offline (bank transfer) or online (once Razorpay is live)",
        ]),
    ]
    return role, story


def build_organiser():
    role = {"tag": "Organiser", "title": "ORGANISER GUIDE", "accent": "#FACC15",
            "subtitle": "Run tournaments end-to-end — approval to podium."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("Independent tournaments, powered."),
        para("Kreeda Nation lets you list independent tournaments to the whole "
             "player community, generate fixtures, invite scorers, and publish "
             "live scoring. Everything under one dashboard."),

        section_divider("#FACC15"), Spacer(1, 4*mm),
        tag("1 · Get started"),
        h2("Signup + approval"),
        numbered([
            "Sign up at <b>/signup-organiser</b> — pick <i>Organiser</i> as your org type",
            "Confirm email · sign in at <b>/login</b>",
            "Create your first event under <b>Admin → Events → New Event</b>",
            "Read + acknowledge the Kreeda Nation event guidelines (shown in a modal)",
            "Event is submitted with status <b>Pending Approval</b>",
            "Platform admin reviews within 24h · you&rsquo;re emailed when approved / rejected with reason",
        ]),
        tip("Rejected? Fix the issue admin flagged and click <b>Resubmit</b> — the same modal reopens."),

        tag("2 · Fixtures & scorers"),
        h2("Bracket generation"),
        bullets([
            "On any approved event, open the <b>Fixtures</b> tab",
            "Choose format: <b>Round-Robin</b> (all-play-all) or <b>Knockout</b> (single elimination)",
            "Click <b>Generate fixtures</b> — the system builds the bracket, seedings and match slots",
            "Add scorers via <b>Scorers</b> tab — invite by email, assign specific fixtures (or all)",
        ]),
        h3("Live scoring"),
        para("Once a match is live, scorers use their dedicated console at "
             "<b>/scorer/dashboard</b>. Ball-by-ball / point-by-point updates "
             "flow to the public <b>/live/{fixture_id}</b> page in real time."),

        tag("3 · Corporate Services"),
        h2("Also submit RFQs"),
        para("Organisers get the same Corporate Services module as HR — browse "
             "packages, submit RFQs, receive quotations. Ideal for organisers "
             "who bundle their tournaments with hospitality, photography, DJ, "
             "and other services from Kreeda Nation&rsquo;s catalogue."),

        tag("4 · Standings & sponsors"),
        h2("Wrap-up"),
        bullets([
            "Standings auto-update as matches complete — visit <b>/standings?event_id=…</b>",
            "Sponsor slots (Title/Gold/Silver/Bronze) can be sold via the Sponsorship marketplace",
            "Player profiles are auto-linked to your event — visible on <b>/players/profiles</b>",
        ]),
    ]
    return role, story


def build_vendor():
    role = {"tag": "Vendor", "title": "VENDOR PLAYBOOK", "accent": "#06B6D4",
            "subtitle": "List venues, coaches, memberships — get bookings."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("Your storefront on Kreeda Nation."),
        para("<b>Venue Vendors</b> — that&rsquo;s you. Turf, badminton court, "
             "cricket coach, box cricket, football pitch, gym, yoga studio — "
             "list it, set availability, take bookings both online and offline."),

        section_divider("#06B6D4"), Spacer(1, 4*mm),
        tag("1 · Onboard"),
        h2("Getting listed"),
        numbered([
            "Sign up at <b>/vendor/signup</b>",
            "Fill business name, type, city, phone",
            "Wait for admin approval (usually within 24h)",
            "Once approved, land on <b>/vendor/dashboard</b>",
        ]),

        tag("2 · Listings"),
        h2("Adding a listing"),
        bullets([
            "Dashboard → <b>My Listings</b> → <b>+ New listing</b>",
            "Add title, description, images, hourly rate, sport tags",
            "Toggle <b>Availability</b> for each weekday · block specific dates/times",
            "Every listing is again admin-moderated before going live",
        ]),
        h3("Weekly schedule & blocks"),
        para("Use <b>Venue schedule editor</b> to configure your weekly template "
             "(e.g. Mon–Fri 6-10am + 6-10pm, weekends 6am-9pm). Individual date "
             "blocks (holidays, private events, maintenance) sit in "
             "<b>venue_blocks</b>."),

        tag("3 · Offline mode"),
        h2("Offline / private bookings"),
        para("If you subscribe to <b>Offline mode</b> (₹99/mo · ₹999/yr), you "
             "unlock <b>Private Bookings</b> — record walk-in bookings, add "
             "custom pricing, capture overtime, generate GST invoices."),
        bullets([
            "Dashboard → <b>Private Bookings</b> → <b>+ New private booking</b>",
            "Complete on the fly: mark the actual end-time, capture overtime billing",
            "Reopen a completed booking within 24h if the customer disputes",
            "Invoice Settings panel — set your GSTIN, billing address, tax rate",
        ]),

        tag("4 · Bookings & commissions"),
        h2("Money"),
        bullets([
            "<b>Platform bookings</b> flow into <b>/vendor-bookings</b> — accept, mark arrived, mark no-show",
            "Each platform booking incurs <b>10% commission</b> (configurable by admin)",
            "Commissions Materialise into <b>/vendor/commissions</b> — pay via bank transfer, admin marks it paid",
            "<b>Offline bookings</b> incur no commission — flat monthly subscription",
        ]),

        tag("5 · Memberships"),
        h2("Sell memberships"),
        para("You can offer monthly/yearly memberships (subscription packs) to "
             "your regulars. Dashboard → <b>Memberships</b> → configure plans "
             "with prices + validity + inclusions. Buyers pay you and you activate "
             "them from <b>Membership Requests</b>. Kreeda takes 5% commission "
             "on member issued via the platform."),
    ]
    return role, story


def build_player():
    role = {"tag": "Player", "title": "PLAYER GUIDE", "accent": "#84CC16",
            "subtitle": "Your sports profile, portable across every event."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("One profile, every tournament."),
        para("Kreeda Nation gives every player a <b>Universal Profile</b> — one "
             "sports resume that follows you from company inter-team tournaments "
             "to weekend leagues to national events. Career stats, batting/bowling "
             "averages, tournaments played — all in one place."),

        section_divider("#84CC16"), Spacer(1, 4*mm),
        tag("1 · Sign up"),
        h2("Create your profile"),
        numbered([
            "Sign up at <b>/players/signup</b>",
            "Mobile number is your login ID — verify via OTP",
            "Optionally add your <b>corporate email</b> to link to your company&rsquo;s HR dashboard (auto-verified once you click the email link)",
            "Login at <b>/players/login</b> — or from <b>/login</b> with email + password",
        ]),
        tip("Multiple companies over your career? Add each corporate email — "
            "each one is verified independently so HR can find you."),

        tag("2 · Book a venue"),
        h2("Play more, book less"),
        bullets([
            "Open <b>/hire</b> — the vendor marketplace",
            "Filter by city + sport",
            "Pick a listing → choose slot → pay online (Razorpay) or offline (vendor confirms)",
            "See all your bookings under <b>My Bookings</b>",
        ]),

        tag("3 · Live matches"),
        h2("Follow the action"),
        para("Every event has a public standings page and every live fixture has "
             "a scoreboard at <b>/live/{fixture_id}</b>. If your team is playing, "
             "the score updates in real time as the scorer clicks."),

        tag("4 · Player directory"),
        h2("Discoverability"),
        para("Once your profile is set up, players + HRs + organisers can find "
             "you on the searchable directory at <b>/players/profiles</b>. Your "
             "public profile lives at <b>/p/{your-slug}</b> — share it in your "
             "bio, cricket group, LinkedIn, wherever."),

        tag("5 · Memberships"),
        h2("Regular at a venue?"),
        para("Some vendors sell monthly/yearly memberships (discounted access + "
             "priority slots). Buy them during a booking or under <b>My Memberships</b>."),
    ]
    return role, story


def build_sponsor():
    role = {"tag": "Sponsor", "title": "SPONSOR GUIDE", "accent": "#EC4899",
            "subtitle": "Discover, bid, brand — the sports sponsorship marketplace."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("Sponsor the events your brand cares about."),
        para("Kreeda Nation runs a <b>tiered sponsorship marketplace</b> — "
             "Title, Gold, Silver, Bronze slots on every tournament. Discover "
             "events by sport / city / audience size, place bids, negotiate, sign."),

        section_divider("#EC4899"), Spacer(1, 4*mm),
        tag("1 · Onboard"),
        h2("Sponsor signup"),
        numbered([
            "Sign up at <b>/sponsor/signup</b>",
            "Add your brand: name, logo, category, target audience",
            "Land on <b>/sponsors/me</b> — your brand hub",
        ]),

        tag("2 · Marketplace"),
        h2("Discover events"),
        para("Open <b>/sponsorships</b> — a filterable grid of every event with "
             "an open sponsorship slot. Each card shows tier availability, "
             "expected footfall, sport, city."),
        bullets([
            "Filter by tier · sport · city · expected reach",
            "Click a card to see full sponsor deck (event dates, previous partners, media metrics)",
            "Click <b>Place bid</b> → set your amount + short pitch",
            "Organiser reviews · accepts / rejects / counters (chat threaded per bid)",
        ]),

        tag("3 · Live deals"),
        h2("Once accepted"),
        bullets([
            "Deal moves to <b>Signed</b> — organiser will reach out for logo assets",
            "Your logo appears on the event banner, standings page, live-score overlay",
            "Post-event you receive a metrics report (impressions, engagement)",
        ]),

        tag("4 · Managing brands"),
        h2("Multi-brand accounts"),
        para("Agencies / holding groups can add multiple brands under one sponsor "
             "login. Each brand has its own logo, bidding history, deals dashboard."),
    ]
    return role, story


def build_scorer():
    role = {"tag": "Scorer", "title": "SCORER CONSOLE", "accent": "#F59E0B",
            "subtitle": "Ball-by-ball, point-by-point — the live scoring toolkit."}
    story = [
        Spacer(1, 5*mm),
        tag("Welcome"),
        h1("You&rsquo;re the source of truth."),
        para("<b>Scorers</b> are invited by an organiser or platform admin to "
             "score specific fixtures. Your inputs power the public live scoreboard, "
             "standings, and player stats."),

        section_divider("#F59E0B"), Spacer(1, 4*mm),
        tag("1 · Invite → login"),
        h2("Getting invited"),
        numbered([
            "Organiser adds you via <b>Events → Scorers → Invite</b>",
            "You&rsquo;re emailed a login link + temp password (also visible to the organiser inside a modal)",
            "Sign in at <b>/login</b> — you&rsquo;ll land on <b>/scorer/dashboard</b>",
        ]),

        tag("2 · Scoring a match"),
        h2("The console"),
        para("<b>/scorer/dashboard</b> lists every fixture you&rsquo;ve been assigned to. "
             "Click a fixture to open the sport-specific scoring UI:"),
        bullets([
            "<b>Cricket</b> — ball-by-ball with over control, wide/no-ball/wide-off, dot/1/2/3/4/6, wicket flow",
            "<b>Badminton / Tennis</b> — game/set point control, tiebreak logic",
            "<b>Football / Kabaddi / Volleyball</b> — score buttons, event log",
        ]),
        h3("What updates live"),
        bullets([
            "Public scoreboard at <b>/live/{fixture_id}</b>",
            "Event standings",
            "Player career stats",
        ]),

        tag("3 · Limits"),
        h2("What you cannot do"),
        para("Scorers cannot generate fixtures, edit events, or score fixtures "
             "they weren&rsquo;t assigned to — those return 403 by design. Ask "
             "your organiser if you need extra access."),
    ]
    return role, story


# ─────────────────────────── PDF builder ───────────────────────────

def render(role_meta, story, out_path: Path):
    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=22*mm,
        title=f"Kreeda Nation — {role_meta['title']}",
        author="Kreeda Nation",
    )
    # Insert a manual page break after the cover so cover uses full-bleed onFirstPage
    story_full = [PageBreak()] + story

    def on_first(canvas_, doc_):
        draw_cover(canvas_, doc_, role_meta)
    doc.build(story_full, onFirstPage=on_first, onLaterPages=make_footer(role_meta))
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size // 1024}KB)")


def main():
    print("Generating Kreeda Nation manuals →", OUT)
    generators = [
        ("kreeda-nation-platform-admin-manual.pdf", build_admin),
        ("kreeda-nation-company-manual.pdf",        build_company),
        ("kreeda-nation-organiser-manual.pdf",      build_organiser),
        ("kreeda-nation-vendor-manual.pdf",         build_vendor),
        ("kreeda-nation-player-manual.pdf",         build_player),
        ("kreeda-nation-sponsor-manual.pdf",        build_sponsor),
        ("kreeda-nation-scorer-manual.pdf",         build_scorer),
    ]
    for filename, factory in generators:
        role, story = factory()
        render(role, story, OUT / filename)
    print("\nDone. 7 manuals written to", OUT)


if __name__ == "__main__":
    main()
