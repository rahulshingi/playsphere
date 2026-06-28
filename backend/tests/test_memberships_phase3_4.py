"""
Phase 3 (apply membership at booking + renewal reminder) and Phase 4 (utilization endpoint)
backend tests. Uses OTP-driven signup with OTPs read directly from MongoDB
(same pattern as test_memberships_phase2.py).
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

# Allow importing backend modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from routes.memberships_scheduler import _check_and_send  # noqa: E402


BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"

RUN = uuid.uuid4().hex[:8]
VENDOR_A_EMAIL = f"p34_vendorA_{RUN}@turf.in"
VENDOR_B_EMAIL = f"p34_vendorB_{RUN}@turf.in"
HR_EMAIL = f"p34_hr_{RUN}@acmecorp.in"
HR_OTHER_EMAIL = f"p34_hr_other_{RUN}@acmecorp.in"


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
    assert rec, f"No OTP record for {email} in {collection}"
    return rec["otp"]


def _sess():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- cleanup ----------
@pytest.fixture(scope="session", autouse=True)
def cleanup(db):
    yield
    emails = [VENDOR_A_EMAIL, VENDOR_B_EMAIL, HR_EMAIL, HR_OTHER_EMAIL]
    _run(db.users.delete_many({"email": {"$in": emails}}))
    _run(db.vendors.delete_many({"email": {"$in": [VENDOR_A_EMAIL, VENDOR_B_EMAIL]}}))
    _run(db.vendor_signup_otps.delete_many({"email": {"$in": [VENDOR_A_EMAIL, VENDOR_B_EMAIL]}}))
    _run(db.company_signup_otps.delete_many({"email": {"$in": [HR_EMAIL, HR_OTHER_EMAIL]}}))
    _run(db.companies.delete_many({"name": {"$regex": f"^P34_.*{RUN}"}}))
    _run(db.vendor_listings.delete_many({"title": {"$regex": f"^P34_.*{RUN}"}}))
    _run(db.membership_plans.delete_many({"title": {"$regex": f"^P34_.*{RUN}"}}))
    _run(db.membership_purchases.delete_many({"buyer_email": {"$in": emails}}))
    _run(db.vendor_bookings.delete_many({"hr_email": {"$in": emails}}))


# ---------- fixtures ----------
@pytest.fixture(scope="module")
def admin_sess():
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


def _create_vendor(db, admin_sess, email, label):
    s = _sess()
    r = s.post(f"{API}/vendors/signup/request-otp", json={
        "email": email, "business_name": f"P34_{label}_{RUN}",
    })
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "vendor_signup_otps", email)
    r = s.post(f"{API}/vendors/signup", json={
        "business_name": f"P34_{label}_{RUN}",
        "vendor_type": "ground", "contact_name": f"Vendor {label}",
        "mobile": "+91999900" + str(abs(hash(label)) % 10000).zfill(4),
        "email": email, "password": "vendor123", "city": "Bangalore",
        "otp": otp,
    })
    assert r.status_code == 200, r.text
    vdoc = _run(db.vendors.find_one({"email": email.lower()}, {"_id": 0}))
    assert vdoc, f"vendor row not found for {email}"
    admin_sess.patch(f"{API}/vendors/{vdoc['id']}/approve", json={"approved": True})
    r = s.post(f"{API}/auth/login", json={"email": email, "password": "vendor123"})
    assert r.status_code == 200, r.text
    return {"sess": s, "vendor_id": vdoc["id"]}


def _create_listing(sess, admin_sess, label):
    r = sess.post(f"{API}/vendors/me/listings", json={
        "title": f"P34_{label}_{RUN}", "sports": ["cricket"], "city": "Bangalore",
        "price": 1500, "currency": "INR", "description": "Test", "vendor_type": "ground",
    })
    assert r.status_code in (200, 201), r.text
    listing = r.json()
    lid = listing.get("id") or listing.get("listing", {}).get("id")
    admin_sess.patch(f"{API}/admin/listings/{lid}/approve", json={"approved": True})
    return lid


@pytest.fixture(scope="module")
def vendor_a(db, admin_sess):
    ctx = _create_vendor(db, admin_sess, VENDOR_A_EMAIL, "VA")
    ctx["listing_id"] = _create_listing(ctx["sess"], admin_sess, "VA_L1")
    ctx["listing_id_2"] = _create_listing(ctx["sess"], admin_sess, "VA_L2")
    # Plan covers ONLY listing_id (listing-scoped) with max_bookings=2 to test exhaustion
    r = ctx["sess"].post(f"{API}/memberships/mine", json={
        "title": f"P34_Plan_{RUN}", "plan_type": "monthly", "sports": ["cricket"],
        "listing_ids": [ctx["listing_id"]], "price": 2999, "duration_days": 30,
        "max_bookings": 2, "advance_booking_hours": 24,
    })
    assert r.status_code == 200, r.text
    ctx["plan_id"] = r.json()["id"]
    # Second plan, vendor-wide (no listing_ids), for cross-vendor test
    r = ctx["sess"].post(f"{API}/memberships/mine", json={
        "title": f"P34_PlanWide_{RUN}", "plan_type": "monthly", "sports": ["cricket"],
        "listing_ids": [], "price": 3999, "duration_days": 30,
        "max_bookings": None, "advance_booking_hours": 24,
    })
    assert r.status_code == 200, r.text
    ctx["plan_wide_id"] = r.json()["id"]
    return ctx


@pytest.fixture(scope="module")
def vendor_b(db, admin_sess):
    ctx = _create_vendor(db, admin_sess, VENDOR_B_EMAIL, "VB")
    ctx["listing_id"] = _create_listing(ctx["sess"], admin_sess, "VB_L1")
    return ctx


def _signup_hr(db, email, label):
    s = _sess()
    r = s.post(f"{API}/companies/signup/request-otp",
               json={"admin_email": email, "company_name": f"P34_{label}_{RUN}"})
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "company_signup_otps", email)
    r = s.post(f"{API}/companies/signup", json={
        "company_name": f"P34_{label}_{RUN}", "admin_name": "HR Tester",
        "admin_email": email, "admin_password": "hrpass123",
        "city": "Bangalore", "otp": otp,
    })
    assert r.status_code == 200, r.text
    return {"sess": s, "user_id": r.json()["id"], "email": email}


@pytest.fixture(scope="module")
def hr(db):
    return _signup_hr(db, HR_EMAIL, "AcmeHR")


@pytest.fixture(scope="module")
def hr_other(db):
    return _signup_hr(db, HR_OTHER_EMAIL, "OtherHR")


@pytest.fixture(scope="module")
def active_purchase(vendor_a, hr):
    """HR buys plan_id; vendor activates → active purchase with max_bookings=2."""
    s = hr["sess"]
    r = s.post(f"{API}/memberships/purchase", json={
        "plan_id": vendor_a["plan_id"], "payment_method": "offline",
    })
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    r = vendor_a["sess"].post(f"{API}/memberships/mine/purchases/{pid}/activate")
    assert r.status_code == 200, r.text
    return r.json()


# =========================================================================
# Phase 3 — Eligibility + Apply membership at booking
# =========================================================================
class TestEligibility:
    def test_eligible_for_active_membership(self, hr, vendor_a, active_purchase):
        r = hr["sess"].get(f"{API}/memberships/my-eligibility",
                           params={"listing_id": vendor_a["listing_id"]})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["eligible"] is not None
        e = d["eligible"]
        assert e["purchase_id"] == active_purchase["id"]
        assert e["bookings_used"] == 0
        assert e["bookings_allowed"] == 2
        assert e["bookings_remaining"] == 2

    def test_other_hr_no_eligibility(self, hr_other, vendor_a):
        r = hr_other["sess"].get(f"{API}/memberships/my-eligibility",
                                  params={"listing_id": vendor_a["listing_id"]})
        assert r.status_code == 200, r.text
        assert r.json()["eligible"] is None


class TestApplyMembership:
    def test_apply_membership_zero_total_and_increments(self, hr, vendor_a, active_purchase):
        s = hr["sess"]
        # Booking date 5 days out
        date = (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat()
        r = s.post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_a["listing_id"],
            "requested_date": date, "start_time": "09:00", "end_time": "10:00",
            "sport": "cricket", "notes": "phase3 apply",
            "apply_membership_id": active_purchase["id"],
        })
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] == 0
        assert b["applied_membership_id"] == active_purchase["id"]
        # Verify bookings_used increment
        r = s.get(f"{API}/memberships/my-purchases")
        assert r.status_code == 200, r.text
        mine = [p for p in r.json() if p["id"] == active_purchase["id"]][0]
        assert mine["bookings_used"] == 1

    def test_normal_booking_without_membership_charges_hourly(self, hr_other, vendor_a):
        date = (datetime.now(timezone.utc) + timedelta(days=6)).date().isoformat()
        r = hr_other["sess"].post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_a["listing_id"],
            "requested_date": date, "start_time": "11:00", "end_time": "12:00",
            "sport": "cricket",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["total"] > 0  # 1500 * 1h
        assert b.get("applied_membership_id") is None

    def test_apply_membership_listing_scoped_rejected(self, hr, vendor_a, active_purchase):
        # plan_id covers only listing_id (not listing_id_2)
        date = (datetime.now(timezone.utc) + timedelta(days=7)).date().isoformat()
        r = hr["sess"].post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_a["listing_id_2"],
            "requested_date": date, "start_time": "09:00", "end_time": "10:00",
            "sport": "cricket",
            "apply_membership_id": active_purchase["id"],
        })
        assert r.status_code == 400, r.text
        assert "doesn't cover this listing" in r.json().get("detail", "")

    def test_apply_membership_cross_vendor_rejected(self, hr, vendor_a, vendor_b, db):
        # Buy + activate the vendor-wide plan, then try to apply on vendor_b listing
        s = hr["sess"]
        r = s.post(f"{API}/memberships/purchase", json={
            "plan_id": vendor_a["plan_wide_id"], "payment_method": "offline",
        })
        assert r.status_code == 200, r.text
        wide_pid = r.json()["id"]
        r = vendor_a["sess"].post(f"{API}/memberships/mine/purchases/{wide_pid}/activate")
        assert r.status_code == 200, r.text

        date = (datetime.now(timezone.utc) + timedelta(days=8)).date().isoformat()
        r = s.post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_b["listing_id"],
            "requested_date": date, "start_time": "09:00", "end_time": "10:00",
            "sport": "cricket",
            "apply_membership_id": wide_pid,
        })
        assert r.status_code == 400, r.text
        detail = r.json().get("detail", "").lower()
        assert "different vendor" in detail or "doesn't cover" in detail

    def test_apply_membership_expired_rejected(self, hr, vendor_a, db):
        # Create a fresh active purchase, then mutate expires_at to the past
        s = hr["sess"]
        # Vendor manually issues to bypass dup guard
        r = vendor_a["sess"].post(f"{API}/memberships/mine/issue", json={
            "plan_id": vendor_a["plan_wide_id"], "buyer_email": HR_EMAIL,
            "activate_immediately": True, "notes": "for expiry test",
        })
        assert r.status_code == 200, r.text
        expired_pid = r.json()["id"]
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        _run(db.membership_purchases.update_one(
            {"id": expired_pid}, {"$set": {"expires_at": past}}
        ))
        date = (datetime.now(timezone.utc) + timedelta(days=9)).date().isoformat()
        r = s.post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_a["listing_id"],
            "requested_date": date, "start_time": "09:00", "end_time": "10:00",
            "sport": "cricket",
            "apply_membership_id": expired_pid,
        })
        assert r.status_code == 400, r.text
        assert "expired" in r.json().get("detail", "").lower()

    def test_apply_membership_exhausted_rejected(self, hr, vendor_a, active_purchase, db):
        # Force bookings_used = max_bookings = 2
        _run(db.membership_purchases.update_one(
            {"id": active_purchase["id"]}, {"$set": {"bookings_used": 2}}
        ))
        # Eligibility should now hide it
        r = hr["sess"].get(f"{API}/memberships/my-eligibility",
                           params={"listing_id": vendor_a["listing_id"]})
        # May surface a different active membership (vendor_wide_id) — but the
        # exhausted purchase must not be the one returned.
        if r.json().get("eligible"):
            assert r.json()["eligible"]["purchase_id"] != active_purchase["id"]
        # POST anyway should 400
        date = (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()
        r2 = hr["sess"].post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_a["listing_id"],
            "requested_date": date, "start_time": "09:00", "end_time": "10:00",
            "sport": "cricket",
            "apply_membership_id": active_purchase["id"],
        })
        assert r2.status_code == 400, r2.text
        assert "already used" in r2.json().get("detail", "").lower()


# =========================================================================
# Phase 4 — Utilization endpoint
# =========================================================================
class TestUtilization:
    def test_buyer_can_fetch_utilization(self, hr, active_purchase):
        r = hr["sess"].get(f"{API}/memberships/purchase/{active_purchase['id']}/utilization")
        assert r.status_code == 200, r.text
        d = r.json()
        # After test_apply_membership_zero_total_and_increments + exhausted-mutate,
        # bookings_used should be 2 on this purchase by the time this runs.
        assert d["sessions_allowed"] == 2
        assert d["days_total"] == 30
        # Percent sanity
        if d["sessions_allowed"]:
            expected = round(min(100.0, (d["sessions_used"] / d["sessions_allowed"]) * 100), 1)
            assert d["sessions_percent"] == expected
        # Days percent ~ 0 since just activated
        assert 0 <= d["days_percent"] <= 100

    def test_vendor_can_fetch_utilization(self, vendor_a, active_purchase):
        r = vendor_a["sess"].get(f"{API}/memberships/purchase/{active_purchase['id']}/utilization")
        assert r.status_code == 200, r.text

    def test_random_user_forbidden(self, hr_other, active_purchase):
        r = hr_other["sess"].get(f"{API}/memberships/purchase/{active_purchase['id']}/utilization")
        assert r.status_code == 403, r.text

    def test_unknown_purchase_404(self, hr):
        r = hr["sess"].get(f"{API}/memberships/purchase/does-not-exist/utilization")
        assert r.status_code == 404


# =========================================================================
# Phase 3 — Renewal reminder scheduler (_check_and_send)
# =========================================================================
class TestRenewalReminder:
    @pytest.fixture
    def fake_purchase(self, db, vendor_a, hr):
        # Insert a fake active purchase with expires_at = now+5d, buyer_email set
        pid = f"fake_renewal_{uuid.uuid4().hex[:8]}"
        doc = {
            "id": pid,
            "plan_id": vendor_a["plan_id"],
            "vendor_id": vendor_a["vendor_id"],
            "plan_title": "P34_Renewal_Plan",
            "plan_type": "monthly",
            "price": 999.0,
            "currency": "INR",
            "duration_days": 30,
            "max_bookings": None,
            "buyer_user_id": hr["user_id"],
            "buyer_role": "company_admin",
            "buyer_name": "HR Tester",
            "buyer_email": HR_EMAIL,
            "buyer_company_id": None,
            "payment_method": "offline",
            "notes": "",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "starts_at": (datetime.now(timezone.utc) - timedelta(days=25)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=5)).isoformat(),
            "bookings_used": 0,
            "cancelled_reason": None,
            "issued_by_vendor": True,
            "renewal_reminder_sent_at": None,
        }
        _run(db.membership_purchases.insert_one(doc))
        yield pid
        _run(db.membership_purchases.delete_one({"id": pid}))

    @pytest.fixture
    def fake_purchase_far(self, db, vendor_a, hr):
        # expires in 10 days — outside the 7-day window
        pid = f"fake_far_{uuid.uuid4().hex[:8]}"
        doc = {
            "id": pid, "plan_id": vendor_a["plan_id"],
            "vendor_id": vendor_a["vendor_id"],
            "plan_title": "P34_Far_Plan", "plan_type": "monthly",
            "price": 999.0, "currency": "INR", "duration_days": 30,
            "max_bookings": None,
            "buyer_user_id": hr["user_id"], "buyer_role": "company_admin",
            "buyer_name": "HR Tester", "buyer_email": HR_EMAIL,
            "buyer_company_id": None, "payment_method": "offline",
            "notes": "", "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "starts_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=10)).isoformat(),
            "bookings_used": 0, "cancelled_reason": None,
            "issued_by_vendor": True, "renewal_reminder_sent_at": None,
        }
        _run(db.membership_purchases.insert_one(doc))
        yield pid
        _run(db.membership_purchases.delete_one({"id": pid}))

    def test_within_7day_window_sends_and_idempotent(self, db, fake_purchase):
        calls = []

        def stub_send(email, subject, body, kind=None):
            calls.append({"email": email, "subject": subject, "kind": kind})
            return {"ok": True}

        sent_1 = _run(_check_and_send(db, stub_send))
        assert sent_1 >= 1
        assert any(c["email"] == HR_EMAIL for c in calls)
        doc = _run(db.membership_purchases.find_one({"id": fake_purchase}, {"_id": 0}))
        assert doc["renewal_reminder_sent_at"] is not None

        # Idempotency: 2nd run for THIS purchase must not change the timestamp.
        _run(_check_and_send(db, stub_send))
        doc2 = _run(db.membership_purchases.find_one({"id": fake_purchase}, {"_id": 0}))
        assert doc2["renewal_reminder_sent_at"] == doc["renewal_reminder_sent_at"]

    def test_outside_7day_window_skipped(self, db, fake_purchase_far):
        calls = []

        def stub_send(email, subject, body, kind=None):
            calls.append(email)
            return {"ok": True}

        _run(_check_and_send(db, stub_send))
        # The far purchase's timestamp must remain None
        doc = _run(db.membership_purchases.find_one({"id": fake_purchase_far}, {"_id": 0}))
        assert doc["renewal_reminder_sent_at"] is None
