"""
PlaySphere multi-tenant tests:
- Company signup
- Roles (platform_admin / company_admin)
- Services catalog (7 seeded) + RBAC CRUD
- Bookings flow (pricing, scoping, status RBAC, delete)
- Event tenancy stamping & filter & 403 cross-company
- Stats (global + per-company)
"""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@playsphere.com")
ADMIN_PASSWORD = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")
ACME_EMAIL = os.environ.get("TEST_ACME_EMAIL", "acme@example.com")
ACME_PASSWORD = os.environ.get("TEST_ACME_PASSWORD", "acme123")
VIEWER_EMAIL = os.environ.get("TEST_VIEWER_EMAIL", "viewer@playsphere.com")
VIEWER_PASSWORD = os.environ.get("TEST_VIEWER_PASSWORD", "viewer123")


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return s, r.json()


@pytest.fixture(scope="module")
def platform_admin():
    s, me = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    return s, me


@pytest.fixture(scope="module")
def company_admin():
    s, me = _login(ACME_EMAIL, ACME_PASSWORD)
    return s, me


@pytest.fixture(scope="module")
def viewer():
    s, me = _login(VIEWER_EMAIL, VIEWER_PASSWORD)
    return s, me


# ---------- Roles ----------
class TestRoles:
    def test_platform_admin_role(self, platform_admin):
        _, me = platform_admin
        assert me["role"] == "platform_admin", me
        assert me["email"] == ADMIN_EMAIL

    def test_company_admin_role(self, company_admin):
        _, me = company_admin
        assert me["role"] == "company_admin"
        assert me["company_id"]
        assert me["company_name"] == "Acme Corp"


# ---------- Company signup ----------
class TestCompanySignup:
    def test_signup_creates_company_and_admin(self):
        s = requests.Session()
        uniq = uuid.uuid4().hex[:8]
        payload = {
            "company_name": f"TEST_Co_{uniq}",
            "admin_name": "TEST Owner",
            "admin_email": f"test_owner_{uniq}@example.com",
            "admin_password": "testpass123",
            "contact_phone": "+1 555 000 1234",
        }
        r = s.post(f"{API}/companies/signup", json=payload, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["role"] == "company_admin"
        assert d["company_id"]
        assert d["company_name"] == payload["company_name"]
        # cookie set
        assert "access_token" in s.cookies.get_dict()
        # /me works
        me = s.get(f"{API}/auth/me").json()
        assert me["role"] == "company_admin"
        assert me["company_name"] == payload["company_name"]

    def test_signup_duplicate_email(self):
        # Reuse Acme email -> 400
        r = requests.post(f"{API}/companies/signup", json={
            "company_name": "Dup",
            "admin_name": "x",
            "admin_email": ACME_EMAIL,
            "admin_password": "x",
        })
        assert r.status_code == 400


# ---------- Services catalog ----------
class TestServices:
    def test_list_services_seed(self):
        r = requests.get(f"{API}/services")
        assert r.status_code == 200
        services = r.json()
        names = {s["name"] for s in services}
        expected = {
            "Live YouTube Streaming", "Team Jerseys", "Branded Caps",
            "Trophies & Awards", "Ground Booking", "Match Instruments", "Training Kits",
        }
        assert expected.issubset(names), f"Missing services: {expected - names}"
        # Trophies variants
        trophies = next(s for s in services if s["name"] == "Trophies & Awards")
        variant_ids = {v["id"] for v in trophies["variants"]}
        assert {"trophy-gold", "trophy-crystal", "trophy-silver", "trophy-medal"}.issubset(variant_ids)
        assert trophies["base_price"] == 35.0
        # config fields present on streaming
        streaming = next(s for s in services if s["name"] == "Live YouTube Streaming")
        keys = {f["key"] for f in streaming["config_fields"]}
        assert "cameras" in keys and "umpires_mic" in keys

    def test_services_crud_rbac(self, platform_admin, company_admin):
        s_admin, _ = platform_admin
        s_co, _ = company_admin
        payload = {
            "name": f"TEST_Service_{uuid.uuid4().hex[:6]}",
            "category": "other",
            "base_price": 50,
            "description": "test",
            "config_fields": [{"key": "n", "label": "N", "type": "number"}],
            "variants": [{"id": "v1", "name": "Variant 1", "image_url": "http://x", "extra_price": 5}],
        }
        # company_admin forbidden
        r_forb = s_co.post(f"{API}/services", json=payload)
        assert r_forb.status_code == 403

        # platform admin allowed
        r = s_admin.post(f"{API}/services", json=payload)
        assert r.status_code == 200, r.text
        svc = r.json()
        # PATCH
        r2 = s_admin.patch(f"{API}/services/{svc['id']}", json={"base_price": 75})
        assert r2.status_code == 200 and r2.json()["base_price"] == 75
        # company_admin cannot patch
        assert s_co.patch(f"{API}/services/{svc['id']}", json={"base_price": 1}).status_code == 403
        # company_admin cannot delete
        assert s_co.delete(f"{API}/services/{svc['id']}").status_code == 403
        # cleanup
        assert s_admin.delete(f"{API}/services/{svc['id']}").status_code == 200


# ---------- Bookings ----------
class TestBookings:
    def test_trophy_booking_pricing(self, company_admin):
        s, me = company_admin
        services = requests.get(f"{API}/services").json()
        trophies = next(s for s in services if s["name"] == "Trophies & Awards")
        payload = {
            "service_id": trophies["id"],
            "quantity": 3,
            "variant_id": "trophy-gold",
            "custom_text": "Best Batsman",
            "config": {"height_inches": 12},
        }
        r = s.post(f"{API}/bookings", json=payload)
        assert r.status_code == 200, r.text
        b = r.json()
        # base 35 + variant 0 = 35 * 3 = 105
        assert b["total_price"] == 105.0
        assert b["status"] == "pending"
        assert b["variant_id"] == "trophy-gold"
        assert b["variant_name"] == "Golden Cup"
        assert b["company_id"] == me["company_id"]
        assert b["custom_text"] == "Best Batsman"
        return b["id"]

    def test_crystal_variant_pricing(self, company_admin):
        s, _ = company_admin
        services = requests.get(f"{API}/services").json()
        trophies = next(s for s in services if s["name"] == "Trophies & Awards")
        # crystal = +18; (35+18)*2 = 106
        r = s.post(f"{API}/bookings", json={
            "service_id": trophies["id"], "quantity": 2,
            "variant_id": "trophy-crystal", "custom_text": "MVP",
        })
        assert r.status_code == 200
        assert r.json()["total_price"] == 106.0
        # cleanup
        s.delete(f"{API}/bookings/{r.json()['id']}")

    def test_list_bookings_scoped(self, platform_admin, company_admin, viewer):
        s_pa, _ = platform_admin
        s_co, _ = company_admin
        s_v, _ = viewer
        # platform sees all (>=1)
        r_pa = s_pa.get(f"{API}/bookings")
        assert r_pa.status_code == 200 and len(r_pa.json()) >= 1
        # company sees only own
        r_co = s_co.get(f"{API}/bookings")
        assert r_co.status_code == 200
        for b in r_co.json():
            assert b["company_id"] == _login(ACME_EMAIL, ACME_PASSWORD)[1]["company_id"]
        # viewer forbidden
        assert s_v.get(f"{API}/bookings").status_code == 403

    def test_status_update_rbac(self, platform_admin, company_admin):
        s_pa, _ = platform_admin
        s_co, _ = company_admin
        services = requests.get(f"{API}/services").json()
        trophies = next(s for s in services if s["name"] == "Trophies & Awards")
        r = s_co.post(f"{API}/bookings", json={
            "service_id": trophies["id"], "quantity": 1, "variant_id": "trophy-silver",
        })
        bid = r.json()["id"]
        # company_admin status update is silently dropped
        r2 = s_co.patch(f"{API}/bookings/{bid}", json={"status": "approved", "notes": "n"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "pending"  # status dropped
        assert r2.json()["notes"] == "n"
        # platform admin can change status
        r3 = s_pa.patch(f"{API}/bookings/{bid}", json={"status": "approved"})
        assert r3.status_code == 200 and r3.json()["status"] == "approved"
        # owner can delete
        r4 = s_co.delete(f"{API}/bookings/{bid}")
        assert r4.status_code == 200
        # gone
        assert s_co.get(f"{API}/bookings/{bid}").status_code == 404

    def test_booking_unauthenticated_forbidden(self):
        services = requests.get(f"{API}/services").json()
        sid = services[0]["id"]
        r = requests.post(f"{API}/bookings", json={"service_id": sid, "quantity": 1})
        assert r.status_code == 401


# ---------- Tenancy on events ----------
class TestEventTenancy:
    def test_company_admin_event_stamped(self, company_admin):
        s, me = company_admin
        r = s.post(f"{API}/events", json={"name": f"TEST_CoEv_{uuid.uuid4().hex[:5]}", "sport": "football"})
        assert r.status_code == 200, r.text
        ev = r.json()
        assert ev["company_id"] == me["company_id"]
        # filter
        r2 = requests.get(f"{API}/events", params={"company_id": me["company_id"]})
        ids = {e["id"] for e in r2.json()}
        assert ev["id"] in ids
        # cleanup
        s.delete(f"{API}/events/{ev['id']}")

    def test_company_admin_cannot_edit_other_company_event(self, company_admin, platform_admin):
        s_co, _ = company_admin
        s_pa, _ = platform_admin
        # Create a foreign company + admin via signup
        uniq = uuid.uuid4().hex[:6]
        s_other = requests.Session()
        signup = s_other.post(f"{API}/companies/signup", json={
            "company_name": f"TEST_Other_{uniq}",
            "admin_name": "Other",
            "admin_email": f"other_{uniq}@example.com",
            "admin_password": "pass",
        })
        assert signup.status_code == 200
        ev = s_other.post(f"{API}/events", json={"name": "TEST_OtherEv", "sport": "cricket"}).json()
        # Acme tries to patch/delete
        r_patch = s_co.patch(f"{API}/events/{ev['id']}", json={"venue": "hijack"})
        assert r_patch.status_code == 403
        r_del = s_co.delete(f"{API}/events/{ev['id']}")
        assert r_del.status_code == 403
        # cleanup as platform admin
        s_pa.delete(f"{API}/events/{ev['id']}")


# ---------- Stats ----------
class TestStats:
    def test_global_stats(self):
        r = requests.get(f"{API}/stats")
        assert r.status_code == 200
        d = r.json()
        for key in ["services", "companies", "bookings", "events"]:
            assert key in d and isinstance(d[key], int)
        assert d["services"] >= 7
        assert d["companies"] >= 1

    def test_company_stats_scoped(self, company_admin):
        s, me = company_admin
        r = s.get(f"{API}/stats/company")
        assert r.status_code == 200
        d = r.json()
        for k in ["events", "teams", "players", "bookings", "pending_bookings"]:
            assert k in d
        # Acme has 3 demo events
        assert d["events"] >= 3

    def test_company_stats_requires_company_admin(self, viewer):
        s, _ = viewer
        r = s.get(f"{API}/stats/company")
        assert r.status_code == 403
