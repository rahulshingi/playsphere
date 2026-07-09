"""Phase 5 tests — sport-specific default_score + winner auto-fill for new sports (snooker, pickleball, chess)."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kreedanation.com", "password": "admin123"}


@pytest.fixture(scope="module")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    r = sess.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return sess


def _create_event_with_fixture(s, sport, player_format="singles"):
    payload = {
        "name": f"TEST_phase5_{sport}_{uuid.uuid4().hex[:6]}",
        "sport": sport,
        "description": "phase 5 e2e",
        "format": "knockout",
        "event_type": "playsphere_organized",
    }
    # Racket sports with both singles/doubles support require a player_format.
    if sport in ("badminton", "pickleball", "tabletennis", "tennis", "lawntennis", "squash"):
        payload["player_format"] = player_format
    ev = s.post(f"{API}/events", json=payload, timeout=10)
    assert ev.status_code == 200, ev.text
    eid = ev.json()["id"]
    for i in range(2):
        r = s.post(f"{API}/events/{eid}/teams", json={"name": f"P{i+1}", "color": "#84CC16"}, timeout=10)
        assert r.status_code == 200, r.text
    g = s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    assert g.status_code == 200, g.text
    fx = s.get(f"{API}/events/{eid}/fixtures").json()
    assert len(fx) >= 1
    return eid, fx[0]


def test_default_score_pickleball(s):
    _, fx = _create_event_with_fixture(s, "pickleball")
    r = s.post(f"{API}/fixtures/{fx['id']}/init-score", timeout=10)
    assert r.status_code == 200, r.text
    score = r.json()["score"]
    assert score["team_a"]["sets"] == [0, 0, 0]
    assert score["team_b"]["sets"] == [0, 0, 0]


def test_default_score_tabletennis_best_of_5(s):
    _, fx = _create_event_with_fixture(s, "tabletennis")
    r = s.post(f"{API}/fixtures/{fx['id']}/init-score", timeout=10)
    score = r.json()["score"]
    assert len(score["team_a"]["sets"]) == 5
    assert len(score["team_b"]["sets"]) == 5


def test_default_score_snooker_uses_frames_won(s):
    _, fx = _create_event_with_fixture(s, "snooker")
    r = s.post(f"{API}/fixtures/{fx['id']}/init-score", timeout=10)
    score = r.json()["score"]
    assert score["team_a"] == {"frames_won": 0}
    assert score["team_b"] == {"frames_won": 0}


def test_default_score_chess_has_result_field(s):
    _, fx = _create_event_with_fixture(s, "chess")
    r = s.post(f"{API}/fixtures/{fx['id']}/init-score", timeout=10)
    score = r.json()["score"]
    assert "result" in score
    assert score["result"] is None


def test_snooker_frames_completion_picks_winner(s):
    eid, fx = _create_event_with_fixture(s, "snooker")
    # Team A wins race to 5 frames
    payload = {
        "score": {"team_a": {"frames_won": 5}, "team_b": {"frames_won": 3}},
        "status": "completed",
    }
    r = s.patch(f"{API}/fixtures/{fx['id']}", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    # Backend auto-fills winner_id based on higher total (frames_won compared)
    assert body["winner_id"] == fx["team_a_id"]


def test_pickleball_sets_winner_computed(s):
    eid, fx = _create_event_with_fixture(s, "pickleball")
    # Team B wins 2 sets to 1 (best-of-3)
    payload = {
        "score": {"team_a": {"sets": [11, 8, 9]}, "team_b": {"sets": [9, 11, 11]}},
        "status": "completed",
    }
    r = s.patch(f"{API}/fixtures/{fx['id']}", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["winner_id"] == fx["team_b_id"]


def test_chess_result_can_be_stored(s):
    eid, fx = _create_event_with_fixture(s, "chess")
    payload = {
        "score": {"team_a": {"points": 1}, "team_b": {"points": 0}, "result": "white"},
        "status": "completed",
        "winner_id": fx["team_a_id"],
    }
    r = s.patch(f"{API}/fixtures/{fx['id']}", json=payload, timeout=10)
    assert r.status_code == 200
    got = s.get(f"{API}/fixtures/{fx['id']}").json()
    assert got["score"]["result"] == "white"
    assert got["winner_id"] == fx["team_a_id"]
