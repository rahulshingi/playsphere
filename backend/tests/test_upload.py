"""Backend tests for POST /api/upload and GET /api/uploads/<filename>.

Authentication is via httpOnly cookie `access_token` (not Bearer header).
"""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com").rstrip("/")


def _login(session, email, password):
    """Login admin/vendor via /api/auth/login (cookie-based)."""
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert "access_token" in session.cookies, "access_token cookie not set"
    return r.json()


@pytest.fixture
def admin_session():
    s = requests.Session()
    _login(s, "admin@kreedanation.com", "admin123")
    return s


@pytest.fixture
def vendor_session():
    s = requests.Session()
    _login(s, "ravi@turf.in", "vendor123")
    return s


PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE426082"
)


# ---------- Auth & happy path ----------

class TestUploadAuth:
    def test_upload_without_auth_returns_401(self):
        # No cookie session
        r = requests.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("a.png", io.BytesIO(PNG_BYTES), "image/png")},
        )
        assert r.status_code == 401, f"expected 401, got {r.status_code} {r.text}"

    def test_upload_png_as_admin_returns_200(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("test.png", io.BytesIO(PNG_BYTES), "image/png")},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "url" in data and "filename" in data and "size" in data
        assert data["url"].startswith("/api/uploads/")
        assert data["filename"].endswith(".png")
        assert data["size"] == len(PNG_BYTES)
        # GET the served file
        get_r = requests.get(f"{BASE_URL}{data['url']}")
        assert get_r.status_code == 200
        assert get_r.headers.get("content-type", "").startswith("image/")
        assert get_r.content == PNG_BYTES

    def test_upload_as_vendor_returns_200(self, vendor_session):
        r = vendor_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("v.png", io.BytesIO(PNG_BYTES), "image/png")},
        )
        assert r.status_code == 200, r.text
        assert r.json()["url"].startswith("/api/uploads/")


# ---------- Validation ----------

class TestUploadValidation:
    def test_non_image_returns_400(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("x.txt", io.BytesIO(b"hello world"), "text/plain")},
        )
        assert r.status_code == 400, r.text
        assert "image" in r.text.lower()

    def test_oversized_file_returns_400(self, admin_session):
        big = b"\x00" * (5 * 1024 * 1024 + 10)  # 5MB + 10 bytes
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("big.png", io.BytesIO(big), "image/png")},
        )
        assert r.status_code == 400, r.text
        assert "too large" in r.text.lower()

    def test_jpeg_accepted(self, admin_session):
        # Minimal JPEG-typed payload (content_type is what backend checks)
        jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
        if False: jpeg = bytes.fromhex(
            "FFD8FFE000104A46494600010100000100010000FFDB0043000806060706050806070707"
            "0909080A0C140D0C0B0B0C1912130F141D1A1F1E1D1A1C1C20242E2720222C231C1C2837"
            "292C30313434341F27393D38323C2E333432FFC0000B080001000101011100FFC4001F00"
            "0001050101010101010000000000000000010203040506070809000A0BFFC4003510000201030302"
            "04030506050001000000000000000000010203040506070708090A0B11122131410551617181"
            "92A1B1C109233352636F1F00000FFDA0008010100003F00FBD0FFD9"
        )
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("a.jpg", io.BytesIO(jpeg), "image/jpeg")},
        )
        assert r.status_code == 200, r.text
        assert r.json()["filename"].endswith(".jpg") or r.json()["filename"].endswith(".jpeg")

    def test_webp_accepted(self, admin_session):
        # Minimal-ish webp header (won't be a valid image, but content_type is what's checked)
        webp = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 32
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("a.webp", io.BytesIO(webp), "image/webp")},
        )
        assert r.status_code == 200, r.text


# ---------- Static serving ----------

class TestStaticServing:
    def test_uploaded_file_served_with_image_content_type(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/upload",
            files={"file": ("served.png", io.BytesIO(PNG_BYTES), "image/png")},
        )
        assert r.status_code == 200
        url = r.json()["url"]
        get_r = requests.get(f"{BASE_URL}{url}")
        assert get_r.status_code == 200
        ct = get_r.headers.get("content-type", "")
        assert ct.startswith("image/"), f"unexpected content-type: {ct}"
