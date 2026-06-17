"""Iteration 8 — Vendor bookings v2 (HR ground-booking wizard, state machine,
notifications & log mocking).

Covers:
- GET /api/vendor-listings/cities (filters, sorted, distinct)
- GET /api/vendor-listings filter by sport+city (case-insensitive)
- POST /api/vendor-bookings (hours computed, end_time derived, sport+city denorm,
  notifications[0].event == 'created')
- POST authorisation (vendor & anonymous denied)
- PATCH state machine
    vendor 'confirmed' → 'vendor_accepted', 'declined' → 'vendor_declined'
    vendor cross-tenant → 403
    admin can confirm + add admin_notes; admin can override (reject after accept)
    HR cancellation allowed at any non-terminal state; other HR statuses → 400
- BOOKING NOTIFICATION log line is emitted on every status_change PATCH
"""
import os
import time
import uuid
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

ADMIN = ("admin@kreedanation.com", "admin123")
ACME = ("acme@example.com", "acme123")
VENDOR = ("ravi@turf.in", "vendor123")
LOG_PATH = "/var/log/supervisor/backend.err.log"


def _session(email=None, password=None):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    if email:
        r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _session(*ADMIN)


@pytest.fixture(scope="module")
def hr_s():
    return _session(*ACME)


@pytest.fixture(scope="module")
def vendor_s():
    return _session(*VENDOR)


# ---------------- helpers ----------------
def _ensure_listing(vendor_s, admin_s, sport="cricket", city="Bangalore",
                    vendor_type="ground", price=500.0, currency="INR"):
    """Make sure an approved+active listing exists matching sport/city. Returns the listing."""
    rows = requests.get(
        f"{API}/vendor-listings",
        params={"vendor_type": vendor_type, "sport": sport, "city": city},
    ).json()
    if rows:
        return rows[0]
    # Create one as vendor + approve as admin
    body = {
        "title": f"TEST_Listing_{sport}_{city}_{uuid.uuid4().hex[:6]}",
        "city": city,
        "sports": [sport],
        "price": price,
        "currency": currency,
    }
    r = vendor_s.post(f"{API}/vendors/me/listings", json=body)
    assert r.status_code == 200, r.text
    lid = r.json()["id"]
    r2 = admin_s.patch(f"{API}/admin/listings/{lid}/approve", json={"approved": True})
    assert r2.status_code == 200
    r3 = requests.get(f"{API}/vendor-listings/{lid}")
    assert r3.status_code == 200
    return r3.json()


def _tail_log(n=400):
    try:
        with open(LOG_PATH, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 200_000))
            return f.read().decode("utf-8", errors="ignore").splitlines()[-n:]
    except FileNotFoundError:
        return []


# =====================================================================
# 1. /api/vendor-listings/cities
# =====================================================================
class TestCities:
    def test_cities_unfiltered_returns_sorted_distinct_non_empty(self, vendor_s, admin_s):
        _ensure_listing(vendor_s, admin_s)
        r = requests.get(f"{API}/vendor-listings/cities")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "expected at least one city from approved+active listings"
        assert data == sorted(data), "cities must be sorted"
        assert len(data) == len(set(data)), "cities must be distinct"
        assert all(c and isinstance(c, str) for c in data)

    def test_cities_filtered_by_sport_and_vendor_type(self, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s, sport="cricket",
                                  city="Bangalore", vendor_type="ground")
        r = requests.get(
            f"{API}/vendor-listings/cities",
            params={"sport": "cricket", "vendor_type": "ground"},
        )
        assert r.status_code == 200
        cities = r.json()
        assert listing["city"] in cities

    def test_cities_filtered_by_uncommon_sport_excludes_unrelated(self, vendor_s, admin_s):
        # cricket-only listing in Bangalore — querying for a different sport
        # should NOT include 'Bangalore' UNLESS another listing is tagged with that sport
        _ensure_listing(vendor_s, admin_s, sport="cricket", city="Bangalore")
        unique_sport = f"sport_{uuid.uuid4().hex[:6]}"
        r = requests.get(f"{API}/vendor-listings/cities", params={"sport": unique_sport})
        assert r.status_code == 200
        assert r.json() == [], "no listings tagged with unique sport → empty cities"


# =====================================================================
# 2. /api/vendor-listings filter
# =====================================================================
class TestListingFilter:
    def test_filter_by_sport_and_city_case_insensitive(self, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s, sport="cricket",
                                  city="Bangalore", vendor_type="ground")
        r = requests.get(
            f"{API}/vendor-listings",
            params={"vendor_type": "ground", "sport": "cricket", "city": "bangalore"},
        )
        assert r.status_code == 200
        rows = r.json()
        assert any(x["id"] == listing["id"] for x in rows)
        for row in rows:
            assert row["vendor_type"] == "ground"
            assert "cricket" in row.get("sports", [])
            assert row["city"].lower() == "bangalore"
            assert row.get("approved")
            assert row.get("active")


# =====================================================================
# 3. POST /api/vendor-bookings — happy path + auth
# =====================================================================
class TestCreateBooking:
    def test_hr_creates_with_hours_derives_end_and_total(self, hr_s, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s, sport="cricket",
                                  city="Bangalore", price=500.0, currency="INR")
        r = hr_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-12-31",
            "start_time": "18:00",
            "hours": 3,
            "notes": "TEST hours-flow",
        })
        assert r.status_code == 200, r.text
        bk = r.json()
        assert bk["status"] == "pending"
        assert bk["start_time"] == "18:00"
        assert bk["end_time"] == "21:00", "end_time should be derived from hours"
        assert bk["hours"] == 3
        assert bk["total"] == listing["price"] * 3
        assert bk["sport"] == "cricket", "sport denormalised from listing.sports[0]"
        assert bk["city"] == listing["city"]
        assert bk["hr_email"] == ACME[0]
        assert bk["currency"] == listing["currency"]
        notes = bk.get("notifications") or []
        assert notes and notes[0]["event"] == "created", "first notification should be 'created'"

    def test_hr_creates_with_end_time_derives_hours(self, hr_s, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s)
        r = hr_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-11-15",
            "start_time": "10:00",
            "end_time": "13:30",  # 3.5h → rounded
            "notes": "TEST end-only",
        })
        assert r.status_code == 200, r.text
        bk = r.json()
        # 3h30m → round(3.5)=4 (banker's) OR 4 — accept either rounding (3 or 4)
        assert bk["hours"] in (3, 4), f"derived hours unexpected: {bk['hours']}"
        assert bk["end_time"] == "13:30"
        assert bk["total"] == bk["price"] * bk["hours"]

    def test_vendor_cannot_create_booking(self, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s)
        r = vendor_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-12-25",
            "start_time": "10:00", "hours": 1,
        })
        assert r.status_code in (401, 403)

    def test_anonymous_cannot_create_booking(self, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s)
        r = requests.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-12-25",
            "start_time": "10:00", "hours": 1,
        })
        assert r.status_code in (401, 403)


# =====================================================================
# 4. PATCH state machine
# =====================================================================
class TestStateMachine:
    @pytest.fixture
    def new_booking(self, hr_s, vendor_s, admin_s):
        listing = _ensure_listing(vendor_s, admin_s)
        r = hr_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-10-10",
            "start_time": "18:00", "hours": 2,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_vendor_confirmed_is_remapped_to_vendor_accepted(self, vendor_s, new_booking):
        bid = new_booking["id"]
        r = vendor_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "confirmed"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "vendor_accepted"

    def test_vendor_declined_is_remapped_to_vendor_declined(self, vendor_s, new_booking):
        bid = new_booking["id"]
        r = vendor_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "declined"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "vendor_declined"

    def test_vendor_cannot_patch_booking_of_other_vendor(self, hr_s, admin_s):
        # Sign up a *second* vendor + create their own approved listing,
        # then HR books listing #1 (Whitefield/ravi). Vendor #2 must NOT be
        # able to PATCH that booking.
        s2 = _session()
        email = f"vendor2_{uuid.uuid4().hex[:6]}@example.com"
        r = s2.post(f"{API}/vendors/signup", json={
            "business_name": f"TEST_Biz2_{uuid.uuid4().hex[:4]}",
            "vendor_type": "ground",
            "contact_name": "TEST V2",
            "mobile": "7" + uuid.uuid4().hex[:9],
            "email": email, "password": "p", "city": "Pune",
        })
        assert r.status_code == 200, r.text
        # Vendor #2 signs in via cookie already returned. Confirm by hitting /vendors/me
        me = s2.get(f"{API}/vendors/me")
        assert me.status_code == 200, me.text

        # Book listing belonging to vendor #1
        ravi_s = _session(*VENDOR)
        listing = _ensure_listing(ravi_s, admin_s)
        bk = hr_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": "2026-10-11",
            "start_time": "20:00", "hours": 1,
        }).json()
        assert bk.get("id"), bk
        # Vendor #2 PATCH must be 403
        r2 = s2.patch(f"{API}/vendor-bookings/{bk['id']}", json={"status": "confirmed"})
        assert r2.status_code == 403, r2.text

    def test_admin_can_confirm_with_notes_and_logs_notification(self, admin_s, new_booking):
        bid = new_booking["id"]
        r = admin_s.patch(f"{API}/vendor-bookings/{bid}",
                          json={"status": "confirmed", "admin_notes": "ok"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "confirmed"
        assert d["admin_notes"] == "ok"
        notes = d.get("notifications") or []
        assert any(n["event"] == "status_change" for n in notes)

    def test_admin_can_override_vendor_accept_with_reject(self, vendor_s, admin_s, new_booking):
        bid = new_booking["id"]
        # vendor accepts first
        r1 = vendor_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "confirmed"})
        assert r1.status_code == 200
        assert r1.json()["status"] == "vendor_accepted"
        # admin overrides → rejected
        r2 = admin_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "rejected"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "rejected"

    def test_hr_can_cancel_after_confirmed(self, hr_s, admin_s, new_booking):
        bid = new_booking["id"]
        admin_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "confirmed"})
        r = hr_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "cancelled"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "cancelled"

    def test_hr_cannot_set_arbitrary_status(self, hr_s, new_booking):
        bid = new_booking["id"]
        for bad in ("confirmed", "rejected", "vendor_accepted"):
            r = hr_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": bad})
            assert r.status_code == 400, f"HR PATCH status={bad} expected 400, got {r.status_code}"

    def test_status_change_emits_log_line(self, hr_s, vendor_s, admin_s):
        """E2E: after a PATCH, backend log MUST contain BOOKING NOTIFICATION line
        with hr_email + booking id + status_change."""
        listing = _ensure_listing(vendor_s, admin_s)
        bk = hr_s.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"], "requested_date": "2026-09-09",
            "start_time": "11:00", "hours": 1,
        }).json()
        bid = bk["id"]
        # vendor accepts
        r = vendor_s.patch(f"{API}/vendor-bookings/{bid}", json={"status": "confirmed"})
        assert r.status_code == 200
        time.sleep(0.5)  # let logger flush
        log = "\n".join(_tail_log(800))
        needle_prefix = f"BOOKING NOTIFICATION for {ACME[0]} | booking={bid}"
        assert needle_prefix in log, f"missing log line. Tail: ...{log[-2000:]}"
        assert "status_change" in log
        assert "Status changed from" in log


# =====================================================================
# 5. Regression smoke — key endpoints still 200
# =====================================================================
class TestRegression:
    def test_events_endpoint_still_lists(self, hr_s):
        r = hr_s.get(f"{API}/events")
        assert r.status_code == 200

    def test_players_profiles_still_lists(self, hr_s):
        r = hr_s.get(f"{API}/players/profiles")
        assert r.status_code == 200

    def test_companies_public_still_lists(self):
        r = requests.get(f"{API}/companies/public")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_settings_public_still_returns(self):
        r = requests.get(f"{API}/settings")
        assert r.status_code == 200
