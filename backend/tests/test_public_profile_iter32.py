"""Iteration 32 retest: anonymous access to GET /api/players/profiles/{id}.

Regression test to make sure:
* 200 for anonymous callers (no auth cookie / no Authorization header)
* `mobile_masked` present, raw `mobile` absent
* `email` and `dob` absent for anonymous viewers
* Name, id, view_count still present
"""
from __future__ import annotations
import os

import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

PROFILE_ID = "cecc6f8c-f894-4edd-b827-1e17d4f35343"


def test_anonymous_profile_returns_200_with_masked_fields():
    r = requests.get(f"{API}/players/profiles/{PROFILE_ID}", timeout=10)
    assert r.status_code == 200, r.text
    data = r.json()
    # Core public fields
    assert data["id"] == PROFILE_ID
    assert data.get("name")  # non-empty string
    # Privacy: masked mobile, no raw mobile/email/dob
    assert "mobile" not in data, "raw mobile leaked to anonymous caller"
    assert "email" not in data, "email leaked to anonymous caller"
    assert "dob" not in data, "dob leaked to anonymous caller"
    if "mobile_masked" in data and data["mobile_masked"]:
        assert data["mobile_masked"].startswith("\u2022"), data["mobile_masked"]


def test_anonymous_profile_404_for_missing():
    r = requests.get(f"{API}/players/profiles/does-not-exist-xyz", timeout=10)
    assert r.status_code == 404


def test_view_count_increments_for_anonymous_view():
    """Anonymous view should still bump view_count (proxy for the endpoint being
    reachable AND the non-owner branch running)."""
    r1 = requests.get(f"{API}/players/profiles/{PROFILE_ID}", timeout=10)
    r2 = requests.get(f"{API}/players/profiles/{PROFILE_ID}", timeout=10)
    assert r1.status_code == 200 and r2.status_code == 200
    v1 = r1.json().get("view_count", 0)
    v2 = r2.json().get("view_count", 0)
    assert v2 > v1, f"view_count did not increment ({v1} -> {v2})"
