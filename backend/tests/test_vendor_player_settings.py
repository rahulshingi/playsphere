"""End-to-end tests for the iteration-4 feature set:
- /api/companies/public
- /api/settings (GET public, PATCH platform_admin)
- Player accounts: /api/players/register|login|me|profiles
- Vendors: /api/vendors/signup|me, /api/vendors/me/listings, /api/vendor-listings (public)
- Admin: PATCH /api/vendors/{id}/approve, /api/admin/listings
- Vendor bookings: POST/GET/PATCH /api/vendor-bookings
"""

import os
import uuid
import time
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip()
    return None


_url = os.environ.get("REACT_APP_BACKEND_URL") or _load_frontend_env()
assert _url, "REACT_APP_BACKEND_URL must be set"
BASE_URL = _url.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@playsphere.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
ACME_EMAIL = os.environ.get("TEST_ACME_EMAIL", "acme@example.com")
ACME_PASSWORD = os.environ.get("TEST_ACME_PASSWORD", "acme123")
VENDOR_EMAIL = os.environ.get("TEST_VENDOR_EMAIL", "ravi@turf.in")
VENDOR_PASSWORD = os.environ.get("TEST_VENDOR_PASSWORD", "vendor123")

UNIQ = uuid.uuid4().hex[:6]


def _new_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(s, email, password):
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()


# -------- Shared fixtures --------
@pytest.fixture(scope="module")
def admin_session():
    s = _new_session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def acme_session():
    s = _new_session()
    _login(s, ACME_EMAIL, ACME_PASSWORD)
    return s


@pytest.fixture(scope="module")
def vendor_session():
    s = _new_session()
    r = s.post(f"{API}/auth/login", json={"email": VENDOR_EMAIL, "password": VENDOR_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"Vendor login unavailable: {r.status_code}")
    return s


@pytest.fixture(scope="module")
def acme_company_id(admin_session):
    r = admin_session.get(f"{API}/companies")
    assert r.status_code == 200
    for c in r.json():
        if c.get("name") == "Acme Corp":
            return c["id"]
    pytest.skip("Acme Corp not seeded")


# ---------------- Public companies + settings ----------------
class TestPublicEndpoints:
    def test_companies_public_no_auth(self):
        r = requests.get(f"{API}/companies/public")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) > 0
        sample = data[0]
        assert set(sample.keys()) >= {"id", "name", "slug", "logo_url"}
        # no _id field leakage
        assert "_id" not in sample

    def test_settings_get_no_auth(self):
        r = requests.get(f"{API}/settings")
        assert r.status_code == 200
        d = r.json()
        for k in ("facebook_url", "instagram_url", "linkedin_url",
                  "twitter_url", "youtube_url"):
            assert k in d

    def test_settings_patch_requires_platform_admin(self, acme_session):
        r = acme_session.patch(f"{API}/settings", json={"facebook_url": "https://example.com/no"})
        assert r.status_code == 403

    def test_settings_patch_as_admin_persists(self, admin_session):
        url = f"https://facebook.com/playsphere-{UNIQ}"
        r = admin_session.patch(f"{API}/settings", json={"facebook_url": url})
        assert r.status_code == 200, r.text
        assert r.json().get("facebook_url") == url
        # verify persistence via public GET
        r2 = requests.get(f"{API}/settings")
        assert r2.json().get("facebook_url") == url


# ---------------- Player accounts ----------------
@pytest.fixture(scope="module")
def player_a(acme_company_id):
    s = _new_session()
    body = {
        "name": f"TEST_PlayerA_{UNIQ}",
        "mobile": "9" + uuid.uuid4().hex[:9],
        "password": "playerpass1",
        "company_id": acme_company_id,
        "email": f"test_pa_{UNIQ}@example.com",
    }
    r = s.post(f"{API}/players/register", json=body)
    assert r.status_code == 200, r.text
    user = r.json()
    assert user["role"] == "player"
    assert user["company_id"] == acme_company_id
    assert user["company_name"] == "Acme Corp"
    return {"session": s, "user": user, "mobile": body["mobile"], "password": body["password"]}


@pytest.fixture(scope="module")
def player_b(acme_company_id):
    s = _new_session()
    body = {
        "name": f"TEST_PlayerB_{UNIQ}",
        "mobile": "8" + uuid.uuid4().hex[:9],
        "password": "playerpass2",
        "company_id": acme_company_id,
        "email": f"test_pb_{UNIQ}@example.com",
    }
    r = s.post(f"{API}/players/register", json=body)
    assert r.status_code == 200, r.text
    return {"session": s, "user": r.json(), "mobile": body["mobile"], "password": body["password"]}


class TestPlayers:
    # Both blockers fixed: (1) auto-email now @players.playsphere.app, (2) legacy roster
    # routes renamed to /api/team-players/{player_id} so /api/players/me &
    # /api/players/profiles reach their proper handlers.

    def test_register_without_email_succeeds(self, acme_company_id):
        """Frontend PlayerSignup has no email field — backend must auto-generate a routable
        email and return UserPublic + httpOnly cookie."""
        body = {
            "name": f"TEST_NoEmail_{UNIQ}",
            "mobile": "5" + uuid.uuid4().hex[:9],
            "password": "x",
            "company_id": acme_company_id,
        }
        r = requests.post(f"{API}/players/register", json=body)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data.get("role") == "player"
        assert data["email"].endswith("@players.playsphere.app")
        assert r.cookies.get("access_token"), "Expected httpOnly session cookie"

    def test_duplicate_mobile_returns_400(self, player_a, acme_company_id):
        r = requests.post(f"{API}/players/register", json={
            "name": "Dup",
            "mobile": player_a["mobile"],
            "password": "x",
            "company_id": acme_company_id,
        })
        assert r.status_code == 400

    def test_player_login_success(self, player_a):
        s = _new_session()
        r = s.post(f"{API}/players/login",
                   json={"mobile": player_a["mobile"], "password": player_a["password"]})
        assert r.status_code == 200
        assert r.json()["role"] == "player"
        # auth cookie set
        assert "access_token" in s.cookies or any("access" in c.name for c in s.cookies)

    def test_player_login_wrong_password(self, player_a):
        r = requests.post(f"{API}/players/login",
                          json={"mobile": player_a["mobile"], "password": "wrong"})
        assert r.status_code == 401

    def test_get_my_profile(self, player_a):
        r = player_a["session"].get(f"{API}/players/me")
        assert r.status_code == 200
        d = r.json()
        assert d["mobile"] == player_a["mobile"]
        assert d["user_id"] == player_a["user"]["id"]
        assert d["view_count"] == 0

    def test_patch_profile_updates_fields(self, player_a):
        s = player_a["session"]
        patch = {
            "city": "Mumbai", "role": "batsman",
            "batting_hand": "left", "bowling_style": "off-spin",
            "jersey_number": 7, "bio": "TEST bio",
            "cricheroes_url": "https://cricheroes.in/player/test",
        }
        r = s.patch(f"{API}/players/me", json=patch)
        assert r.status_code == 200, r.text
        d = r.json()
        for k, v in patch.items():
            assert d[k] == v, f"{k}: {d[k]} != {v}"

    def test_patch_cannot_change_mobile_view_count_or_user_id(self, player_a):
        s = player_a["session"]
        original_mobile = player_a["mobile"]
        bogus_uid = str(uuid.uuid4())
        r = s.patch(f"{API}/players/me", json={
            "mobile": "0000000000", "view_count": 9999,
            "user_id": bogus_uid, "id": "hack",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["mobile"] == original_mobile
        assert d["view_count"] == 0
        assert d["user_id"] == player_a["user"]["id"]

    def test_change_company_updates_user_and_profile(self, player_a, admin_session):
        # find a different company
        comps = admin_session.get(f"{API}/companies").json()
        other = next((c for c in comps if c["name"] != "Acme Corp"), None)
        if not other:
            pytest.skip("Need a second company to test re-association")
        r = player_a["session"].patch(f"{API}/players/me", json={"company_id": other["id"]})
        assert r.status_code == 200
        assert r.json()["company_name"] == other["name"]
        # auth/me also reflects new company
        me = player_a["session"].get(f"{API}/auth/me").json()
        assert me["company_id"] == other["id"]
        # restore back
        acme_id = next(c["id"] for c in comps if c["name"] == "Acme Corp")
        player_a["session"].patch(f"{API}/players/me", json={"company_id": acme_id})

    def test_profile_list_masks_mobile_for_others(self, player_a, player_b):
        # player_a viewing list — player_b's mobile should be masked
        r = player_a["session"].get(f"{API}/players/profiles")
        assert r.status_code == 200
        rows = r.json()
        b_row = next((x for x in rows if x.get("user_id") == player_b["user"]["id"]), None)
        assert b_row is not None
        assert "mobile" not in b_row, "Raw mobile must not leak to other players"
        assert b_row.get("mobile_masked", "").endswith(player_b["mobile"][-4:])
        # own row should retain raw mobile
        a_row = next((x for x in rows if x.get("user_id") == player_a["user"]["id"]), None)
        assert a_row and a_row.get("mobile") == player_a["mobile"]

    def test_profile_list_search_filter(self, player_a):
        r = player_a["session"].get(f"{API}/players/profiles",
                                    params={"q": f"TEST_PlayerB_{UNIQ}"})
        assert r.status_code == 200
        names = [x["name"] for x in r.json()]
        assert any(f"TEST_PlayerB_{UNIQ}" in n for n in names)

    def test_view_count_increments_for_other_viewer(self, player_a, player_b):
        # find B's profile id
        b_user_id = player_b["user"]["id"]
        rows = player_a["session"].get(f"{API}/players/profiles").json()
        b_profile = next(x for x in rows if x["user_id"] == b_user_id)
        b_profile_id = b_profile["id"]
        # baseline (B sees own raw counter)
        before = player_b["session"].get(f"{API}/players/me").json().get("view_count", 0)
        # A views B
        r = player_a["session"].get(f"{API}/players/profiles/{b_profile_id}")
        assert r.status_code == 200
        # response should reflect incremented view_count and mobile masked
        assert r.json()["view_count"] == before + 1
        assert "mobile" not in r.json()
        # B self-view does NOT increment
        r_self = player_b["session"].get(f"{API}/players/profiles/{b_profile_id}")
        assert r_self.status_code == 200
        assert r_self.json()["view_count"] == before + 1  # unchanged

    def test_profiles_list_filter_by_company(self, player_a, acme_company_id):
        r = player_a["session"].get(f"{API}/players/profiles",
                                    params={"company_id": acme_company_id})
        assert r.status_code == 200
        for x in r.json():
            assert x.get("company_id") == acme_company_id


# ---------------- Vendors + listings + admin approval + bookings ----------------
class TestVendorsListingsBookings:
    def test_vendor_signup_creates_unapproved(self):
        s = _new_session()
        email = f"vendor_{UNIQ}_{uuid.uuid4().hex[:4]}@example.com"
        body = {
            "business_name": f"TEST_Biz_{UNIQ}",
            "vendor_type": "ground",
            "contact_name": "TEST Owner",
            "mobile": "7" + uuid.uuid4().hex[:9],
            "email": email,
            "password": "vendpass1",
            "city": "Pune",
        }
        r = s.post(f"{API}/vendors/signup", json=body)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "vendor"
        r2 = s.get(f"{API}/vendors/me")
        assert r2.status_code == 200
        assert r2.json()["approved"] is False
        assert r2.json()["business_name"] == body["business_name"]

    def test_public_listings_strip_vendor_id_and_only_approved(self):
        r = requests.get(f"{API}/vendor-listings")
        assert r.status_code == 200
        rows = r.json()
        assert isinstance(rows, list)
        for row in rows:
            assert "vendor_id" not in row, "vendor_id must be stripped from public response"
            assert row.get("approved") is True
            assert row.get("active") is True

    def test_public_listings_filters(self):
        r = requests.get(f"{API}/vendor-listings", params={"vendor_type": "ground", "city": "Bangalore"})
        assert r.status_code == 200
        for row in r.json():
            assert row["vendor_type"] == "ground"
            assert "bangalore" in row["city"].lower()

    def test_vendor_create_listing_pending_then_admin_approve(self, vendor_session, admin_session):
        body = {
            "title": f"TEST_Listing_{UNIQ}",
            "description": "auto test listing",
            "city": "Pune",
            "sports": ["cricket"],
            "price": 999.0,
            "currency": "INR",
            "images": ["https://example.com/a.jpg"],
        }
        r = vendor_session.post(f"{API}/vendors/me/listings", json=body)
        assert r.status_code == 200, r.text
        listing = r.json()
        listing_id = listing["id"]
        assert listing["approved"] is False
        assert listing["vendor_type"] == "ground"  # inherited
        # public list must NOT contain it yet
        pub = requests.get(f"{API}/vendor-listings").json()
        assert all(x["id"] != listing_id for x in pub)
        # admin: GET /admin/listings ?approved=false includes it
        r2 = admin_session.get(f"{API}/admin/listings", params={"approved": "false"})
        assert r2.status_code == 200
        assert any(x["id"] == listing_id for x in r2.json())
        # approve
        r3 = admin_session.patch(f"{API}/admin/listings/{listing_id}/approve", json={"approved": True})
        assert r3.status_code == 200
        # public list must NOW contain it
        pub2 = requests.get(f"{API}/vendor-listings").json()
        assert any(x["id"] == listing_id for x in pub2)
        # cleanup: revoke + delete
        admin_session.patch(f"{API}/admin/listings/{listing_id}/approve", json={"approved": False})
        vendor_session.delete(f"{API}/vendors/me/listings/{listing_id}")

    def test_vendor_listing_patch_cannot_self_approve(self, vendor_session):
        body = {
            "title": f"TEST_NoSelfApprove_{UNIQ}",
            "city": "Pune", "sports": ["cricket"], "price": 100.0,
        }
        r = vendor_session.post(f"{API}/vendors/me/listings", json=body)
        listing_id = r.json()["id"]
        r2 = vendor_session.patch(f"{API}/vendors/me/listings/{listing_id}",
                                  json={"approved": True, "title": "Renamed"})
        assert r2.status_code == 200
        assert r2.json()["approved"] is False  # ignored
        assert r2.json()["title"] == "Renamed"
        vendor_session.delete(f"{API}/vendors/me/listings/{listing_id}")

    def test_vendor_listings_owner_only(self, vendor_session):
        # Try via a fresh vendor session
        s = _new_session()
        email = f"vendor2_{UNIQ}_{uuid.uuid4().hex[:4]}@example.com"
        s.post(f"{API}/vendors/signup", json={
            "business_name": f"TEST_Biz2_{UNIQ}", "vendor_type": "court",
            "contact_name": "TEST2", "mobile": "6" + uuid.uuid4().hex[:9],
            "email": email, "password": "p", "city": "Delhi",
        })
        # Create a listing as vendor #1
        listing_id = vendor_session.post(f"{API}/vendors/me/listings", json={
            "title": f"TEST_Owner_{UNIQ}", "city": "Pune", "sports": ["cricket"], "price": 1.0,
        }).json()["id"]
        # vendor #2 cannot PATCH/DELETE it
        r = s.patch(f"{API}/vendors/me/listings/{listing_id}", json={"title": "hack"})
        assert r.status_code == 404
        r2 = s.delete(f"{API}/vendors/me/listings/{listing_id}")
        # delete is idempotent; ensure listing still exists in owner's list
        own = vendor_session.get(f"{API}/vendors/me/listings").json()
        assert any(x["id"] == listing_id for x in own)
        vendor_session.delete(f"{API}/vendors/me/listings/{listing_id}")


class TestVendorBookings:
    def _approved_listing_id(self):
        rows = requests.get(f"{API}/vendor-listings").json()
        assert rows, "No approved public listings available — fixture data missing"
        return rows[0]["id"], rows[0]

    def test_company_admin_books_approved_listing(self, acme_session, vendor_session, admin_session):
        listing_id, listing = self._approved_listing_id()
        body = {
            "listing_id": listing_id,
            "requested_date": "2026-12-25",
            "start_time": "10:00", "end_time": "12:00",
            "notes": "TEST booking",
        }
        r = acme_session.post(f"{API}/vendor-bookings", json=body)
        assert r.status_code == 200, r.text
        bk = r.json()
        assert bk["status"] == "pending"
        assert bk["price"] == listing["price"]
        assert bk["currency"] == listing["currency"]
        assert bk["company_name"] == "Acme Corp"
        bid = bk["id"]
        # company_admin sees it
        rows = acme_session.get(f"{API}/vendor-bookings").json()
        assert any(x["id"] == bid for x in rows)
        # platform admin sees it
        all_rows = admin_session.get(f"{API}/vendor-bookings").json()
        assert any(x["id"] == bid for x in all_rows)
        # vendor sees it (Whitefield vendor)
        vrows = vendor_session.get(f"{API}/vendor-bookings").json()
        assert any(x["id"] == bid for x in vrows), "Vendor should see bookings on own listings"
        # vendor confirms
        r2 = vendor_session.patch(f"{API}/vendor-bookings/{bid}", json={"status": "confirmed"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "confirmed"
        # company_admin cancels own
        r3 = acme_session.patch(f"{API}/vendor-bookings/{bid}", json={"status": "cancelled"})
        assert r3.status_code == 200
        assert r3.json()["status"] == "cancelled"

    def test_booking_rejected_when_listing_not_approved(self, acme_session, vendor_session, admin_session):
        # Create unapproved listing
        listing_id = vendor_session.post(f"{API}/vendors/me/listings", json={
            "title": f"TEST_Unapproved_{UNIQ}", "city": "Pune",
            "sports": ["cricket"], "price": 50.0,
        }).json()["id"]
        r = acme_session.post(f"{API}/vendor-bookings", json={
            "listing_id": listing_id,
            "requested_date": "2026-12-25", "start_time": "10:00", "end_time": "11:00",
        })
        assert r.status_code == 404
        # cleanup
        vendor_session.delete(f"{API}/vendors/me/listings/{listing_id}")

    def test_non_company_admin_cannot_create_booking(self, vendor_session):
        listing_id, _ = self._approved_listing_id()
        r = vendor_session.post(f"{API}/vendor-bookings", json={
            "listing_id": listing_id,
            "requested_date": "2026-12-25", "start_time": "10:00", "end_time": "11:00",
        })
        assert r.status_code in (401, 403)


class TestAdminVendorApproval:
    def test_admin_lists_vendors_filtered(self, admin_session):
        r = admin_session.get(f"{API}/vendors", params={"approved": "false"})
        assert r.status_code == 200
        for v in r.json():
            assert v["approved"] is False

    def test_non_admin_cannot_list_vendors(self, acme_session):
        r = acme_session.get(f"{API}/vendors")
        assert r.status_code == 403

    def test_admin_can_flip_vendor_approval(self, admin_session):
        # find or create a vendor to flip
        rows = admin_session.get(f"{API}/vendors").json()
        target = next((v for v in rows if v["business_name"].startswith("TEST_Biz_")), None)
        if not target:
            pytest.skip("No TEST vendor present")
        vid = target["id"]
        orig = target["approved"]
        r = admin_session.patch(f"{API}/vendors/{vid}/approve", json={"approved": not orig})
        assert r.status_code == 200
        assert r.json()["approved"] is (not orig)
        # restore
        admin_session.patch(f"{API}/vendors/{vid}/approve", json={"approved": orig})
