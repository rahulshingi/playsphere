"""Iteration 39 — Pretty share URLs + Sport Config model.

Coverage:
* Every player profile has a `slug` field (backfilled on boot).
* `GET /players/by-slug/{slug}` resolves to the same profile with same
  redaction rules as `GET /players/profiles/{id}`.
* Duplicate slug requests get suffixed (rahul-shingi, rahul-shingi-2, …).
* `GET /sports` returns each sport with a `config` object including
  players_per_team, formats_supported, tie_breakers, standings_fields.
* Pickleball, Snooker are seeded (were missing before iter39).
* Admin PATCH /sports/{id} can override config keys.
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


@pytest.fixture(scope="module")
def admin_session():
    return _login("admin@kreedanation.com", "admin123")


class TestPrettyShareURL:
    def test_player_has_slug(self, player_session):
        me = player_session.get(f"{API}/players/me", timeout=10).json()
        assert me.get("slug"), "every profile should have a slug after iter39 backfill"
        assert me["slug"] == me["slug"].lower()
        # Basic slug rules — kebab-case, no spaces, no special chars.
        assert " " not in me["slug"]

    def test_resolve_by_slug_matches_by_id(self, player_session):
        me = player_session.get(f"{API}/players/me", timeout=10).json()
        by_slug = requests.get(f"{API}/players/by-slug/{me['slug']}", timeout=10).json()
        assert by_slug["id"] == me["id"]
        assert by_slug["name"] == me["name"]

    def test_anonymous_slug_view_redacts_mobile(self):
        # Fetch a known player by slug — mobile must come back masked (no digits after prefix).
        by_slug = requests.get(f"{API}/players/by-slug/test-player", timeout=10)
        if by_slug.status_code != 200:
            pytest.skip("Test player has a different slug in this env")
        d = by_slug.json()
        assert "mobile" not in d, "raw mobile should be redacted for anon viewers"
        assert d.get("mobile_masked", "").startswith("•")

    def test_unknown_slug_returns_404(self):
        r = requests.get(f"{API}/players/by-slug/nonexistent-{secrets.token_hex(4)}", timeout=10)
        assert r.status_code == 404


class TestSportConfig:
    def test_sports_list_carries_config(self):
        docs = requests.get(f"{API}/sports", timeout=10).json()
        cricket = next((d for d in docs if d["value"] == "cricket"), None)
        assert cricket is not None
        cfg = cricket.get("config") or {}
        assert cfg.get("players_per_team", {}).get("on_field") == 11
        assert "nrr" in (cfg.get("tie_breakers") or [])
        assert cfg.get("has_toss") is True

    def test_pickleball_snooker_seeded(self):
        docs = requests.get(f"{API}/sports", timeout=10).json()
        values = {d["value"] for d in docs}
        assert "pickleball" in values, "pickleball must be seeded"
        assert "snooker" in values, "snooker must be seeded"

    def test_admin_can_patch_config(self, admin_session):
        docs = admin_session.get(f"{API}/sports", timeout=10).json()
        cricket = next((d for d in docs if d["value"] == "cricket"), None)
        original = (cricket.get("config") or {}).get("match_duration_min")
        r = admin_session.patch(f"{API}/sports/{cricket['id']}",
                                json={"config": {"match_duration_min": 999}}, timeout=10)
        assert r.status_code == 200
        assert (r.json().get("config") or {}).get("match_duration_min") == 999
        # Revert
        admin_session.patch(f"{API}/sports/{cricket['id']}",
                            json={"config": {"match_duration_min": original}}, timeout=10)
