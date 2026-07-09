"""Feb 2026 batch — 6 user-reported fixes:
Task 1: Past slots filtered from listing availability.
Task 4: Event creator can soft-cancel event.
Task 6: Sponsor signup accepts mobile number.
"""
import os
import uuid
import requests
from datetime import datetime, timezone
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


# ---- Task 1: past slots ----
def test_availability_marks_today_past_slots_as_past(s):
    # Pick any approved+active listing
    listings = s.get(f"{API}/vendor-listings").json()
    if not listings:
        pytest.skip("no active listings on this instance")
    listing_id = listings[0]["id"]
    today = datetime.now(timezone.utc).date().isoformat()
    r = s.get(f"{API}/vendor-listings/{listing_id}/availability?date={today}")
    assert r.status_code == 200, r.text
    body = r.json()
    # If it's still early morning (00:00 UTC), the test naturally has no "past"
    # yet — treat that as skip-worthy.
    now = datetime.now(timezone.utc)
    now_min = now.hour * 60 + now.minute
    # Any slot whose HH:MM is <= now should be marked past
    past_slots = [slt for slt in body["slots"] if slt["status"] == "past"]
    expected_past = [slt for slt in body["slots"]
                     if int(slt["time"].split(":")[0]) * 60 + int(slt["time"].split(":")[1]) <= now_min]
    if not expected_past:
        pytest.skip("no elapsed slots for today's opening window yet")
    assert len(past_slots) == len(expected_past), f"expected {len(expected_past)} past, got {len(past_slots)}"


def test_availability_future_date_has_no_past_slots(s):
    listings = s.get(f"{API}/vendor-listings").json()
    if not listings:
        pytest.skip("no active listings on this instance")
    listing_id = listings[0]["id"]
    # Tomorrow — no slot should be "past"
    from datetime import timedelta
    future = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
    r = s.get(f"{API}/vendor-listings/{listing_id}/availability?date={future}")
    assert r.status_code == 200
    past = [x for x in r.json()["slots"] if x["status"] == "past"]
    assert past == []


# ---- Task 4: cancel event ----
def _create_event(s):
    r = s.post(f"{API}/events", json={
        "name": f"TEST_cancel_{uuid.uuid4().hex[:6]}",
        "sport": "football",
        "format": "round_robin",
        "event_type": "playsphere_organized",
        "description": "cancel test",
    }, timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


def test_cancel_event_marks_status_cancelled(s):
    ev = _create_event(s)
    r = s.post(f"{API}/events/{ev['id']}/cancel", json={"reason": "Rain, no rescheduling"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "cancelled"
    assert body.get("cancellation_reason") == "Rain, no rescheduling"


def test_cancel_event_idempotent_rejects_double_cancel(s):
    ev = _create_event(s)
    r1 = s.post(f"{API}/events/{ev['id']}/cancel", json={})
    assert r1.status_code == 200
    r2 = s.post(f"{API}/events/{ev['id']}/cancel", json={})
    assert r2.status_code == 400


def test_cancel_event_requires_auth(s):
    ev = _create_event(s)
    # Unauthenticated (fresh session)
    anon = requests.Session()
    r = anon.post(f"{API}/events/{ev['id']}/cancel", json={})
    assert r.status_code in (401, 403)


def test_cancel_event_404_for_missing(s):
    r = s.post(f"{API}/events/nonexistent/cancel", json={})
    assert r.status_code == 404


# ---- Task 6: sponsor signup with mobile ----
def test_sponsor_signup_accepts_mobile(s):
    uid = uuid.uuid4().hex[:8]
    payload = {
        "email": f"sponsor_{uid}@example.com",
        "password": "sponsor12345",
        "company_name": f"TestSponsor {uid}",
        "contact_person": "Alice",
        "mobile": f"+91987654{uid[:4]}",
    }
    r = requests.post(f"{API}/auth/sponsors/signup", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["email"] == payload["email"]


def test_sponsor_signup_rejects_duplicate_mobile(s):
    uid = uuid.uuid4().hex[:8]
    mobile = f"+91987655{uid[:4]}"
    r1 = requests.post(f"{API}/auth/sponsors/signup", json={
        "email": f"sponsora_{uid}@example.com", "password": "x1234567",
        "company_name": f"A {uid}", "mobile": mobile,
    }, timeout=10)
    assert r1.status_code == 200
    r2 = requests.post(f"{API}/auth/sponsors/signup", json={
        "email": f"sponsorb_{uid}@example.com", "password": "x1234567",
        "company_name": f"B {uid}", "mobile": mobile,
    }, timeout=10)
    assert r2.status_code == 400


def test_sponsor_signup_without_mobile_still_works(s):
    uid = uuid.uuid4().hex[:8]
    r = requests.post(f"{API}/auth/sponsors/signup", json={
        "email": f"sponsor_nomob_{uid}@example.com", "password": "x1234567",
        "company_name": f"NoMob {uid}",
    }, timeout=10)
    assert r.status_code == 200
