"""Iteration 38 — Phase 1: profile stats auto-update across sports.

Coverage:
* Completed cricket local match with per-player batters increments the player's
  cricket auto stats (matches / runs / balls / highest_score).
* Completed badminton sets match increments matches + won + sets_won on the
  auto side (was previously empty for non-cricket sports).
* Player who was on the winning roster gets `won++` and `mom++` credited.
* Non-owner (anonymous) can view the stats endpoint (public profile view).
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


def _complete_cricket_match(session, player_profile_id):
    ev = session.post(f"{API}/events", json={"name": f"iter38_c_{secrets.token_hex(4)}", "sport": "cricket", "format": "knockout"}, timeout=10).json()
    eid = ev["id"]
    ta = session.post(f"{API}/events/{eid}/teams", json={"name": "A", "color": "#84CC16"}, timeout=10).json()
    tb = session.post(f"{API}/events/{eid}/teams", json={"name": "B", "color": "#EC4899"}, timeout=10).json()
    session.post(f"{API}/events/{eid}/teams/{ta['id']}/members", json={"player_id": player_profile_id}, timeout=10)
    session.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fx = session.get(f"{API}/events/{eid}/fixtures", timeout=10).json()[0]
    fid = fx["id"]
    my_key = "team_a" if fx["team_a_id"] == ta["id"] else "team_b"
    opp_key = "team_b" if my_key == "team_a" else "team_a"
    score = {
        my_key: {"total": 150, "batters": [{"player_id": player_profile_id, "name": "Test", "runs": 92, "balls": 55, "fours": 8, "sixes": 3}]},
        opp_key: {"total": 120, "bowlers": []},
    }
    session.patch(f"{API}/fixtures/{fid}", json={"score": score, "status": "completed"}, timeout=10)
    return eid


def _complete_badminton_match(session, player_profile_id):
    ev = session.post(f"{API}/events", json={"name": f"iter38_b_{secrets.token_hex(4)}", "sport": "badminton", "format": "knockout", "player_format": "singles"}, timeout=10).json()
    eid = ev["id"]
    ta = session.post(f"{API}/events/{eid}/teams", json={"name": "A", "color": "#84CC16"}, timeout=10).json()
    tb = session.post(f"{API}/events/{eid}/teams", json={"name": "B", "color": "#EC4899"}, timeout=10).json()
    session.post(f"{API}/events/{eid}/teams/{ta['id']}/members", json={"player_id": player_profile_id}, timeout=10)
    session.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fx = session.get(f"{API}/events/{eid}/fixtures", timeout=10).json()[0]
    fid = fx["id"]
    my_key = "team_a" if fx["team_a_id"] == ta["id"] else "team_b"
    opp_key = "team_b" if my_key == "team_a" else "team_a"
    score = {my_key: {"sets": [21, 15, 21]}, opp_key: {"sets": [18, 21, 15]}}
    session.patch(f"{API}/fixtures/{fid}", json={"score": score, "status": "completed"}, timeout=10)
    return eid


class TestCricketAutoStatsFromLocalMatch:
    def test_cricket_stats_populate_from_simple_score_shape(self, player_session, player_profile_id):
        eid = _complete_cricket_match(player_session, player_profile_id)
        try:
            r = player_session.get(f"{API}/players/profiles/{player_profile_id}/stats", timeout=10)
            assert r.status_code == 200, r.text
            cricket = r.json().get("cricket", {}).get("auto", {})
            assert cricket.get("runs", 0) >= 92
            assert cricket.get("balls_faced", 0) >= 55
            assert cricket.get("fours", 0) >= 8
            assert cricket.get("highest_score", 0) >= 92
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)


class TestBadmintonAutoStats:
    def test_badminton_auto_matches_won_sets(self, player_session, player_profile_id):
        eid = _complete_badminton_match(player_session, player_profile_id)
        try:
            r = player_session.get(f"{API}/players/profiles/{player_profile_id}/stats", timeout=10)
            assert r.status_code == 200
            bag = r.json().get("badminton", {}).get("auto", {})
            assert bag.get("matches", 0) >= 1, f"expected matches >= 1, got {bag}"
            assert bag.get("won", 0) >= 1
            assert bag.get("sets_won", 0) >= 2  # won sets 1 and 3
            # Fallback awards path from iter37: MoM auto-credited for individual sports
            assert bag.get("mom", 0) >= 1
        finally:
            player_session.delete(f"{API}/events/{eid}", timeout=10)


class TestAnonymousStatsAccess:
    def test_stats_endpoint_open_to_anonymous(self, player_profile_id):
        # Public profile view should reach the stats endpoint without a session.
        r = requests.get(f"{API}/players/profiles/{player_profile_id}/stats", timeout=10)
        assert r.status_code == 200, r.text
        # Cricket dict is always present in response shape.
        assert "cricket" in r.json()
