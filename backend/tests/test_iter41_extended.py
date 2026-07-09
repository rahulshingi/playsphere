"""Iteration 41 — extended verification for iter40 bug batch.

Covers additional edge cases NOT in test_batch_bugs_iter40.py:
* #1 future end_date event should STAY upcoming (not falsely completed)
* #6 login with full +91 prefix mobile (+919000000001) works
* #5 quick-add player returns temp_password + email attempt logged
* #4 also_player enabled unlocks /players/me for admin/HR/organiser
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
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return s


@pytest.fixture(scope="module")
def player_session():
    return _login("testplayer@example.com", "player123")


@pytest.fixture(scope="module")
def admin_session():
    return _login("admin@kreedanation.com", "admin123")


# ------------ Bug #1 negative path ------------
class TestEventFutureStaysUpcoming:
    def test_event_with_future_end_date_stays_upcoming(self, player_session):
        ev = player_session.post(f"{API}/events", json={
            "name": f"iter41_future_{secrets.token_hex(4)}",
            "sport": "cricket", "format": "knockout",
            "start_date": "2099-01-01", "end_date": "2099-01-02",
        }, timeout=10).json()
        try:
            one = player_session.get(f"{API}/events/{ev['id']}", timeout=10).json()
            # Must NOT be flipped to completed
            assert one["status"] != "completed", f"future event wrongly auto-completed: {one['status']}"
        finally:
            player_session.delete(f"{API}/events/{ev['id']}", timeout=10)


# ------------ Bug #6 additional mobile formats ------------
class TestMobileLoginFormats:
    def test_login_with_full_country_code_mobile(self):
        r = requests.post(f"{API}/auth/login", json={"email": "+919000000001", "password": "player123"}, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "player"

    def test_login_with_10_digit_mobile(self):
        r = requests.post(f"{API}/auth/login", json={"email": "9000000001", "password": "player123"}, timeout=10)
        assert r.status_code == 200, r.text

    def test_login_unknown_mobile_fails(self):
        r = requests.post(f"{API}/auth/login", json={"email": "1234567890", "password": "player123"}, timeout=10)
        assert r.status_code in (401, 404)


# ------------ Bug #3 endpoint contract ------------
class TestVendorSportsEndpoint:
    def test_public_anonymous_access(self):
        r = requests.get(f"{API}/vendor-listings/sports", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # All elements must be strings (sport slugs)
        for s in data:
            assert isinstance(s, str)


# ------------ Feature #5 quick-add welcome email ------------
class TestQuickAddWelcomeEmail:
    def test_quick_add_returns_temp_password(self, player_session):
        # Create an event + team, then quick-add a new member with an email
        ev = player_session.post(f"{API}/events", json={
            "name": f"iter41_qa_{secrets.token_hex(4)}",
            "sport": "cricket", "format": "knockout",
        }, timeout=10).json()
        try:
            # Create a team on the event
            team = player_session.post(f"{API}/events/{ev['id']}/teams",
                                       json={"name": f"Team_{secrets.token_hex(3)}"}, timeout=10)
            assert team.status_code in (200, 201), team.text
            team_id = team.json()["id"]

            # Quick-add a fresh member with an email
            new_email = f"iter41_qa_{secrets.token_hex(4)}@example.com"
            r = player_session.post(
                f"{API}/events/{ev['id']}/teams/{team_id}/members",
                json={"quick": {"name": "QA Fresh", "email": new_email, "mobile": f"+9199{secrets.token_hex(4)}"}},
                timeout=15,
            )
            # Endpoint should return 200 even if SendGrid fails (best-effort)
            assert r.status_code in (200, 201), r.text
            body = r.json()
            # temp_password should be returned for the organiser hand-off fallback
            # (may be nested under 'quick' or root; accept either)
            has_temp = ("temp_password" in body) or (
                isinstance(body.get("member"), dict) and "temp_password" in body["member"]
            ) or any("temp_password" in v for v in body.values() if isinstance(v, dict))
            assert has_temp, f"temp_password missing in response: {body}"
        finally:
            player_session.delete(f"{API}/events/{ev['id']}", timeout=10)


# ------------ Feature #4 also_player unlocks /players/me ------------
class TestAlsoPlayerUnlocksPlayersMe:
    def test_admin_can_access_players_me_after_opt_in(self, admin_session):
        # Enable also_player
        r = admin_session.post(f"{API}/auth/also-player", json={"enabled": True}, timeout=10)
        assert r.status_code == 200
        try:
            me = admin_session.get(f"{API}/auth/me", timeout=10).json()
            assert me.get("also_player") is True
            pid = me.get("player_profile_id")
            assert pid, "player_profile_id must be set"

            # /players/me should be accessible (returns the player profile)
            pm = admin_session.get(f"{API}/players/me", timeout=10)
            assert pm.status_code == 200, pm.text
        finally:
            admin_session.post(f"{API}/auth/also-player", json={"enabled": False}, timeout=10)
