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
