"""Tests for CricHeroes-style cricket scoring (toss, playing XI, ball-by-ball, innings)."""
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
def cricket_fixture(admin_session):
    """Create event + 2 teams + add 11 members + generate fixtures, return fixture id + team data."""
    uniq = str(int(time.time()))
    ev = admin_session.post(f"{API}/events", json={
        "name": f"TEST_Cricket_{uniq}",
        "sport": "cricket",
        "description": "cricket scoring test",
        "format": "round_robin",
    }).json()
    event_id = ev["id"]

    teams = []
    for tn in ("A", "B"):
        t = admin_session.post(f"{API}/events/{event_id}/teams", json={
            "name": f"Team_{tn}_{uniq}",
            "short_name": tn * 3,
            "color": "#FF3B30" if tn == "A" else "#06B6D4",
        }).json()
        teams.append(t)
        # add 11 members
        for i in range(11):
            admin_session.post(f"{API}/events/{event_id}/teams/{t['id']}/members", json={
                "quick": {
                    "name": f"P_{tn}_{i}_{uniq}",
                    "mobile": f"+9199{uniq[-4:]}{tn}{i:02d}",
                }
            })

    # Generate fixtures
    r = admin_session.post(f"{API}/events/{event_id}/generate-fixtures")
    assert r.status_code == 200, r.text
    fixtures = admin_session.get(f"{API}/events/{event_id}/fixtures").json()
    assert len(fixtures) >= 1
    fixture = fixtures[0]
    # Ensure team_a/b assigned
    assert fixture["team_a_id"] and fixture["team_b_id"]

    # Resolve playing XIs from team members
    xi_a = admin_session.get(f"{API}/events/{event_id}/teams/{teams[0]['id']}/members").json()
    xi_b = admin_session.get(f"{API}/events/{event_id}/teams/{teams[1]['id']}/members").json()
    return {
        "event_id": event_id,
        "fixture_id": fixture["id"],
        "team_a_id": fixture["team_a_id"],
        "team_b_id": fixture["team_b_id"],
        "xi_a": [{"player_id": p["id"], "name": p["name"]} for p in xi_a],
        "xi_b": [{"player_id": p["id"], "name": p["name"]} for p in xi_b],
    }


class TestCricketSetup:
    def test_setup_initializes_state(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/setup", json={"overs_limit": 5})
        assert r.status_code == 200, r.text
        score = r.json()["score"]
        assert score["sport"] == "cricket"
        assert score["match_state"] == "toss"
        assert score["overs_limit"] == 5
        assert score["innings"] == []

    def test_setup_rejects_invalid_overs(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/setup", json={"overs_limit": 0})
        assert r.status_code == 400

    def test_setup_rejects_non_cricket(self, admin_session):
        # Find existing non-cricket event/fixture to test rejection
        evs = admin_session.get(f"{API}/events").json()
        non_cricket = next((e for e in evs if e["sport"] != "cricket"), None)
        if not non_cricket:
            pytest.skip("No non-cricket events available")
        fx = admin_session.get(f"{API}/events/{non_cricket['id']}/fixtures").json()
        if not fx:
            pytest.skip("No fixtures on non-cricket event")
        r = admin_session.post(f"{API}/fixtures/{fx[0]['id']}/cricket/setup", json={"overs_limit": 5})
        assert r.status_code == 400


class TestCricketTossAndXI:
    def test_toss(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/toss", json={
            "winner_team_id": cf["team_a_id"], "decision": "bat",
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert sc["toss"]["winner_team_id"] == cf["team_a_id"]
        assert sc["toss"]["decision"] == "bat"
        assert sc["match_state"] == "playing_xi"

    def test_playing_xi(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/playing-xi", json={
            "team_a": cf["xi_a"], "team_b": cf["xi_b"],
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert len(sc["playing_xi"]["team_a"]) == 11
        assert len(sc["playing_xi"]["team_b"]) == 11
        assert sc["match_state"] == "ready"


class TestCricketPlay:
    def test_start_innings(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/start-innings", json={
            "striker_id": cf["xi_a"][0]["player_id"],
            "non_striker_id": cf["xi_a"][1]["player_id"],
            "bowler_id": cf["xi_b"][0]["player_id"],
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert sc["match_state"] == "in_play"
        assert sc["current_innings"] == 0
        inn = sc["innings"][0]
        assert inn["batting_team_id"] == cf["team_a_id"]
        assert len(inn["batsmen"]) == 2
        assert len(inn["bowlers"]) == 1

    def test_ball_legal_single(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/ball", json={"runs": 1})
        sc = r.json()["score"]
        inn = sc["innings"][0]
        assert inn["runs"] == 1
        assert inn["legal_balls"] == 1
        # Strike rotated
        assert inn["striker_id"] == cricket_fixture["xi_a"][1]["player_id"]

    def test_ball_boundary_four(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/ball", json={"runs": 4})
        inn = r.json()["score"]["innings"][0]
        assert inn["runs"] == 5
        # Striker should not have rotated (4 is even)
        bat = next(b for b in inn["batsmen"] if b["player_id"] == cricket_fixture["xi_a"][1]["player_id"])
        assert bat["runs"] == 4
        assert bat["fours"] == 1

    def test_ball_wide(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/ball", json={"runs": 0, "extra": "wd"})
        inn = r.json()["score"]["innings"][0]
        assert inn["runs"] == 6
        assert inn["extras"]["wd"] == 1
        assert inn["legal_balls"] == 2  # wide doesn't count

    def test_ball_noball_with_2_runs(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/ball", json={"runs": 2, "extra": "nb"})
        inn = r.json()["score"]["innings"][0]
        # 1 (nb) + 2 (off bat) = 3 added
        assert inn["runs"] == 9
        assert inn["extras"]["nb"] == 1

    def test_ball_bye(self, admin_session, cricket_fixture):
        r = admin_session.post(f"{API}/fixtures/{cricket_fixture['fixture_id']}/cricket/ball", json={"runs": 2, "extra": "b"})
        inn = r.json()["score"]["innings"][0]
        assert inn["extras"]["b"] == 2

    def test_wicket_blocks_play_until_new_batsman(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        # Take a wicket — bowled
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/ball", json={
            "runs": 0,
            "wicket": {"type": "bowled"},
        })
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert sc["match_state"] == "wicket"
        inn = sc["innings"][0]
        assert inn["wickets"] == 1
        # Cannot send another ball
        r2 = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/ball", json={"runs": 1})
        assert r2.status_code == 400
        # Add a new batsman
        new_id = cf["xi_a"][2]["player_id"]
        r3 = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/new-batsman", json={"player_id": new_id})
        assert r3.status_code == 200, r3.text
        sc3 = r3.json()["score"]
        assert sc3["match_state"] == "in_play"
        assert new_id in (sc3["innings"][0]["striker_id"], sc3["innings"][0]["non_striker_id"])

    def test_end_of_over_forces_new_bowler(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        # Bowl until 6 legal balls in over. We've already bowled some legal balls; check count.
        sc = admin_session.get(f"{API}/fixtures/{cf['fixture_id']}").json()["score"]
        bowled = sc["innings"][0]["legal_balls"]
        needed = 6 - (bowled % 6) if bowled % 6 != 0 else 0
        for _ in range(needed):
            admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/ball", json={"runs": 0})
        sc = admin_session.get(f"{API}/fixtures/{cf['fixture_id']}").json()["score"]
        if sc["innings"][0]["legal_balls"] % 6 == 0 and not sc["innings"][0]["completed"]:
            assert sc["innings"][0]["current_bowler_id"] is None
            # Cannot record a ball without a bowler
            r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/ball", json={"runs": 0})
            assert r.status_code == 400
            # Add new bowler
            new_bowler = cf["xi_b"][1]["player_id"]
            r2 = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/new-bowler", json={"player_id": new_bowler})
            assert r2.status_code == 200, r2.text
            assert r2.json()["score"]["innings"][0]["current_bowler_id"] == new_bowler


class TestCricketUndo:
    def test_undo_reverts_last_ball(self, admin_session, cricket_fixture):
        cf = cricket_fixture
        before = admin_session.get(f"{API}/fixtures/{cf['fixture_id']}").json()["score"]
        before_runs = before["innings"][0]["runs"]
        before_log_len = len(before["innings"][0]["balls_log"])
        # Skip if we're in wicket state — need to ensure in_play
        if before["match_state"] == "wicket":
            pytest.skip("Cannot undo while waiting for new batsman")
        admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/ball", json={"runs": 6})
        after = admin_session.get(f"{API}/fixtures/{cf['fixture_id']}").json()["score"]
        assert after["innings"][0]["runs"] == before_runs + 6
        r = admin_session.post(f"{API}/fixtures/{cf['fixture_id']}/cricket/undo")
        assert r.status_code == 200, r.text
        sc = r.json()["score"]
        assert sc["innings"][0]["runs"] == before_runs
        assert len(sc["innings"][0]["balls_log"]) == before_log_len
