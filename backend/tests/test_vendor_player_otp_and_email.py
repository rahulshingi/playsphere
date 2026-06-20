"""Backend tests for iteration 14 (vendor + player signup OTP + SendGrid forgot-password).

Covers:
- Vendor & Player request-otp accepts any email (no corporate-only block here).
- Vendor & Player signup require + validate OTP, increment attempts, lock at 5.
- Valid OTP completes signup: creates user (email_verified=true), vendor/player doc, cookie set, OTP marked verified.
- Forgot-password: admin email -> SendGrid 202 + sent log + {ok:true}; non-existent -> {ok:true} no sent log; /api/players/forgot-password works too.
- Regression: company signup OTP flow (gmail blocked, corporate accepted) + admin login.
"""
import os
import re
import time
import uuid
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _otp_for(db, collection, email):
    return _run(db[collection].find_one({"email": email}, {"_id": 0}))


def _set_otp(db, collection, email, patch):
    _run(db[collection].update_one({"email": email}, {"$set": patch}))


def _cleanup_vendor(db, email):
    _run(db.users.delete_many({"email": email}))
    _run(db.vendors.delete_many({"email": email}))
    _run(db.vendor_signup_otps.delete_many({"email": email}))


def _cleanup_player(db, email, mobile=None):
    _run(db.users.delete_many({"email": email}))
    _run(db.player_profiles.delete_many({"email": email}))
    _run(db.player_signup_otps.delete_many({"email": email}))
    if mobile:
        _run(db.player_profiles.delete_many({"mobile": mobile}))
        _run(db.users.delete_many({"mobile": mobile}))


def _rand_mobile():
    import random
    return "+9199" + "".join(str(random.randint(0, 9)) for _ in range(8))


@pytest.fixture
def s():
    return requests.Session()


# ===================== VENDOR =====================

class TestVendorOtp:
    @pytest.mark.parametrize("provider", ["gmail.com", "yahoo.com", "qa-vendor.io"])
    def test_request_otp_accepts_any_domain(self, s, db, provider):
        email = f"vendor-qa-{uuid.uuid4().hex[:6]}@{provider}"
        try:
            r = s.post(f"{API}/vendors/signup/request-otp", json={
                "business_name": "Vendor QA", "email": email,
            })
            assert r.status_code == 200, r.text
            data = r.json()
            assert data == {"ok": True, "expires_in": 600, "email": email}
            rec = _otp_for(db, "vendor_signup_otps", email)
            assert rec and rec["otp"].isdigit() and len(rec["otp"]) == 6
            assert rec["attempts"] == 0 and rec["verified"] is False
        finally:
            _cleanup_vendor(db, email)

    def test_signup_missing_otp_returns_400(self, s, db):
        email = f"vendor-qa-{uuid.uuid4().hex[:6]}@example.com"
        try:
            r = s.post(f"{API}/vendors/signup/request-otp", json={
                "business_name": "VQ", "email": email,
            })
            assert r.status_code == 200
            r2 = s.post(f"{API}/vendors/signup", json={
                "business_name": "VQ", "vendor_type": "ground", "contact_name": "Q",
                "mobile": "+919800000001", "email": email, "password": "secret123",
                "city": "Bangalore",
            })
            assert r2.status_code == 400
            assert "verification code is required" in r2.json()["detail"].lower()
        finally:
            _cleanup_vendor(db, email)

    def test_wrong_otp_increments_and_locks_at_5(self, s, db):
        email = f"vendor-qa-{uuid.uuid4().hex[:6]}@example.com"
        try:
            r = s.post(f"{API}/vendors/signup/request-otp", json={
                "business_name": "VQ2", "email": email,
            })
            assert r.status_code == 200
            body = {
                "business_name": "VQ2", "vendor_type": "ground", "contact_name": "Q",
                "mobile": "+919800000002", "email": email, "password": "secret123",
                "city": "Bangalore", "otp": "000000",
            }
            r2 = s.post(f"{API}/vendors/signup", json=body)
            if r2.status_code == 200:
                pytest.skip("Lucky OTP collision")
            assert r2.status_code == 400
            assert "incorrect verification code" in r2.json()["detail"].lower()
            assert _otp_for(db, "vendor_signup_otps", email)["attempts"] == 1
            # Bump to 5 then 6th -> 429
            _set_otp(db, "vendor_signup_otps", email, {"attempts": 5})
            r3 = s.post(f"{API}/vendors/signup", json=body)
            assert r3.status_code == 429
            assert "too many" in r3.json()["detail"].lower()
        finally:
            _cleanup_vendor(db, email)

    def test_valid_otp_creates_vendor_and_sets_cookie(self, s, db):
        email = f"vendor-qa-{uuid.uuid4().hex[:6]}@example.com"
        try:
            r = s.post(f"{API}/vendors/signup/request-otp", json={
                "business_name": "QA Vendor Inc", "email": email,
            })
            assert r.status_code == 200, r.text
            otp = _otp_for(db, "vendor_signup_otps", email)["otp"]
            mobile = _rand_mobile()
            r2 = s.post(f"{API}/vendors/signup", json={
                "business_name": "QA Vendor Inc", "vendor_type": "ground",
                "contact_name": "Vendor Q", "mobile": mobile, "email": email,
                "password": "vendor123", "city": "Bangalore", "otp": otp,
            })
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["email"] == email
            assert data["role"] == "vendor"
            assert "access_token" in s.cookies.get_dict()
            # OTP marked verified
            assert _otp_for(db, "vendor_signup_otps", email)["verified"] is True
            # Vendor + User docs
            v = _run(db.vendors.find_one({"email": email}, {"_id": 0}))
            assert v and v["business_name"] == "QA Vendor Inc"
            u = _run(db.users.find_one({"email": email}, {"_id": 0}))
            assert u and u["role"] == "vendor" and u.get("email_verified") is True
        finally:
            _cleanup_vendor(db, email)


# ===================== PLAYER =====================

class TestPlayerOtp:
    def test_request_otp_accepts_any_domain(self, s, db):
        email = f"player-qa-{uuid.uuid4().hex[:6]}@gmail.com"
        try:
            r = s.post(f"{API}/players/signup/request-otp", json={
                "name": "Player QA", "email": email,
            })
            assert r.status_code == 200, r.text
            assert r.json() == {"ok": True, "expires_in": 600, "email": email}
            rec = _otp_for(db, "player_signup_otps", email)
            assert rec and rec["otp"].isdigit() and len(rec["otp"]) == 6
        finally:
            _cleanup_player(db, email)

    def test_register_requires_email_and_otp(self, s, db):
        mobile = _rand_mobile()
        # Missing email -> 422 pydantic (EmailStr is required)
        r = s.post(f"{API}/players/register", json={
            "name": "QA", "mobile": mobile, "password": "player123",
        })
        assert r.status_code in (400, 422), r.text
        # With email but no OTP -> 400 explicit
        email = f"player-qa-{uuid.uuid4().hex[:6]}@example.com"
        try:
            # First request OTP so the user-doesn't-exist check passes
            r1 = s.post(f"{API}/players/signup/request-otp", json={"name": "QA", "email": email})
            assert r1.status_code == 200
            r2 = s.post(f"{API}/players/register", json={
                "name": "QA", "mobile": mobile, "password": "player123", "email": email,
            })
            assert r2.status_code == 400
            assert "verification code is required" in r2.json()["detail"].lower()
        finally:
            _cleanup_player(db, email, mobile)

    def test_valid_otp_creates_player(self, s, db):
        email = f"player-qa-{uuid.uuid4().hex[:6]}@example.com"
        mobile = _rand_mobile()
        try:
            r = s.post(f"{API}/players/signup/request-otp", json={
                "name": "Player QA", "email": email,
            })
            assert r.status_code == 200
            otp = _otp_for(db, "player_signup_otps", email)["otp"]
            r2 = s.post(f"{API}/players/register", json={
                "name": "Player QA", "mobile": mobile, "email": email,
                "password": "player123", "otp": otp,
            })
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["role"] == "player"
            assert data["email"] == email
            assert "access_token" in s.cookies.get_dict()
            assert _otp_for(db, "player_signup_otps", email)["verified"] is True
            u = _run(db.users.find_one({"email": email}, {"_id": 0}))
            assert u and u.get("email_verified") is True
            p = _run(db.player_profiles.find_one({"email": email}, {"_id": 0}))
            assert p is not None
        finally:
            _cleanup_player(db, email, mobile)


# ===================== FORGOT PASSWORD =====================

LOG_PATH = "/var/log/supervisor/backend.err.log"


def _read_log_tail(path=LOG_PATH, bytes_back=20000):
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            f.seek(max(0, size - bytes_back))
            return f.read().decode("utf-8", errors="ignore")
    except FileNotFoundError:
        return ""


class TestForgotPassword:
    def test_admin_forgot_password_sends_email(self, s):
        # Read log size up-front so we only inspect new content
        before = len(_read_log_tail())
        r = s.post(f"{API}/auth/forgot-password", json={"email": "admin@kreedanation.com"})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}
        time.sleep(2)
        tail = _read_log_tail()
        new_log = tail[before:] if len(tail) > before else tail
        # Should see kreeda.email "Email sent" + kreeda.routes.auth "PASSWORD RESET EMAIL sent"
        assert "Email sent" in new_log and "admin@kreedanation.com" in new_log, \
            f"Expected 'Email sent' for admin in log, got: ...{new_log[-1500:]}"
        assert "status=202" in new_log or re.search(r"status=20\d", new_log), \
            f"Expected SendGrid 2xx status in log, got: ...{new_log[-1500:]}"
        assert "PASSWORD RESET EMAIL sent for admin@kreedanation.com" in new_log, \
            f"Expected 'PASSWORD RESET EMAIL sent' from kreeda.routes.auth, got: ...{new_log[-1500:]}"
        assert "non-2xx" not in new_log

    def test_nonexistent_email_no_leak(self, s):
        before = len(_read_log_tail())
        ghost = f"ghost-{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/forgot-password", json={"email": ghost})
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        time.sleep(1)
        tail = _read_log_tail()
        new_log = tail[before:] if len(tail) > before else tail
        # Should NOT see an "Email sent" / "PASSWORD RESET EMAIL sent" line for this email
        assert f"Email sent: to={ghost}" not in new_log
        assert f"PASSWORD RESET EMAIL sent for {ghost}" not in new_log

    def test_players_forgot_password_works(self, s):
        # Just verify the alias route returns 200 + ok for admin email
        r = s.post(f"{API}/players/forgot-password", json={"email": "admin@kreedanation.com"})
        assert r.status_code == 200, r.text
        assert r.json() == {"ok": True}


# ===================== REGRESSION =====================

class TestRegression:
    def test_admin_login_still_works(self, s):
        r = s.post(f"{API}/auth/login", json={
            "email": "admin@kreedanation.com", "password": "admin123",
        })
        assert r.status_code == 200, r.text
        assert r.json()["role"] in ("platform_admin", "admin")

    def test_company_signup_still_blocks_gmail(self, s):
        r = s.post(f"{API}/companies/signup/request-otp", json={
            "company_name": "QA Co", "admin_email": f"qa-{uuid.uuid4().hex[:6]}@gmail.com",
        })
        assert r.status_code == 400
        assert "official company email" in r.json()["detail"].lower()

    def test_company_signup_corporate_otp_still_works(self, s, db):
        email = f"qa-{uuid.uuid4().hex[:6]}@iter14corp.io"
        try:
            r = s.post(f"{API}/companies/signup/request-otp", json={
                "company_name": "Iter14 Corp", "admin_email": email,
            })
            assert r.status_code == 200, r.text
            otp = _run(db.company_signup_otps.find_one({"email": email}, {"_id": 0}))["otp"]
            r2 = s.post(f"{API}/companies/signup", json={
                "company_name": "Iter14 Corp", "admin_name": "QA",
                "admin_email": email, "admin_password": "secret123", "otp": otp,
            })
            assert r2.status_code == 200, r2.text
            assert r2.json()["role"] == "company_admin"
        finally:
            _run(db.users.delete_many({"email": email}))
            _run(db.company_signup_otps.delete_many({"email": email}))
            _run(db.companies.delete_many({"slug": {"$regex": "^iter14-corp"}}))
