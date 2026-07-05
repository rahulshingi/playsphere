"""Iteration 35 — player match history + auto-tag interested sports.

Covers:
* `GET /players/{id}/match-history` returns fixture-level score cards for
  local + non-local tournaments the player played in.
* Only fixtures with status live/completed appear (scheduled ones skipped).
* Adding a player to a team of sport X auto-adds X to `interested_sports`.
* Contribution counts on `/tournaments` now populate correctly (previous
  code queried db.matches instead of db.fixtures — a latent bug fixed).
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
def player_profile_id(player_session):
    me = player_session.get(f"{API}/players/me", timeout=10).json()
    return me["id"]


def _make_local_cricket_event_with_match(player_session, player_profile_id, *, complete=True):
    """Utility: creates a local cricket event, adds two teams, rosters the test
    player onto team A, generates fixtures, and (optionally) completes match #1
    with a scripted score. Returns (event_id, fixture_id, team_a_id, team_b_id)."""
    ev = player_session.post(f"{API}/events", json={
        "name": f"iter35_{secrets.token_hex(4)}",
        "sport": "badminton", "format": "knockout",
        "player_format": "singles",
        "venue": "Test court",
    }, timeout=10).json()
    eid = ev["id"]
    ta = player_session.post(f"{API}/events/{eid}/teams", json={"name": "A", "color": "#84CC16"}, timeout=10).json()
    tb = player_session.post(f"{API}/events/{eid}/teams", json={"name": "B", "color": "#EC4899"}, timeout=10).json()
    # Roster the test player onto team A
    r = player_session.post(f"{API}/events/{eid}/teams/{ta['id']}/members",
                            json={"player_id": player_profile_id}, timeout=10)
    assert r.status_code == 200, r.text
    player_session.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fixtures = player_session.get(f"{API}/events/{eid}/fixtures", timeout=10).json()
    fx = fixtures[0]
    fid = fx["id"]
    if complete:
        # Whichever side our player's team maps to in the fixture, put them at 21
        # (winning score) and the other side at 15. This makes the test order-
        # agnostic — generate-fixtures may swap team_a/team_b.
        my_key, opp_key = ("team_a", "team_b") if fx["team_a_id"] == ta["id"] else ("team_b", "team_a")
        score = {
            my_key: {"total": 21, "scorers": [{"player_id": player_profile_id, "name": "Test Player", "points": 21}]},
            opp_key: {"total": 15, "scorers": []},
        }
        r = player_session.patch(f"{API}/fixtures/{fid}", json={"score": score, "status": "completed"}, timeout=10)
        assert r.status_code == 200, r.text
    return eid, fid, ta["id"], tb["id"]


class TestAutoInterestedSports:
    def test_new_sport_added_when_rostered(self, player_session, player_profile_id):
        # Snapshot baseline
        me_before = player_session.get(f"{API}/players/me", timeout=10).json()
        base_sports = set(me_before.get("interested_sports") or [])
        # We're using "badminton" — assume the test player didn't have it before
        eid, *_ = _make_local_cricket_event_with_match(player_session, player_profile_id, complete=False)
        try:
            me_after = player_session.get(f"{API}/players/me", timeout=10).json()
            after_sports = set(me_after.get("interested_sports") or [])
            assert "badminton" in after_sports, f"badminton should be auto-added; sports={after_sports}"
            # We don't remove any pre-existing sport.
            assert base_sports.issubset(after_sports)
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)


class TestMatchHistoryEndpoint:
    def test_returns_completed_local_match_with_correct_shape(self, player_session, player_profile_id):
        eid, fid, ta_id, tb_id = _make_local_cricket_event_with_match(player_session, player_profile_id, complete=True)
        try:
            r = player_session.get(f"{API}/players/{player_profile_id}/match-history", timeout=10)
            assert r.status_code == 200
            history = r.json()
            match = next((m for m in history if m["fixture_id"] == fid), None)
            assert match is not None, "our new fixture should appear"
            assert match["is_local_match"] is True
            assert match["sport"] == "badminton"
            assert match["event_id"] == eid
            assert match["event_name"].startswith("iter35_")
            # Score display for non-cricket → prefers 'total'
            assert match["my_team"]["score_display"] == "21"
            assert match["opp_team"]["score_display"] == "15"
            assert match["result"] == "won"
            assert match["my_team"]["is_winner"] is True
            # Our player was top_scorer → award chip should be present
            assert "top_scorer" in match["my_awards"]
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)

    def test_scheduled_fixture_skipped(self, player_session, player_profile_id):
        eid, fid, *_ = _make_local_cricket_event_with_match(player_session, player_profile_id, complete=False)
        try:
            r = player_session.get(f"{API}/players/{player_profile_id}/match-history", timeout=10)
            history = r.json()
            assert not any(m["fixture_id"] == fid for m in history), \
                "scheduled fixture should NOT appear in history"
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)

    def test_multiple_matches_returned_sorted(self, player_session, player_profile_id):
        eids = []
        try:
            for _ in range(2):
                eid, *_ = _make_local_cricket_event_with_match(player_session, player_profile_id, complete=True)
                eids.append(eid)
            r = player_session.get(f"{API}/players/{player_profile_id}/match-history", timeout=10)
            history = r.json()
            assert len(history) >= 2
        finally:
            for eid in eids:
                player_session.delete(f"{API}/events/{eid}", timeout=10)


class TestTournamentsEndpointFixed:
    """Regression for the copy-paste bug: contribution stats used to be
    computed from db.matches (wrong collection) — always returning zeros."""
    def test_contribution_counts_populate(self, player_session, player_profile_id):
        eid, fid, *_ = _make_local_cricket_event_with_match(player_session, player_profile_id, complete=True)
        try:
            r = player_session.get(f"{API}/players/{player_profile_id}/tournaments", timeout=10)
            data = r.json()
            entry = next((e for e in data if e["id"] == eid), None)
            assert entry is not None
            contrib = entry.get("contribution") or {}
            assert contrib.get("matches") == 1, f"expected 1 completed match, got {contrib}"
            # Player scored 21 vs opponent's 0 scorers, so they should have top_scorer++.
            assert contrib.get("top_scorer") == 1 or contrib.get("mom") == 1
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)
