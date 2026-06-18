"""Tests for the public, no-auth /api/public/fixtures/{id} endpoint."""
import os
import time
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@kreedanation.com", "password": "admin123"}


def _admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


def test_public_endpoint_404_for_missing():
    r = requests.get(f"{API}/public/fixtures/nonexistent-id")
    assert r.status_code == 404


def test_public_endpoint_no_auth_required():
    """Without any cookies/headers, the public endpoint must return fixture data."""
    s = _admin_session()
    uniq = "PUB" + str(int(time.time()))
    ev = s.post(f"{API}/events", json={
        "name": f"TEST_Public_{uniq}", "sport": "cricket", "format": "round_robin",
    }).json()
    teams = []
    for tn in ("P", "Q"):
        t = s.post(f"{API}/events/{ev['id']}/teams", json={
            "name": f"Team_{tn}_{uniq}", "short_name": tn * 3, "color": "#FF0000" if tn == "P" else "#00FF00",
        }).json()
        teams.append(t)
        for i in range(2):
            s.post(f"{API}/events/{ev['id']}/teams/{t['id']}/members", json={
                "quick": {"name": f"Pl_{tn}_{i}_{uniq}", "mobile": f"+9195{uniq[-4:]}{tn}{i:02d}"}
            })
    s.post(f"{API}/events/{ev['id']}/generate-fixtures")
    fx = s.get(f"{API}/events/{ev['id']}/fixtures").json()[0]

    # Anonymous request (no session cookie)
    r = requests.get(f"{API}/public/fixtures/{fx['id']}")
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["fixture"]["id"] == fx["id"]
    assert payload["event"]["sport"] == "cricket"
    assert payload["event"]["name"] == f"TEST_Public_{uniq}"
    assert len(payload["teams"]) == 2
    a = payload["teams"][teams[0]["id"]]
    assert a["name"] == teams[0]["name"]
    assert a["color"] == "#FF0000"


def test_public_endpoint_returns_event_meta_only():
    """Verify the event payload doesn't leak admin-only fields (status, internal flags)."""
    s = _admin_session()
    fx = s.get(f"{API}/events/{s.get(f'{API}/events').json()[0]['id']}/fixtures").json()
    if not fx:
        return  # skip if no fixtures
    r = requests.get(f"{API}/public/fixtures/{fx[0]['id']}")
    assert r.status_code == 200
    event = r.json()["event"]
    public_keys = {"id", "name", "sport", "format", "location", "company_id"}
    assert set(event.keys()) <= public_keys
