"""Iteration 28 — Sports enrichment + player_format picker regression suite.

Verifies:
  * Admin can create the 'pickleball' sport → scoring_pattern='racket' + player_format='both' auto-populated.
  * GET /api/sports returns the sport with enrichment applied.
  * Event creation for a `both` sport without player_format → 400.
  * Event creation for pickleball with player_format='doubles' → 200,
    response includes scoring_pattern='racket' + player_format='doubles'.
  * Event creation for cricket (team sport) → auto-derives scoring_pattern='cricket', player_format='team'.
  * Event creation for volleyball (team sport with racket scoring pattern) → passes.
  * Event creation for chess (individual sport) → player_format='individual'.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@kreedanation.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    return s


# ----- Sports catalog enrichment -----

def _find_sport(session, value: str):
    r = session.get(f"{BASE_URL}/api/sports?include_inactive=true")
    assert r.status_code == 200, r.text
    return next((s for s in r.json() if s.get("value") == value), None)


def test_get_sports_returns_list(admin_client):
    r = admin_client.get(f"{BASE_URL}/api/sports")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_create_pickleball_sport_auto_enriches(admin_client):
    # Idempotent — POST may return 400 "already exists". Either way, we then GET
    # and validate the enriched fields.
    resp = admin_client.post(f"{BASE_URL}/api/sports", json={
        "value": "pickleball",
        "label": "Pickleball",
    })
    assert resp.status_code in (200, 400), resp.text
    if resp.status_code == 200:
        body = resp.json()
        assert body["value"] == "pickleball"
        assert body["label"] == "Pickleball"
        assert body["scoring_pattern"] == "racket", body
        assert body["player_format"] == "both", body

    # Verify GET returns pickleball with enrichment.
    sport = _find_sport(admin_client, "pickleball")
    assert sport is not None, "Pickleball missing from GET /api/sports"
    assert sport.get("scoring_pattern") == "racket"
    assert sport.get("player_format") == "both"


def test_get_sports_enriches_legacy_rows_after_patch(admin_client):
    """After a PATCH that only toggles `active`, enrichment must still populate
    scoring_pattern + player_format on the returned doc."""
    sport = _find_sport(admin_client, "pickleball")
    assert sport is not None
    sport_id = sport["id"]
    # toggle active off then on to trigger a mutation without touching enriched fields
    r1 = admin_client.patch(f"{BASE_URL}/api/sports/{sport_id}", json={"active": False})
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1.get("scoring_pattern") == "racket"
    assert j1.get("player_format") == "both"
    r2 = admin_client.patch(f"{BASE_URL}/api/sports/{sport_id}", json={"active": True})
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("scoring_pattern") == "racket"
    assert j2.get("player_format") == "both"


# ----- Event creation enrichment / validation -----

def _mk_evt(sport, name_suffix, **extras):
    payload = {
        "name": f"TEST_{sport}_{name_suffix}_{uuid.uuid4().hex[:6]}",
        "sport": sport,
        "format": "round_robin",
        "event_type": "playsphere_organized",
    }
    payload.update(extras)
    return payload


def test_event_pickleball_missing_player_format_returns_400(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/events", json=_mk_evt("pickleball", "no_pf"))
    assert r.status_code == 400, r.text
    detail = (r.json() or {}).get("detail", "")
    assert "singles" in detail.lower() and "doubles" in detail.lower(), detail


def test_event_pickleball_with_doubles_succeeds_with_enrichment(admin_client):
    payload = _mk_evt("pickleball", "doubles", player_format="doubles")
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["sport"] == "pickleball"
    assert ev.get("scoring_pattern") == "racket", ev
    assert ev.get("player_format") == "doubles", ev

    # GET to verify persistence
    g = admin_client.get(f"{BASE_URL}/api/events/{ev['id']}")
    assert g.status_code == 200
    got = g.json()
    assert got.get("scoring_pattern") == "racket"
    assert got.get("player_format") == "doubles"
    # cleanup
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_cricket_auto_enriches_team_and_cricket_scoring(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/events", json=_mk_evt("cricket", "team"))
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["sport"] == "cricket"
    assert ev.get("scoring_pattern") == "cricket", ev
    assert ev.get("player_format") == "team", ev
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_volleyball_auto_enriches_team_and_racket_scoring(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/events", json=_mk_evt("volleyball", "team"))
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["sport"] == "volleyball"
    assert ev.get("scoring_pattern") == "racket", ev
    assert ev.get("player_format") == "team", ev
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_chess_auto_enriches_individual_and_chess_scoring(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/events", json=_mk_evt("chess", "indiv"))
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev["sport"] == "chess"
    assert ev.get("scoring_pattern") == "chess", ev
    assert ev.get("player_format") == "individual", ev
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_badminton_with_singles_succeeds(admin_client):
    payload = _mk_evt("badminton", "singles", player_format="singles")
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev.get("scoring_pattern") == "racket"
    assert ev.get("player_format") == "singles"
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_tennis_missing_pf_returns_400(admin_client):
    r = admin_client.post(f"{BASE_URL}/api/events", json=_mk_evt("tennis", "no_pf"))
    assert r.status_code == 400, r.text


def test_event_lawntennis_with_doubles_succeeds(admin_client):
    payload = _mk_evt("lawntennis", "doubles", player_format="doubles")
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 200, r.text
    ev = r.json()
    assert ev.get("scoring_pattern") == "racket"
    assert ev.get("player_format") == "doubles"
    admin_client.delete(f"{BASE_URL}/api/events/{ev['id']}")


def test_event_invalid_pf_for_racket_returns_400(admin_client):
    payload = _mk_evt("pickleball", "invalidpf", player_format="mixed")
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 400, r.text
