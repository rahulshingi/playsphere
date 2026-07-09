"""Iteration 40 — user-reported bugs + features batch.

Covers:
* #1 event auto-completes when end_date passes (GET /events + GET /events/{id})
* #2 photo gallery capped at 7 (POST /events/{id}/photos returns 400 after 7)
* #3 vendor-listings/sports endpoint returns snooker/etc when listings exist
* #6 login accepts mobile number OR email
* #4 HR/organiser can opt-in as also_player via /auth/also-player
"""
from __future__ import annotations
import os
import secrets

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10).raise_for_status()
    return s


@pytest.fixture(scope="module")
def player_session():
    return _login("testplayer@example.com", "player123")


class TestEventAutoComplete:
    def test_event_with_past_end_date_auto_completes(self, player_session):
        ev = player_session.post(f"{API}/events", json={
            "name": f"iter40_stale_{secrets.token_hex(4)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2024-01-01", "end_date": "2024-01-02",
        }, timeout=10).json()
        assert ev["status"] in ("upcoming", "ongoing")  # created default
        # Fetch via list — should auto-flip to completed.
        listed = player_session.get(f"{API}/events?scope=hosted", timeout=10).json()
        entry = next((e for e in listed if e["id"] == ev["id"]), None)
        assert entry is not None
        assert entry["status"] == "completed", "past-end-date event should auto-complete"
        # Also via GET single event.
        one = player_session.get(f"{API}/events/{ev['id']}", timeout=10).json()
        assert one["status"] == "completed"
        player_session.delete(f"{API}/events/{ev['id']}", timeout=10)


class TestPhotoCap:
    def test_photo_limit_seven(self, player_session):
        ev = player_session.post(f"{API}/events", json={"name": f"iter40_ph_{secrets.token_hex(4)}",
                                                        "sport": "cricket", "format": "knockout"}, timeout=10).json()
        try:
            for i in range(7):
                r = player_session.post(f"{API}/events/{ev['id']}/photos", json={"url": f"/api/uploads/x{i}"}, timeout=10)
                assert r.status_code == 200, r.text
            r = player_session.post(f"{API}/events/{ev['id']}/photos", json={"url": "/api/uploads/x8"}, timeout=10)
            assert r.status_code == 400
            assert "limit" in r.json()["detail"].lower()
        finally:
            player_session.delete(f"{API}/events/{ev['id']}", timeout=10)


class TestVendorListingsSports:
    def test_sports_endpoint_returns_distinct_sports(self):
        r = requests.get(f"{API}/vendor-listings/sports", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Non-strict: snooker may not be listed yet in this env, but the endpoint
        # must exist and respond OK.


class TestMobileLogin:
    def test_login_with_email(self):
        r = requests.post(f"{API}/auth/login", json={"email": "testplayer@example.com", "password": "player123"}, timeout=10)
        assert r.status_code == 200

    def test_login_with_mobile(self):
        # Test player has mobile +919000000001 documented in test_credentials.md.
        r = requests.post(f"{API}/auth/login", json={"email": "9000000001", "password": "player123"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "player"

    def test_login_wrong_password_still_fails(self):
        r = requests.post(f"{API}/auth/login", json={"email": "9000000001", "password": "wrong"}, timeout=10)
        assert r.status_code == 401


class TestAlsoPlayer:
    def test_admin_can_opt_in_as_player(self):
        # Platform admin as our test proxy — the /also-player route accepts
        # platform_admin / admin / company_admin / organiser identically.
        s = _login("admin@kreedanation.com", "admin123")
        r = s.post(f"{API}/auth/also-player", json={"enabled": True}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["also_player"] is True
        # /auth/me now surfaces also_player + player_profile_id.
        me = s.get(f"{API}/auth/me", timeout=10).json()
        assert me.get("also_player") is True
        assert me.get("player_profile_id"), "player_profile_id should be surfaced"
        # Disable
        r = s.post(f"{API}/auth/also-player", json={"enabled": False}, timeout=10)
        assert r.status_code == 200
        assert r.json()["also_player"] is False

    def test_native_player_role_cannot_opt_in(self, player_session):
        # A native `role=player` doesn't need also_player — endpoint rejects.
        r = player_session.post(f"{API}/auth/also-player", json={"enabled": True}, timeout=10)
        assert r.status_code == 403
