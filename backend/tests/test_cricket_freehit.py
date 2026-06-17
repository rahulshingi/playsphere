"""Tests for cricket free-hit rule (no-ball ⇒ next delivery is free-hit, only runout dismisses)."""
import os
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kreedanation.com", "password": "admin123"}


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def freehit_fixture(admin_session):
    uniq = "FH" + str(int(time.time()))
    ev = admin_session.post(f"{API}/events", json={
        "name": f"TEST_FreeHit_{uniq}", "sport": "cricket", "format": "round_robin",
    }).json()
    event_id = ev["id"]
    teams = []
    for tn in ("X", "Y"):
        t = admin_session.post(f"{API}/events/{event_id}/teams", json={
            "name": f"FH_{tn}_{uniq}", "short_name": tn * 3,
        }).json()
        teams.append(t)
        for i in range(11):
            admin_session.post(f"{API}/events/{event_id}/teams/{t['id']}/members", json={
                "quick": {"name": f"FH_{tn}_{i}_{uniq}", "mobile": f"+9197{uniq[-4:]}{tn}{i:02d}"}
            })
    admin_session.post(f"{API}/events/{event_id}/generate-fixtures")
    fixtures = admin_session.get(f"{API}/events/{event_id}/fixtures").json()
    fixture = fixtures[0]
    xi_a = admin_session.get(f"{API}/events/{event_id}/teams/{teams[0]['id']}/members").json()
    xi_b = admin_session.get(f"{API}/events/{event_id}/teams/{teams[1]['id']}/members").json()

    admin_session.post(f"{API}/fixtures/{fixture['id']}/cricket/setup", json={"overs_limit": 5})
    admin_session.post(f"{API}/fixtures/{fixture['id']}/cricket/toss", json={
        "winner_team_id": fixture["team_a_id"], "decision": "bat",
    })
    admin_session.post(f"{API}/fixtures/{fixture['id']}/cricket/playing-xi", json={
        "team_a": [{"player_id": p["id"], "name": p["name"]} for p in xi_a],
        "team_b": [{"player_id": p["id"], "name": p["name"]} for p in xi_b],
    })
    admin_session.post(f"{API}/fixtures/{fixture['id']}/cricket/start-innings", json={
        "striker_id": xi_a[0]["id"], "non_striker_id": xi_a[1]["id"], "bowler_id": xi_b[0]["id"],
    })
    return {
        "fixture_id": fixture["id"],
        "xi_a": [{"player_id": p["id"], "name": p["name"]} for p in xi_a],
        "xi_b": [{"player_id": p["id"], "name": p["name"]} for p in xi_b],
    }


class TestFreeHit:
    def test_noball_sets_free_hit_pending(self, admin_session, freehit_fixture):
        fid = freehit_fixture["fixture_id"]
        r = admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={"runs": 0, "extra": "nb"})
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert sc["innings"][0]["free_hit_pending"] is True

    def test_bowled_on_freehit_is_ignored(self, admin_session, freehit_fixture):
        fid = freehit_fixture["fixture_id"]
        # Bowled wicket attempted on free-hit
        r = admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={
            "runs": 0, "wicket": {"type": "bowled"},
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        inn = sc["innings"][0]
        assert inn["wickets"] == 0, "Bowled on free-hit must be ignored"
        # ball was a legal delivery so it should consume the free-hit
        assert inn["free_hit_pending"] is False
        # last ball entry tagged as ignored
        last = inn["balls_log"][-1]
        assert last.get("free_hit") is True
        assert last.get("wicket", {}).get("ignored_free_hit") is True

    def test_runout_on_freehit_is_allowed(self, admin_session, freehit_fixture):
        fid = freehit_fixture["fixture_id"]
        # Set up another free-hit
        admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={"runs": 0, "extra": "nb"})
        # Runout on free-hit should dismiss
        r = admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={
            "runs": 0, "wicket": {"type": "runout"},
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        inn = sc["innings"][0]
        assert inn["wickets"] == 1, "Runout on free-hit must dismiss"
        assert sc["match_state"] == "wicket"

    def test_free_hit_persists_through_wide(self, admin_session, freehit_fixture):
        fid = freehit_fixture["fixture_id"]
        # Bring a new batsman after the previous wicket
        cf = freehit_fixture
        sc = admin_session.get(f"{API}/fixtures/{fid}").json()["score"]
        if sc["match_state"] == "wicket":
            new_p = next((p for p in cf["xi_a"] if p["player_id"] not in (sc["innings"][0]["striker_id"], sc["innings"][0]["non_striker_id"]) and not any(b["player_id"] == p["player_id"] and b["out"] for b in sc["innings"][0]["batsmen"])), None)
            assert new_p, "Expected a free batsman in XI"
            admin_session.post(f"{API}/fixtures/{fid}/cricket/new-batsman", json={"player_id": new_p["player_id"]})
        # No ball
        admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={"runs": 0, "extra": "nb"})
        # Then a wide — free-hit should still be pending (wide isn't a legal delivery)
        r = admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={"runs": 0, "extra": "wd"})
        sc = r.json()["score"]
        assert sc["innings"][0]["free_hit_pending"] is True, "Free-hit must persist through wide"

    def test_legal_ball_clears_free_hit(self, admin_session, freehit_fixture):
        fid = freehit_fixture["fixture_id"]
        # Now bowl a legal delivery; free-hit should clear
        r = admin_session.post(f"{API}/fixtures/{fid}/cricket/ball", json={"runs": 1})
        sc = r.json()["score"]
        assert sc["innings"][0]["free_hit_pending"] is False
