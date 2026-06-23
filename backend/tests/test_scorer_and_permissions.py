"""End-to-end tests for the scorer role + fixture-permission scoping batch.

Covers:
- Cross-company isolation for POST /events/{id}/generate-fixtures
- Fixture-lock once a fixture is live/completed
- Score-permission scoping (PATCH /fixtures/{fid}, /init-score, /cricket/setup)
- Scorer invitation lifecycle (POST/GET/DELETE /events/{id}/scorers)
- Scorer dashboard (GET /scorers/me/events)
- Scorer scoring restrictions (scope=all vs specific fixture_ids)
- Scorer cannot manage other scorers or regenerate fixtures
- Regression on existing flows (platform admin login)

Test data is seeded directly into MongoDB to bypass the email-OTP signup gate.
"""
import os
import sys
import uuid
import bcrypt
import pytest
import requests
from datetime import datetime, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

_mongo = MongoClient(MONGO_URL)
_db = _mongo[DB_NAME]


def _hash(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


# ---------- Seed helpers ----------
def _seed_company(name: str) -> dict:
    cid = str(uuid.uuid4())
    doc = {
        "id": cid,
        "name": name,
        "slug": f"test-{cid[:8]}",
        "contact_email": f"{cid[:8]}@example.com",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _db.companies.insert_one(doc)
    return doc


def _seed_user(email: str, password: str, role: str, company_id=None) -> dict:
    uid = str(uuid.uuid4())
    doc = {
        "id": uid,
        "email": email.lower(),
        "name": email.split("@")[0],
        "role": role,
        "company_id": company_id,
        "password_hash": _hash(password),
        "email_verified": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _db.users.delete_many({"email": email.lower()})
    _db.users.insert_one(doc)
    return doc


def _seed_event(name: str, company_id: str, fmt: str = "round_robin", sport: str = "cricket") -> dict:
    eid = str(uuid.uuid4())
    doc = {
        "id": eid,
        "name": name,
        "sport": sport,
        "format": fmt,
        "event_type": "single_company",
        "status": "upcoming",
        "company_id": company_id,
        "companies": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _db.events.insert_one(doc)
    return doc


def _seed_team(event_id: str, name: str) -> dict:
    tid = str(uuid.uuid4())
    doc = {
        "id": tid,
        "name": name,
        "short_name": name[:3].upper(),
        "event_id": event_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _db.teams.insert_one(doc)
    return doc


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return s


# ---------- Fixtures ----------
@pytest.fixture(scope="module")
def env_setup():
    """Create two companies A & B, an HR for each, an event under A with 4 teams."""
    co_a = _seed_company("TEST_CO_A")
    co_b = _seed_company("TEST_CO_B")

    hr_a_email = f"test_hr_a_{uuid.uuid4().hex[:6]}@coa.com"
    hr_b_email = f"test_hr_b_{uuid.uuid4().hex[:6]}@cob.com"
    _seed_user(hr_a_email, "pass123", "company_admin", co_a["id"])
    _seed_user(hr_b_email, "pass123", "company_admin", co_b["id"])

    event = _seed_event("TEST_EVT_RR", co_a["id"], fmt="round_robin", sport="cricket")
    teams = [_seed_team(event["id"], f"T{i}") for i in range(4)]

    yield {
        "co_a": co_a,
        "co_b": co_b,
        "hr_a_email": hr_a_email,
        "hr_b_email": hr_b_email,
        "event": event,
        "teams": teams,
    }

    # cleanup
    _db.events.delete_one({"id": event["id"]})
    _db.teams.delete_many({"event_id": event["id"]})
    _db.fixtures.delete_many({"event_id": event["id"]})
    _db.event_scorers.delete_many({"event_id": event["id"]})
    _db.companies.delete_many({"id": {"$in": [co_a["id"], co_b["id"]]}})
    _db.users.delete_many({"email": {"$in": [hr_a_email, hr_b_email]}})


@pytest.fixture(scope="module")
def admin_session():
    s = _login("admin@kreedanation.com", "admin123")
    return s


@pytest.fixture(scope="module")
def hr_a_session(env_setup):
    return _login(env_setup["hr_a_email"], "pass123")


@pytest.fixture(scope="module")
def hr_b_session(env_setup):
    return _login(env_setup["hr_b_email"], "pass123")


# ============================================================
# Regression: admin login + events list still working
# ============================================================
class TestRegression:
    def test_admin_login_works(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == "admin@kreedanation.com"
        assert data["role"] == "platform_admin"

    def test_events_list(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/events")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ============================================================
# Fixture generation permission boundaries
# ============================================================
class TestGenerateFixturesPermissions:
    def test_admin_can_generate(self, admin_session, env_setup):
        r = admin_session.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        assert r.status_code == 200, r.text
        assert r.json()["count"] >= 1

    def test_other_company_hr_cannot_generate(self, hr_b_session, env_setup):
        r = hr_b_session.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        assert r.status_code == 403, r.text
        assert "organiser" in r.json().get("detail", "").lower()

    def test_owner_hr_can_generate(self, hr_a_session, env_setup):
        r = hr_a_session.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        assert r.status_code == 200, r.text


# ============================================================
# Fixture lock once a fixture is live/completed
# ============================================================
class TestFixtureLock:
    def test_lock_blocks_regeneration(self, hr_a_session, admin_session, env_setup):
        # Ensure fixtures exist (regenerate clean)
        admin_session.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        r = admin_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        assert r.status_code == 200
        fixtures = r.json()
        assert fixtures, "fixtures list empty"
        fid = fixtures[0]["id"]

        # Mark first fixture as live via PATCH
        patch_body = {"score": {"team_a": {"runs": 10}, "team_b": {"runs": 0}}, "status": "live"}
        r = hr_a_session.patch(f"{BASE_URL}/api/fixtures/{fid}", json=patch_body)
        assert r.status_code == 200, r.text

        # Now regenerate must be 400 "locked"
        r = hr_a_session.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        assert r.status_code == 400, r.text
        assert "locked" in r.json().get("detail", "").lower()

        # cleanup: reset fixture status so subsequent tests can score
        _db.fixtures.update_one({"id": fid}, {"$set": {"status": "scheduled"}})


# ============================================================
# Score permission
# ============================================================
class TestScorePermissions:
    def test_unrelated_hr_cannot_patch_score(self, hr_b_session, env_setup):
        r = hr_b_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        assert r.status_code == 200
        fid = r.json()[0]["id"]
        r = hr_b_session.patch(
            f"{BASE_URL}/api/fixtures/{fid}",
            json={"score": {"team_a": {"runs": 1}, "team_b": {"runs": 0}}},
        )
        assert r.status_code == 403, r.text

    def test_owner_hr_can_init_score(self, hr_a_session, env_setup):
        r = hr_a_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fid = r.json()[1]["id"]
        r = hr_a_session.post(f"{BASE_URL}/api/fixtures/{fid}/init-score")
        assert r.status_code == 200, r.text
        # cleanup
        _db.fixtures.update_one({"id": fid}, {"$set": {"status": "scheduled"}})

    def test_unrelated_hr_cannot_init_score(self, hr_b_session, env_setup):
        r = hr_b_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fid = r.json()[0]["id"]
        r = hr_b_session.post(f"{BASE_URL}/api/fixtures/{fid}/init-score")
        assert r.status_code == 403, r.text

    def test_cricket_setup_unrelated_hr_403(self, hr_b_session, env_setup):
        r = hr_b_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fid = r.json()[0]["id"]
        r = hr_b_session.post(
            f"{BASE_URL}/api/fixtures/{fid}/cricket/setup",
            json={"overs_limit": 5},
        )
        assert r.status_code == 403, r.text

    def test_cricket_setup_owner_hr_ok(self, hr_a_session, env_setup):
        r = hr_a_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fid = r.json()[0]["id"]
        r = hr_a_session.post(
            f"{BASE_URL}/api/fixtures/{fid}/cricket/setup",
            json={"overs_limit": 5},
        )
        # cricket setup may need teams to exist; either 200 or known business 400
        assert r.status_code in (200, 400), r.text
        # If 400, it must NOT be the permission denial
        if r.status_code == 400:
            assert "not allowed" not in r.json().get("detail", "").lower()


# ============================================================
# Scorer invitation lifecycle
# ============================================================
class TestScorerInvitation:
    _shared = {}

    def test_invite_requires_event_manager(self, hr_b_session, env_setup):
        r = hr_b_session.post(
            f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers",
            json={"email": "TEST_scorer_x@example.com", "fixture_ids": []},
        )
        assert r.status_code == 403, r.text

    def test_invite_creates_scorer_all_fixtures(self, hr_a_session, env_setup):
        email = f"test_scorer_all_{uuid.uuid4().hex[:6]}@example.com"
        r = hr_a_session.post(
            f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers",
            json={"email": email, "name": "All Scorer", "fixture_ids": []},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["ok"] is True
        assert data["user_created"] is True
        assert data["temp_password"]
        assert "assignment_id" in data
        TestScorerInvitation._shared["all_email"] = email
        TestScorerInvitation._shared["all_pwd"] = data["temp_password"]
        TestScorerInvitation._shared["all_assignment_id"] = data["assignment_id"]

    def test_invite_invalid_fixture_id_rejected(self, hr_a_session, env_setup):
        r = hr_a_session.post(
            f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers",
            json={"email": "TEST_bad@example.com", "fixture_ids": ["nonexistent-fid"]},
        )
        assert r.status_code == 400, r.text

    def test_invite_specific_fixtures(self, hr_a_session, env_setup):
        # Pick the first fixture only
        r = hr_a_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fixtures = r.json()
        target_fid = fixtures[0]["id"]
        other_fid = fixtures[1]["id"]
        email = f"test_scorer_spec_{uuid.uuid4().hex[:6]}@example.com"
        r = hr_a_session.post(
            f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers",
            json={"email": email, "fixture_ids": [target_fid]},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        TestScorerInvitation._shared["spec_email"] = email
        TestScorerInvitation._shared["spec_pwd"] = data["temp_password"]
        TestScorerInvitation._shared["spec_target_fid"] = target_fid
        TestScorerInvitation._shared["spec_other_fid"] = other_fid

    def test_list_scorers_requires_owner(self, hr_b_session, env_setup):
        r = hr_b_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers")
        assert r.status_code == 403

    def test_list_scorers_owner_ok(self, hr_a_session, env_setup):
        r = hr_a_session.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
        assert len(r.json()) >= 2


# ============================================================
# Scorer login + dashboard + scoring
# ============================================================
class TestScorerWorkflow:
    def test_scorer_login_role_check(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        assert email and pwd, "prior invite test missing"
        s = _login(email, pwd)
        r = s.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        assert r.json()["role"] == "scorer"

    def test_scorer_dashboard_lists_event(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        s = _login(email, pwd)
        r = s.get(f"{BASE_URL}/api/scorers/me/events")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "events" in data and len(data["events"]) >= 1
        ev = data["events"][0]
        assert ev["event"]["id"] == env_setup["event"]["id"]
        assert ev["scope"] == "all"
        assert len(ev["fixtures"]) >= 1

    def test_scorer_all_can_patch_any_fixture(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        s = _login(email, pwd)
        r = s.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/fixtures")
        fid = r.json()[2]["id"]
        r = s.patch(
            f"{BASE_URL}/api/fixtures/{fid}",
            json={"score": {"team_a": {"runs": 5}, "team_b": {"runs": 0}}},
        )
        assert r.status_code == 200, r.text

    def test_scorer_specific_scope(self, env_setup):
        email = TestScorerInvitation._shared.get("spec_email")
        pwd = TestScorerInvitation._shared.get("spec_pwd")
        target_fid = TestScorerInvitation._shared.get("spec_target_fid")
        other_fid = TestScorerInvitation._shared.get("spec_other_fid")
        assert email and target_fid and other_fid

        s = _login(email, pwd)
        # Allowed for target fixture
        r = s.patch(
            f"{BASE_URL}/api/fixtures/{target_fid}",
            json={"score": {"team_a": {"runs": 2}, "team_b": {"runs": 0}}},
        )
        assert r.status_code == 200, r.text

        # Denied for other fixture
        r = s.patch(
            f"{BASE_URL}/api/fixtures/{other_fid}",
            json={"score": {"team_a": {"runs": 9}, "team_b": {"runs": 0}}},
        )
        assert r.status_code == 403, r.text

        # Denied from cricket endpoint too
        r = s.post(
            f"{BASE_URL}/api/fixtures/{other_fid}/cricket/setup",
            json={"overs_limit": 5},
        )
        assert r.status_code == 403, r.text

        # Dashboard scope reads 'specific'
        r = s.get(f"{BASE_URL}/api/scorers/me/events")
        assert r.status_code == 200
        evs = r.json()["events"]
        assert any(e["scope"] == "specific" for e in evs)


# ============================================================
# Scorer restrictions (negative)
# ============================================================
class TestScorerRestrictions:
    def test_scorer_cannot_generate_fixtures(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        s = _login(email, pwd)
        r = s.post(f"{BASE_URL}/api/events/{env_setup['event']['id']}/generate-fixtures")
        # Could be 403 from require_admin or our scorer gate
        assert r.status_code in (401, 403), r.text

    def test_scorer_cannot_list_scorers(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        s = _login(email, pwd)
        r = s.get(f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers")
        assert r.status_code == 403, r.text

    def test_scorer_cannot_invite_scorers(self, env_setup):
        email = TestScorerInvitation._shared.get("all_email")
        pwd = TestScorerInvitation._shared.get("all_pwd")
        s = _login(email, pwd)
        r = s.post(
            f"{BASE_URL}/api/events/{env_setup['event']['id']}/scorers",
            json={"email": "TEST_nope@x.com", "fixture_ids": []},
        )
        assert r.status_code == 403, r.text


# ============================================================
# Cleanup leftover test users at end of module
# ============================================================
def teardown_module(module):
    for key in ("all_email", "spec_email"):
        em = TestScorerInvitation._shared.get(key)
        if em:
            _db.users.delete_many({"email": em})
            _db.event_scorers.delete_many({"email": em})
