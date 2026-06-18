"""RBAC / multi-admin tests for iteration 12.

Covers:
- /api/admin/permissions/me returns is_super_admin=True for seed admin
- /api/admin/staff CRUD (super-only)
- 403 for non-super admin on protected endpoints
- Permission-gated approve endpoints (manage_vendors, manage_listings)
- super admin cannot be deleted via DELETE /api/admin/staff
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
SUPER_EMAIL = "admin@kreedanation.com"
SUPER_PASSWORD = "admin123"


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
def staff_without_perms(super_session):
    """Create staff admin with NO permissions. Yields (session, admin_dict)."""
    email = f"TEST_staff_noperm_{uuid.uuid4().hex[:8]}@kreedanation.com"
    pw = "staffpass123"
    r = super_session.post(
        f"{BASE_URL}/api/admin/staff",
        json={"email": email, "name": "TEST NoPerm", "password": pw, "permissions": []},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    admin = r.json()["admin"]
    sess = _login(email, pw)
    yield sess, admin
    # cleanup
    try:
        super_session.delete(f"{BASE_URL}/api/admin/staff/{admin['id']}", timeout=10)
    except Exception:
        pass


@pytest.fixture(scope="module")
def staff_with_vendor_perm(super_session):
    """Create staff admin WITH manage_vendors only."""
    email = f"TEST_staff_vend_{uuid.uuid4().hex[:8]}@kreedanation.com"
    pw = "staffpass123"
    r = super_session.post(
        f"{BASE_URL}/api/admin/staff",
        json={
            "email": email,
            "name": "TEST VendorPerm",
            "password": pw,
            "permissions": ["manage_vendors"],
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    admin = r.json()["admin"]
    sess = _login(email, pw)
    yield sess, admin
    try:
        super_session.delete(f"{BASE_URL}/api/admin/staff/{admin['id']}", timeout=10)
    except Exception:
        pass


# ---------- permissions/me ----------
class TestPermissionsMe:
    def test_super_admin_permissions_me(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/admin/permissions/me", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_super_admin"] is True
        assert isinstance(data["permissions"], list)
        # super admin should have all perms
        assert "manage_vendors" in data["permissions"]
        assert "manage_listings" in data["permissions"]
        assert "manage_events" in data["permissions"]
        assert isinstance(data["all_permissions"], list)
        assert len(data["all_permissions"]) >= 7

    def test_auth_me_returns_super_flag(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code == 200, r.text
        me = r.json()
        assert me.get("is_super_admin") is True
        assert isinstance(me.get("permissions"), list)

    def test_staff_admin_permissions_me(self, staff_without_perms):
        sess, _ = staff_without_perms
        r = sess.get(f"{BASE_URL}/api/admin/permissions/me", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["is_super_admin"] is False
        assert data["permissions"] == []


# ---------- Staff CRUD ----------
class TestStaffCrud:
    def test_create_and_list_staff_admin(self, super_session):
        email = f"TEST_staff_crud_{uuid.uuid4().hex[:8]}@kreedanation.com"
        pw = "newstaffpass1"
        r = super_session.post(
            f"{BASE_URL}/api/admin/staff",
            json={
                "email": email,
                "name": "TEST CRUD",
                "password": pw,
                "permissions": ["manage_events"],
            },
            timeout=15,
        )
        assert r.status_code == 200, r.text
        payload = r.json()
        assert payload["ok"] is True
        assert payload["invite"]["temp_password"] == pw
        assert payload["invite"]["email"] == email.lower()
        admin = payload["admin"]
        assert admin["email"] == email.lower()
        assert admin["is_super_admin"] is False
        assert "manage_events" in admin["permissions"]
        admin_id = admin["id"]

        # list
        r2 = super_session.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        assert r2.status_code == 200, r2.text
        ids = [a["id"] for a in r2.json()]
        assert admin_id in ids

        # patch permissions
        r3 = super_session.patch(
            f"{BASE_URL}/api/admin/staff/{admin_id}",
            json={"permissions": ["manage_events", "manage_vendors"]},
            timeout=10,
        )
        assert r3.status_code == 200, r3.text
        assert set(r3.json()["permissions"]) == {"manage_events", "manage_vendors"}

        # delete
        r4 = super_session.delete(f"{BASE_URL}/api/admin/staff/{admin_id}", timeout=10)
        assert r4.status_code == 200, r4.text

        # verify gone
        r5 = super_session.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        assert admin_id not in [a["id"] for a in r5.json()]

    def test_super_admin_cannot_be_deleted(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        assert r.status_code == 200
        super_doc = next((a for a in r.json() if a.get("is_super_admin")), None)
        assert super_doc is not None, "Seed super admin not found in staff list"
        r2 = super_session.delete(
            f"{BASE_URL}/api/admin/staff/{super_doc['id']}", timeout=10
        )
        assert r2.status_code == 400, r2.text

    def test_super_admin_cannot_be_modified(self, super_session):
        r = super_session.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        super_doc = next(a for a in r.json() if a.get("is_super_admin"))
        r2 = super_session.patch(
            f"{BASE_URL}/api/admin/staff/{super_doc['id']}",
            json={"permissions": []},
            timeout=10,
        )
        assert r2.status_code == 400

    def test_duplicate_email_rejected(self, super_session):
        r = super_session.post(
            f"{BASE_URL}/api/admin/staff",
            json={
                "email": SUPER_EMAIL,
                "name": "dup",
                "password": "abcdef1",
                "permissions": [],
            },
            timeout=10,
        )
        assert r.status_code == 400


# ---------- 403 enforcement ----------
class TestStaffAccessForbidden:
    def test_staff_cannot_list_admins(self, staff_without_perms):
        sess, _ = staff_without_perms
        r = sess.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        assert r.status_code == 403

    def test_staff_cannot_create_admin(self, staff_without_perms):
        sess, _ = staff_without_perms
        r = sess.post(
            f"{BASE_URL}/api/admin/staff",
            json={"email": "TEST_x@x.com", "name": "x", "password": "abcdef1", "permissions": []},
            timeout=10,
        )
        assert r.status_code == 403

    def test_staff_cannot_delete_admin(self, staff_without_perms, super_session):
        # try delete the super admin id
        r = super_session.get(f"{BASE_URL}/api/admin/staff", timeout=10)
        any_id = r.json()[0]["id"]
        sess, _ = staff_without_perms
        r2 = sess.delete(f"{BASE_URL}/api/admin/staff/{any_id}", timeout=10)
        assert r2.status_code == 403

    def test_staff_cannot_create_service(self, staff_without_perms):
        sess, _ = staff_without_perms
        r = sess.post(
            f"{BASE_URL}/api/services",
            json={"name": "TEST svc", "description": "x"},
            timeout=10,
        )
        assert r.status_code == 403

    def test_staff_without_vendor_perm_cannot_approve_vendor(
        self, staff_without_perms, super_session
    ):
        # find any vendor id
        r = super_session.get(f"{BASE_URL}/api/vendors", timeout=10)
        if r.status_code != 200 or not r.json():
            pytest.skip("No vendors seeded for this assertion")
        vid = r.json()[0]["id"]
        sess, _ = staff_without_perms
        r2 = sess.patch(
            f"{BASE_URL}/api/vendors/{vid}/approve",
            json={"approved": True},
            timeout=10,
        )
        assert r2.status_code == 403

    def test_staff_without_listings_perm_cannot_approve_listing(
        self, staff_without_perms, super_session
    ):
        # find a listing
        r = super_session.get(f"{BASE_URL}/api/admin/listings", timeout=10)
        if r.status_code != 200 or not r.json():
            pytest.skip("No listings to approve")
        lid = r.json()[0]["id"]
        sess, _ = staff_without_perms
        r2 = sess.patch(
            f"{BASE_URL}/api/admin/listings/{lid}/approve",
            json={"approved": True},
            timeout=10,
        )
        assert r2.status_code == 403


# ---------- granted permission allows action ----------
class TestStaffAccessGranted:
    def test_staff_with_vendor_perm_can_approve(self, staff_with_vendor_perm, super_session):
        r = super_session.get(f"{BASE_URL}/api/vendors", timeout=10)
        if r.status_code != 200 or not r.json():
            pytest.skip("No vendors seeded")
        vid = r.json()[0]["id"]
        original = r.json()[0].get("approved", False)
        sess, _ = staff_with_vendor_perm
        r2 = sess.patch(
            f"{BASE_URL}/api/vendors/{vid}/approve",
            json={"approved": True},
            timeout=10,
        )
        assert r2.status_code == 200, r2.text
        # restore
        sess.patch(
            f"{BASE_URL}/api/vendors/{vid}/approve",
            json={"approved": original},
            timeout=10,
        )
