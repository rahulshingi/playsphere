"""QR-based check-in tests (Iteration 42).

Covers:
  • GET  /api/checkin/venue/{listing_id}/my-bookings   (player auth)
  • GET  /api/checkin/player/{player_id}/bookings      (vendor auth)
  • POST /api/checkin/vendor-booking/{id}              (idempotent, roles)
  • POST /api/checkin/private-booking/{id}             (vendor-only)

Seed context: uses live credentials + IDs supplied by main agent.  Tests
create a fresh vendor booking for TODAY, exercise the full happy-path,
then attempt to clean up the booking they created.
"""
import os
from datetime import datetime, timezone
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

PLAYER_EMAIL = "testplayer@example.com"
PLAYER_PASSWORD = "player123"
PLAYER_ID = "cecc6f8c-f894-4edd-b827-1e17d4f35343"
PLAYER_USER_ID = "bf756a6c-a183-4f4f-aa17-c493876a1c52"

VENDOR_EMAIL = "rmshingi@gmail.com"
VENDOR_PASSWORD = "vendor123"
VENDOR_ID = "0f3a5a52-2f0f-44ea-82da-4746e33e444b"
LISTING_ID = "b2dc4502-5330-415f-952a-b4629754ee03"


# ---------- Fixtures ----------
def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text}")
    return s


@pytest.fixture(scope="module")
def player_session():
    return _login(PLAYER_EMAIL, PLAYER_PASSWORD)


@pytest.fixture(scope="module")
def vendor_session():
    return _login(VENDOR_EMAIL, VENDOR_PASSWORD)


@pytest.fixture(scope="module")
def today_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _now_hh_mm():
    # Round current UTC time to nearest hour string
    now = datetime.now(timezone.utc)
    return now.strftime("%H:%M")


@pytest.fixture(scope="module")
def fresh_booking(player_session, today_iso):
    """Create a vendor booking for today at 'now' so within_window==True."""
    payload = {
        "listing_id": LISTING_ID,
        "requested_date": today_iso,
        "start_time": _now_hh_mm(),
        "hours": 1,
        "sport": "Cricket",
        "notes": "TEST_iter42_checkin",
    }
    r = player_session.post(f"{API}/vendor-bookings", json=payload, timeout=15)
    if r.status_code not in (200, 201):
        pytest.skip(f"Cannot create test booking: {r.status_code} {r.text[:200]}")
    booking = r.json()
    booking_id = booking.get("id") or booking.get("_id")
    assert booking_id, f"no id in booking response: {booking}"

    # Vendor accepts (so status is 'vendor_accepted' / open)
    s_v = _login(VENDOR_EMAIL, VENDOR_PASSWORD)
    # Try common accept endpoints
    for path in (f"/vendor-bookings/{booking_id}/accept", f"/vendor-bookings/{booking_id}/vendor-accept"):
        rr = s_v.post(f"{API}{path}", timeout=15)
        if rr.status_code in (200, 201):
            break
    yield booking_id

    # Cleanup: cancel or delete
    try:
        player_session.post(f"{API}/vendor-bookings/{booking_id}/cancel", timeout=10)
    except Exception:
        pass


# ---------- Player-scans-venue ----------
class TestPlayerScanVenue:
    def test_returns_bookings_with_within_window(self, player_session, fresh_booking, today_iso):
        r = player_session.get(f"{API}/checkin/venue/{LISTING_ID}/my-bookings", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        # Our fresh booking must be present
        ours = [b for b in data if b["id"] == fresh_booking]
        assert ours, f"Fresh booking not returned. Payload={data}"
        b = ours[0]
        assert b["source"] == "platform"
        assert b["vendor_id"] == VENDOR_ID
        assert b["requested_date"] == today_iso
        assert isinstance(b["within_window"], bool)
        assert b["within_window"] is True, "Booking at current hour should be within ±2h window"

    def test_404_on_missing_listing(self, player_session):
        r = player_session.get(f"{API}/checkin/venue/does-not-exist/my-bookings", timeout=15)
        assert r.status_code == 404


# ---------- Vendor-scans-player ----------
class TestVendorScanPlayer:
    def test_vendor_sees_player_platform_booking(self, vendor_session, fresh_booking):
        r = vendor_session.get(f"{API}/checkin/player/{PLAYER_ID}/bookings", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        ours = [b for b in data if b["id"] == fresh_booking]
        assert ours, f"Vendor did not see player's booking. Payload={data}"
        assert ours[0]["vendor_id"] == VENDOR_ID

    def test_non_vendor_gets_403(self, player_session):
        r = player_session.get(f"{API}/checkin/player/{PLAYER_ID}/bookings", timeout=15)
        assert r.status_code == 403, f"Player should NOT be able to call vendor endpoint, got {r.status_code}"

    def test_404_on_missing_player(self, vendor_session):
        r = vendor_session.get(f"{API}/checkin/player/does-not-exist/bookings", timeout=15)
        assert r.status_code == 404


# ---------- Check-in (idempotent + role) ----------
class TestCheckInVendorBooking:
    def test_player_can_self_check_in_then_second_call_409(self, player_session, fresh_booking):
        r = player_session.post(f"{API}/checkin/vendor-booking/{fresh_booking}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("status") == "checked_in"
        assert data.get("checked_in_by_role") == "player"
        assert data.get("checked_in_at")

        # Second call → 409 with structured detail
        r2 = player_session.post(f"{API}/checkin/vendor-booking/{fresh_booking}", timeout=15)
        assert r2.status_code == 409, r2.text
        detail = r2.json().get("detail")
        # FastAPI wraps HTTPException detail dict as-is inside 'detail'
        assert isinstance(detail, dict), f"expected structured detail, got {detail!r}"
        assert detail.get("code") == "already_checked_in"
        assert detail.get("checked_in_at")
        assert detail.get("checked_in_by_role") == "player"

    def test_404_on_missing_booking(self, player_session):
        r = player_session.post(f"{API}/checkin/vendor-booking/nope-nope-nope", timeout=15)
        assert r.status_code == 404


# ---------- Private booking check-in ----------
class TestCheckInPrivate:
    def test_player_forbidden(self, player_session):
        r = player_session.post(f"{API}/checkin/private-booking/anything", timeout=15)
        # Non-vendor users must be rejected before we even hit the doc lookup.
        assert r.status_code in (401, 403), r.text

    def test_404_when_not_found_for_vendor(self, vendor_session):
        r = vendor_session.post(f"{API}/checkin/private-booking/nonexistent-id", timeout=15)
        assert r.status_code == 404, r.text
