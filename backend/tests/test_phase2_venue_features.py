"""Tests for Phase 2 venue-owner features:
 - Happy-hour pricing (slot-level discount factor)
 - Cancellation policy + refund auto-calc
 - Reschedule policy + max count + fee
 - Mocked email helper dispatch on booking lifecycle events
"""
import os
import time
import logging
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
    """Get the vendor's first approved listing."""
    rows = vendor_session.get(f"{API}/vendors/me/listings").json()
    for L in rows:
        if L.get("approved"):
            return L
    pytest.skip("Vendor has no approved listings")


class TestHappyHourPricing:
    def test_set_happy_hour_and_observe_in_availability(self, vendor_session, listing):
        # Configure 18:00-19:00 every day as a 50%-off happy hour
        r = vendor_session.patch(f"{API}/vendor-listings/{listing['id']}/schedule", json={
            "opening_time": "10:00", "closing_time": "22:00", "slot_minutes": 60,
            "peak_hours": ["20:00"], "peak_price_factor": 1.5,
            "weekend_price_factor": 1.0,
            "happy_hours": [{"label": "Discount Hour", "days": [], "start": "18:00", "end": "19:00", "factor": 0.5}],
        })
        assert r.status_code == 200, r.text

        future = (datetime.utcnow() + timedelta(days=10)).date()
        # Find the next weekday from `future` so peak/happy hour tests aren't masked by weekend factor
        while future.weekday() >= 5:
            future = future + timedelta(days=1)
        future = future.isoformat()
        av = requests.get(f"{API}/vendor-listings/{listing['id']}/availability", params={"date": future}).json()
        base = float(listing["price"])
        slot_18 = next(s for s in av["slots"] if s["time"] == "18:00")
        slot_20 = next(s for s in av["slots"] if s["time"] == "20:00")
        assert slot_18["price"] == round(base * 0.5, 2), f"expected happy-hour price; got {slot_18}"
        assert slot_18.get("happy_hour") == "Discount Hour"
        assert slot_20["price"] == round(base * 1.5, 2), "peak hour should keep peak factor"

    def test_clear_happy_hours(self, vendor_session, listing):
        r = vendor_session.patch(f"{API}/vendor-listings/{listing['id']}/schedule", json={
            "happy_hours": []
        })
        assert r.status_code == 200
        assert r.json().get("happy_hours") == []


class TestCancellationPolicy:
    def _create_booking(self, hr_session, listing, hours_from_now: int = 48):
        # pick a date/time `hours_from_now` from now
        slot_dt = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
        date = slot_dt.date().isoformat()
        start = slot_dt.strftime("%H:00")  # bucket to the hour
        r = hr_session.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": date,
            "start_time": start,
            "hours": 1,
            "notes": "test booking",
        })
        assert r.status_code in (200, 201), r.text
        return r.json()

    def test_full_refund_when_far_out(self, hr_session, vendor_session, listing):
        # Set policy: full refund ≥ 24h, partial ≥ 6h (50%), no refund < 2h
        vendor_session.patch(f"{API}/vendors/me/listings/{listing['id']}", json={
            "cancellation_policy": {
                "full_refund_hours_before": 24,
                "partial_refund_hours_before": 6,
                "partial_refund_percent": 50,
                "no_refund_window_hours": 2,
            },
        })
        bk = self._create_booking(hr_session, listing, hours_from_now=72)
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={"notes": "test"})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "cancelled"
        assert out["refund_amount"] == out["total"]  # 100% refund
        assert "Full refund" in (out.get("refund_reason") or "")

    def test_partial_refund_inside_window(self, hr_session, vendor_session, listing):
        # Slot only 10h away → partial refund (10h is between 6h and 24h)
        bk = self._create_booking(hr_session, listing, hours_from_now=10)
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["status"] == "cancelled"
        assert 0 < out["refund_amount"] < out["total"]
        assert "Partial refund" in (out.get("refund_reason") or "")

    def test_no_refund_close_to_slot(self, hr_session, listing):
        # Slot only 1h away → no refund
        bk = self._create_booking(hr_session, listing, hours_from_now=1)
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["refund_amount"] == 0
        assert "No refund" in (out.get("refund_reason") or "")

    def test_cannot_double_cancel(self, hr_session, listing):
        bk = self._create_booking(hr_session, listing, hours_from_now=48)
        hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={})
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={})
        assert r.status_code == 400


class TestReschedulePolicy:
    def _create_booking(self, hr_session, listing, hours_from_now: int = 72):
        slot_dt = datetime.now(timezone.utc) + timedelta(hours=hours_from_now)
        r = hr_session.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": slot_dt.date().isoformat(),
            "start_time": slot_dt.strftime("%H:00"),
            "hours": 1,
            "notes": "resched test",
        })
        assert r.status_code in (200, 201), r.text
        return r.json()

    def test_reschedule_far_out_is_free(self, hr_session, vendor_session, listing):
        vendor_session.patch(f"{API}/vendors/me/listings/{listing['id']}", json={
            "reschedule_policy": {"free_reschedule_hours_before": 24, "max_reschedules": 2, "fee_amount": 100},
        })
        bk = self._create_booking(hr_session, listing, hours_from_now=72)
        new_dt = datetime.now(timezone.utc) + timedelta(days=5)
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/reschedule", json={
            "requested_date": new_dt.date().isoformat(),
            "start_time": "15:00",
            "hours": 1,
        })
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["reschedule_count"] == 1
        assert out["start_time"] == "15:00"
        assert out["previous_slots"][-1]["fee_charged"] == 0

    def test_reschedule_too_close_charges_fee(self, hr_session, listing):
        bk = self._create_booking(hr_session, listing, hours_from_now=4)
        new_dt = datetime.now(timezone.utc) + timedelta(days=5)
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/reschedule", json={
            "requested_date": new_dt.date().isoformat(),
            "start_time": "16:00",
            "hours": 1,
        })
        assert r.status_code == 200, r.text
        assert r.json()["previous_slots"][-1]["fee_charged"] == 100

    def test_max_reschedules_enforced(self, hr_session, vendor_session, listing):
        vendor_session.patch(f"{API}/vendors/me/listings/{listing['id']}", json={
            "reschedule_policy": {"free_reschedule_hours_before": 24, "max_reschedules": 1, "fee_amount": 0},
        })
        bk = self._create_booking(hr_session, listing, hours_from_now=72)
        new_dt = (datetime.now(timezone.utc) + timedelta(days=3))
        ok = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/reschedule", json={
            "requested_date": new_dt.date().isoformat(),
            "start_time": "17:00",
            "hours": 1,
        })
        assert ok.status_code == 200
        fail = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/reschedule", json={
            "requested_date": (new_dt + timedelta(days=1)).date().isoformat(),
            "start_time": "18:00",
            "hours": 1,
        })
        assert fail.status_code == 400
        assert "limit" in fail.json()["detail"].lower()


class TestEmailMockedDispatch:
    def test_cancel_logs_mock_email(self, hr_session, vendor_session, listing, caplog):
        """Verify the MOCK EMAIL log line is emitted when a booking is cancelled."""
        slot_dt = datetime.now(timezone.utc) + timedelta(hours=72)
        bk = hr_session.post(f"{API}/vendor-bookings", json={
            "listing_id": listing["id"],
            "requested_date": slot_dt.date().isoformat(),
            "start_time": slot_dt.strftime("%H:00"),
            "hours": 1,
        }).json()
        # The email dispatch happens server-side; we can only verify externally via the booking
        # notifications array (mirror of the email content).
        r = hr_session.post(f"{API}/vendor-bookings/{bk['id']}/cancel", json={})
        out = r.json()
        notes = out.get("notifications") or []
        assert any(n.get("event") == "cancelled_hr" for n in notes), f"missing cancellation notification: {notes}"
