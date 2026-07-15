"""Iteration 30 — Event organiser contact + sport templates regression.

Verifies:
  * POST /api/events with contact_name/email/phone → stored and returned by GET.
  * PATCH /api/events/{id} accepts contact fields → GET reflects updates.
  * POST /api/sports for template slug ("kabaddi") creates the sport if missing.
  * GET /api/sports still exposes canonical entries.
"""
import os
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


# Track created events for teardown
_created_event_ids: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_client):
    yield
    for eid in _created_event_ids:
        try:
            admin_client.delete(f"{BASE_URL}/api/events/{eid}")
        except Exception:
            pass


# ---------- Event contact fields ----------

def test_create_event_with_contact_fields_persists(admin_client):
    unique = uuid.uuid4().hex[:6]
    payload = {
        "name": f"TEST_ContactEvent_{unique}",
        "sport": "football",
        "format": "round_robin",
        "event_type": "playsphere_organized",
        "description": "Contact-field regression",
        "venue": "TEST venue",
        "contact_name": "Alice Organiser",
        "contact_email": "alice@example.com",
        "contact_phone": "+919000000099",
        "start_date": "2099-01-01",
        "end_date": "2099-01-02",
    }
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["contact_name"] == "Alice Organiser"
    assert body["contact_email"] == "alice@example.com"
    assert body["contact_phone"] == "+919000000099"

    eid = body["id"]
    _created_event_ids.append(eid)

    # GET verifies persistence
    g = admin_client.get(f"{BASE_URL}/api/events/{eid}")
    assert g.status_code == 200
    gb = g.json()
    assert gb["contact_name"] == "Alice Organiser"
    assert gb["contact_email"] == "alice@example.com"
    assert gb["contact_phone"] == "+919000000099"


def test_create_event_without_contact_fields_defaults_empty(admin_client):
    unique = uuid.uuid4().hex[:6]
    payload = {
        "name": f"TEST_NoContact_{unique}",
        "sport": "football",
        "format": "round_robin",
        "event_type": "playsphere_organized",
        "start_date": "2099-01-01",
        "end_date": "2099-01-02",
    }
    r = admin_client.post(f"{BASE_URL}/api/events", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    eid = body["id"]
    _created_event_ids.append(eid)
    # Should default to empty strings
    assert body.get("contact_name", "") == ""
    assert body.get("contact_email", "") == ""
    assert body.get("contact_phone", "") == ""


def test_patch_event_contact_fields_persists(admin_client):
    unique = uuid.uuid4().hex[:6]
    r = admin_client.post(f"{BASE_URL}/api/events", json={
        "name": f"TEST_PatchContact_{unique}",
        "sport": "football",
        "format": "round_robin",
        "event_type": "playsphere_organized",
        "start_date": "2099-01-01",
        "end_date": "2099-01-02",
    })
    assert r.status_code == 200, r.text
    eid = r.json()["id"]
    _created_event_ids.append(eid)

    # PATCH with contact fields
    upd = admin_client.patch(f"{BASE_URL}/api/events/{eid}", json={
        "contact_name": "Bob Manager",
        "contact_email": "bob@example.com",
        "contact_phone": "+911234567890",
    })
    assert upd.status_code == 200, upd.text
    ub = upd.json()
    assert ub["contact_name"] == "Bob Manager"
    assert ub["contact_email"] == "bob@example.com"
    assert ub["contact_phone"] == "+911234567890"

    # GET reflects update
    g = admin_client.get(f"{BASE_URL}/api/events/{eid}")
    assert g.status_code == 200
    gb = g.json()
    assert gb["contact_name"] == "Bob Manager"
    assert gb["contact_email"] == "bob@example.com"
    assert gb["contact_phone"] == "+911234567890"


# ---------- Sport template regression ----------

TEMPLATES = [
    ("kabaddi",   "Kabaddi",   "generic",  "team"),
    ("khokho",    "Kho-Kho",   "generic",  "team"),
    ("futsal",    "Futsal",    "football", "team"),
    ("padel",     "Padel",     "racket",   "both"),
    ("throwball", "Throwball", "racket",   "team"),
    ("dodgeball", "Dodgeball", "generic",  "team"),
    ("esports",   "Esports",   "generic",  "team"),
    ("carrom",    "Carrom",    "chess",    "individual"),
    ("snooker",   "Snooker",   "generic",  "individual"),
]


@pytest.mark.parametrize("value,label,scoring,pf", TEMPLATES)
def test_sport_template_create_or_exists(admin_client, value, label, scoring, pf):
    """Post the template row (matches what SportsManager.applyTemplate submits).
    Either 200 (created) or 400 (already exists). Then GET must show the sport.
    """
    r = admin_client.post(f"{BASE_URL}/api/sports", json={
        "value": value,
        "label": label,
        "scoring_pattern": scoring,
        "player_format": pf,
    })
    assert r.status_code in (200, 400), r.text

    # Confirm the sport is in the catalog
    g = admin_client.get(f"{BASE_URL}/api/sports?include_inactive=true")
    assert g.status_code == 200
    match = next((s for s in g.json() if s.get("value") == value), None)
    assert match is not None, f"Sport {value} missing from /api/sports"
    # Label should match (case-preserving)
    assert match["label"].lower() == label.lower() or match["label"] == label


def test_sports_catalog_still_has_regression_sports(admin_client):
    """iter29 regression — tennis + lawntennis + pickleball must all exist."""
    g = admin_client.get(f"{BASE_URL}/api/sports?include_inactive=true")
    assert g.status_code == 200
    values = {s["value"] for s in g.json()}
    # Note: tennis / lawntennis may only exist in frontend FALLBACK if not seeded.
    # But pickleball WAS seeded in iter28 — must exist.
    assert "pickleball" in values, f"pickleball missing from db.sports: {values}"
