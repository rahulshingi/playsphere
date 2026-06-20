"""Tests for the admin-controlled account suspension feature.

Covers:
- GET /api/admin/users with optional role filter (organiser/vendor/player/company_admin)
- PATCH /api/admin/users/{id}/disabled toggles the disabled flag
- Disabled users get 403 with exact contact-admin message on login
- Re-enabling restores login
- Platform admins cannot be disabled via this endpoint
- An admin cannot disable themselves
- Invalid role filter rejected with 400
- Non-admin callers get 403 on these endpoints
"""
import os
import uuid
import asyncio

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
SUPER_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@kreedanation.com")
SUPER_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")

DISABLED_MSG = (
    "Your account has been disabled. "
    "Please contact admin with admin email: admin@kreedanation.com"
)

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _login(email: str, password: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def super_session() -> requests.Session:
    return _login(SUPER_EMAIL, SUPER_PASSWORD)


@pytest.fixture(scope="module")
def organiser_account():
    """Seed an organiser directly in Mongo (avoids OTP/email dependency) and clean up after."""
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    email = f"test-organiser-{uuid.uuid4().hex[:8]}@example.com"
    password = "test123"

    async def _setup():
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        uid = str(uuid.uuid4())
        cid = str(uuid.uuid4())
        await db.companies.insert_one({
            "id": cid, "name": f"Susp Org {uid[:6]}",
            "slug": f"susp-org-{uid[:6]}", "org_type": "organiser",
            "owner_user_id": uid, "contact_email": email,
        })
        await db.users.insert_one({
            "id": uid, "email": email, "name": "Susp Org Owner",
            "role": "organiser", "company_id": cid,
            "password_hash": _pwd.hash(password), "email_verified": True,
            "created_at": "2026-01-01T00:00:00+00:00",
        })
        return uid, cid

    async def _cleanup(uid, cid):
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        await db.users.delete_one({"id": uid})
        await db.companies.delete_one({"id": cid})

    uid, cid = asyncio.run(_setup())
    yield {"id": uid, "company_id": cid, "email": email, "password": password}
    asyncio.run(_cleanup(uid, cid))


def test_list_users_requires_platform_admin():
    r = requests.get(f"{BASE_URL}/api/admin/users", timeout=15)
    assert r.status_code in (401, 403)


def test_list_users_returns_suspendable_roles(super_session, organiser_account):
    r = super_session.get(f"{BASE_URL}/api/admin/users", timeout=15)
    assert r.status_code == 200
    users = r.json()
    emails = {u["email"] for u in users}
    assert organiser_account["email"] in emails
    # No platform admins should leak through
    assert all(u["role"] in {"organiser", "vendor", "player", "company_admin"} for u in users)


def test_list_users_role_filter(super_session, organiser_account):
    r = super_session.get(f"{BASE_URL}/api/admin/users", params={"role": "organiser"}, timeout=15)
    assert r.status_code == 200
    users = r.json()
    assert all(u["role"] == "organiser" for u in users)
    assert any(u["id"] == organiser_account["id"] for u in users)


def test_list_users_invalid_role(super_session):
    r = super_session.get(f"{BASE_URL}/api/admin/users", params={"role": "platform_admin"}, timeout=15)
    assert r.status_code == 400


def test_disable_and_re_enable_organiser(super_session, organiser_account):
    uid = organiser_account["id"]
    email = organiser_account["email"]
    password = organiser_account["password"]

    # Login works before disabling
    pre = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert pre.status_code == 200

    # Disable
    d = super_session.patch(f"{BASE_URL}/api/admin/users/{uid}/disabled", json={"disabled": True}, timeout=15)
    assert d.status_code == 200
    assert d.json().get("disabled") is True

    # Login now blocked with the exact contact message
    blocked = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert blocked.status_code == 403
    assert blocked.json().get("detail") == DISABLED_MSG

    # List reflects disabled=true and metadata
    listed = super_session.get(f"{BASE_URL}/api/admin/users", params={"role": "organiser"}, timeout=15).json()
    row = next(u for u in listed if u["id"] == uid)
    assert row["disabled"] is True
    assert row.get("disabled_by") == SUPER_EMAIL
    assert row.get("disabled_at")

    # Re-enable
    e = super_session.patch(f"{BASE_URL}/api/admin/users/{uid}/disabled", json={"disabled": False}, timeout=15)
    assert e.status_code == 200
    assert e.json().get("disabled") is False

    # Login works again
    post = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert post.status_code == 200


def test_cannot_disable_platform_admin(super_session):
    me = super_session.get(f"{BASE_URL}/api/auth/me", timeout=15).json()
    r = super_session.patch(
        f"{BASE_URL}/api/admin/users/{me['id']}/disabled",
        json={"disabled": True},
        timeout=15,
    )
    assert r.status_code == 400


def test_cannot_disable_unknown_user(super_session):
    r = super_session.patch(
        f"{BASE_URL}/api/admin/users/{uuid.uuid4()}/disabled",
        json={"disabled": True},
        timeout=15,
    )
    assert r.status_code == 404


def test_toggle_requires_platform_admin(organiser_account):
    # Caller is unauthenticated
    r = requests.patch(
        f"{BASE_URL}/api/admin/users/{organiser_account['id']}/disabled",
        json={"disabled": True},
        timeout=15,
    )
    assert r.status_code in (401, 403)
