"""Tests for the review + moderation pipeline (player/HR submits -> vendor approves -> admin publishes)."""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN = {"email": "admin@kreedanation.com", "password": "admin123"}
HR = {"email": "acme@example.com", "password": "acme123"}
VENDOR = {"email": "ravi@turf.in", "password": "vendor123"}


def _login(creds):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def admin_session():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def hr_session():
    return _login(HR)


@pytest.fixture(scope="module")
def vendor_session():
    return _login(VENDOR)


@pytest.fixture(scope="module")
def listing(vendor_session):
    rows = vendor_session.get(f"{API}/vendors/me/listings").json()
    for L in rows:
        if L.get("approved"):
            return L
    pytest.skip("Vendor has no approved listings")


@pytest.fixture
def completed_booking(hr_session, admin_session, listing):
    """Create + force-complete a booking so we can review it."""
    slot_dt = datetime.now(timezone.utc) + timedelta(days=7)
    bk = hr_session.post(f"{API}/vendor-bookings", json={
        "listing_id": listing["id"],
        "requested_date": slot_dt.date().isoformat(),
        "start_time": slot_dt.strftime("%H:00"),
        "hours": 1,
    }).json()
    r = admin_session.patch(f"{API}/vendor-bookings/{bk['id']}", json={"status": "completed"})
    assert r.status_code == 200, r.text
    return r.json()


class TestReviewFlow:
    def test_review_requires_completed_booking(self, hr_session, listing):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 5, "text": "Great", "booking_id": str(uuid.uuid4()),
        })
        assert r.status_code == 400

    def test_rating_bounds(self, hr_session, listing, completed_booking):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 6, "text": "Too high", "booking_id": completed_booking["id"],
        })
        assert r.status_code == 400
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 0, "text": "Too low", "booking_id": completed_booking["id"],
        })
        assert r.status_code == 400

    def test_full_lifecycle(self, hr_session, vendor_session, admin_session, listing, completed_booking):
        # 1) HR submits review
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 4, "text": "Solid turf, lights good.", "booking_id": completed_booking["id"],
        })
        assert r.status_code == 200, r.text
        review = r.json()
        assert review["status"] == "pending_vendor"
        rid = review["id"]

        # 2) Public list should NOT include pending reviews
        pub = requests.get(f"{API}/vendor-listings/{listing['id']}/reviews").json()
        assert all(rv["id"] != rid for rv in pub["reviews"])

        # 3) Vendor approves -> pending_admin
        r2 = vendor_session.post(f"{API}/reviews/{rid}/respond", json={"action": "approve"})
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] == "pending_admin"

        # 4) Vendor adds public response
        vendor_session.post(f"{API}/reviews/{rid}/respond", json={"action": "respond", "response": "Thanks for the kind words."})

        # 5) Admin publishes -> visible
        r3 = admin_session.post(f"{API}/admin/reviews/{rid}/moderate", json={"action": "publish"})
        assert r3.status_code == 200, r3.text
        out = r3.json()
        assert out["status"] == "visible"
        assert out["vendor_response"] == "Thanks for the kind words."

        # 6) Public list now includes it + summary
        pub = requests.get(f"{API}/vendor-listings/{listing['id']}/reviews").json()
        assert any(rv["id"] == rid for rv in pub["reviews"])
        assert pub["summary"]["count"] >= 1
        assert 0 < pub["summary"]["average"] <= 5

    def test_one_review_per_booking(self, hr_session, listing, completed_booking):
        # First review
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 3, "text": "ok", "booking_id": completed_booking["id"],
        })
        assert r.status_code == 200
        # Second attempt
        r2 = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 4, "text": "updated", "booking_id": completed_booking["id"],
        })
        assert r2.status_code == 400

    def test_admin_reject_path(self, hr_session, vendor_session, admin_session, listing, completed_booking):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 5, "text": "Will be rejected", "booking_id": completed_booking["id"],
        })
        rid = r.json()["id"]
        vendor_session.post(f"{API}/reviews/{rid}/respond", json={"action": "approve"})
        r2 = admin_session.post(f"{API}/admin/reviews/{rid}/moderate", json={"action": "reject", "note": "spam"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "rejected"
        # Public list excludes
        pub = requests.get(f"{API}/vendor-listings/{listing['id']}/reviews").json()
        assert all(rv["id"] != rid for rv in pub["reviews"])

    def test_vendor_flag_skips_admin_queue(self, hr_session, vendor_session, listing, completed_booking):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 1, "text": "spam content", "booking_id": completed_booking["id"],
        })
        rid = r.json()["id"]
        r2 = vendor_session.post(f"{API}/reviews/{rid}/respond", json={"action": "flag", "note": "abuse"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "flagged"

    def test_admin_queue_endpoint(self, admin_session, hr_session, vendor_session, listing, completed_booking):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 4, "text": "Pending for admin", "booking_id": completed_booking["id"],
        })
        rid = r.json()["id"]
        vendor_session.post(f"{API}/reviews/{rid}/respond", json={"action": "approve"})
        queue = admin_session.get(f"{API}/admin/reviews/queue").json()
        assert any(rv["id"] == rid for rv in queue), f"Review {rid} should be in admin queue"

    def test_vendor_inbox_endpoint(self, vendor_session, hr_session, listing, completed_booking):
        r = hr_session.post(f"{API}/vendor-listings/{listing['id']}/reviews", json={
            "rating": 4, "text": "Vendor inbox check", "booking_id": completed_booking["id"],
        })
        rid = r.json()["id"]
        inbox = vendor_session.get(f"{API}/vendors/me/reviews").json()
        assert any(rv["id"] == rid for rv in inbox), "review should appear in vendor inbox"
