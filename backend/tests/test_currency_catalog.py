"""
PlaySphere currency & catalog expansion tests (Iteration 3).
- 17 services seeded with mix of USD & INR
- Service.currency field present; PATCH updates currency
- Booking auto-populates currency from service
- seed_services idempotent (no dupes if called repeatedly via service count stable)
- Per-service required config fields present for new services
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@playsphere.com"
ADMIN_PASSWORD = "admin123"
ACME_EMAIL = "acme@example.com"
ACME_PASSWORD = "acme123"

EXPECTED_INR = {"Anchor / MC", "DJ & Sound System", "Catering & Refreshments",
                "Banners & Venue Branding", "Match Officials & Umpires"}
EXPECTED_USD_NEW = {"Professional Photography", "Videography & Highlights Reel",
                    "Drone Aerial Coverage", "Custom Medals", "First Aid & Paramedic Stand"}


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="module")
def admin_s():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def acme_s():
    return _login(ACME_EMAIL, ACME_PASSWORD)


@pytest.fixture(scope="module")
def all_services():
    r = requests.get(f"{API}/services")
    assert r.status_code == 200
    return r.json()


# ---------- Catalog count & currency mix ----------
class TestServicesCatalog:
    def test_seed_has_17_services(self, all_services):
        names = {s["name"] for s in all_services}
        # Idempotent: should be exactly 17 well-known seeds (DB may also contain TEST_ created services)
        seeded = [s for s in all_services if not s["name"].startswith("TEST_")]
        assert len(seeded) >= 17, f"Expected >=17 seeded services, got {len(seeded)}: {sorted(names)}"

    def test_inr_services_present(self, all_services):
        names_currency = {s["name"]: s["currency"] for s in all_services}
        for n in EXPECTED_INR:
            assert n in names_currency, f"Missing INR service: {n}"
            assert names_currency[n] == "INR", f"{n} currency expected INR got {names_currency[n]}"

    def test_usd_new_services_present(self, all_services):
        names_currency = {s["name"]: s["currency"] for s in all_services}
        for n in EXPECTED_USD_NEW:
            assert n in names_currency, f"Missing USD service: {n}"
            assert names_currency[n] == "USD", f"{n} currency expected USD got {names_currency[n]}"

    def test_each_service_has_currency_field(self, all_services):
        for s in all_services:
            assert "currency" in s
            assert s["currency"] in {"USD", "INR"}


# ---------- Service required config fields ----------
class TestNewServiceConfig:
    def _service(self, all_services, name):
        m = [s for s in all_services if s["name"] == name]
        assert m, f"No service named {name}"
        return m[0]

    def _keys(self, svc):
        return {f["key"] for f in svc.get("config_fields", [])}

    def test_photography_fields(self, all_services):
        s = self._service(all_services, "Professional Photography")
        assert {"photographers", "hours", "deliverable"}.issubset(self._keys(s))

    def test_videography_fields(self, all_services):
        s = self._service(all_services, "Videography & Highlights Reel")
        assert {"cameras", "reel_length_minutes", "voiceover", "turnaround"}.issubset(self._keys(s))

    def test_drone_fields(self, all_services):
        s = self._service(all_services, "Drone Aerial Coverage")
        assert "duration_hours" in self._keys(s)

    def test_anchor_fields(self, all_services):
        s = self._service(all_services, "Anchor / MC")
        assert {"language", "hours"}.issubset(self._keys(s))
        assert s["currency"] == "INR"
        assert s["base_price"] == 12000

    def test_dj_fields(self, all_services):
        s = self._service(all_services, "DJ & Sound System")
        assert {"venue_size", "wireless_mics"}.issubset(self._keys(s))

    def test_catering_fields(self, all_services):
        s = self._service(all_services, "Catering & Refreshments")
        assert {"headcount", "meal_type", "preference"}.issubset(self._keys(s))

    def test_medals_fields_and_variants(self, all_services):
        s = self._service(all_services, "Custom Medals")
        assert {"diameter_mm", "ribbon_color"}.issubset(self._keys(s))
        vids = {v["id"] for v in s.get("variants", [])}
        assert {"medal-gold", "medal-silver", "medal-bronze"}.issubset(vids)

    def test_banners_fields_and_variants(self, all_services):
        s = self._service(all_services, "Banners & Venue Branding")
        keys = self._keys(s)
        assert {"size", "material"}.issubset(keys)
        assert len(s.get("variants", [])) >= 3

    def test_first_aid_fields(self, all_services):
        s = self._service(all_services, "First Aid & Paramedic Stand")
        assert {"paramedics", "hours"}.issubset(self._keys(s))

    def test_match_officials_fields(self, all_services):
        s = self._service(all_services, "Match Officials & Umpires")
        assert {"sport", "officials_count", "certification"}.issubset(self._keys(s))


# ---------- PATCH service currency ----------
class TestServiceCurrencyPatch:
    def test_admin_can_patch_currency(self, admin_s):
        # create temp service then change currency
        create = admin_s.post(f"{API}/services", json={
            "name": f"TEST_CurrencyToggle_{os.urandom(3).hex()}",
            "category": "other", "description": "tmp",
            "base_price": 100.0, "currency": "USD",
        })
        assert create.status_code == 200, create.text
        sid = create.json()["id"]
        try:
            r = admin_s.patch(f"{API}/services/{sid}", json={"currency": "INR"})
            assert r.status_code == 200
            assert r.json()["currency"] == "INR"
            # GET to verify persistence
            g = requests.get(f"{API}/services/{sid}")
            assert g.json()["currency"] == "INR"
            # back to USD
            r2 = admin_s.patch(f"{API}/services/{sid}", json={"currency": "USD"})
            assert r2.json()["currency"] == "USD"
        finally:
            admin_s.delete(f"{API}/services/{sid}")


# ---------- Booking currency propagation ----------
class TestBookingCurrency:
    def test_booking_inr_service_carries_inr_currency(self, acme_s, all_services):
        anchor = next((s for s in all_services if s["name"] == "Anchor / MC"), None)
        assert anchor, "Anchor / MC service not found"
        assert anchor["currency"] == "INR"
        assert anchor["base_price"] == 12000

        r = acme_s.post(f"{API}/bookings", json={
            "service_id": anchor["id"], "quantity": 1,
            "notes": "TEST_currency_inr",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        try:
            assert b["currency"] == "INR"
            assert b["total_price"] == 12000
            # verify persistence via GET
            g = acme_s.get(f"{API}/bookings/{b['id']}")
            assert g.status_code == 200
            assert g.json()["currency"] == "INR"
        finally:
            acme_s.delete(f"{API}/bookings/{b['id']}")

    def test_booking_usd_service_carries_usd(self, acme_s, all_services):
        photo = next((s for s in all_services if s["name"] == "Professional Photography"), None)
        assert photo and photo["currency"] == "USD"

        r = acme_s.post(f"{API}/bookings", json={
            "service_id": photo["id"], "quantity": 1, "notes": "TEST_currency_usd",
        })
        assert r.status_code == 200, r.text
        b = r.json()
        try:
            assert b["currency"] == "USD"
            assert b["total_price"] == 199.0
        finally:
            acme_s.delete(f"{API}/bookings/{b['id']}")


# ---------- Idempotent seed: calling list twice returns same count ----------
class TestIdempotentSeed:
    def test_service_count_stable(self):
        a = requests.get(f"{API}/services").json()
        b = requests.get(f"{API}/services").json()
        names_a = sorted([s["name"] for s in a])
        names_b = sorted([s["name"] for s in b])
        assert names_a == names_b
        # No duplicate names in seeded catalog
        seeded = [s["name"] for s in a if not s["name"].startswith("TEST_")]
        assert len(seeded) == len(set(seeded)), "Duplicate seeded service names found"
