"""Iteration 9 — Sports CRUD, dashboards (admin/company/vendor), event scope=mine,
/my/teams, venues/suggest, venue sub-units/schedule/blocks/availability.

Tests cover:
- GET /api/sports (>=10 seeded)
- POST/PATCH/DELETE /api/sports (admin-only)
- GET /api/dashboard/{admin,company,vendor}
- GET /api/events?scope=mine
- GET /api/my/teams (HR only)
- GET /api/venues/suggest
- POST/GET /api/vendor-listings/{id}/sub-units (vendor-owner enforcement)
- GET/PATCH /api/vendor-listings/{id}/schedule
- POST/GET/DELETE /api/vendor-listings/{id}/blocks
- GET /api/vendor-listings/{id}/availability (slot grid + peak/weekend pricing)
"""
import os
import uuid
import datetime as dt
import pytest
import requests
from pathlib import Path


def _load_frontend_env():
    p = Path("/app/frontend/.env")
    if p.exists():
        for line in p.read_text().splitlines():
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


@pytest.fixture(scope="module")
def anon_s():
    return requests.Session()


# ============================================================
# SPORTS CRUD
# ============================================================
class TestSports:
    def test_list_sports_seeded(self):
        r = requests.get(f"{API}/sports")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 10, f"expected >=10 seeded sports, got {len(data)}"
        values = {s["value"] for s in data}
        for required in ("cricket", "football", "badminton"):
            assert required in values, f"{required} missing from seeded sports"
        # shape
        first = data[0]
        for k in ("id", "value", "label", "active"):
            assert k in first

    def test_create_sport_admin(self, admin_s):
        suffix = uuid.uuid4().hex[:6]
        body = {"value": f"test_{suffix}", "label": f"Test Sport {suffix}"}
        r = admin_s.post(f"{API}/sports", json=body)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["value"] == body["value"]
        assert doc["label"] == body["label"]
        assert doc["active"] is True
        # Persisted
        r2 = requests.get(f"{API}/sports")
        assert any(s["value"] == body["value"] for s in r2.json())
        TestSports._created_id = doc["id"]
        TestSports._created_val = body["value"]

    def test_create_sport_non_admin_forbidden(self, hr_s):
        r = hr_s.post(f"{API}/sports", json={"value": "nope_x", "label": "Nope"})
        assert r.status_code == 403

    def test_create_sport_anonymous_forbidden(self):
        r = requests.post(f"{API}/sports", json={"value": "nope_y", "label": "Nope"})
        assert r.status_code in (401, 403)

    def test_patch_sport_toggle_active(self, admin_s):
        sid = TestSports._created_id
        r = admin_s.patch(f"{API}/sports/{sid}", json={"active": False})
        assert r.status_code == 200
        assert r.json()["active"] is False
        # Verify hidden from default list
        listed = requests.get(f"{API}/sports").json()
        assert not any(s["id"] == sid for s in listed)
        # include_inactive shows it
        listed_all = requests.get(f"{API}/sports", params={"include_inactive": True}).json()
        assert any(s["id"] == sid for s in listed_all)

    def test_delete_sport(self, admin_s):
        sid = TestSports._created_id
        r = admin_s.delete(f"{API}/sports/{sid}")
        assert r.status_code == 200
        # gone
        r2 = admin_s.delete(f"{API}/sports/{sid}")
        assert r2.status_code == 404


# ============================================================
# DASHBOARDS
# ============================================================
class TestDashboards:
    def test_admin_dashboard(self, admin_s):
        r = admin_s.get(f"{API}/dashboard/admin")
        assert r.status_code == 200, r.text
        d = r.json()
        expected_keys = {
            "events_total", "events_ongoing", "companies", "vendors_total",
            "vendors_pending", "listings_pending", "vendor_bookings_total",
            "vendor_bookings_pending", "vendor_bookings_confirmed",
            "players", "teams", "service_bookings",
        }
        missing = expected_keys - set(d.keys())
        assert not missing, f"missing: {missing}"
        for k in expected_keys:
            assert isinstance(d[k], int) and d[k] >= 0

    def test_admin_dashboard_non_admin_forbidden(self, hr_s, vendor_s):
        assert hr_s.get(f"{API}/dashboard/admin").status_code == 403
        assert vendor_s.get(f"{API}/dashboard/admin").status_code == 403

    def test_company_dashboard(self, hr_s):
        r = hr_s.get(f"{API}/dashboard/company")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("my_events", "my_events_ongoing", "my_events_upcoming",
                   "my_events_completed", "my_teams", "my_matches",
                   "matches_completed", "service_bookings",
                   "ground_bookings_pending", "ground_bookings_confirmed",
                   "players_in_company"):
            assert k in d, f"missing {k}"
            assert isinstance(d[k], int)

    def test_company_dashboard_vendor_forbidden(self, vendor_s):
        # vendor should not be company_admin
        r = vendor_s.get(f"{API}/dashboard/company")
        assert r.status_code in (400, 403)

    def test_vendor_dashboard(self, vendor_s):
        r = vendor_s.get(f"{API}/dashboard/vendor")
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("listings_total", "listings_approved", "listings_pending",
                   "bookings_total", "bookings_pending", "bookings_vendor_accepted",
                   "bookings_confirmed", "bookings_completed", "bookings_upcoming",
                   "bookings_rejected", "bookings_cancelled"):
            assert k in d, f"missing {k}"
            assert isinstance(d[k], int)

    def test_vendor_dashboard_non_vendor_forbidden(self, hr_s, admin_s):
        assert hr_s.get(f"{API}/dashboard/vendor").status_code in (403, 404)
        # admin is not a vendor role
        assert admin_s.get(f"{API}/dashboard/vendor").status_code in (403, 404)


# ============================================================
# EVENTS scope=mine + /my/teams
# ============================================================
class TestEventsScope:
    def test_events_scope_mine_hr(self, hr_s):
        all_ev = requests.get(f"{API}/events").json()
        mine = hr_s.get(f"{API}/events", params={"scope": "mine"}).json()
        # mine subset of all
        assert isinstance(mine, list)
        assert len(mine) <= len(all_ev)

    def test_events_scope_mine_anonymous_returns_all(self):
        all_ev = requests.get(f"{API}/events").json()
        mine = requests.get(f"{API}/events", params={"scope": "mine"}).json()
        assert len(mine) == len(all_ev)


class TestMyTeams:
    def test_my_teams_hr(self, hr_s):
        r = hr_s.get(f"{API}/my/teams")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Each team should have company_id
        for t in data:
            assert "company_id" in t

    def test_my_teams_vendor_forbidden(self, vendor_s):
        assert vendor_s.get(f"{API}/my/teams").status_code == 403


# ============================================================
# VENUES SUGGEST
# ============================================================
class TestVenuesSuggest:
    def test_suggest_by_city(self):
        r = requests.get(f"{API}/venues/suggest", params={"city": "Bangalore"})
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Each result is approved + in Bangalore
        for v in data:
            assert v.get("city", "").lower() == "bangalore"

    def test_suggest_by_query_case_insensitive(self):
        r = requests.get(f"{API}/venues/suggest", params={"city": "bangalore", "q": "turf"})
        assert r.status_code == 200
        for v in r.json():
            assert "turf" in v.get("title", "").lower()


# ============================================================
# VENUE SUB-UNITS / SCHEDULE / BLOCKS / AVAILABILITY
# ============================================================
def _ensure_listing(vendor_s, admin_s):
    """Ensure vendor ravi has at least 1 approved+active listing."""
    listings = vendor_s.get(f"{API}/vendors/me/listings").json()
    if listings:
        for li in listings:
            if li.get("approved") and li.get("active"):
                return li
        # approve first one
        lid = listings[0]["id"]
        admin_s.patch(f"{API}/admin/listings/{lid}/approve", json={"approved": True})
        return vendor_s.get(f"{API}/vendor-listings/{lid}").json() if lid else listings[0]
    # create one
    body = {
        "title": f"TEST Turf {uuid.uuid4().hex[:6]}",
        "vendor_type": "ground", "sports": ["cricket"],
        "city": "Bangalore", "price": 1000.0, "currency": "INR",
        "active": True,
    }
    r = vendor_s.post(f"{API}/vendors/me/listings", json=body)
    assert r.status_code == 200, r.text
    listing = r.json()
    admin_s.patch(f"{API}/admin/listings/{listing['id']}/approve", json={"approved": True})
    return listing


@pytest.fixture(scope="module")
def listing(vendor_s, admin_s):
    return _ensure_listing(vendor_s, admin_s)


class TestSubUnits:
    def test_create_sub_unit_as_owner(self, vendor_s, listing):
        body = {"name": f"Turf A {uuid.uuid4().hex[:4]}", "capacity": 10}
        r = vendor_s.post(f"{API}/vendor-listings/{listing['id']}/sub-units", json=body)
        assert r.status_code == 200, r.text
        doc = r.json()
        assert doc["name"] == body["name"]
        assert doc["listing_id"] == listing["id"]
        TestSubUnits._sub_id = doc["id"]

    def test_list_sub_units(self, listing):
        r = requests.get(f"{API}/vendor-listings/{listing['id']}/sub-units")
        assert r.status_code == 200
        assert any(s["id"] == TestSubUnits._sub_id for s in r.json())

    def test_create_sub_unit_anonymous_forbidden(self, listing):
        r = requests.post(f"{API}/vendor-listings/{listing['id']}/sub-units",
                          json={"name": "Nope"})
        assert r.status_code in (401, 403)

    def test_create_sub_unit_non_owner_forbidden(self, hr_s, listing):
        # HR is not a vendor and not platform admin → 403
        r = hr_s.post(f"{API}/vendor-listings/{listing['id']}/sub-units",
                      json={"name": "Nope"})
        assert r.status_code == 403

    def test_admin_can_create_sub_unit(self, admin_s, listing):
        r = admin_s.post(f"{API}/vendor-listings/{listing['id']}/sub-units",
                         json={"name": f"AdminUnit {uuid.uuid4().hex[:4]}"})
        assert r.status_code == 200


class TestSchedule:
    def test_default_schedule(self, listing):
        r = requests.get(f"{API}/vendor-listings/{listing['id']}/schedule")
        assert r.status_code == 200
        d = r.json()
        for k in ("opening_time", "closing_time", "slot_minutes",
                   "peak_hours", "peak_price_factor", "weekend_price_factor"):
            assert k in d

    def test_upsert_schedule_as_owner(self, vendor_s, listing):
        body = {
            "opening_time": "07:00", "closing_time": "23:00",
            "slot_minutes": 60,
            "peak_hours": ["18:00", "19:00", "20:00"],
            "peak_price_factor": 1.25,
            "weekend_price_factor": 1.2,
            "amenities": ["parking", "showers"],
        }
        r = vendor_s.patch(f"{API}/vendor-listings/{listing['id']}/schedule", json=body)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["opening_time"] == "07:00"
        assert d["closing_time"] == "23:00"
        # GET reflects
        d2 = requests.get(f"{API}/vendor-listings/{listing['id']}/schedule").json()
        assert d2["opening_time"] == "07:00"
        assert "parking" in d2.get("amenities", [])


class TestBlocks:
    def test_create_block_owner(self, vendor_s, listing):
        future = (dt.date.today() + dt.timedelta(days=7)).isoformat()
        body = {"date": future, "start_time": "10:00", "end_time": "12:00",
                "reason": "Maintenance"}
        r = vendor_s.post(f"{API}/vendor-listings/{listing['id']}/blocks", json=body)
        assert r.status_code == 200
        TestBlocks._block_id = r.json()["id"]
        TestBlocks._date = future

    def test_list_blocks_by_date(self, listing):
        r = requests.get(f"{API}/vendor-listings/{listing['id']}/blocks",
                         params={"date": TestBlocks._date})
        assert r.status_code == 200
        assert any(b["id"] == TestBlocks._block_id for b in r.json())

    def test_delete_block(self, vendor_s, listing):
        r = vendor_s.delete(
            f"{API}/vendor-listings/{listing['id']}/blocks/{TestBlocks._block_id}")
        assert r.status_code == 200


class TestAvailability:
    def test_slot_grid_shape(self, listing):
        # pick a weekday (Wednesday) ~10 days out
        d = dt.date.today() + dt.timedelta(days=10)
        while d.weekday() >= 5:  # skip weekends
            d += dt.timedelta(days=1)
        date = d.isoformat()
        r = requests.get(f"{API}/vendor-listings/{listing['id']}/availability",
                         params={"date": date})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["date"] == date
        assert body["is_weekend"] is False
        slots = body["slots"]
        assert isinstance(slots, list) and len(slots) > 0
        for s in slots:
            assert "time" in s
            assert s["status"] in ("available", "booked", "blocked")
            assert isinstance(s["price"], (int, float))

    def test_block_marks_slot_blocked(self, vendor_s, listing):
        d = dt.date.today() + dt.timedelta(days=15)
        while d.weekday() >= 5:
            d += dt.timedelta(days=1)
        date = d.isoformat()
        # block 11:00-12:00
        vendor_s.post(f"{API}/vendor-listings/{listing['id']}/blocks",
                      json={"date": date, "start_time": "11:00", "end_time": "12:00",
                            "reason": "test"})
        r = requests.get(f"{API}/vendor-listings/{listing['id']}/availability",
                         params={"date": date})
        slots = r.json()["slots"]
        target = next((s for s in slots if s["time"] == "11:00"), None)
        assert target is not None
        assert target["status"] == "blocked"

    def test_peak_and_weekend_pricing(self, vendor_s, listing):
        # Weekday — peak factor applied at 19:00; weekend — factor applied all day.
        wd = dt.date.today() + dt.timedelta(days=1)
        while wd.weekday() >= 5:
            wd += dt.timedelta(days=1)
        we = dt.date.today() + dt.timedelta(days=1)
        while we.weekday() < 5:
            we += dt.timedelta(days=1)
        rd = requests.get(f"{API}/vendor-listings/{listing['id']}/availability",
                          params={"date": wd.isoformat()}).json()
        rw = requests.get(f"{API}/vendor-listings/{listing['id']}/availability",
                          params={"date": we.isoformat()}).json()
        assert rd["is_weekend"] is False
        assert rw["is_weekend"] is True
        # Find a non-peak 09:00 on weekday — should be base price
        nonpeak = next((s for s in rd["slots"] if s["time"] == "09:00"), None)
        peak = next((s for s in rd["slots"] if s["time"] == "19:00"), None)
        if nonpeak and peak:
            assert peak["price"] >= nonpeak["price"]
        # weekend 09:00 should be >= weekday 09:00 (weekend factor 1.2)
        nonpeak_we = next((s for s in rw["slots"] if s["time"] == "09:00"), None)
        if nonpeak and nonpeak_we:
            assert nonpeak_we["price"] >= nonpeak["price"]
