"""
PlaySphere backend API tests.
Covers: auth, events CRUD, teams, players, fixtures (round-robin & knockout),
standings, sponsors, stats, public root, and RBAC checks.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@playsphere.com"
ADMIN_PASSWORD = "admin123"
VIEWER_EMAIL = "viewer@playsphere.com"
VIEWER_PASSWORD = "viewer123"


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def viewer_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": VIEWER_EMAIL, "password": VIEWER_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"viewer login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def anon_session():
    return requests.Session()


# ---------- Basic / metadata ----------
class TestMeta:
    def test_root(self, anon_session):
        r = anon_session.get(f"{API}/")
        assert r.status_code == 200
        data = r.json()
        assert data.get("name") == "PlaySphere API"
        assert "Compete" in data.get("tagline", "")

    def test_stats(self, anon_session):
        r = anon_session.get(f"{API}/stats")
        assert r.status_code == 200
        d = r.json()
        for k in ["events", "teams", "players", "fixtures", "live", "sponsors"]:
            assert k in d and isinstance(d[k], int)
        # Demo seeded counts (>=)
        assert d["events"] >= 3
        assert d["teams"] >= 4
        assert d["players"] >= 16
        assert d["sponsors"] >= 4


# ---------- Auth ----------
class TestAuth:
    def test_login_admin_sets_cookie(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == ADMIN_EMAIL
        assert body["role"] == "platform_admin"
        assert "access_token" in s.cookies.get_dict()

    def test_me_with_cookie(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "platform_admin"

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_me_unauthenticated(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code == 401

    def test_logout(self):
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        r = s.post(f"{API}/auth/logout")
        assert r.status_code == 200
        # cookie cleared -> /me should now 401
        s.cookies.clear()
        r2 = s.get(f"{API}/auth/me")
        assert r2.status_code == 401

    def test_register_viewer(self):
        import uuid as _u
        email = f"test_{_u.uuid4().hex[:8]}@playsphere.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "Test User"})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == email
        assert d["role"] == "viewer"
        # duplicate
        r2 = requests.post(f"{API}/auth/register", json={"email": email, "password": "pass1234", "name": "X"})
        assert r2.status_code == 400


# ---------- Events CRUD ----------
class TestEvents:
    def test_list_events(self, anon_session):
        r = anon_session.get(f"{API}/events")
        assert r.status_code == 200
        evs = r.json()
        assert isinstance(evs, list) and len(evs) >= 3

    def test_get_event(self, anon_session):
        evs = anon_session.get(f"{API}/events").json()
        eid = evs[0]["id"]
        r = anon_session.get(f"{API}/events/{eid}")
        assert r.status_code == 200
        assert r.json()["id"] == eid

    def test_get_event_404(self, anon_session):
        r = anon_session.get(f"{API}/events/nonexistent-id")
        assert r.status_code == 404

    def test_create_event_requires_admin(self, viewer_session):
        r = viewer_session.post(f"{API}/events", json={"name": "Hack", "sport": "hackathon"})
        assert r.status_code == 403

    def test_create_event_unauth(self):
        r = requests.post(f"{API}/events", json={"name": "Hack", "sport": "hackathon"})
        assert r.status_code == 401

    def test_admin_event_full_crud(self, admin_session):
        payload = {"name": "TEST_Event", "sport": "basketball", "format": "round_robin",
                   "venue": "Court 1", "description": "Test"}
        r = admin_session.post(f"{API}/events", json=payload)
        assert r.status_code == 200, r.text
        ev = r.json()
        assert ev["name"] == "TEST_Event"
        assert ev["sport"] == "basketball"
        eid = ev["id"]

        # PATCH
        r2 = admin_session.patch(f"{API}/events/{eid}", json={"venue": "Court 2"})
        assert r2.status_code == 200
        assert r2.json()["venue"] == "Court 2"

        # GET to verify persistence
        r3 = admin_session.get(f"{API}/events/{eid}")
        assert r3.json()["venue"] == "Court 2"

        # DELETE
        r4 = admin_session.delete(f"{API}/events/{eid}")
        assert r4.status_code == 200
        r5 = admin_session.get(f"{API}/events/{eid}")
        assert r5.status_code == 404


# ---------- Teams ----------
class TestTeams:
    def test_list_teams(self, anon_session):
        r = anon_session.get(f"{API}/teams")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_teams_filter(self, anon_session):
        evs = anon_session.get(f"{API}/events").json()
        eid = next((e["id"] for e in evs if e["sport"] == "football"), evs[0]["id"])
        r = anon_session.get(f"{API}/teams", params={"event_id": eid})
        assert r.status_code == 200
        teams = r.json()
        if teams:
            assert all(t["event_id"] == eid for t in teams)

    def test_create_team_public(self):
        r = requests.post(f"{API}/teams", json={"name": "TEST_PublicTeam", "department": "QA"})
        assert r.status_code == 200
        tid = r.json()["id"]
        assert r.json()["name"] == "TEST_PublicTeam"
        # Verify persistence
        r2 = requests.get(f"{API}/teams/{tid}")
        assert r2.status_code == 200

    def test_team_update_requires_admin(self, viewer_session):
        r = requests.post(f"{API}/teams", json={"name": "TEST_NoAdminTeam"})
        tid = r.json()["id"]
        r2 = viewer_session.patch(f"{API}/teams/{tid}", json={"name": "Hacked"})
        assert r2.status_code == 403

    def test_admin_team_update_delete(self, admin_session):
        r = requests.post(f"{API}/teams", json={"name": "TEST_AdminTeam"})
        tid = r.json()["id"]
        r2 = admin_session.patch(f"{API}/teams/{tid}", json={"name": "TEST_AdminTeamUpdated"})
        assert r2.status_code == 200 and r2.json()["name"] == "TEST_AdminTeamUpdated"
        r3 = admin_session.delete(f"{API}/teams/{tid}")
        assert r3.status_code == 200


# ---------- Players ----------
class TestPlayers:
    def test_list_players(self, anon_session):
        r = anon_session.get(f"{API}/players")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_get_player(self, admin_session):
        team = requests.post(f"{API}/teams", json={"name": "TEST_PlayersTeam"}).json()
        r = requests.post(f"{API}/players", json={"name": "TEST_Player", "team_id": team["id"], "role": "GK"})
        assert r.status_code == 200
        pid = r.json()["id"]
        r2 = requests.get(f"{API}/players/{pid}")
        assert r2.status_code == 200 and r2.json()["name"] == "TEST_Player"
        # cleanup admin delete player & team
        admin_session.delete(f"{API}/players/{pid}")
        admin_session.delete(f"{API}/teams/{team['id']}")

    def test_player_patch_requires_admin(self, viewer_session):
        team = requests.post(f"{API}/teams", json={"name": "TEST_PlayerRBAC"}).json()
        p = requests.post(f"{API}/players", json={"name": "TEST_P", "team_id": team["id"]}).json()
        r = viewer_session.patch(f"{API}/players/{p['id']}", json={"name": "Hack"})
        assert r.status_code == 403


# ---------- Fixtures (round-robin + knockout) ----------
class TestFixtures:
    def test_existing_football_fixtures_sorted(self, anon_session):
        evs = anon_session.get(f"{API}/events").json()
        ev = next((e for e in evs if e["sport"] == "football"), None)
        assert ev is not None
        r = anon_session.get(f"{API}/events/{ev['id']}/fixtures")
        assert r.status_code == 200
        fs = r.json()
        # 4 teams round robin => 6 matches
        assert len(fs) == 6
        # sorted by round then match_number
        for i in range(len(fs) - 1):
            assert (fs[i]["round"], fs[i]["match_number"]) <= (fs[i+1]["round"], fs[i+1]["match_number"])

    def test_generate_round_robin(self, admin_session):
        ev = admin_session.post(f"{API}/events", json={"name": "TEST_RR", "sport": "football", "format": "round_robin"}).json()
        # add 4 teams
        tids = []
        for i in range(4):
            t = requests.post(f"{API}/teams", json={"name": f"TEST_RR_T{i}", "event_id": ev["id"]}).json()
            tids.append(t["id"])
        r = admin_session.post(f"{API}/events/{ev['id']}/generate-fixtures")
        assert r.status_code == 200, r.text
        assert r.json()["count"] == 6  # n*(n-1)/2 = 6
        fs = admin_session.get(f"{API}/events/{ev['id']}/fixtures").json()
        assert len(fs) == 6
        # cleanup
        admin_session.delete(f"{API}/events/{ev['id']}")
        for tid in tids:
            admin_session.delete(f"{API}/teams/{tid}")

    def test_generate_knockout_and_propagate(self, admin_session):
        ev = admin_session.post(f"{API}/events", json={"name": "TEST_KO", "sport": "cricket", "format": "knockout"}).json()
        tids = []
        for i in range(4):
            t = requests.post(f"{API}/teams", json={"name": f"TEST_KO_T{i}", "event_id": ev["id"]}).json()
            tids.append(t["id"])
        r = admin_session.post(f"{API}/events/{ev['id']}/generate-fixtures")
        assert r.status_code == 200
        # 4 teams => 2 R1 matches + 1 R2 match = 3
        assert r.json()["count"] == 3
        fs = admin_session.get(f"{API}/events/{ev['id']}/fixtures").json()
        r1 = [f for f in fs if f["round"] == 1]
        r2 = [f for f in fs if f["round"] == 2]
        assert len(r1) == 2 and len(r2) == 1
        # update first R1 match winner
        m1 = r1[0]
        winner = m1["team_a_id"]
        r_upd = admin_session.patch(f"{API}/fixtures/{m1['id']}",
                                    json={"score": {"team_a": {"runs": 100}, "team_b": {"runs": 80}},
                                          "status": "completed", "winner_id": winner})
        assert r_upd.status_code == 200
        # check propagation
        r2_check = admin_session.get(f"{API}/events/{ev['id']}/fixtures").json()
        final = [f for f in r2_check if f["round"] == 2][0]
        assert final["team_a_id"] == winner
        # cleanup
        admin_session.delete(f"{API}/events/{ev['id']}")
        for tid in tids:
            admin_session.delete(f"{API}/teams/{tid}")

    def test_generate_fixtures_requires_admin(self, viewer_session):
        evs = viewer_session.get(f"{API}/events").json()
        r = viewer_session.post(f"{API}/events/{evs[0]['id']}/generate-fixtures")
        assert r.status_code == 403

    def test_generate_needs_2_teams(self, admin_session):
        ev = admin_session.post(f"{API}/events", json={"name": "TEST_Empty", "sport": "football"}).json()
        r = admin_session.post(f"{API}/events/{ev['id']}/generate-fixtures")
        assert r.status_code == 400
        admin_session.delete(f"{API}/events/{ev['id']}")


# ---------- Standings ----------
class TestStandings:
    def test_standings_football(self, anon_session):
        evs = anon_session.get(f"{API}/events").json()
        ev = next((e for e in evs if e["sport"] == "football"), None)
        r = anon_session.get(f"{API}/events/{ev['id']}/standings")
        assert r.status_code == 200
        rows = r.json()
        # Sum of "won" across all teams should equal number of completed fixtures with winner
        fixtures = anon_session.get(f"{API}/events/{ev['id']}/fixtures").json()
        completed_with_winner = [f for f in fixtures if f["status"] == "completed" and f.get("winner_id")]
        total_wins = sum(row["won"] for row in rows)
        assert total_wins == len(completed_with_winner)
        # points = 3 * wins (no draws in seed)
        for row in rows:
            assert row["points"] == row["won"] * 3 + row["drawn"]


# ---------- Sponsors ----------
class TestSponsors:
    def test_list_sponsors(self, anon_session):
        r = anon_session.get(f"{API}/sponsors")
        assert r.status_code == 200
        sponsors = r.json()
        assert len(sponsors) >= 4
        tiers = {s["tier"] for s in sponsors}
        assert {"title", "gold", "silver", "bronze"}.issubset(tiers)

    def test_sponsor_admin_only(self, viewer_session):
        r = viewer_session.post(f"{API}/sponsors", json={"name": "X", "tier": "gold", "logo_url": "http://x"})
        assert r.status_code == 403

    def test_sponsor_crud(self, admin_session):
        r = admin_session.post(f"{API}/sponsors", json={"name": "TEST_Sp", "tier": "gold", "logo_url": "http://x"})
        assert r.status_code == 200
        sid = r.json()["id"]
        r2 = admin_session.patch(f"{API}/sponsors/{sid}", json={"name": "TEST_SpUpdated"})
        assert r2.status_code == 200 and r2.json()["name"] == "TEST_SpUpdated"
        r3 = admin_session.delete(f"{API}/sponsors/{sid}")
        assert r3.status_code == 200
