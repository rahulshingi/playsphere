"""Task 44 (Feb 2026) — commission, show-up tracking, admin analytics."""
import os
import uuid
import requests
from datetime import datetime, timezone, timedelta
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kreedanation.com", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    r = sess.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return sess


def _first_vendor(s):
    vendors = s.get(f"{API}/vendors").json()
    assert vendors, "no vendors on this instance"
    return vendors[0]


# ---- Task 1: Per-vendor commission ----
def test_admin_can_set_vendor_commission(s):
    v = _first_vendor(s)
    r = s.patch(f"{API}/vendors/{v['id']}/approve",
                json={"approved": True, "commission_percent": 12.5, "commission_min_flat": 150})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["commission_percent"] == 12.5
    assert body["commission_min_flat"] == 150


def test_admin_rejects_bad_commission(s):
    v = _first_vendor(s)
    r = s.patch(f"{API}/vendors/{v['id']}/approve",
                json={"approved": True, "commission_percent": 150})
    assert r.status_code == 400
    r = s.patch(f"{API}/vendors/{v['id']}/approve",
                json={"approved": True, "commission_min_flat": -10})
    assert r.status_code == 400


# ---- Task 2: Admin analytics endpoint ----
def test_admin_bookings_analytics_returns_expected_shape(s):
    for rng in ("day", "week", "month"):
        r = s.get(f"{API}/admin/bookings-analytics?range={rng}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["range"] == rng
        assert "totals" in body
        assert "online_bookings" in body["totals"]
        assert "commission_earned" in body["totals"]
        assert "offline_bookings" in body["totals"]
        assert "by_vendor" in body
        assert "timeseries" in body


# ---- Task 5: Show-up tracking on vendor_bookings ----
@pytest.fixture(scope="module")
def player_s():
    """Use the existing seeded test player for booking-lifecycle tests."""
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    r = sess.post(f"{API}/auth/login", json={"email": "testplayer@example.com", "password": "player123"})
    if r.status_code != 200:
        pytest.skip("Seeded test player not available on this instance")
    return sess


def _make_vendor_booking(s):
    """Create a vendor_booking as a player session."""
    listings = s.get(f"{API}/vendor-listings").json()
    assert listings, "need an approved listing to test"
    listing = listings[0]
    tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
    r = s.post(f"{API}/vendor-bookings", json={
        "listing_id": listing["id"],
        "requested_date": tomorrow,
        "start_time": "10:00",
        "hours": 1,
        "notes": "test",
    })
    assert r.status_code == 200, r.text
    return r.json()


def test_check_in_vendor_booking_marks_completed(s, player_s):
    bk = _make_vendor_booking(player_s)
    # Only admin/vendor can check in — use admin session
    r = s.post(f"{API}/vendor-bookings/{bk['id']}/check-in")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "completed"
    assert body["completed_at"]
    assert body["checked_in_at"]


def test_no_show_vendor_booking_marks_expired(s, player_s):
    bk = _make_vendor_booking(player_s)
    r = s.post(f"{API}/vendor-bookings/{bk['id']}/no-show")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "expired"
    assert body["no_show_at"]


def test_completed_booking_cannot_be_no_showed(s, player_s):
    bk = _make_vendor_booking(player_s)
    s.post(f"{API}/vendor-bookings/{bk['id']}/check-in")
    r = s.post(f"{API}/vendor-bookings/{bk['id']}/no-show")
    assert r.status_code == 400


def test_commission_applies_max_pct_or_flat(s, player_s):
    """A booking whose 10% is below the ₹100 floor should collect ₹100 commission."""
    # Set vendor commission to 10%/₹100 floor
    v = _first_vendor(s)
    s.patch(f"{API}/vendors/{v['id']}/approve", json={"approved": True, "commission_percent": 10.0, "commission_min_flat": 100.0})
    bk = _make_vendor_booking(player_s)
    # The MOCK listing may cost far more than ₹1000 so commission = 10% > ₹100.
    # For a low-price listing (< ₹1000) the ₹100 floor kicks in.
    pct_of_total = 0.10 * float(bk.get("total") or 0)
    expected = round(max(pct_of_total, 100.0 if pct_of_total > 0 else 0), 2)
    # Only if not offline-source and total > 0
    if bk.get("total", 0) > 0 and not bk.get("offline_source"):
        assert abs(bk.get("commission_amount", 0) - expected) < 0.01, \
            f"expected {expected}, got {bk.get('commission_amount')}"

