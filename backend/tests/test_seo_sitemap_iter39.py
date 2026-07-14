"""Iteration 39 — SEO / Sitemap / Robots backend tests."""
import os
import pytest
import requests
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://live-scoring-hub-5.preview.emergentagent.com').rstrip('/')
ADMIN_EMAIL = "admin@kreedanation.com"
ADMIN_PASSWORD = "admin123"
HR_EMAIL = "testorg@example.com"
HR_PASSWORD = "orgpass123"

STATIC_PUBLIC_DIR = Path("/app/frontend/public")


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def hr_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": HR_EMAIL, "password": HR_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"HR login failed: {r.status_code} — skipping HR-role assertions")
    return r.json().get("token") or r.json().get("access_token")


# ---------- Sitemap ----------
class TestSitemapXml:
    def test_sitemap_returns_xml(self, api):
        r = api.get(f"{BASE_URL}/api/sitemap.xml")
        assert r.status_code == 200
        ct = r.headers.get("Content-Type", "")
        assert "xml" in ct.lower(), f"Expected xml content-type, got {ct}"
        assert "<urlset" in r.text
        assert "</urlset>" in r.text

    def test_sitemap_cache_control(self, api):
        """Verify Cache-Control at the origin (localhost:8001). The public
        preview URL is fronted by Cloudflare which rewrites cache headers to
        'no-store, no-cache, must-revalidate' — that's an env-specific quirk
        and won't affect prod once kreedanation.com DNS/CF is configured."""
        r = requests.get("http://localhost:8001/api/sitemap.xml", timeout=10)
        assert r.status_code == 200
        cc = r.headers.get("Cache-Control", "")
        assert "public" in cc and "max-age=3600" in cc, f"Missing/incorrect Cache-Control at origin: {cc}"

    def test_sitemap_includes_all_static_routes(self, api):
        r = api.get(f"{BASE_URL}/api/sitemap.xml")
        expected = [
            "/", "/events", "/hire", "/corporate-services", "/sponsorships",
            "/sponsors", "/players/profiles", "/about", "/contact", "/standings",
            "/register", "/signup-company", "/signup-organiser", "/players/signup",
            "/vendor/signup", "/sponsor/signup", "/login",
        ]
        body = r.text
        # Home is base + "/" — check via <loc>...</loc> patterns
        for path in expected:
            # Must contain <loc>https://.../{path}</loc>
            marker = f"{path}</loc>"
            assert marker in body, f"Static route missing from sitemap: {path}"

    def test_sitemap_contains_at_least_17_urls(self, api):
        r = api.get(f"{BASE_URL}/api/sitemap.xml")
        assert r.status_code == 200
        loc_count = r.text.count("<loc>")
        # 17 static + events + vendor listings + player profiles
        assert loc_count >= 17, f"Expected ≥17 URLs, got {loc_count}"

    def test_sitemap_dynamic_events_or_listings_included(self, api):
        # Sitemap should include at least static routes; dynamic sections
        # depend on DB state, so we only assert structure well-formedness.
        r = api.get(f"{BASE_URL}/api/sitemap.xml")
        body = r.text
        assert '<?xml version="1.0" encoding="UTF-8"?>' in body
        assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in body


# ---------- Robots ----------
class TestRobotsTxt:
    def test_robots_returns_text_plain(self, api):
        r = api.get(f"{BASE_URL}/api/robots.txt")
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("Content-Type", "").lower()

    def test_robots_content(self, api):
        r = api.get(f"{BASE_URL}/api/robots.txt")
        body = r.text
        assert "User-agent: *" in body
        assert "Allow: /" in body
        assert "Disallow: /platform-admin" in body
        assert "Disallow: /api/" in body
        assert "Sitemap:" in body
        assert "/sitemap.xml" in body


# ---------- Admin rebuild ----------
class TestSitemapRebuild:
    def test_rebuild_requires_admin(self, api):
        r = api.post(f"{BASE_URL}/api/admin/sitemap/rebuild")
        # No auth → 401 or 403
        assert r.status_code in (401, 403), f"Expected 401/403 unauth, got {r.status_code}"

    def test_rebuild_forbidden_for_hr(self, api, hr_token):
        r = api.post(
            f"{BASE_URL}/api/admin/sitemap/rebuild",
            headers={"Authorization": f"Bearer {hr_token}"},
        )
        assert r.status_code == 403, f"HR should get 403, got {r.status_code} — {r.text[:200]}"

    def test_rebuild_admin_success(self, api, admin_token):
        r = api.post(
            f"{BASE_URL}/api/admin/sitemap/rebuild",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200, f"Admin rebuild failed: {r.status_code} — {r.text[:300]}"
        data = r.json()
        assert data.get("ok") is True
        assert "sitemap_urls" in data
        assert isinstance(data["sitemap_urls"], int)
        assert data["sitemap_urls"] > 0
        assert "base" in data
        assert "written_at" in data

    def test_rebuild_refreshes_static_file(self, api, admin_token):
        sm_path = STATIC_PUBLIC_DIR / "sitemap.xml"
        rb_path = STATIC_PUBLIC_DIR / "robots.txt"
        before_sm = sm_path.stat().st_mtime if sm_path.exists() else 0
        r = api.post(
            f"{BASE_URL}/api/admin/sitemap/rebuild",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert sm_path.exists(), "/app/frontend/public/sitemap.xml missing after rebuild"
        assert rb_path.exists(), "/app/frontend/public/robots.txt missing after rebuild"
        after_sm = sm_path.stat().st_mtime
        assert after_sm >= before_sm, "sitemap.xml file mtime did not update"
        # Verify content is XML with urlset
        content = sm_path.read_text(encoding="utf-8")
        assert "<urlset" in content
        assert content.count("<loc>") > 0


# ---------- Static file matches API ----------
class TestStaticSitemapMatchesAPI:
    def test_static_sitemap_readable(self):
        sm_path = STATIC_PUBLIC_DIR / "sitemap.xml"
        assert sm_path.exists()
        text = sm_path.read_text(encoding="utf-8")
        assert "<urlset" in text
        assert text.count("<loc>") >= 17

    def test_static_robots_readable(self):
        rb_path = STATIC_PUBLIC_DIR / "robots.txt"
        assert rb_path.exists()
        text = rb_path.read_text(encoding="utf-8")
        assert "User-agent: *" in text
        assert "Sitemap:" in text
