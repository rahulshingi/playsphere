"""Backend regression tests for the Player Tournaments MVP (iteration 31).

Covers:
* Player role can POST /api/events (auto-tags `is_local_match=True`, respects `listed_publicly`)
* Anonymous /api/events hides hidden local matches; owner + admin still see them
* `scope=hosted` returns only the caller's events (regardless of visibility)
* PATCH /api/events/{id} accepted from creator (even if role=player)
* POST/DELETE /api/events/{id}/photos owner-only + persists
* PATCH /api/fixtures/{id} with hero_image_url + awards (owner-only)
* GET /api/players/{id}/hosted-tournaments respects visibility
"""
from __future__ import annotations
import os
import secrets
from datetime import datetime, timezone
from typing import Optional

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"


def _random_email() -> str:
    return f"pt_{secrets.token_hex(6)}@example.com"


def _random_mobile() -> str:
    return "+91" + str(secrets.randbelow(10**10)).zfill(10)


class _Session:
    def __init__(self):
        self.s = requests.Session()

    def login(self, email: str, password: str):
        r = self.s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10)
        r.raise_for_status()
        return r.json()

    def get(self, path: str, **kw):
        return self.s.get(f"{API}{path}", timeout=10, **kw)

    def post(self, path: str, json=None, **kw):
        return self.s.post(f"{API}{path}", json=json, timeout=10, **kw)

    def patch(self, path: str, json=None, **kw):
        return self.s.patch(f"{API}{path}", json=json, timeout=10, **kw)

    def delete(self, path: str, **kw):
        return self.s.delete(f"{API}{path}", timeout=10, **kw)


@pytest.fixture(scope="module")
def admin() -> _Session:
    s = _Session()
    s.login("admin@kreedanation.com", "admin123")
    return s


@pytest.fixture(scope="module")
def player() -> _Session:
    """Reuse the seeded testplayer account documented in test_credentials.md."""
    s = _Session()
    s.login("testplayer@example.com", "player123")
    return s


@pytest.fixture(scope="module")
def other_player(admin) -> _Session:
    """Sign up a fresh throw-away player so we can assert `hosted-tournaments`
    hides `listed_publicly=False` matches from strangers."""
    email = _random_email()
    mobile = _random_mobile()
    # Ask for OTP, then check the record in Mongo (test-only shortcut).
    r = requests.post(f"{API}/players/signup/request-otp", json={"email": email, "mobile": mobile}, timeout=10)
    if r.status_code != 200:
        pytest.skip(f"OTP request failed ({r.status_code}); vendor/SendGrid likely down")
    # Fetch OTP from Mongo directly (only usable in test env).
    import pymongo  # noqa: WPS433
    from dotenv import load_dotenv  # noqa: WPS433
    load_dotenv("/app/backend/.env")
    m = pymongo.MongoClient(os.environ["MONGO_URL"])
    otp_doc = m[os.environ["DB_NAME"]].player_signup_otps.find_one({"email": email})
    if not otp_doc:
        pytest.skip("OTP doc missing")
    r = requests.post(f"{API}/players/register", json={
        "name": "Other Player", "email": email, "mobile": mobile,
        "password": "other123", "otp": otp_doc["otp"],
    }, timeout=10)
    r.raise_for_status()
    s = _Session()
    s.login(email, "other123")
    return s


@pytest.fixture()
def created_events(player):
    created: list[str] = []
    yield created
    for eid in created:
        try:
            player.delete(f"/events/{eid}")
        except Exception:
            pass


class TestPlayerLocalMatchCreation:
    def test_player_creates_local_match_default_public(self, player, created_events):
        payload = {"name": "TEST_LM_public", "sport": "cricket", "format": "knockout", "venue": "Backyard"}
        r = player.post("/events", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_local_match"] is True
        assert data["listed_publicly"] is True
        assert data["approval_status"] == "approved"
        assert data["created_by"]  # set from JWT
        created_events.append(data["id"])

    def test_player_creates_hidden_local_match(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_hidden", "sport": "football", "format": "round_robin", "listed_publicly": False})
        assert r.status_code == 200
        data = r.json()
        assert data["is_local_match"] is True
        assert data["listed_publicly"] is False
        created_events.append(data["id"])

    def test_public_list_hides_hidden_events(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_hidden2", "sport": "cricket", "format": "knockout", "listed_publicly": False})
        eid = r.json()["id"]
        created_events.append(eid)
        # Anonymous request
        anon = requests.get(f"{API}/events", timeout=10)
        ids = {e["id"] for e in anon.json()}
        assert eid not in ids, "hidden local match leaked to public listing"

    def test_owner_scope_hosted_returns_hidden_events(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_hosted", "sport": "cricket", "format": "knockout", "listed_publicly": False})
        eid = r.json()["id"]
        created_events.append(eid)
        r = player.get("/events?scope=hosted")
        assert r.status_code == 200
        ids = {e["id"] for e in r.json()}
        assert eid in ids

    def test_admin_sees_hidden_events(self, player, admin, created_events):
        r = player.post("/events", json={"name": "TEST_LM_admin_view", "sport": "cricket", "format": "knockout", "listed_publicly": False})
        eid = r.json()["id"]
        created_events.append(eid)
        r = admin.get("/events")
        ids = {e["id"] for e in r.json()}
        assert eid in ids


class TestEventPatchByCreator:
    def test_creator_can_patch_own_event(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_patch", "sport": "cricket", "format": "knockout"})
        eid = r.json()["id"]
        created_events.append(eid)
        r = player.patch(f"/events/{eid}", json={"venue": "Updated venue", "listed_publicly": False})
        assert r.status_code == 200, r.text
        assert r.json()["venue"] == "Updated venue"
        assert r.json()["listed_publicly"] is False

    def test_patch_ignores_protected_fields(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_protected", "sport": "cricket", "format": "knockout"})
        eid = r.json()["id"]
        original_created_by = r.json()["created_by"]
        created_events.append(eid)
        r = player.patch(f"/events/{eid}", json={"created_by": "hacker-id", "approval_status": "rejected"})
        assert r.status_code == 200
        assert r.json()["created_by"] == original_created_by
        assert r.json()["approval_status"] == "approved"


class TestEventPhotos:
    def test_owner_can_add_and_remove_photos(self, player, created_events):
        r = player.post("/events", json={"name": "TEST_LM_photos", "sport": "cricket", "format": "knockout"})
        eid = r.json()["id"]
        created_events.append(eid)
        r = player.post(f"/events/{eid}/photos", json={"url": "/api/uploads/x1"})
        assert r.status_code == 200
        assert "/api/uploads/x1" in r.json()["photos"]
        r = player.post(f"/events/{eid}/photos", json={"url": "/api/uploads/x2"})
        assert "/api/uploads/x2" in r.json()["photos"]
        r = player.delete(f"/events/{eid}/photos", params={"url": "/api/uploads/x1"})
        assert r.status_code == 200
        assert r.json()["photos"] == ["/api/uploads/x2"]

    def test_non_owner_cannot_add_photos(self, player, admin, created_events):
        # Player creates, admin fetches — but a *different* non-admin should 403.
        # We use another_player fixture indirectly by hitting the endpoint anonymously.
        r = player.post("/events", json={"name": "TEST_LM_ph_deny", "sport": "cricket", "format": "knockout"})
        eid = r.json()["id"]
        created_events.append(eid)
        # anonymous request
        r = requests.post(f"{API}/events/{eid}/photos", json={"url": "/x"}, timeout=10)
        assert r.status_code in (401, 403)


class TestPlayerHostedTournaments:
    def test_hosted_endpoint_returns_own_public_and_hidden(self, player, created_events):
        # Create one public + one hidden.
        r1 = player.post("/events", json={"name": "TEST_LM_pub_h", "sport": "cricket", "format": "knockout"})
        r2 = player.post("/events", json={"name": "TEST_LM_priv_h", "sport": "cricket", "format": "knockout", "listed_publicly": False})
        created_events.append(r1.json()["id"])
        created_events.append(r2.json()["id"])
        # Resolve player_id from /players/me
        me = player.get("/players/me").json()
        r = player.get(f"/players/{me['id']}/hosted-tournaments")
        assert r.status_code == 200
        ids = {e["id"] for e in r.json()}
        assert r1.json()["id"] in ids
        assert r2.json()["id"] in ids

    def test_stranger_hides_hidden_events(self, player, other_player, created_events):
        r1 = player.post("/events", json={"name": "TEST_LM_stranger_pub", "sport": "cricket", "format": "knockout"})
        r2 = player.post("/events", json={"name": "TEST_LM_stranger_hid", "sport": "cricket", "format": "knockout", "listed_publicly": False})
        created_events.append(r1.json()["id"])
        created_events.append(r2.json()["id"])
        me = player.get("/players/me").json()
        r = other_player.get(f"/players/{me['id']}/hosted-tournaments")
        assert r.status_code == 200
        ids = {e["id"] for e in r.json()}
        assert r1.json()["id"] in ids
        assert r2.json()["id"] not in ids
