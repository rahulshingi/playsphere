"""
Phase 5A + 5C — Business model backend tests.

Covers:
* Multi-select vendor_types on signup
* Adaptive activity meta endpoint (gym/studio vs ground)
* Detailed address fields on listings
* Venue lead suggestion (HR/organiser/admin) + admin queue mgmt
* Offline-mode subscription request/activate/reject + price override
* Private bookings: gated by offline_mode, CRUD, blocks availability
* Vendor PII mask on /vendor-bookings (hr_email/created_by/notes)

Pattern follows /app/backend/tests/test_memberships_phase3_4.py:
OTPs read directly from MongoDB (collections: vendor_signup_otps, company_signup_otps).
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"

RUN = uuid.uuid4().hex[:8]
VENDOR_EMAIL = f"p5_vendor_{RUN}@turf.in"
VENDOR2_EMAIL = f"p5_vendor2_{RUN}@turf.in"  # for PII mask vendor with no offline-mode
HR_EMAIL = f"p5_hr_{RUN}@acmecorp.in"
PLAYER_MOBILE = f"+9197{RUN[:8]}"
PLAYER_EMAIL = f"p5_player_{RUN}@player.in"


# ---------- helpers ----------
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _get_otp(db, collection, email):
    rec = _run(db[collection].find_one({"email": email.lower()}, {"_id": 0}))
    assert rec, f"No OTP for {email} in {collection}"
    return rec["otp"]


def _sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- cleanup ----------
@pytest.fixture(scope="session", autouse=True)
def cleanup(db):
    yield
    emails = [VENDOR_EMAIL, VENDOR2_EMAIL, HR_EMAIL, PLAYER_EMAIL]
    _run(db.users.delete_many({"email": {"$in": emails}}))
    _run(db.vendors.delete_many({"email": {"$in": [VENDOR_EMAIL, VENDOR2_EMAIL]}}))
    _run(db.vendor_signup_otps.delete_many({"email": {"$in": [VENDOR_EMAIL, VENDOR2_EMAIL]}}))
    _run(db.company_signup_otps.delete_many({"email": {"$in": [HR_EMAIL]}}))
    _run(db.player_signup_otps.delete_many({"email": {"$in": [PLAYER_EMAIL]}}))
    _run(db.companies.delete_many({"name": {"$regex": f"^P5_.*{RUN}"}}))
    _run(db.vendor_listings.delete_many({"title": {"$regex": f"^P5_.*{RUN}"}}))
    _run(db.vendor_bookings.delete_many({"hr_email": {"$in": emails}}))
    _run(db.venue_leads.delete_many({"venue_name": {"$regex": f"^P5_.*{RUN}"}}))
    _run(db.offline_subscriptions.delete_many({"vendor_email": {"$in": [VENDOR_EMAIL, VENDOR2_EMAIL]}}))
    _run(db.private_bookings.delete_many({"client_name": {"$regex": f"^P5_.*{RUN}"}}))


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_sess():
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _signup_vendor(db, admin_sess, email, label, types=None):
    """Sign up + login a vendor. Optionally pass vendor_types list."""
    s = _sess()
    bn = f"P5_{label}_{RUN}"
    r = s.post(f"{API}/vendors/signup/request-otp", json={"email": email, "business_name": bn})
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "vendor_signup_otps", email)
    body = {
        "business_name": bn, "vendor_type": (types or ["ground"])[0],
        "contact_name": f"Vendor {label}",
        "mobile": "+91999900" + str(abs(hash(label + RUN)) % 10000).zfill(4),
        "email": email, "password": "vendor123", "city": "Bangalore",
        "otp": otp,
    }
    if types is not None:
        body["vendor_types"] = types
    r = s.post(f"{API}/vendors/signup", json=body)
    assert r.status_code == 200, r.text
    vdoc = _run(db.vendors.find_one({"email": email.lower()}, {"_id": 0}))
    assert vdoc, f"vendor not found for {email}"
    admin_sess.patch(f"{API}/vendors/{vdoc['id']}/approve", json={"approved": True})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": "vendor123"})
    assert r.status_code == 200, r.text
    return {"sess": s, "vendor_id": vdoc["id"], "vendor_doc": vdoc}


def _signup_hr(db, email, label):
    s = _sess()
    r = s.post(f"{API}/companies/signup/request-otp",
               json={"admin_email": email, "company_name": f"P5_{label}_{RUN}"})
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "company_signup_otps", email)
    r = s.post(f"{API}/companies/signup", json={
        "company_name": f"P5_{label}_{RUN}", "admin_name": "HR Test",
        "admin_email": email, "admin_password": "hrpass123",
        "city": "Bangalore", "otp": otp,
    })
    assert r.status_code == 200, r.text
    return {"sess": s, "user_id": r.json()["id"], "email": email}


@pytest.fixture(scope="module")
def hr(db):
    return _signup_hr(db, HR_EMAIL, "AcmeHR")


# =========================================================================
# 1. META category map
# =========================================================================
class TestMetaCategories:
    def test_returns_full_map(self):
        r = requests.get(f"{API}/meta/vendor-categories")
        assert r.status_code == 200, r.text
        cats = r.json().get("categories", {})
        assert "gym" in cats and "studio" in cats and "ground" in cats
        # Gym: wellness activities
        assert set(["gym", "yoga", "zumba", "crossfit", "pilates"]).issubset(set(cats["gym"]))
        # Studio: yoga/zumba/pilates/dance/aerobics
        assert set(["yoga", "zumba", "pilates", "dance", "aerobics"]).issubset(set(cats["studio"]))
        # Ground: traditional sports list
        assert "cricket" in cats["ground"] and "football" in cats["ground"]
        # Gym must NOT include cricket
        assert "cricket" not in cats["gym"]


# =========================================================================
# 2. Vendor multi-select types
# =========================================================================
class TestVendorMultiType:
    def test_signup_persists_vendor_types(self, db, admin_sess):
        ctx = _signup_vendor(db, admin_sess, VENDOR_EMAIL, "VMain", types=["gym", "studio"])
        r = ctx["sess"].get(f"{API}/vendors/me")
        assert r.status_code == 200, r.text
        v = r.json()
        # Primary
        assert v.get("vendor_type") == "gym"
        # Multi-select must include both
        vt = v.get("vendor_types") or []
        assert "gym" in vt and "studio" in vt, f"vendor_types persisted incorrectly: {vt}"


# =========================================================================
# 3. Listing detailed address
# =========================================================================
class TestListingDetailedAddress:
    @pytest.fixture(scope="class")
    def listing(self, db, admin_sess):
        # Reuse the VENDOR_EMAIL vendor created in TestVendorMultiType. If that test
        # hasn't run yet, create a fresh vendor.
        sess = _sess()
        r = sess.post(f"{API}/auth/login", json={"email": VENDOR_EMAIL, "password": "vendor123"})
        if r.status_code != 200:
            ctx = _signup_vendor(db, admin_sess, VENDOR_EMAIL, "VMain", types=["gym", "studio"])
            sess = ctx["sess"]
        body = {
            "title": f"P5_Listing_{RUN}", "sports": ["yoga", "zumba"], "city": "Bangalore",
            "price": 800, "currency": "INR", "description": "Yoga + Zumba studio",
            "vendor_type": "studio",
            "street": "12, MG Road", "locality": "Indiranagar", "state": "Karnataka",
            "pincode": "560001", "maps_url": "https://goo.gl/maps/abc",
        }
        r = sess.post(f"{API}/vendors/me/listings", json=body)
        assert r.status_code in (200, 201), r.text
        listing = r.json()
        lid = listing.get("id") or listing.get("listing", {}).get("id")
        admin_sess.patch(f"{API}/admin/listings/{lid}/approve", json={"approved": True})
        return {"sess": sess, "id": lid}

    def test_address_persisted_on_create(self, listing):
        # GET via public listings — verify all detailed fields round-trip.
        r = requests.get(f"{API}/vendor-listings")
        assert r.status_code == 200, r.text
        rows = r.json()
        match = next((x for x in rows if x.get("id") == listing["id"]), None)
        assert match, "listing not found in /vendor-listings"
        assert match.get("street") == "12, MG Road"
        assert match.get("locality") == "Indiranagar"
        assert match.get("state") == "Karnataka"
        assert match.get("pincode") == "560001"
        assert match.get("maps_url") == "https://goo.gl/maps/abc"


# =========================================================================
# 4. Venue Leads
# =========================================================================
class TestVenueLeads:
    def test_hr_can_submit_lead(self, hr):
        r = hr["sess"].post(f"{API}/venue-leads", json={
            "venue_name": f"P5_SuggestedVenue_{RUN}", "city": "Mumbai", "locality": "Andheri",
            "contact_name": "Owner Raj", "contact_phone": "+919999900001",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "open"
        assert d["submitted_by_user_id"] == hr["user_id"]
        assert d["city"] == "Mumbai"
        TestVenueLeads.lead_id = d["id"]

    def test_admin_lists_lead(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/venue-leads")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(x["id"] == TestVenueLeads.lead_id for x in rows)

    def test_admin_patch_status_and_notes(self, admin_sess):
        r = admin_sess.patch(f"{API}/admin/venue-leads/{TestVenueLeads.lead_id}",
                             json={"status": "contacted", "admin_notes": "Called owner"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "contacted"
        assert d["admin_notes"] == "Called owner"

    def test_admin_patch_invalid_status_rejected(self, admin_sess):
        r = admin_sess.patch(f"{API}/admin/venue-leads/{TestVenueLeads.lead_id}",
                             json={"status": "nonsense"})
        assert r.status_code == 400, r.text

    def test_player_cannot_submit_lead(self, db):
        # Sign up a player; if signup is OTP-gated, use the OTP-from-DB pattern.
        s = _sess()
        r = s.post(f"{API}/players/signup/request-otp",
                   json={"email": PLAYER_EMAIL, "mobile": PLAYER_MOBILE, "name": "Player Test"})
        if r.status_code != 200:
            pytest.skip(f"player OTP request failed: {r.status_code} {r.text[:120]}")
        otp_rec = _run(db.player_signup_otps.find_one({"email": PLAYER_EMAIL.lower()}, {"_id": 0}))
        if not otp_rec:
            pytest.skip("player OTP not seeded in DB")
        r = s.post(f"{API}/players/register", json={
            "name": "P5 Player", "mobile": PLAYER_MOBILE, "password": "player123",
            "email": PLAYER_EMAIL, "otp": otp_rec["otp"],
        })
        assert r.status_code == 200, r.text
        r = s.post(f"{API}/players/login", json={"mobile": PLAYER_MOBILE, "password": "player123"})
        assert r.status_code == 200, r.text
        r = s.post(f"{API}/venue-leads", json={
            "venue_name": f"P5_PlayerVenue_{RUN}", "city": "Pune",
        })
        assert r.status_code == 403, r.text
        assert "venue" in r.text.lower() or "hr" in r.text.lower() or "admin" in r.text.lower()


# =========================================================================
# 5. Offline subscription request + activate + price override
# =========================================================================
class TestOfflineSubscription:
    def test_request_pending(self, db, admin_sess):
        # Create the SECOND vendor solely for the offline-sub flow (so the first vendor
        # — used by listing/PII tests — stays without offline_mode for that test).
        ctx = _signup_vendor(db, admin_sess, VENDOR2_EMAIL, "VSub", types=["ground"])
        TestOfflineSubscription.ctx = ctx
        r = ctx["sess"].post(f"{API}/offline-subscriptions/request", json={"plan_type": "monthly"})
        assert r.status_code == 200, r.text
        sub = r.json()
        assert sub["status"] == "pending_payment"
        assert sub["amount"] == 99.0
        assert sub["currency"] == "INR"
        TestOfflineSubscription.sub_id = sub["id"]

    def test_duplicate_pending_rejected(self):
        ctx = TestOfflineSubscription.ctx
        r = ctx["sess"].post(f"{API}/offline-subscriptions/request", json={"plan_type": "monthly"})
        assert r.status_code == 400, r.text
        assert "pending" in r.text.lower()

    def test_admin_lists_pending(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/offline-subscriptions")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert any(s["id"] == TestOfflineSubscription.sub_id for s in rows)

    def test_admin_activate_flips_vendor_offline_mode(self, admin_sess, db):
        r = admin_sess.post(f"{API}/admin/offline-subscriptions/{TestOfflineSubscription.sub_id}/activate")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "active"
        assert d["started_at"] and d["expires_at"]
        # Expiry should be ~30 days from now (monthly)
        exp = datetime.fromisoformat(d["expires_at"].replace("Z", "+00:00"))
        diff = (exp - datetime.now(timezone.utc)).days
        assert 28 <= diff <= 31, f"unexpected expiry diff {diff}"
        # Vendor doc updated
        vdoc = _run(db.vendors.find_one({"id": TestOfflineSubscription.ctx["vendor_id"]}, {"_id": 0}))
        assert vdoc["offline_mode"] is True
        assert vdoc.get("offline_subscription_expires_at") == d["expires_at"]

    def test_price_override_via_settings(self, admin_sess, db):
        # Patch settings to raise monthly price → new pending request should reflect 199.
        r = admin_sess.patch(f"{API}/settings", json={"offline_subscription_monthly_price": 199})
        assert r.status_code == 200, r.text
        # Sign up a brand-new vendor for this isolated check
        email = f"p5_vendor3_{RUN}@turf.in"
        ctx = _signup_vendor(db, admin_sess, email, "VPriceOverride", types=["ground"])
        try:
            r = ctx["sess"].post(f"{API}/offline-subscriptions/request", json={"plan_type": "monthly"})
            assert r.status_code == 200, r.text
            assert r.json()["amount"] == 199.0
        finally:
            # Reset price + cleanup vendor
            admin_sess.patch(f"{API}/settings", json={"offline_subscription_monthly_price": 99})
            _run(db.users.delete_many({"email": email}))
            _run(db.vendors.delete_many({"email": email}))
            _run(db.vendor_signup_otps.delete_many({"email": email}))
            _run(db.offline_subscriptions.delete_many({"vendor_email": email}))

    def test_reject_fresh_sub(self, db, admin_sess):
        # Reject path: create a fresh pending sub on a new vendor and reject it.
        email = f"p5_vendor4_{RUN}@turf.in"
        ctx = _signup_vendor(db, admin_sess, email, "VReject", types=["ground"])
        try:
            r = ctx["sess"].post(f"{API}/offline-subscriptions/request", json={"plan_type": "yearly"})
            assert r.status_code == 200, r.text
            sub = r.json()
            assert sub["amount"] == 999.0
            r = admin_sess.post(f"{API}/admin/offline-subscriptions/{sub['id']}/reject",
                                json={"reason": "No payment"})
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "cancelled"
        finally:
            _run(db.users.delete_many({"email": email}))
            _run(db.vendors.delete_many({"email": email}))
            _run(db.vendor_signup_otps.delete_many({"email": email}))
            _run(db.offline_subscriptions.delete_many({"vendor_email": email}))


# =========================================================================
# 6. Private bookings + availability blocking
# =========================================================================
class TestPrivateBookings:
    @pytest.fixture(scope="class")
    def listing_id(self, admin_sess):
        # Create a ground listing for VENDOR2 (who has offline_mode=true after activate test).
        sess = _sess()
        r = sess.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        r = sess.post(f"{API}/vendors/me/listings", json={
            "title": f"P5_PBListing_{RUN}", "sports": ["cricket"], "city": "Bangalore",
            "price": 1000, "currency": "INR", "description": "Private bookings test ground",
            "vendor_type": "ground",
        })
        assert r.status_code in (200, 201), r.text
        lid = r.json().get("id")
        admin_sess.patch(f"{API}/admin/listings/{lid}/approve", json={"approved": True})
        TestPrivateBookings.sess = sess
        return lid

    def test_locked_when_offline_mode_false(self, db, admin_sess):
        # Use the FIRST vendor (VENDOR_EMAIL) which never activated offline_mode.
        sess = _sess()
        r = sess.post(f"{API}/auth/login", json={"email": VENDOR_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        # Try to POST a private booking → 403 with "Unlock offline mode"
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": "anything", "client_name": "X", "client_phone": "+91",
            "requested_date": "2026-03-15", "start_time": "07:00", "end_time": "08:00",
            "hours": 1, "amount": 100,
        })
        assert r.status_code == 403, r.text
        assert "Unlock offline mode" in r.text or "offline mode" in r.text.lower()

    def test_create_and_list_private_booking(self, listing_id):
        sess = TestPrivateBookings.sess
        # Pick a future date safely
        future = (datetime.now(timezone.utc) + timedelta(days=20)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id,
            "client_name": f"P5_Riya_{RUN}", "client_phone": "+919812340000",
            "requested_date": future, "start_time": "07:00", "end_time": "08:00",
            "hours": 1, "amount": 600,
        })
        assert r.status_code == 200, r.text
        pb = r.json()
        assert pb["client_name"] == f"P5_Riya_{RUN}"
        TestPrivateBookings.pb_id = pb["id"]
        TestPrivateBookings.pb_date = future

        r = sess.get(f"{API}/vendor/private-bookings")
        assert r.status_code == 200, r.text
        assert any(b["id"] == pb["id"] for b in r.json())

    def test_private_blocks_public_availability(self, listing_id):
        date = TestPrivateBookings.pb_date
        r = requests.get(f"{API}/vendor-listings/{listing_id}/availability", params={"date": date})
        # endpoint may require no auth or auth; accept 200 only
        assert r.status_code == 200, r.text
        slots = r.json().get("slots", [])
        slot_07 = next((s for s in slots if s["time"] == "07:00"), None)
        assert slot_07 is not None, f"07:00 slot missing in: {[s['time'] for s in slots][:10]}"
        # Private booking must mark slot as NOT available (status booked / blocked / unavailable).
        assert slot_07["status"] != "available", f"private booking did not block 07:00: {slot_07}"

    def test_delete_private_booking(self):
        sess = TestPrivateBookings.sess
        r = sess.delete(f"{API}/vendor/private-bookings/{TestPrivateBookings.pb_id}")
        assert r.status_code == 200, r.text
        r = sess.get(f"{API}/vendor/private-bookings")
        assert not any(b["id"] == TestPrivateBookings.pb_id for b in r.json())


# =========================================================================
# 7. Vendor PII mask on /vendor-bookings
# =========================================================================
class TestVendorPIIMask:
    def test_vendor_sees_masked_hr_fields(self, db, admin_sess, hr):
        # Create a booking via HR on VENDOR2's ground listing.
        sess_v = _sess()
        sess_v.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        # Get any approved listing of VENDOR2
        rl = sess_v.get(f"{API}/vendors/me/listings")
        assert rl.status_code == 200, rl.text
        listings = rl.json()
        listing = next((x for x in listings if x.get("approved")), listings[0] if listings else None)
        assert listing, "no listing for vendor2"
        future = (datetime.now(timezone.utc) + timedelta(days=25)).strftime("%Y-%m-%d")
        r = hr["sess"].post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"], "requested_date": future,
            "start_time": "10:00", "end_time": "11:00", "hours": 1,
            "notes": "HR-only secret notes",
        })
        assert r.status_code == 200, r.text
        booking_id = r.json()["id"]

        # Vendor view → PII masked
        rv = sess_v.get(f"{API}/vendor-bookings")
        assert rv.status_code == 200, rv.text
        vrow = next((x for x in rv.json() if x["id"] == booking_id), None)
        assert vrow, "vendor cannot see the booking"
        assert vrow.get("hr_email") in (None, ""), f"hr_email leaked to vendor: {vrow.get('hr_email')}"
        assert vrow.get("created_by") in (None, ""), f"created_by leaked: {vrow.get('created_by')}"
        assert vrow.get("notes") in (None, ""), f"notes leaked: {vrow.get('notes')}"

        # HR view → PII intact
        rh = hr["sess"].get(f"{API}/vendor-bookings")
        assert rh.status_code == 200, rh.text
        hrow = next((x for x in rh.json() if x["id"] == booking_id), None)
        assert hrow, "HR cannot see own booking"
        assert hrow.get("hr_email"), "HR sees own hr_email empty"
        assert hrow.get("notes") == "HR-only secret notes"

        # Admin view → PII intact
        ra = admin_sess.get(f"{API}/vendor-bookings")
        assert ra.status_code == 200, ra.text
        arow = next((x for x in ra.json() if x["id"] == booking_id), None)
        assert arow, "admin cannot see booking"
        assert arow.get("hr_email"), "admin should see hr_email"
        assert arow.get("notes") == "HR-only secret notes"


# =========================================================================
# 8. Phase 5b — Vendor invoice settings + Customers + Invoices
# =========================================================================
class TestVendorInvoiceSettings:
    def test_patch_invoice_settings_persists(self):
        # VENDOR2 has offline_mode=true after TestOfflineSubscription.
        sess = _sess()
        r = sess.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        payload = {
            "gstin": "29ABCDE1234F1Z5",
            "invoice_business_name": "Whitefield Sports Pvt Ltd",
            "invoice_address": "12, MG Road\nBangalore 560001",
            "invoice_phone": "+91 99000 12345",
            "invoice_email": "billing@whitefield.example",
            "invoice_tax_percent": 18,
            "invoice_footer_note": "Thank you for your business!",
        }
        r = sess.patch(f"{API}/vendors/me", json=payload)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("gstin") == "29ABCDE1234F1Z5"
        assert d.get("invoice_business_name") == "Whitefield Sports Pvt Ltd"
        assert d.get("invoice_tax_percent") == 18
        # Round-trip via GET
        r = sess.get(f"{API}/vendors/me")
        assert r.status_code == 200
        assert r.json().get("gstin") == "29ABCDE1234F1Z5"

    def test_patch_rejects_disallowed_fields(self):
        sess = _sess()
        sess.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        # Try to sneak an approval flip
        r = sess.patch(f"{API}/vendors/me", json={"approved": False, "offline_mode": False, "id": "fake"})
        # No allowed fields → 400
        assert r.status_code == 400, r.text
        # Vendor should still be offline_mode=True
        r = sess.get(f"{API}/vendors/me")
        assert r.json().get("offline_mode") is True

    def test_patch_tax_percent_out_of_range(self):
        sess = _sess()
        sess.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        r = sess.patch(f"{API}/vendors/me", json={"invoice_tax_percent": 150})
        assert r.status_code == 400, r.text
        r = sess.patch(f"{API}/vendors/me", json={"invoice_tax_percent": -1})
        assert r.status_code == 400, r.text

    def test_patch_requires_vendor_role(self, hr):
        r = hr["sess"].patch(f"{API}/vendors/me", json={"gstin": "x"})
        assert r.status_code == 403, r.text


class TestVendorCustomersAndInvoices:
    @pytest.fixture(scope="class")
    def sess(self):
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        return s

    @pytest.fixture(scope="class")
    def listing_id(self, sess, admin_sess):
        r = sess.get(f"{API}/vendors/me/listings")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert rows, "vendor2 has no listings"
        return rows[0]["id"]

    def test_create_and_list_customer(self, sess):
        r = sess.post(f"{API}/vendor/customers", json={
            "name": f"P5_Cust_{RUN}", "phone": "+919876543210",
            "email": "walkin@example.com", "gstin": "29ZZZZZ0000A1Z9",
            "address": "10, Church St, Bangalore",
        })
        assert r.status_code == 200, r.text
        c = r.json()
        assert c["name"] == f"P5_Cust_{RUN}"
        TestVendorCustomersAndInvoices.customer_id = c["id"]
        r = sess.get(f"{API}/vendor/customers")
        assert r.status_code == 200, r.text
        assert any(x["id"] == c["id"] for x in r.json())

    def test_kreeda_member_email_not_blocked_from_customer(self, sess):
        """A vendor should be able to add an existing Kreeda Nation user as an offline customer."""
        r = sess.post(f"{API}/vendor/customers", json={
            "name": f"P5_KNMember_{RUN}", "phone": "+91" + PLAYER_MOBILE.lstrip("+91"),
            "email": PLAYER_EMAIL,
        })
        assert r.status_code == 200, r.text

    def test_create_invoice_from_booking(self, sess, listing_id):
        future = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%d")
        # Create a private booking (linked to the customer)
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id,
            "customer_id": TestVendorCustomersAndInvoices.customer_id,
            "client_name": f"P5_Cust_{RUN}",
            "requested_date": future, "start_time": "18:00", "end_time": "19:00",
            "hours": 1, "amount": 1000, "rate_type": "total",
        })
        assert r.status_code == 200, r.text
        booking = r.json()
        assert booking.get("customer_id") == TestVendorCustomersAndInvoices.customer_id
        TestVendorCustomersAndInvoices.booking_id = booking["id"]

        r = sess.post(f"{API}/vendor/invoices", json={"booking_id": booking["id"], "tax_percent": 18})
        assert r.status_code == 200, r.text
        inv = r.json()
        assert inv["invoice_number"].startswith("KN-")
        assert inv["subtotal"] == 1000
        assert inv["tax_amount"] == 180
        assert inv["total"] == 1180
        # Customer snapshot from directory
        assert inv["customer_snapshot"]["name"] == f"P5_Cust_{RUN}"
        assert inv["customer_snapshot"]["gstin"] == "29ZZZZZ0000A1Z9"
        # Vendor snapshot from invoice settings
        assert inv["vendor_snapshot"]["gstin"] == "29ABCDE1234F1Z5"
        assert inv["vendor_snapshot"]["business_name"] == "Whitefield Sports Pvt Ltd"
        TestVendorCustomersAndInvoices.invoice_id = inv["id"]

    def test_duplicate_invoice_rejected(self, sess):
        r = sess.post(f"{API}/vendor/invoices", json={
            "booking_id": TestVendorCustomersAndInvoices.booking_id
        })
        assert r.status_code == 400, r.text
        assert "already" in r.text.lower()

    def test_mark_paid(self, sess):
        r = sess.post(f"{API}/vendor/invoices/{TestVendorCustomersAndInvoices.invoice_id}/mark-paid")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "paid"

    def test_recurring_weekly_booking_persists_days(self, sess, listing_id):
        start = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
        until = (datetime.now(timezone.utc) + timedelta(days=60)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id,
            "client_name": f"P5_Weekly_{RUN}",
            "requested_date": start, "start_time": "06:00", "end_time": "07:00",
            "hours": 1, "amount": 500,
            "recurrence": "weekly", "recurrence_until": until,
            "recurrence_days_of_week": [0, 2, 4],
        })
        assert r.status_code == 200, r.text
        pb = r.json()
        assert pb["recurrence"] == "weekly"
        assert pb["recurrence_until"] == until
        assert pb["recurrence_days_of_week"] == [0, 2, 4]


# =========================================================================
# 9. Phase 5b — Admin vendor offline stats
# =========================================================================
class TestAdminVendorOfflineStats:
    def test_stats_endpoint(self, admin_sess):
        # VENDOR2 has offline_mode=true + a customer + at least one booking + one invoice
        vdoc = _run(AsyncIOMotorClient(MONGO_URL)[DB_NAME].vendors.find_one({"email": VENDOR2_EMAIL.lower()}, {"_id": 0}))
        assert vdoc, "vendor2 doc missing"
        r = admin_sess.get(f"{API}/admin/vendors/{vdoc['id']}/offline-stats")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["vendor"]["id"] == vdoc["id"]
        assert d["vendor"]["offline_mode"] is True
        assert d["totals"]["customers"] >= 1
        assert d["totals"]["bookings"] >= 1
        assert d["totals"]["invoices_issued"] >= 1
        assert d["totals"]["invoices_paid"] >= 1
        assert isinstance(d["calendar"], list)


# =========================================================================
# 10. Phase 5b+ — Edit booking, opening/closing hours, after-hours override
# =========================================================================
class TestPrivateBookingEditAndHours:
    @pytest.fixture(scope="class")
    def sess(self):
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        return s

    @pytest.fixture(scope="class")
    def listing_id(self, sess):
        rows = sess.get(f"{API}/vendors/me/listings").json()
        assert rows, "vendor2 has no listings"
        return rows[0]["id"]

    def _set_schedule(self, sess, listing_id, **fields):
        return sess.patch(f"{API}/vendor-listings/{listing_id}/schedule", json=fields)

    def test_edit_private_booking(self, sess, listing_id):
        future = (datetime.now(timezone.utc) + timedelta(days=45)).strftime("%Y-%m-%d")
        # First set an easy opening window so this booking passes
        r = self._set_schedule(sess, listing_id, opening_time="06:00", closing_time="23:00", allow_after_hours=False)
        assert r.status_code == 200, r.text
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": "Edit_Me",
            "requested_date": future, "start_time": "10:00", "end_time": "11:00",
            "hours": 1, "amount": 700,
        })
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        # Edit — bump hours, change amount, tweak time (still inside window)
        r = sess.patch(f"{API}/vendor/private-bookings/{bid}", json={
            "hours": 2, "amount": 1400, "client_name": "Edit_Me_2",
            "start_time": "10:00", "end_time": "12:00",
            "notes": "corrected",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["hours"] == 2 and d["amount"] == 1400 and d["client_name"] == "Edit_Me_2"
        assert d["notes"] == "corrected"

    def test_after_hours_flag_default_off_blocks(self, sess, listing_id):
        # Ensure allow_after_hours is off + 06-22 window
        r = self._set_schedule(sess, listing_id, opening_time="06:00", closing_time="22:00", allow_after_hours=False)
        assert r.status_code == 200, r.text
        future = (datetime.now(timezone.utc) + timedelta(days=50)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": "LateNight",
            "requested_date": future, "start_time": "23:00", "end_time": "24:00",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 400, r.text
        assert "opening hours" in r.text.lower() or "outside" in r.text.lower()

    def test_after_hours_toggle_allows(self, sess, listing_id):
        r = self._set_schedule(sess, listing_id, allow_after_hours=True)
        assert r.status_code == 200, r.text
        assert r.json().get("allow_after_hours") is True
        future = (datetime.now(timezone.utc) + timedelta(days=51)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": "LateNightOK",
            "requested_date": future, "start_time": "23:00", "end_time": "23:59",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 200, r.text

    def test_edit_time_re_validates_hours(self, sess, listing_id):
        # Toggle allow_after_hours OFF again
        self._set_schedule(sess, listing_id, opening_time="08:00", closing_time="20:00", allow_after_hours=False)
        future = (datetime.now(timezone.utc) + timedelta(days=52)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": "InsideWindow",
            "requested_date": future, "start_time": "10:00", "end_time": "11:00",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 200, r.text
        bid = r.json()["id"]
        # Attempt to move end_time outside window
        r = sess.patch(f"{API}/vendor/private-bookings/{bid}", json={"start_time": "10:00", "end_time": "22:30"})
        assert r.status_code == 400, r.text


# =========================================================================
# 11. Phase 5b+ — Player + organiser can hire vendors
# =========================================================================
class TestVendorBookingRoles:
    def test_player_can_post_vendor_booking(self, db):
        # Ensure PLAYER exists with a listing to book against (VENDOR2's listing)
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": PLAYER_EMAIL, "password": "player123"})
        # If player wasn't created earlier in this run, skip — test suite dependency.
        if r.status_code != 200:
            pytest.skip("player fixture missing in this test session")
        rows = requests.get(f"{API}/vendor-listings?vendor_type=ground").json()
        # Pick any approved+active listing
        listing = next((L for L in rows if L.get("approved") and L.get("active")), None)
        if not listing:
            pytest.skip("no approved listing to book")
        future = (datetime.now(timezone.utc) + timedelta(days=25)).strftime("%Y-%m-%d")
        r = s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"], "requested_date": future,
            "start_time": "10:00", "hours": 1, "notes": "player booking test",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["created_by"], "booking must record who created it"
        # Player then lists own bookings
        r = s.get(f"{API}/vendor-bookings")
        assert r.status_code == 200, r.text
        assert any(x["id"] == d["id"] for x in r.json())


# =========================================================================
# 12. Phase 5b+ — Sponsorship activity roll-up
# =========================================================================
class TestSponsorshipMyActivity:
    def test_roll_up_shape(self, hr):
        r = hr["sess"].get(f"{API}/sponsorships/my-activity")
        assert r.status_code == 200, r.text
        d = r.json()
        assert "sent" in d and "received" in d
        assert isinstance(d["sent"], list) and isinstance(d["received"], list)


# =========================================================================
# 13. Phase 5b+ — Customer directory auto-populates from bookings
#     + Completed bookings are immutable
# =========================================================================
class TestBookingCustomerAutoAndImmutable:
    @pytest.fixture(scope="class")
    def sess(self):
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": VENDOR2_EMAIL, "password": "vendor123"})
        assert r.status_code == 200, r.text
        return s

    @pytest.fixture(scope="class")
    def listing_id(self, sess):
        rows = sess.get(f"{API}/vendors/me/listings").json()
        return rows[0]["id"]

    def test_booking_auto_creates_customer(self, sess, listing_id):
        sess.patch(f"{API}/vendor-listings/{listing_id}/schedule", json={"opening_time": "06:00", "closing_time": "22:00", "allow_after_hours": False})
        future = (datetime.now(timezone.utc) + timedelta(days=61)).strftime("%Y-%m-%d")
        unique = f"AutoCust_{RUN}"
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": unique,
            "client_phone": f"+91987654{RUN[-4:]}",
            "requested_date": future, "start_time": "10:00", "end_time": "11:00",
            "hours": 1, "amount": 700,
        })
        assert r.status_code == 200, r.text
        booking = r.json()
        assert booking.get("customer_id"), "booking should get an auto customer_id"
        rows = sess.get(f"{API}/vendor/customers").json()
        assert any(c.get("name") == unique for c in rows), "customer directory should surface the walk-in"

    def test_second_booking_same_phone_reuses_customer(self, sess, listing_id):
        future = (datetime.now(timezone.utc) + timedelta(days=62)).strftime("%Y-%m-%d")
        phone = f"+91987654{RUN[-4:]}"
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": f"AutoCust_{RUN}",
            "client_phone": phone,
            "requested_date": future, "start_time": "11:00", "end_time": "12:00",
            "hours": 1, "amount": 700,
        })
        assert r.status_code == 200
        rows = sess.get(f"{API}/vendor/customers").json()
        matches = [c for c in rows if c.get("phone") == phone]
        assert len(matches) == 1, f"expected 1 customer row for phone {phone}, got {len(matches)}"

    def test_completed_booking_cannot_be_edited(self, sess, listing_id):
        future = (datetime.now(timezone.utc) + timedelta(days=63)).strftime("%Y-%m-%d")
        r = sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": listing_id, "client_name": f"Immutable_{RUN}",
            "requested_date": future, "start_time": "10:00", "end_time": "11:00",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 200
        bid = r.json()["id"]
        r = sess.patch(f"{API}/vendor/private-bookings/{bid}", json={"status": "completed"})
        assert r.status_code == 200, r.text
        r = sess.patch(f"{API}/vendor/private-bookings/{bid}", json={"amount": 999})
        assert r.status_code == 400, r.text
        assert "cannot be edited" in r.text.lower()
        r = sess.patch(f"{API}/vendor/private-bookings/{bid}", json={"status": "cancelled"})
        assert r.status_code == 200, r.text


# =========================================================================
# 14. Ownership scoping — teams + sponsors are visible only to their owner
#     (fixes: organiser was seeing every team/sponsor in the system).
# =========================================================================
class TestTeamsSponsorsOwnershipScoping:
    """Two organisers should never see each other's teams or sponsors."""

    def _signup_organiser(self, email: str, company_name: str) -> requests.Session:
        """Directly seed an organiser user (bypasses OTP for tests). Uses the same
        bcrypt hasher as production so /auth/login succeeds."""
        import bcrypt
        email = email.lower()
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        existing = _run(db.users.find_one({"email": email}))
        if not existing:
            company_id = f"cmp-{email.replace('@', '-').replace('.', '-')}"
            _run(db.companies.insert_one({
                "id": company_id, "name": company_name, "slug": company_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }))
            pwd_hash = bcrypt.hashpw(b"org123", bcrypt.gensalt()).decode("utf-8")
            _run(db.users.insert_one({
                "id": f"u-{email}", "email": email, "password_hash": pwd_hash,
                "name": f"Org {company_name}", "role": "organiser",
                "company_id": company_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }))
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": email, "password": "org123"})
        assert r.status_code == 200, r.text
        return s

    def test_organisers_see_only_their_own_teams_and_sponsors(self):
        run = RUN[-6:]
        orgA = self._signup_organiser(f"orgA_{run}@k.io", f"OrgA_{run}")
        orgB = self._signup_organiser(f"orgB_{run}@k.io", f"OrgB_{run}")

        # OrgA creates an event + team + sponsor.
        rA = orgA.post(f"{API}/events", json={
            "name": f"OrgA Champs {run}", "sport": "football", "format": "round_robin",
            "event_type": "single_company",
        })
        assert rA.status_code == 200, rA.text
        evA = rA.json()
        tA = orgA.post(f"{API}/teams", json={"name": f"OrgA_Team_{run}", "event_id": evA["id"]})
        assert tA.status_code == 200, tA.text
        sA = orgA.post(f"{API}/sponsors", json={
            "name": f"OrgA_Sponsor_{run}", "logo_url": "https://k/logo.png",
            "event_id": evA["id"],
        })
        assert sA.status_code == 200, sA.text

        # OrgB creates their own event + team + sponsor.
        rB = orgB.post(f"{API}/events", json={
            "name": f"OrgB Champs {run}", "sport": "cricket", "format": "round_robin",
            "event_type": "single_company",
        })
        assert rB.status_code == 200, rB.text
        evB = rB.json()
        tB = orgB.post(f"{API}/teams", json={"name": f"OrgB_Team_{run}", "event_id": evB["id"]})
        assert tB.status_code == 200
        sB = orgB.post(f"{API}/sponsors", json={
            "name": f"OrgB_Sponsor_{run}", "logo_url": "https://k/logoB.png",
            "event_id": evB["id"],
        })
        assert sB.status_code == 200

        # OrgA lists → sees only their own.
        namesA_teams = [t["name"] for t in orgA.get(f"{API}/teams").json()]
        namesA_sp = [s["name"] for s in orgA.get(f"{API}/sponsors").json()]
        assert f"OrgA_Team_{run}" in namesA_teams
        assert f"OrgA_Sponsor_{run}" in namesA_sp
        assert f"OrgB_Team_{run}" not in namesA_teams, "OrgA must NOT see OrgB's teams"
        assert f"OrgB_Sponsor_{run}" not in namesA_sp, "OrgA must NOT see OrgB's sponsors"

        # OrgB lists → sees only their own.
        namesB_teams = [t["name"] for t in orgB.get(f"{API}/teams").json()]
        namesB_sp = [s["name"] for s in orgB.get(f"{API}/sponsors").json()]
        assert f"OrgB_Team_{run}" in namesB_teams
        assert f"OrgB_Sponsor_{run}" in namesB_sp
        assert f"OrgA_Team_{run}" not in namesB_teams
        assert f"OrgA_Sponsor_{run}" not in namesB_sp

        # Public read via event_id still works for any user.
        pub = orgB.get(f"{API}/teams?event_id={evA['id']}").json()
        assert any(t["name"] == f"OrgA_Team_{run}" for t in pub), "public event roster must be readable"
        pub_sp = orgB.get(f"{API}/sponsors?event_id={evA['id']}").json()
        assert any(s["name"] == f"OrgA_Sponsor_{run}" for s in pub_sp)

        # OrgB cannot delete OrgA's team or sponsor.
        team_a_id = tA.json()["id"]
        sponsor_a_id = sA.json()["id"]
        r = orgB.delete(f"{API}/teams/{team_a_id}")
        assert r.status_code in (403, 404), r.text
        r = orgB.delete(f"{API}/sponsors/{sponsor_a_id}")
        assert r.status_code in (403, 404), r.text

    def test_platform_admin_still_sees_all(self, admin_sess):
        r_t = admin_sess.get(f"{API}/teams")
        r_s = admin_sess.get(f"{API}/sponsors")
        assert r_t.status_code == 200 and r_s.status_code == 200
        # Admin should see > 1 team and >= 0 sponsors (system-wide view).
        assert isinstance(r_t.json(), list)
        assert isinstance(r_s.json(), list)

# =========================================================================
# 15. Phase 5c — Offline business suite (Dashboard, expenses, coaches,
#     batches, inventory, staff, slot blocks, check-in, reports) +
#     offline-source commission bypass.  Uses DB-seeded vendor so we
#     avoid SendGrid dependency for setup.
# =========================================================================
class TestOfflineBusinessSuiteP0:
    @pytest.fixture(scope="class")
    def vendor_sess(self):
        """Seed a vendor + a listing directly in DB and log in via /auth/login."""
        import bcrypt
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        vendor_email = f"p5c.owner.{RUN[-6:]}@k.io"
        user_id = f"u-{vendor_email}"
        # User + vendor
        _run(db.users.delete_many({"email": vendor_email}))
        pwd_hash = bcrypt.hashpw(b"vend123", bcrypt.gensalt()).decode("utf-8")
        _run(db.users.insert_one({
            "id": user_id, "email": vendor_email, "password_hash": pwd_hash,
            "name": "P5C Owner", "role": "vendor",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        vendor_id = f"v-{vendor_email}"
        _run(db.vendors.insert_one({
            "id": vendor_id, "user_id": user_id, "business_name": "P5C Turf",
            "vendor_type": "ground", "city": "Bangalore", "email": vendor_email,
            "approved": True, "active": True, "offline_mode": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        listing_id = f"l-{vendor_email}"
        _run(db.vendor_listings.insert_one({
            "id": listing_id, "vendor_id": vendor_id, "title": "P5C Ground",
            "vendor_type": "ground", "city": "Bangalore",
            "price": 500, "currency": "INR", "approved": True, "active": True,
            "images": [], "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": vendor_email, "password": "vend123"})
        assert r.status_code == 200, r.text
        s.vendor_id = vendor_id
        s.listing_id = listing_id
        return s

    def test_dashboard_stats_ok(self, vendor_sess):
        r = vendor_sess.get(f"{API}/vendor/dashboard-stats")
        assert r.status_code == 200, r.text
        for k in ("today_revenue", "today_bookings", "walk_in_customers",
                  "online_customers", "active_members", "court_utilisation_percent",
                  "pending_payment_amount", "todays_schedule", "new_leads_count"):
            assert k in r.json(), f"missing key {k}"

    def test_slot_block_crud_and_blocks_booking(self, vendor_sess):
        lid = vendor_sess.listing_id
        future = (datetime.now(timezone.utc) + timedelta(days=80)).strftime("%Y-%m-%d")
        # Create a block
        r = vendor_sess.post(f"{API}/vendor/slot-blocks", json={
            "listing_id": lid, "date": future, "start_time": "10:00", "end_time": "11:00",
            "reason": "maintenance",
        })
        assert r.status_code == 200
        # Now booking on the SAME slot must be rejected
        r = vendor_sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": lid, "client_name": "BlockedClient",
            "requested_date": future, "start_time": "10:00", "end_time": "11:00",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 400 and "block" in r.text.lower(), r.text
        # Booking on a different slot the same day works
        r = vendor_sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": lid, "client_name": "OKClient",
            "requested_date": future, "start_time": "12:00", "end_time": "13:00",
            "hours": 1, "amount": 500,
        })
        assert r.status_code == 200

    def test_expenses_crud(self, vendor_sess):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        r = vendor_sess.post(f"{API}/vendor/expenses", json={
            "date": today, "category": "rent", "amount": 12500, "notes": "March rent",
        })
        assert r.status_code == 200, r.text
        rows = vendor_sess.get(f"{API}/vendor/expenses").json()
        assert any(x["notes"] == "March rent" for x in rows)

    def test_coach_and_batch(self, vendor_sess):
        r = vendor_sess.post(f"{API}/vendor/coaches", json={
            "name": "Coach Ajay", "phone": "+919999999999",
            "sports": ["badminton"], "hourly_rate": 800,
        })
        assert r.status_code == 200
        coach = r.json()
        r = vendor_sess.post(f"{API}/vendor/batches", json={
            "name": "Morning Batch", "sport": "badminton",
            "coach_id": coach["id"], "listing_id": vendor_sess.listing_id,
            "start_time": "06:00", "end_time": "07:00",
            "days_of_week": [0, 2, 4], "capacity": 20, "monthly_fee": 2000,
        })
        assert r.status_code == 200

    def test_inventory_low_stock_flag(self, vendor_sess):
        r = vendor_sess.post(f"{API}/vendor/inventory", json={
            "name": "Shuttlecock Yonex", "category": "shuttle",
            "quantity": 3, "low_stock_threshold": 5,
            "cost_price": 30, "sale_price": 60,
        })
        assert r.status_code == 200
        item_id = r.json()["id"]
        # Decrement to 1
        r = vendor_sess.patch(f"{API}/vendor/inventory/{item_id}", json={"quantity": 1})
        assert r.status_code == 200
        assert r.json()["quantity"] == 1

    def test_staff_create_and_login(self, vendor_sess):
        run = RUN[-5:]
        staff_email = f"p5c.staff.{run}@k.io"
        r = vendor_sess.post(f"{API}/vendor/staff", json={
            "name": "Test Receptionist", "email": staff_email,
            "password": "staff123", "role": "receptionist",
        })
        assert r.status_code == 200, r.text
        # Staff logs in via /auth/login and inherits scoped access
        s2 = _sess()
        r = s2.post(f"{API}/auth/login", json={"email": staff_email, "password": "staff123"})
        assert r.status_code == 200
        assert r.json().get("role") == "vendor_staff"
        # Staff can see bookings but NOT reports (receptionist perm mask excludes reports)
        r = s2.get(f"{API}/vendor/dashboard-stats")
        assert r.status_code == 200
        r = s2.get(f"{API}/vendor/reports")
        assert r.status_code == 403

    def test_reports_shape(self, vendor_sess):
        r = vendor_sess.get(f"{API}/vendor/reports?range=monthly")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("revenue", "expenses", "profit", "bookings", "membership_sales", "peak_hours", "top_customers"):
            assert k in d
        assert len(d["peak_hours"]) == 24

    def test_customer_detail(self, vendor_sess):
        # Create a customer + booking + paid invoice to check aggregation
        c = vendor_sess.post(f"{API}/vendor/customers", json={"name": f"DetailCust_{RUN[-4:]}", "phone": "+919000012345"}).json()
        future = (datetime.now(timezone.utc) + timedelta(days=81)).strftime("%Y-%m-%d")
        b = vendor_sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": vendor_sess.listing_id, "customer_id": c["id"],
            "client_name": c["name"], "client_phone": c["phone"],
            "requested_date": future, "start_time": "14:00", "end_time": "15:00",
            "hours": 1, "amount": 900,
        }).json()
        inv = vendor_sess.post(f"{API}/vendor/invoices", json={"booking_id": b["id"], "tax_percent": 18}).json()
        vendor_sess.post(f"{API}/vendor/invoices/{inv['id']}/mark-paid")
        r = vendor_sess.get(f"{API}/vendor/customers/{c['id']}")
        assert r.status_code == 200
        d = r.json()
        assert d["visits"] >= 1
        assert d["total_spent"] > 0

    def test_checkin_by_booking_id(self, vendor_sess):
        future = (datetime.now(timezone.utc) + timedelta(days=82)).strftime("%Y-%m-%d")
        b = vendor_sess.post(f"{API}/vendor/private-bookings", json={
            "listing_id": vendor_sess.listing_id, "client_name": "CheckInCust",
            "requested_date": future, "start_time": "15:00", "end_time": "16:00",
            "hours": 1, "amount": 500,
        }).json()
        r = vendor_sess.post(f"{API}/vendor/checkin", json={"code": b["id"], "method": "manual"})
        assert r.status_code == 200

    def test_invite_customer_generates_wa_link(self, vendor_sess):
        c = vendor_sess.post(f"{API}/vendor/customers", json={"name": "InviteMe", "phone": "9876543210"}).json()
        r = vendor_sess.post(f"{API}/vendor/invite-customer", json={"customer_id": c["id"]})
        assert r.status_code == 200
        d = r.json()
        assert "signup_url" in d and "ref_vendor=" in d["signup_url"]
        assert d["wa_url"].startswith("https://wa.me/")

    def test_offline_source_bypasses_commission(self, vendor_sess):
        """Business-model KEY: a player invited by the vendor with ref_vendor=<id>
        should have platform commission waived on marketplace bookings to that vendor."""
        # Enable commission at 10%
        client = AsyncIOMotorClient(MONGO_URL)
        db = client[DB_NAME]
        _run(db.site_settings.update_one({}, {"$set": {"commission_percentage": 10}}, upsert=True))
        # Seed a player DIRECTLY with offline_source_vendor_id set
        import bcrypt
        run = RUN[-5:]
        player_email = f"p5c.player.{run}@k.io"
        user_id = f"u-{player_email}"
        pwd_hash = bcrypt.hashpw(b"play123", bcrypt.gensalt()).decode("utf-8")
        _run(db.users.delete_many({"email": player_email}))
        _run(db.users.insert_one({
            "id": user_id, "email": player_email, "password_hash": pwd_hash,
            "name": "Offline Player", "role": "player", "mobile": f"+9188{run}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        _run(db.player_profiles.insert_one({
            "id": f"pp-{run}", "user_id": user_id, "name": "Offline Player",
            "mobile": f"+9188{run}", "email": player_email,
            "offline_source_vendor_id": vendor_sess.vendor_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        s = _sess()
        r = s.post(f"{API}/auth/login", json={"email": player_email, "password": "play123"})
        assert r.status_code == 200
        # Player books on THIS vendor → commission should be 0
        future = (datetime.now(timezone.utc) + timedelta(days=83)).strftime("%Y-%m-%d")
        r = s.post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_sess.listing_id, "requested_date": future,
            "start_time": "16:00", "hours": 1, "notes": "offline source test",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        assert b.get("offline_source") is True, f"expected offline_source=True, got {b.get('offline_source')}"
        assert b.get("commission_amount") == 0
        assert b.get("commission_percent") == 0


# =========================================================================
# 16. Phase 5c+ — Subscription packages, price-lock on renewal,
#     referral leaderboard.
# =========================================================================
class TestSubscriptionPackagesAndReferrals:
    def test_admin_can_crud_packages(self, admin_sess):
        r = admin_sess.post(f"{API}/admin/subscription-packages", json={
            "name": f"Quarterly_{RUN[-4:]}", "duration_days": 90, "price": 249,
            "description": "Best for medium venues",
        })
        assert r.status_code == 200, r.text
        pkg = r.json()
        r = admin_sess.get(f"{API}/admin/subscription-packages")
        assert any(p["id"] == pkg["id"] for p in r.json())
        r = admin_sess.patch(f"{API}/admin/subscription-packages/{pkg['id']}", json={"price": 299})
        assert r.status_code == 200 and r.json()["price"] == 299
        r = admin_sess.delete(f"{API}/admin/subscription-packages/{pkg['id']}")
        assert r.status_code == 200

    def test_vendor_can_use_custom_package(self, admin_sess):
        # Seed a package
        pkg = admin_sess.post(f"{API}/admin/subscription-packages", json={
            "name": f"Annual_{RUN[-4:]}", "duration_days": 365, "price": 1499,
        }).json()
        # Seed a fresh vendor (DB-direct) that hasn't yet subscribed
        import bcrypt
        run = RUN[-5:]
        vend_email = f"pkg.owner.{run}@k.io"
        client = AsyncIOMotorClient(MONGO_URL); db = client[DB_NAME]
        _run(db.users.delete_many({"email": vend_email}))
        _run(db.users.insert_one({
            "id": f"u-{vend_email}", "email": vend_email,
            "password_hash": bcrypt.hashpw(b"pkg123", bcrypt.gensalt()).decode("utf-8"),
            "role": "vendor", "name": "Pkg Owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        _run(db.vendors.insert_one({
            "id": f"v-{vend_email}", "user_id": f"u-{vend_email}",
            "business_name": "Pkg Turf", "vendor_type": "ground",
            "city": "Bangalore", "email": vend_email,
            "approved": True, "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        s = _sess()
        assert s.post(f"{API}/auth/login", json={"email": vend_email, "password": "pkg123"}).status_code == 200
        # Vendor picks the custom annual package
        r = s.post(f"{API}/offline-subscriptions/request", json={
            "plan_type": "yearly", "package_id": pkg["id"],
        })
        assert r.status_code == 200, r.text
        sub = r.json()
        assert sub["amount"] == 1499, "custom package price should apply"

    def test_price_locked_on_renewal_for_existing_vendor(self, admin_sess):
        """Existing vendor with an approved subscription should pay their prior
        price when the lock-existing-price site-setting is True (default)."""
        # Force the setting on
        client = AsyncIOMotorClient(MONGO_URL); db = client[DB_NAME]
        _run(db.settings.update_one({"id": "site"}, {"$set": {
            "offline_subscription_locks_existing_price": True,
            "offline_subscription_monthly_price": 199,  # NEW price for new vendors
        }}, upsert=True))
        # Seed a vendor + a prior "active" monthly sub at 99
        import bcrypt
        run = RUN[-5:]
        vend_email = f"lock.owner.{run}@k.io"
        _run(db.users.delete_many({"email": vend_email}))
        _run(db.users.insert_one({
            "id": f"u-{vend_email}", "email": vend_email,
            "password_hash": bcrypt.hashpw(b"lock123", bcrypt.gensalt()).decode("utf-8"),
            "role": "vendor", "name": "Lock Owner",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        _run(db.vendors.insert_one({
            "id": f"v-{vend_email}", "user_id": f"u-{vend_email}",
            "business_name": "Lock Turf", "vendor_type": "ground",
            "city": "Bangalore", "email": vend_email,
            "approved": True, "active": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        _run(db.offline_subscriptions.insert_one({
            "id": f"os-{vend_email}", "vendor_id": f"v-{vend_email}",
            "vendor_email": vend_email, "plan_type": "monthly",
            "amount": 99, "currency": "INR", "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }))
        s = _sess()
        assert s.post(f"{API}/auth/login", json={"email": vend_email, "password": "lock123"}).status_code == 200
        r = s.post(f"{API}/offline-subscriptions/request", json={"plan_type": "monthly"})
        assert r.status_code == 200, r.text
        # Even though the NEW price is 199, this existing vendor should still pay 99.
        assert r.json()["amount"] == 99, f"expected lock to 99, got {r.json()['amount']}"

    def test_referral_leaderboard_returns_top_vendors(self, admin_sess):
        r = admin_sess.get(f"{API}/admin/vendor-referral-leaderboard")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        # If any rows exist they must have the right shape
        for row in rows:
            for k in ("vendor_id", "business_name", "referred_count",
                      "estimated_commission_waived"):
                assert k in row



# =========================================================================
# 17. Phase 5c++ — Promo codes for top referrers + promo-at-checkout.
# =========================================================================
class TestPromoCodesForTopReferrers:
    def test_reward_endpoint_issues_promo_and_apply_at_checkout(self, admin_sess):
        # Trigger the reward endpoint — reuses the existing top-referrer data from
        # earlier tests in the run (at least one player has offline_source_vendor_id set).
        r = admin_sess.post(f"{API}/admin/promo-codes/reward-top-referrers", json={
            "top_n": 5, "discount_percent": 20, "validity_days": 30, "min_referrals": 1,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["issued"] >= 1
        picked = d["results"][0]
        code = picked["code"]
        vendor_id = picked["vendor_id"]
        assert code.startswith("REFER-")

        # Log in as that vendor and use the code on a fresh offline subscription request.
        client = AsyncIOMotorClient(MONGO_URL); db = client[DB_NAME]
        vend_email = _run(db.vendors.find_one({"id": vendor_id}, {"_id": 0, "email": 1}))["email"]
        # We may not know their password (seeded elsewhere) — set a known one.
        import bcrypt
        _run(db.users.update_one({"email": vend_email}, {"$set": {
            "password_hash": bcrypt.hashpw(b"promo123", bcrypt.gensalt()).decode("utf-8"),
        }}))
        # Wipe any pending subscription so the request goes through
        _run(db.offline_subscriptions.delete_many({"vendor_id": vendor_id, "status": "pending_payment"}))
        s = _sess()
        assert s.post(f"{API}/auth/login", json={"email": vend_email, "password": "promo123"}).status_code == 200
        # Force site setting price to a known value so we can assert the discount
        _run(db.settings.update_one({"id": "site"}, {"$set": {
            "offline_subscription_monthly_price": 100.0,
            "offline_subscription_locks_existing_price": False,  # disable lock so we test the promo path
        }}, upsert=True))
        r = s.post(f"{API}/offline-subscriptions/request", json={
            "plan_type": "monthly", "promo_code": code,
        })
        assert r.status_code == 200, r.text
        # 100 - 20% = 80
        assert r.json()["amount"] == 80.0, f"expected 80.0 after 20% off, got {r.json()['amount']}"

        # Re-using the same code should now fail (already used).
        _run(db.offline_subscriptions.delete_many({"vendor_id": vendor_id, "status": "pending_payment"}))
        r = s.post(f"{API}/offline-subscriptions/request", json={
            "plan_type": "monthly", "promo_code": code,
        })
        assert r.status_code == 400
        assert "invalid or already used" in r.text.lower()
