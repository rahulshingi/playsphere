"""Iteration 41 — Event Lifecycle Automation + required create-time dates.

Covers:
  * POST /api/events — start_date/end_date now REQUIRED at create-time
  * PATCH /api/events/{id} — blank guards + order check (uses existing values)
  * event_lifecycle.run_tick — status transitions (upcoming/ongoing/completed/cancelled)
  * event_lifecycle.run_tick — reminder emails per stage w/ cooldown
  * POST /api/admin/events/lifecycle/tick — platform_admin only

The lifecycle tests call run_tick(db, mock_send_email) DIRECTLY against a real Mongo
instance (via motor) so we exercise the actual DB code path but don't spam SendGrid.
"""
from __future__ import annotations

import asyncio
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ─────────────────────── Session fixtures ───────────────────────

def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    return s


@pytest.fixture(scope="module")
def player_session():
    return _login("testplayer@example.com", "player123")


@pytest.fixture(scope="module")
def admin_session():
    return _login("admin@kreedanation.com", "admin123")


@pytest.fixture(scope="module")
def organiser_session():
    return _login("testorg@example.com", "orgpass123")


@pytest.fixture(scope="module")
def hr_session():
    try:
        return _login("acme@example.com", "acme123")
    except Exception:
        pytest.skip("HR seed account not available (clean-slate mode)")


# ─────────────────────── Required create-time dates ───────────────────────

class TestCreateRequiresDates:
    """POST /api/events — start_date + end_date REQUIRED at create-time."""

    def test_missing_start_date_returns_400(self, player_session):
        r = player_session.post(f"{API}/events", json={
            "name": f"iter41_no_start_{secrets.token_hex(3)}",
            "sport": "cricket", "format": "knockout",
            "end_date": "2099-01-02",
        }, timeout=15)
        assert r.status_code == 400, r.text
        assert "start_date" in r.text.lower()

    def test_missing_end_date_returns_400(self, player_session):
        r = player_session.post(f"{API}/events", json={
            "name": f"iter41_no_end_{secrets.token_hex(3)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2099-01-01",
        }, timeout=15)
        assert r.status_code == 400, r.text
        assert "end_date" in r.text.lower()

    def test_end_before_start_returns_400(self, player_session):
        r = player_session.post(f"{API}/events", json={
            "name": f"iter41_backwards_{secrets.token_hex(3)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2099-06-01",
            "end_date": "2099-01-01",
        }, timeout=15)
        assert r.status_code == 400, r.text
        assert "earlier" in r.text.lower() or "start_date" in r.text.lower()

    def test_valid_dates_create_succeeds(self, player_session):
        r = player_session.post(f"{API}/events", json={
            "name": f"iter41_ok_{secrets.token_hex(3)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2099-05-01",
            "end_date": "2099-05-05",
        }, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["start_date"] == "2099-05-01"
        assert body["end_date"] == "2099-05-05"
        # cleanup
        player_session.delete(f"{API}/events/{body['id']}", timeout=10)


# ─────────────────────── PATCH behavior ───────────────────────

class TestPatchDates:
    """PATCH must not re-require dates, but must reject blanks + bad order."""

    @pytest.fixture
    def existing_event(self, player_session):
        r = player_session.post(f"{API}/events", json={
            "name": f"iter41_patch_{secrets.token_hex(3)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2099-06-01",
            "end_date": "2099-06-10",
        }, timeout=15)
        assert r.status_code == 200, r.text
        ev = r.json()
        yield ev
        player_session.delete(f"{API}/events/{ev['id']}", timeout=10)

    def test_partial_update_without_dates_succeeds(self, player_session, existing_event):
        r = player_session.patch(f"{API}/events/{existing_event['id']}",
                                 json={"description": "updated description iter41"}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "updated description iter41"
        # dates unchanged
        assert r.json()["start_date"] == "2099-06-01"

    def test_blank_start_date_rejected(self, player_session, existing_event):
        r = player_session.patch(f"{API}/events/{existing_event['id']}",
                                 json={"start_date": ""}, timeout=15)
        assert r.status_code == 400, r.text
        assert "start_date" in r.text.lower()

    def test_blank_end_date_rejected(self, player_session, existing_event):
        r = player_session.patch(f"{API}/events/{existing_event['id']}",
                                 json={"end_date": ""}, timeout=15)
        assert r.status_code == 400, r.text
        assert "end_date" in r.text.lower()

    def test_new_end_before_existing_start_rejected(self, player_session, existing_event):
        # existing start=2099-06-01. patch end=2020-01-01 → order check fails
        r = player_session.patch(f"{API}/events/{existing_event['id']}",
                                 json={"end_date": "2020-01-01"}, timeout=15)
        assert r.status_code == 400, r.text
        assert "earlier" in r.text.lower()

    def test_valid_new_dates_succeed(self, player_session, existing_event):
        r = player_session.patch(f"{API}/events/{existing_event['id']}",
                                 json={"start_date": "2099-07-01", "end_date": "2099-07-15"},
                                 timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["start_date"] == "2099-07-01"
        assert r.json()["end_date"] == "2099-07-15"


# ─────────────────────── Manual admin tick endpoint ───────────────────────

class TestManualTickEndpoint:
    def test_platform_admin_can_tick(self, admin_session):
        r = admin_session.post(f"{API}/admin/events/lifecycle/tick", timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert set(body.keys()) >= {"scanned", "status_changed", "reminders_sent"}
        assert isinstance(body["scanned"], int)

    def test_non_admin_forbidden(self, player_session):
        r = player_session.post(f"{API}/admin/events/lifecycle/tick", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_organiser_forbidden(self, organiser_session):
        r = organiser_session.post(f"{API}/admin/events/lifecycle/tick", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_hr_forbidden(self, hr_session):
        r = hr_session.post(f"{API}/admin/events/lifecycle/tick", timeout=15)
        assert r.status_code in (401, 403), r.text

    def test_anonymous_forbidden(self):
        r = requests.post(f"{API}/admin/events/lifecycle/tick", timeout=15)
        assert r.status_code in (401, 403), r.text


# ─────────────────────── Direct run_tick unit tests ───────────────────────

# Import the module under test
import sys
sys.path.insert(0, "/app/backend")
from routes import event_lifecycle as lifecycle  # noqa: E402


@pytest.fixture
def db():
    """Real motor client to /app/backend/.env's MONGO_URL + DB_NAME."""
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _iso_days(delta: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=delta)).isoformat()


async def _insert_event(db, **overrides) -> str:
    eid = f"iter41_life_{secrets.token_hex(4)}"
    doc = {
        "id": eid,
        "name": f"iter41 lifecycle {eid}",
        "sport": "cricket",
        "format": "knockout",
        "status": overrides.get("status", "upcoming"),
        "start_date": overrides.get("start_date", _iso_days(1)),
        "end_date": overrides.get("end_date", _iso_days(3)),
        "created_by": "test-user",
        "contact_email": overrides.get("contact_email", "iter41@example.com"),
        "is_local_match": False,
        "approval_status": "approved",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    for k, v in overrides.items():
        doc[k] = v
    await db.events.insert_one(doc)
    return eid


async def _cleanup(db, eid: str):
    await db.events.delete_one({"id": eid})
    await db.teams.delete_many({"event_id": eid})
    await db.fixtures.delete_many({"event_id": eid})


class TestRunTickStatus:
    """Direct unit tests for run_tick's status transition rules."""

    @pytest.mark.asyncio
    async def test_past_end_no_matches_started_cancels(self, db):
        eid = await _insert_event(db,
            start_date=_iso_days(-5), end_date=_iso_days(-2),
            status="upcoming",
        )
        try:
            # insert a fixture but with status="scheduled" (not started)
            await db.fixtures.insert_one({
                "id": f"fx_{eid}", "event_id": eid, "status": "scheduled",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            mock_send = MagicMock(return_value=True)
            stats = await lifecycle.run_tick(db, mock_send)
            assert stats["scanned"] >= 1
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev["status"] == "cancelled"
            assert ev.get("auto_status_reason") == "No matches were played."
            assert "auto_status_updated_at" in ev
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_past_end_with_live_fixture_completes(self, db):
        eid = await _insert_event(db,
            start_date=_iso_days(-5), end_date=_iso_days(-1),
            status="ongoing",
        )
        try:
            await db.fixtures.insert_one({
                "id": f"fx_{eid}", "event_id": eid, "status": "live",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev["status"] == "completed"
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_today_between_start_end_goes_ongoing(self, db):
        eid = await _insert_event(db,
            start_date=_iso_days(-1), end_date=_iso_days(1),
            status="upcoming",
        )
        try:
            # add a team + fixture so we don't get reminder-only progress
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            await db.fixtures.insert_one({"id": f"fx_{eid}", "event_id": eid, "status": "scheduled"})
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev["status"] == "ongoing"
        finally:
            await _cleanup(db, eid)


class TestRunTickReminders:
    """Direct unit tests for run_tick's reminder policy."""

    @pytest.mark.asyncio
    async def test_no_teams_reminder(self, db):
        # brand-new event, 0 teams → 'no_teams' reminder
        eid = await _insert_event(db,
            start_date=_iso_days(3), end_date=_iso_days(5),
        )
        try:
            mock_send = MagicMock(return_value=True)
            stats = await lifecycle.run_tick(db, mock_send)
            assert stats["reminders_sent"] >= 1
            mock_send.assert_called()
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev.get("last_reminder_sent", {}).get("no_teams")
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_no_fixtures_reminder_with_cooldown(self, db):
        # teams but no fixtures → 'no_fixtures' reminder
        eid = await _insert_event(db,
            start_date=_iso_days(3), end_date=_iso_days(5),
        )
        try:
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            mock_send = MagicMock(return_value=True)
            stats1 = await lifecycle.run_tick(db, mock_send)
            initial_calls = mock_send.call_count
            assert initial_calls >= 1
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev.get("last_reminder_sent", {}).get("no_fixtures")

            # Second tick within cooldown (<23h) → no additional call
            stats2 = await lifecycle.run_tick(db, mock_send)
            # For this specific event stage, we assert the counter didn't advance
            # (other events on the shared DB might trigger their own reminders,
            #  so use the stored ts as the source of truth)
            ev2 = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev2["last_reminder_sent"]["no_fixtures"] == ev["last_reminder_sent"]["no_fixtures"]
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_starts_tomorrow_reminder(self, db):
        eid = await _insert_event(db,
            start_date=_iso_days(1), end_date=_iso_days(3),
        )
        try:
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            await db.fixtures.insert_one({"id": f"fx_{eid}", "event_id": eid, "status": "scheduled"})
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev.get("last_reminder_sent", {}).get("starts_tomorrow")
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_start_today_reminder(self, db):
        # start_date == today, no fixture started → 'start_today' reminder
        eid = await _insert_event(db,
            start_date=_today(), end_date=_iso_days(2),
        )
        try:
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            await db.fixtures.insert_one({"id": f"fx_{eid}", "event_id": eid, "status": "scheduled"})
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev.get("last_reminder_sent", {}).get("start_today")
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_no_activity_8h_reminder(self, db):
        # ongoing event, last fixture activity was 10h ago
        eid = await _insert_event(db,
            start_date=_iso_days(-1), end_date=_iso_days(1),
            status="ongoing",
        )
        try:
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            ten_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
            await db.fixtures.insert_one({
                "id": f"fx_{eid}", "event_id": eid, "status": "live",
                "updated_at": ten_hours_ago,
            })
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            assert ev.get("last_reminder_sent", {}).get("no_activity_8h")
        finally:
            await _cleanup(db, eid)

    @pytest.mark.asyncio
    async def test_publish_results_reminder(self, db):
        # All fixtures completed but event.status != completed and today <= end_date
        eid = await _insert_event(db,
            start_date=_iso_days(-2), end_date=_iso_days(1),
            status="ongoing",
        )
        try:
            await db.teams.insert_one({"id": f"tm_{eid}", "event_id": eid, "name": "T"})
            await db.fixtures.insert_one({
                "id": f"fx_{eid}", "event_id": eid, "status": "completed",
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            })
            mock_send = MagicMock(return_value=True)
            await lifecycle.run_tick(db, mock_send)
            ev = await db.events.find_one({"id": eid}, {"_id": 0})
            # publish_results triggers only when status != completed. Confirm reminder fired
            # (auto-status flip is bounded by end_date so this event stays ongoing here).
            assert ev.get("last_reminder_sent", {}).get("publish_results")
        finally:
            await _cleanup(db, eid)


# ─────────────────────── Regression: lifecycle endpoints ───────────────────────

class TestRegressionApprovalFlow:
    """Existing approve/reject/cancel still work."""

    def test_approve_reject_still_present(self, admin_session):
        # Verify these routes exist by hitting a 404 event (which is fine — proves
        # the route is mounted and returns 404 not 405)
        r1 = admin_session.post(f"{API}/events/nonexistent-id/approve", timeout=10)
        r2 = admin_session.post(f"{API}/events/nonexistent-id/reject", json={"reason": "x"}, timeout=10)
        r3 = admin_session.post(f"{API}/events/nonexistent-id/cancel", json={}, timeout=10)
        assert r1.status_code == 404, r1.text
        assert r2.status_code == 404, r2.text
        assert r3.status_code == 404, r3.text

    def test_events_list_shape_unchanged(self):
        r = requests.get(f"{API}/events", timeout=15)
        assert r.status_code == 200
        events = r.json()
        assert isinstance(events, list)
        if events:
            e = events[0]
            assert "id" in e and "status" in e
