"""Tests for ios_app_url / android_app_url fields on /api/settings (iteration_42).

Covers:
- GET /api/settings returns the new fields (default empty strings).
- PATCH /api/settings as platform admin persists values and GET reflects them.
- PATCH /api/settings from an unauthenticated caller is rejected (401/403).
- Cleanup restores the fields to empty strings (production default).
"""
import os
import pytest
import requests
from pathlib import Path


def _load_backend_url():
    val = os.environ.get("REACT_APP_BACKEND_URL")
    if val:
        return val.rstrip("/")
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not configured")


BASE_URL = _load_backend_url()
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


class TestAppStoreSettings:
    def test_get_settings_exposes_new_fields(self, anon_session):
        r = anon_session.get(f"{API}/settings")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ios_app_url" in data, "ios_app_url missing from /settings"
        assert "android_app_url" in data, "android_app_url missing from /settings"
        # Should be strings (empty by default in production).
        assert isinstance(data["ios_app_url"], str)
        assert isinstance(data["android_app_url"], str)

    def test_patch_settings_requires_auth(self, anon_session):
        r = anon_session.patch(
            f"{API}/settings",
            json={"ios_app_url": "https://apps.apple.com/app/idHACK"},
        )
        assert r.status_code in (401, 403), (
            f"Unauth PATCH /settings should be rejected, got {r.status_code} {r.text}"
        )

    def test_patch_updates_and_persists(self, admin_session, anon_session):
        ios = "https://apps.apple.com/app/id1234567890"
        android = "https://play.google.com/store/apps/details?id=com.kreedanation.app"

        r = admin_session.patch(
            f"{API}/settings",
            json={"ios_app_url": ios, "android_app_url": android},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ios_app_url") == ios
        assert body.get("android_app_url") == android

        # Verify GET reflects the change (persistence).
        r2 = anon_session.get(f"{API}/settings")
        assert r2.status_code == 200
        data = r2.json()
        assert data["ios_app_url"] == ios
        assert data["android_app_url"] == android

    def test_patch_accepts_partial_and_preserves_other(self, admin_session, anon_session):
        # Change only android_app_url — ios should remain from previous test.
        new_android = "https://play.google.com/store/apps/details?id=com.kreedanation.app.v2"
        r = admin_session.patch(f"{API}/settings", json={"android_app_url": new_android})
        assert r.status_code == 200
        body = r.json()
        assert body["android_app_url"] == new_android
        # ios_app_url should still hold the value from previous test.
        assert body["ios_app_url"].startswith("https://apps.apple.com/")

    def test_cleanup_restore_empty(self, admin_session, anon_session):
        # Restore the desired production default → both empty strings.
        r = admin_session.patch(
            f"{API}/settings",
            json={"ios_app_url": "", "android_app_url": ""},
        )
        assert r.status_code == 200
        r2 = anon_session.get(f"{API}/settings")
        data = r2.json()
        assert data["ios_app_url"] == ""
        assert data["android_app_url"] == ""
