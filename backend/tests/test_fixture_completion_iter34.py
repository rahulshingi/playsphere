"""Iteration 34 — fixture completion locks + auto-awards + reopen escape hatch.

Tests cover:
* PATCH /fixtures/{id} with `status=completed` auto-fills `winner_id` + `awards`
* PATCH /fixtures/{id}/media returns 409 when awards are edited on a locked fixture
* PATCH /fixtures/{id}/media STILL accepts hero_image edits when locked
* PATCH /fixtures/{id} returns 409 when scored on a completed fixture
* POST /fixtures/{id}/reopen clears winner + awards and flips status back to live
* Reopen is gated to event creator + platform admin
"""
from __future__ import annotations
import os
import secrets
import uuid

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"


def _session_for(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=10)
    r.raise_for_status()
    return s


@pytest.fixture(scope="module")
def player_session():
    return _session_for("testplayer@example.com", "player123")


@pytest.fixture(scope="module")
def admin_session():
    return _session_for("admin@kreedanation.com", "admin123")


@pytest.fixture()
def cricket_fixture(player_session):
    """Create a cricket event + 2 teams + generate fixtures. Returns (event_id, fixture_id)."""
    ev = player_session.post(f"{API}/events", json={
        "name": f"iter34_{secrets.token_hex(4)}",
        "sport": "cricket", "format": "knockout",
        "venue": "Test ground",
    }, timeout=10).json()
    eid = ev["id"]
    # 2 teams
    ta = player_session.post(f"{API}/events/{eid}/teams", json={"name": "Alpha", "color": "#84CC16"}, timeout=10).json()
    tb = player_session.post(f"{API}/events/{eid}/teams", json={"name": "Beta", "color": "#EC4899"}, timeout=10).json()
    # Generate fixtures then fetch them
    player_session.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fixtures = player_session.get(f"{API}/events/{eid}/fixtures", timeout=10).json()
    fixture_id = fixtures[0]["id"]
    yield eid, fixture_id, ta["id"], tb["id"]
    # Cleanup
    try:
        player_session.delete(f"{API}/events/{eid}", timeout=10)
    except Exception:
        pass


def _cricket_score(a_total: int, b_total: int, batters_a=None, bowlers_b=None):
    return {
        "team_a": {"total": a_total, "batters": batters_a or []},
        "team_b": {"total": b_total, "bowlers": bowlers_b or []},
    }


class TestAutoCompleteAwards:
    def test_status_completed_auto_fills_winner(self, player_session, cricket_fixture):
        eid, fid, ta_id, tb_id = cricket_fixture
        # Fetch the actual fixture to learn which team is team_a vs team_b —
        # generate_fixtures may pair them either way.
        fx = player_session.get(f"{API}/fixtures/{fid}").json()
        # Make sure team_a scores higher.
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(180, 165, batters_a=[{"name": "Rohit", "runs": 92}]),
            "status": "completed",
        }, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "completed"
        assert data["winner_id"] == fx["team_a_id"], "higher-total team should win"
        awards = data.get("awards") or {}
        assert awards.get("best_batter", {}).get("name") == "Rohit"
        assert awards.get("mom", {}).get("name") == "Rohit"

    def test_bowler_with_three_wickets_becomes_mom_when_no_winning_batter(self, player_session, cricket_fixture):
        eid, fid, ta_id, tb_id = cricket_fixture
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": {
                # Team A (winners) has no batter list at all → fall back to bowler.
                "team_a": {"total": 100},
                "team_b": {"total": 80, "bowlers": [{"name": "Bumrah", "wickets": 5, "runs_conceded": 20, "overs": 4}]},
            },
            "status": "completed",
        }, timeout=10)
        assert r.status_code == 200
        awards = r.json().get("awards") or {}
        assert awards.get("best_bowler", {}).get("name") == "Bumrah"
        assert awards.get("mom", {}).get("name") == "Bumrah"


class TestLockAfterCompletion:
    def _complete(self, player_session, fid):
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(200, 150), "status": "completed",
        }, timeout=10)
        assert r.status_code == 200
        return r.json()

    def test_score_patch_rejected_after_completion(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        self._complete(player_session, fid)
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(999, 0), "status": "live",
        }, timeout=10)
        assert r.status_code == 409

    def test_media_awards_rejected_after_completion(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        self._complete(player_session, fid)
        r = player_session.patch(f"{API}/fixtures/{fid}/media", json={
            "awards": {"mom": {"name": "Manual override"}},
        }, timeout=10)
        assert r.status_code == 409

    def test_media_hero_image_still_editable_after_completion(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        self._complete(player_session, fid)
        r = player_session.patch(f"{API}/fixtures/{fid}/media", json={
            "hero_image_url": "https://example.com/hero.jpg",
        }, timeout=10)
        assert r.status_code == 200, r.text
        assert r.json()["hero_image_url"] == "https://example.com/hero.jpg"


class TestReopen:
    def test_reopen_clears_winner_and_awards(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(200, 150, batters_a=[{"name": "X", "runs": 80}]),
            "status": "completed",
        }, timeout=10)
        assert r.status_code == 200
        assert r.json().get("winner_id")
        assert r.json().get("awards")
        # Reopen
        r = player_session.post(f"{API}/fixtures/{fid}/reopen", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["status"] == "live"
        assert not data.get("winner_id")
        assert not data.get("awards")
        # Now score edits are allowed again
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(999, 0), "status": "live",
        }, timeout=10)
        assert r.status_code == 200

    def test_reopen_rejects_non_creator(self, cricket_fixture, player_session):
        _, fid, *_ = cricket_fixture
        # Mark completed
        player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(150, 120), "status": "completed",
        }, timeout=10)
        # Anonymous reopen must fail
        r = requests.post(f"{API}/fixtures/{fid}/reopen", timeout=10)
        assert r.status_code in (401, 403)

    def test_reopen_rejected_when_not_completed(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        r = player_session.post(f"{API}/fixtures/{fid}/reopen", timeout=10)
        assert r.status_code == 400


class TestMediaEndpointDoesNotBlankPage:
    """Regression for the iter31 shipped bug: FixtureAwardsEditor.save() was
    hitting PATCH /fixtures/{id} (score route) with hero_image+awards keys,
    which returned 422 and blanked the UI. The editor now hits /media."""
    def test_media_endpoint_accepts_hero_image_and_awards_together(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        r = player_session.patch(f"{API}/fixtures/{fid}/media", json={
            "hero_image_url": "/api/uploads/x",
            "awards": {"mom": {"name": "Manual pick"}},
        }, timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["hero_image_url"] == "/api/uploads/x"
        assert data["awards"]["mom"]["name"] == "Manual pick"

    def test_score_endpoint_no_longer_accepts_media_fields(self, player_session, cricket_fixture):
        _, fid, *_ = cricket_fixture
        # A well-behaved client should NEVER send this shape; the endpoint may
        # simply ignore unknown keys, but we assert it doesn't 500.
        r = player_session.patch(f"{API}/fixtures/{fid}", json={
            "score": _cricket_score(50, 40),
            "hero_image_url": "should-be-ignored",
        }, timeout=10)
        assert r.status_code == 200
        assert not r.json().get("hero_image_url")
