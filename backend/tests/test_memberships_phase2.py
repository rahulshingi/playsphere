"""
Phase 2 membership purchase + manual issue + Phase 1 past-date regression.

Uses real OTP flow via direct DB read of the OTP collections.
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
import asyncio
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
API = f"{BASE}/api"
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"

RUN = uuid.uuid4().hex[:8]
VENDOR_EMAIL = f"test_vendor_{RUN}@turf.in"
HR_EMAIL = f"test_hr_{RUN}@acmecorp.in"
HR2_EMAIL = f"test_hr2_{RUN}@walkin.in"
PLAYER_EMAIL = f"test_player_{RUN}@example.com"
PLAYER_MOBILE = "+9199" + RUN[:8].ljust(8, "0").replace("a", "0").replace("b", "0").replace("c", "0").replace("d", "0").replace("e", "0").replace("f", "0")


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


@pytest.fixture(scope="session", autouse=True)
def cleanup(db):
    yield
    for email in [VENDOR_EMAIL, HR_EMAIL, HR2_EMAIL, PLAYER_EMAIL]:
        _run(db.users.delete_many({"email": email}))
    _run(db.vendors.delete_many({"email": VENDOR_EMAIL}))
    _run(db.vendor_signup_otps.delete_many({"email": {"$in": [VENDOR_EMAIL]}}))
    _run(db.company_signup_otps.delete_many({"email": {"$in": [HR_EMAIL, HR2_EMAIL]}}))
    _run(db.player_signup_otps.delete_many({"email": PLAYER_EMAIL}))
    _run(db.player_profiles.delete_many({"email": PLAYER_EMAIL}))
    _run(db.companies.delete_many({"name": {"$regex": f"^TEST_.*{RUN}"}}))
    _run(db.vendor_listings.delete_many({"title": {"$regex": f"^TEST_.*{RUN}"}}))
    _run(db.membership_plans.delete_many({"title": {"$regex": f"^TEST_.*{RUN}"}}))
    _run(db.membership_purchases.delete_many({"buyer_email": {"$in": [HR_EMAIL, HR2_EMAIL, PLAYER_EMAIL]}}))


@pytest.fixture(scope="module")
def admin_sess():
    s = _sess()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def vendor_ctx(db, admin_sess):
    s = _sess()
    # Request OTP
    r = s.post(f"{API}/vendors/signup/request-otp", json={
        "email": VENDOR_EMAIL, "business_name": f"TEST_Turf_{RUN}",
    })
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "vendor_signup_otps", VENDOR_EMAIL)
    # Signup
    r = s.post(f"{API}/vendors/signup", json={
        "business_name": f"TEST_Whitefield_{RUN}",
        "vendor_type": "ground",
        "contact_name": "Test Vendor",
        "mobile": "+919999000111",
        "email": VENDOR_EMAIL,
        "password": "vendor123",
        "city": "Bangalore",
        "otp": otp,
    })
    assert r.status_code == 200, r.text
    # Get vendor id from DB
    vdoc = _run(db.vendors.find_one({"email": VENDOR_EMAIL}, {"_id": 0}))
    vendor_id = vdoc["id"]
    # Admin approves vendor
    r = admin_sess.patch(f"{API}/vendors/{vendor_id}/approve", json={"approved": True})
    assert r.status_code == 200, r.text
    # Re-login vendor to refresh cookie/role
    r = s.post(f"{API}/auth/login", json={"email": VENDOR_EMAIL, "password": "vendor123"})
    assert r.status_code == 200, r.text

    # Create listing
    r = s.post(f"{API}/vendors/me/listings", json={
        "title": f"TEST_Turf_{RUN}",
        "sports": ["cricket"],
        "city": "Bangalore",
        "price": 1500,
        "currency": "INR",
        "description": "Test ground",
        "vendor_type": "ground",
    })
    assert r.status_code in (200, 201), r.text
    listing = r.json()
    listing_id = listing.get("id") or listing.get("listing", {}).get("id")
    assert listing_id, listing
    # Admin approves listing
    r = admin_sess.patch(f"{API}/admin/listings/{listing_id}/approve", json={"approved": True})
    assert r.status_code == 200, r.text

    # Create plan
    r = s.post(f"{API}/memberships/mine", json={
        "title": f"TEST_Monthly_{RUN}",
        "plan_type": "monthly",
        "sports": ["cricket"],
        "listing_ids": [listing_id],
        "price": 4999,
        "duration_days": 30,
        "advance_booking_hours": 24,
    })
    assert r.status_code == 200, r.text
    plan = r.json()
    return {"sess": s, "vendor_id": vendor_id, "listing_id": listing_id, "plan_id": plan["id"], "plan": plan}


@pytest.fixture(scope="module")
def hr_ctx(db):
    s = _sess()
    r = s.post(f"{API}/companies/signup/request-otp",
               json={"admin_email": HR_EMAIL, "company_name": f"TEST_Acme_{RUN}"})
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "company_signup_otps", HR_EMAIL)
    r = s.post(f"{API}/companies/signup", json={
        "company_name": f"TEST_Acme_{RUN}",
        "admin_name": "HR Tester",
        "admin_email": HR_EMAIL,
        "admin_password": "hrpass123",
        "city": "Bangalore",
        "otp": otp,
    })
    assert r.status_code == 200, r.text
    me = r.json()
    return {"sess": s, "user_id": me["id"], "email": HR_EMAIL}


@pytest.fixture(scope="module")
def hr2_ctx(db):
    s = _sess()
    r = s.post(f"{API}/companies/signup/request-otp",
               json={"admin_email": HR2_EMAIL, "company_name": f"TEST_Walkin_{RUN}"})
    assert r.status_code == 200, r.text
    otp = _get_otp(db, "company_signup_otps", HR2_EMAIL)
    r = s.post(f"{API}/companies/signup", json={
        "company_name": f"TEST_Walkin_{RUN}",
        "admin_name": "Walkin HR",
        "admin_email": HR2_EMAIL,
        "admin_password": "walkin123",
        "city": "Bangalore",
        "otp": otp,
    })
    assert r.status_code == 200, r.text
    return {"sess": s, "email": HR2_EMAIL}


# ---------- Tests ----------
class TestMembershipPurchase:
    def test_buy_offline_creates_pending(self, hr_ctx, vendor_ctx):
        s = hr_ctx["sess"]
        r = s.post(f"{API}/memberships/purchase", json={
            "plan_id": vendor_ctx["plan_id"],
            "payment_method": "offline",
            "notes": "Will pay UPI tomorrow",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "pending_payment"
        assert d["plan_id"] == vendor_ctx["plan_id"]
        assert d["buyer_email"].lower() == HR_EMAIL.lower()
        assert d["payment_method"] == "offline"
        assert d["price"] == 4999
        pytest.purchase_id = d["id"]

    def test_online_also_lands_pending(self, hr2_ctx, vendor_ctx):
        # Different buyer so no duplicate guard kick-in
        s = hr2_ctx["sess"]
        r = s.post(f"{API}/memberships/purchase", json={
            "plan_id": vendor_ctx["plan_id"],
            "payment_method": "online",
        })
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending_payment"
        # Clean for later manual-issue tests
        pytest.hr2_purchase_id = r.json()["id"]

    def test_duplicate_buy_blocked(self, hr_ctx, vendor_ctx):
        s = hr_ctx["sess"]
        r = s.post(f"{API}/memberships/purchase", json={
            "plan_id": vendor_ctx["plan_id"], "payment_method": "offline",
        })
        assert r.status_code == 400, r.text
        assert "pending" in r.json().get("detail", "").lower()

    def test_my_purchases_lists_pending(self, hr_ctx):
        r = hr_ctx["sess"].get(f"{API}/memberships/my-purchases")
        assert r.status_code == 200, r.text
        ids = [p["id"] for p in r.json()]
        assert pytest.purchase_id in ids

    def test_vendor_inbox_sees_request(self, vendor_ctx):
        r = vendor_ctx["sess"].get(f"{API}/memberships/mine/purchases",
                                    params={"status": "pending_payment"})
        assert r.status_code == 200, r.text
        ids = [p["id"] for p in r.json()]
        assert pytest.purchase_id in ids

    def test_vendor_activates_purchase(self, vendor_ctx):
        r = vendor_ctx["sess"].post(f"{API}/memberships/mine/purchases/{pytest.purchase_id}/activate")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "active"
        assert d["starts_at"] and d["expires_at"]

    def test_activate_twice_rejected(self, vendor_ctx):
        r = vendor_ctx["sess"].post(f"{API}/memberships/mine/purchases/{pytest.purchase_id}/activate")
        assert r.status_code == 400, r.text

    def test_buyer_cannot_cancel_active(self, hr_ctx):
        r = hr_ctx["sess"].post(f"{API}/memberships/my-purchases/{pytest.purchase_id}/cancel",
                                  json={"reason": "oops"})
        assert r.status_code == 400, r.text


class TestRejectAndCancel:
    def test_vendor_rejects_hr2_pending(self, vendor_ctx, hr2_ctx):
        # hr2 still has pending purchase from test_online_also_lands_pending
        r = vendor_ctx["sess"].post(
            f"{API}/memberships/mine/purchases/{pytest.hr2_purchase_id}/reject",
            json={"reason": "no payment received"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

    def test_buyer_cancels_own_pending(self, hr2_ctx, vendor_ctx):
        # hr2 buys again now that previous is cancelled
        s = hr2_ctx["sess"]
        r = s.post(f"{API}/memberships/purchase", json={
            "plan_id": vendor_ctx["plan_id"], "payment_method": "offline"})
        assert r.status_code == 200, r.text
        pid = r.json()["id"]
        r = s.post(f"{API}/memberships/my-purchases/{pid}/cancel", json={"reason": "test"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"


class TestManualIssue:
    def test_issue_unknown_email_404(self, vendor_ctx):
        r = vendor_ctx["sess"].post(f"{API}/memberships/mine/issue", json={
            "plan_id": vendor_ctx["plan_id"],
            "buyer_email": f"nobody_{RUN}@nowhere.test",
            "activate_immediately": True,
        })
        assert r.status_code == 404, r.text
        assert "no kreeda nation user" in r.json().get("detail", "").lower()

    def test_issue_to_existing_user(self, vendor_ctx, hr2_ctx):
        r = vendor_ctx["sess"].post(f"{API}/memberships/mine/issue", json={
            "plan_id": vendor_ctx["plan_id"],
            "buyer_email": HR2_EMAIL,
            "activate_immediately": True,
            "notes": "walk-in cash",
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "active"
        assert d["issued_by_vendor"] is True
        assert d["buyer_email"].lower() == HR2_EMAIL.lower()
        assert d["starts_at"] and d["expires_at"]

    def test_issue_not_my_plan(self, hr_ctx, vendor_ctx):
        # HR tries to call vendor-only endpoint → 403
        r = hr_ctx["sess"].post(f"{API}/memberships/mine/issue", json={
            "plan_id": vendor_ctx["plan_id"],
            "buyer_email": HR2_EMAIL,
        })
        assert r.status_code == 403, r.text


class TestPastDateRegression:
    def test_vendor_booking_past_date_rejected(self, hr_ctx, vendor_ctx):
        r = hr_ctx["sess"].post(f"{API}/vendor-bookings", json={
            "listing_id": vendor_ctx["listing_id"],
            "requested_date": "2020-01-01",
            "start_time": "09:00",
            "end_time": "10:00",
            "sport": "cricket",
            "notes": "past date test",
        })
        assert r.status_code == 400, r.text
        assert "past" in r.json().get("detail", "").lower()

    def test_block_past_date_rejected(self, vendor_ctx):
        r = vendor_ctx["sess"].post(
            f"{API}/vendor-listings/{vendor_ctx['listing_id']}/blocks",
            json={"date": "2020-01-01", "start_time": "09:00", "end_time": "10:00", "reason": "test"},
        )
        # Endpoint must reject past date
        assert r.status_code == 400, r.text
        assert "past" in r.json().get("detail", "").lower()


class TestAuthGuards:
    def test_purchase_requires_login(self):
        r = _sess().post(f"{API}/memberships/purchase",
                         json={"plan_id": "x", "payment_method": "offline"})
        assert r.status_code in (401, 403)

    def test_vendor_inbox_forbidden_for_hr(self, hr_ctx):
        r = hr_ctx["sess"].get(f"{API}/memberships/mine/purchases")
        assert r.status_code == 403


class TestPublicList:
    def test_listing_memberships_visible_anon(self, vendor_ctx):
        r = _sess().get(f"{API}/memberships/listing/{vendor_ctx['listing_id']}")
        assert r.status_code == 200, r.text
        ids = [p["id"] for p in r.json()]
        assert vendor_ctx["plan_id"] in ids
