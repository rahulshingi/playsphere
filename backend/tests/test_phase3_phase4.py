"""Phase 3 (team roles + fixture metadata) & Phase 4 (Swiss + double elimination) tests."""
import os
import time
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


def _make_event(s, fmt, sport="football", n_teams=4):
    """Create an event of the given format and register n teams. Returns (event_id, [team_ids])."""
    ev = s.post(f"{API}/events", json={
        "name": f"TEST_phase34_{fmt}_{uuid.uuid4().hex[:6]}",
        "sport": sport,
        "description": "phase 3/4 e2e",
        "format": fmt,
        "event_type": "playsphere_organized",
    }, timeout=10)
    assert ev.status_code == 200, ev.text
    eid = ev.json()["id"]
    team_ids = []
    for i in range(n_teams):
        r = s.post(f"{API}/events/{eid}/teams", json={
            "name": f"Team {chr(65+i)}", "color": "#84CC16",
            "jersey_color": "#FF0000" if i == 0 else "#0000FF",
            "coach_name": f"Coach {i}" if i == 0 else "",
            "manager_name": f"Manager {i}" if i == 0 else "",
        }, timeout=10)
        assert r.status_code == 200, r.text
        team_ids.append(r.json()["id"])
    return eid, team_ids


# -------- Phase 3: Team roles --------
def test_team_create_stores_new_role_fields(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=1)
    t = s.get(f"{API}/teams/{team_ids[0]}").json()
    assert t.get("jersey_color") == "#FF0000"
    assert t.get("coach_name") == "Coach 0"
    assert t.get("manager_name") == "Manager 0"


def test_patch_team_meta_updates_roles(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=1)
    tid = team_ids[0]
    r = s.patch(f"{API}/events/{eid}/teams/{tid}", json={
        "coach_name": "New Coach",
        "manager_name": "New Manager",
        "jersey_color": "#00FF00",
    }, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["coach_name"] == "New Coach"
    assert body["manager_name"] == "New Manager"
    assert body["jersey_color"] == "#00FF00"


def test_patch_team_vc_auto_resolves_name(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=1)
    tid = team_ids[0]
    # Quick-add a player via the team-members endpoint to get a valid player_id
    quick = {"name": f"VC Player {uuid.uuid4().hex[:6]}", "mobile": f"+91{uuid.uuid4().int % 10**10:010d}"}
    m = s.post(f"{API}/events/{eid}/teams/{tid}/members", json={"quick": quick}, timeout=10)
    assert m.status_code == 200, m.text
    pid = m.json()["player_id"]
    r = s.patch(f"{API}/events/{eid}/teams/{tid}", json={"vice_captain_player_id": pid}, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["vice_captain_player_id"] == pid
    assert body["vice_captain"] == quick["name"]
    # Clearing works
    r = s.patch(f"{API}/events/{eid}/teams/{tid}", json={"vice_captain_player_id": None}, timeout=10)
    assert r.status_code == 200
    assert r.json()["vice_captain_player_id"] in (None, "")
    assert r.json()["vice_captain"] in ("", None)


def test_patch_team_rejects_unknown_vc(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=1)
    r = s.patch(f"{API}/events/{eid}/teams/{team_ids[0]}", json={"vice_captain_player_id": "bogus-id"}, timeout=10)
    assert r.status_code == 404


def test_patch_team_rejects_empty(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=1)
    r = s.patch(f"{API}/events/{eid}/teams/{team_ids[0]}", json={}, timeout=10)
    assert r.status_code == 400


# -------- Phase 3: Fixture meta --------
def test_patch_fixture_meta_sets_court_and_toss(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=2, sport="cricket")
    g = s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    assert g.status_code == 200, g.text
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    assert len(fx_list) >= 1
    fx_id = fx_list[0]["id"]
    payload = {
        "venue": "Chinnaswamy Stadium",
        "court_number": "Pitch 1",
        "officials": [{"role": "umpire", "name": "Kumar Dharmasena"}],
        "toss": {"winner_team_id": fx_list[0]["team_a_id"], "decision": "bat"},
    }
    r = s.patch(f"{API}/fixtures/{fx_id}/meta", json=payload, timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["venue"] == "Chinnaswamy Stadium"
    assert body["court_number"] == "Pitch 1"
    assert body["officials"] == [{"role": "umpire", "name": "Kumar Dharmasena"}]
    assert body["toss"]["winner_team_id"] == fx_list[0]["team_a_id"]
    assert body["toss"]["decision"] == "bat"


def test_patch_fixture_meta_rejects_bad_toss_winner(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=2, sport="cricket")
    s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    r = s.patch(f"{API}/fixtures/{fx_list[0]['id']}/meta", json={"toss": {"winner_team_id": "not-a-team"}}, timeout=10)
    assert r.status_code == 400


def test_patch_fixture_meta_rejects_bad_decision(s):
    eid, team_ids = _make_event(s, "round_robin", n_teams=2, sport="cricket")
    s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    r = s.patch(f"{API}/fixtures/{fx_list[0]['id']}/meta",
                json={"toss": {"winner_team_id": fx_list[0]["team_a_id"], "decision": "moon-walk"}}, timeout=10)
    assert r.status_code == 400


# -------- Phase 4: Swiss generation --------
def test_generate_swiss_creates_round_1_and_placeholders(s):
    eid, team_ids = _make_event(s, "swiss", n_teams=8)
    g = s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["format"] == "swiss"
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    round1 = [f for f in fx_list if f["round"] == 1]
    assert len(round1) == 4  # 8 teams -> 4 matches in round 1
    # All round-1 pairings are concrete
    assert all(f["team_a_id"] and f["team_b_id"] for f in round1)
    # Later rounds have empty placeholders
    round2 = [f for f in fx_list if f["round"] == 2]
    assert len(round2) >= 1
    assert all(f["team_a_id"] is None and f["team_b_id"] is None for f in round2)


def test_swiss_pair_next_round_requires_completion(s):
    eid, team_ids = _make_event(s, "swiss", n_teams=4)
    s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    # Round 1 is incomplete → pairing next should 400
    r = s.post(f"{API}/events/{eid}/swiss/pair-next-round", timeout=10)
    assert r.status_code == 400


def test_swiss_pair_next_round_after_round1_completes(s):
    eid, team_ids = _make_event(s, "swiss", n_teams=4)
    s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    round1 = [f for f in fx_list if f["round"] == 1]
    # Mark each round-1 match completed with team_a as winner
    for f in round1:
        r = s.patch(f"{API}/fixtures/{f['id']}",
                    json={"score": {"team_a": {"total": 3}, "team_b": {"total": 1}},
                          "status": "completed", "winner_id": f["team_a_id"]}, timeout=10)
        assert r.status_code == 200, r.text
    r = s.post(f"{API}/events/{eid}/swiss/pair-next-round", timeout=10)
    assert r.status_code == 200, r.text
    assert r.json()["paired"] >= 1
    assert r.json()["round"] == 2
    # Round 2 fixtures now have concrete pairings
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    round2 = [f for f in fx_list if f["round"] == 2]
    concrete = [f for f in round2 if f["team_a_id"] and f["team_b_id"]]
    assert len(concrete) >= 1


# -------- Phase 4: Double elimination --------
def test_generate_double_elimination_creates_bracket(s):
    eid, team_ids = _make_event(s, "double_elimination", n_teams=4)
    g = s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    assert g.status_code == 200, g.text
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    positions = [f.get("bracket_position") or "" for f in fx_list]
    wb = [p for p in positions if p.startswith("WB-")]
    lb = [p for p in positions if p.startswith("LB-")]
    gf = [p for p in positions if p.startswith("GF-")]
    # 4 teams: WB has 2 R1 matches + 1 R2 = 3 WB matches
    assert len(wb) >= 3
    # LB has at least 1 losers-bracket match
    assert len(lb) >= 1
    # Exactly one grand final
    assert len(gf) == 1


def test_generate_double_elimination_8_teams(s):
    eid, team_ids = _make_event(s, "double_elimination", n_teams=8)
    g = s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    assert g.status_code == 200
    fx_list = s.get(f"{API}/events/{eid}/fixtures").json()
    positions = [f.get("bracket_position") or "" for f in fx_list]
    # 8 teams: WB has 4+2+1=7 WB matches
    wb = [p for p in positions if p.startswith("WB-")]
    assert len(wb) == 7
    # Grand final always exactly one
    gf = [p for p in positions if p.startswith("GF-")]
    assert len(gf) == 1


def test_swiss_pair_next_no_op_when_all_paired(s):
    eid, team_ids = _make_event(s, "swiss", n_teams=2)
    s.post(f"{API}/events/{eid}/generate-fixtures", timeout=10)
    # 2 teams, 1 round in Swiss (ceil(log2(2))=1) -> everything paired already
    r = s.post(f"{API}/events/{eid}/swiss/pair-next-round", timeout=10)
    assert r.status_code == 200
    assert r.json()["paired"] == 0
