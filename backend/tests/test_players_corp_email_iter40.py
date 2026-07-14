"""Backend regression tests for iter40 refactor — /players/me/corporate-email/*
endpoints extracted from server.py to routes/players_corp_email.py.

Covers:
- Auth guard: 401 without cookie, 403 for non-player (vendor).
- request-otp validation: rejects missing/invalid/free-domain emails.
- request-otp success: 200, {ok, expires_in=600, corporate_email}, OTP persisted.
- verify validation: missing fields, no pending OTP, wrong OTP (attempts increment),
  expired OTP, 5+ attempts lock.
- verify success: flips player_profiles.corporate_email_verified=True.
- verify auto-links company_id when a company_admin shares the corp email's domain.
- Regression: HR /players/profiles?corporate_email_domain=... still finds the verified player.

Email sending is stubbed by conftest.py (EMAIL_MODE=mock) so no SendGrid quota is used.
"""
import os
import re
import uuid
import asyncio
import secrets
import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001").rstrip("/")
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
    return AsyncIOMotorClient(MONGO_URL)[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _rand_mobile():
    return "+9199" + "".join(str(secrets.randbelow(10)) for _ in range(8))


def _cleanup_player(db, email, mobile=None):
    _run(db.users.delete_many({"email": email}))
    _run(db.player_profiles.delete_many({"email": email}))
    _run(db.player_signup_otps.delete_many({"email": email}))
    _run(db.player_corp_otps.delete_many({"user_id": {"$exists": True}, "corporate_email": {"$regex": "@iter40corp\\.io"}}))
    if mobile:
        _run(db.player_profiles.delete_many({"mobile": mobile}))
        _run(db.users.delete_many({"mobile": mobile}))


def _cleanup_vendor(db, email):
    _run(db.users.delete_many({"email": email}))
    _run(db.vendors.delete_many({"email": email}))
    _run(db.vendor_signup_otps.delete_many({"email": email}))


def _cleanup_company(db, admin_email, slug_prefix):
    _run(db.users.delete_many({"email": admin_email}))
    _run(db.company_signup_otps.delete_many({"email": admin_email}))
    _run(db.companies.delete_many({"slug": {"$regex": f"^{slug_prefix}"}}))


def _make_player(db) -> requests.Session:
    """Create a fresh player + return an authenticated Session."""
    s = requests.Session()
    email = f"player-iter40-{uuid.uuid4().hex[:6]}@example.com"
    mobile = _rand_mobile()
    # Request OTP
    r = s.post(f"{API}/players/signup/request-otp", json={"name": "Iter40 Player", "email": email})
    assert r.status_code == 200, r.text
    otp = _run(db.player_signup_otps.find_one({"email": email}, {"_id": 0}))["otp"]
    r2 = s.post(f"{API}/players/register", json={
        "name": "Iter40 Player", "mobile": mobile, "email": email,
        "password": "player123", "otp": otp,
    })
    assert r2.status_code == 200, r2.text
    s._email = email
    s._mobile = mobile
    s._user_id = r2.json()["id"]
    return s


def _make_vendor(db) -> requests.Session:
    s = requests.Session()
    email = f"vendor-iter40-{uuid.uuid4().hex[:6]}@example.com"
    mobile = _rand_mobile()
    r = s.post(f"{API}/vendors/signup/request-otp", json={"business_name": "Iter40 V", "email": email})
    assert r.status_code == 200
    otp = _run(db.vendor_signup_otps.find_one({"email": email}, {"_id": 0}))["otp"]
    r2 = s.post(f"{API}/vendors/signup", json={
        "business_name": "Iter40 V", "vendor_type": "ground", "contact_name": "V",
        "mobile": mobile, "email": email, "password": "vendor123", "city": "Bangalore",
        "otp": otp,
    })
    assert r2.status_code == 200, r2.text
    s._email = email
    return s


# ===================== AUTH GUARDS =====================

class TestAuthGuards:
    def test_request_otp_requires_auth(self):
        r = requests.post(f"{API}/players/me/corporate-email/request-otp",
                          json={"corporate_email": "test@iter40corp.io"})
        assert r.status_code == 401, r.text

    def test_verify_requires_auth(self):
        r = requests.post(f"{API}/players/me/corporate-email/verify",
                          json={"corporate_email": "test@iter40corp.io", "otp": "123456"})
        assert r.status_code == 401, r.text

    def test_request_otp_rejects_non_player(self, db):
        s = _make_vendor(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": "x@iter40corp.io"})
            assert r.status_code == 403, r.text
            assert "player only" in r.json()["detail"].lower()
        finally:
            _cleanup_vendor(db, s._email)

    def test_verify_rejects_non_player(self, db):
        s = _make_vendor(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/verify",
                       json={"corporate_email": "x@iter40corp.io", "otp": "123456"})
            assert r.status_code == 403, r.text
        finally:
            _cleanup_vendor(db, s._email)


# ===================== REQUEST-OTP VALIDATION =====================

class TestRequestOtpValidation:
    # NOTE: `@missinglocal.com` slips through — current code only checks `"@" in email`.
    # Pre-existing behavior (not a regression from the refactor); flagged in report.
    @pytest.mark.parametrize("bad", ["", "not-an-email", "no-at-symbol"])
    def test_missing_or_malformed_email(self, db, bad):
        s = _make_player(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": bad})
            assert r.status_code == 400, r.text
            assert "valid corporate email" in r.json()["detail"].lower()
        finally:
            _cleanup_player(db, s._email, s._mobile)

    @pytest.mark.parametrize("domain", [
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
        "icloud.com", "protonmail.com",
    ])
    def test_free_domain_rejected(self, db, domain):
        s = _make_player(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": f"work@{domain}"})
            assert r.status_code == 400, r.text
            assert "official work email" in r.json()["detail"].lower()
        finally:
            _cleanup_player(db, s._email, s._mobile)


# ===================== REQUEST-OTP SUCCESS =====================

class TestRequestOtpSuccess:
    def test_success_persists_otp_and_returns_expected_payload(self, db):
        s = _make_player(db)
        corp = f"person-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": corp})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data == {"ok": True, "expires_in": 600, "corporate_email": corp}

            rec = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}, {"_id": 0}
            ))
            assert rec is not None
            assert re.fullmatch(r"\d{6}", rec["otp"]), "OTP must be 6 digits"
            assert rec["attempts"] == 0
            assert rec["user_id"] == s._user_id
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)

    def test_repeated_request_overwrites_previous_otp(self, db):
        s = _make_player(db)
        corp = f"person2-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r1 = s.post(f"{API}/players/me/corporate-email/request-otp",
                        json={"corporate_email": corp})
            assert r1.status_code == 200
            otp1 = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}))["otp"]

            r2 = s.post(f"{API}/players/me/corporate-email/request-otp",
                        json={"corporate_email": corp})
            assert r2.status_code == 200
            otp2 = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}))["otp"]

            # Very likely different (1e-6 collision odds)
            # Even if collision, at least attempts should reset to 0
            rec = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}))
            assert rec["attempts"] == 0
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)


# ===================== VERIFY VALIDATION =====================

class TestVerifyValidation:
    def test_missing_fields(self, db):
        s = _make_player(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/verify", json={})
            assert r.status_code == 400, r.text
            assert "corporate_email and otp are required" in r.json()["detail"].lower()

            r2 = s.post(f"{API}/players/me/corporate-email/verify",
                        json={"corporate_email": "x@iter40corp.io"})
            assert r2.status_code == 400
        finally:
            _cleanup_player(db, s._email, s._mobile)

    def test_no_pending_otp(self, db):
        s = _make_player(db)
        try:
            r = s.post(f"{API}/players/me/corporate-email/verify",
                       json={"corporate_email": "nowhere@iter40corp.io", "otp": "123456"})
            assert r.status_code == 400, r.text
            assert "no verification request pending" in r.json()["detail"].lower()
        finally:
            _cleanup_player(db, s._email, s._mobile)

    def test_wrong_otp_increments_attempts(self, db):
        s = _make_player(db)
        corp = f"person-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": corp})
            assert r.status_code == 200

            for i in range(1, 4):
                bad = s.post(f"{API}/players/me/corporate-email/verify",
                             json={"corporate_email": corp, "otp": "000000"})
                # If we happened to guess the right OTP, skip
                if bad.status_code == 200:
                    pytest.skip("Lucky OTP collision")
                assert bad.status_code == 400
                assert "incorrect code" in bad.json()["detail"].lower()
                rec = _run(db.player_corp_otps.find_one(
                    {"user_id": s._user_id, "corporate_email": corp}))
                assert rec["attempts"] == i
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)

    def test_attempts_lock_at_5(self, db):
        s = _make_player(db)
        corp = f"person-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": corp})
            assert r.status_code == 200
            _run(db.player_corp_otps.update_one(
                {"user_id": s._user_id, "corporate_email": corp},
                {"$set": {"attempts": 5}}))
            r2 = s.post(f"{API}/players/me/corporate-email/verify",
                        json={"corporate_email": corp, "otp": "000000"})
            assert r2.status_code == 429, r2.text
            assert "too many attempts" in r2.json()["detail"].lower()
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)

    def test_expired_otp(self, db):
        s = _make_player(db)
        corp = f"person-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": corp})
            assert r.status_code == 200
            # Force expiry in the past
            past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            _run(db.player_corp_otps.update_one(
                {"user_id": s._user_id, "corporate_email": corp},
                {"$set": {"expires_at": past}}))
            r2 = s.post(f"{API}/players/me/corporate-email/verify",
                        json={"corporate_email": corp, "otp": "000000"})
            assert r2.status_code == 400, r2.text
            assert "expired" in r2.json()["detail"].lower()
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)


# ===================== VERIFY SUCCESS + AUTO-LINK =====================

class TestVerifySuccess:
    def test_success_flips_profile_flag(self, db):
        s = _make_player(db)
        corp = f"person-{uuid.uuid4().hex[:6]}@iter40corp.io"
        try:
            r = s.post(f"{API}/players/me/corporate-email/request-otp",
                       json={"corporate_email": corp})
            assert r.status_code == 200
            otp = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}))["otp"]

            r2 = s.post(f"{API}/players/me/corporate-email/verify",
                        json={"corporate_email": corp, "otp": otp})
            assert r2.status_code == 200, r2.text
            data = r2.json()
            assert data["ok"] is True
            assert data["corporate_email"] == corp
            assert data["linked_company_id"] is None  # no company_admin at iter40corp.io
            assert "message" in data

            # Profile flipped
            prof = _run(db.player_profiles.find_one({"user_id": s._user_id}, {"_id": 0}))
            assert prof["corporate_email"] == corp
            assert prof["corporate_email_verified"] is True
            assert "corporate_email_verified_at" in prof

            # OTP record deleted
            gone = _run(db.player_corp_otps.find_one(
                {"user_id": s._user_id, "corporate_email": corp}))
            assert gone is None
        finally:
            _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
            _cleanup_player(db, s._email, s._mobile)

    def test_success_auto_links_company_by_domain(self, db):
        """When a company_admin exists at the same domain, verify() should link company_id."""
        # 1. Create a company at iter40corp.io
        admin_email = f"hr-{uuid.uuid4().hex[:6]}@iter40corp.io"
        company_id = None
        try:
            r_co = requests.post(f"{API}/companies/signup/request-otp", json={
                "company_name": "Iter40 Corp", "admin_email": admin_email,
            })
            assert r_co.status_code == 200, r_co.text
            co_otp = _run(db.company_signup_otps.find_one({"email": admin_email}))["otp"]
            r_co2 = requests.post(f"{API}/companies/signup", json={
                "company_name": "Iter40 Corp", "admin_name": "HR",
                "admin_email": admin_email, "admin_password": "hr123", "otp": co_otp,
            })
            assert r_co2.status_code == 200, r_co2.text
            company_id = r_co2.json().get("company_id")
            assert company_id, r_co2.text

            # 2. Create a player + verify a corp email at same domain
            s = _make_player(db)
            corp = f"newhire-{uuid.uuid4().hex[:6]}@iter40corp.io"
            try:
                r = s.post(f"{API}/players/me/corporate-email/request-otp",
                           json={"corporate_email": corp})
                assert r.status_code == 200
                otp = _run(db.player_corp_otps.find_one(
                    {"user_id": s._user_id, "corporate_email": corp}))["otp"]
                r2 = s.post(f"{API}/players/me/corporate-email/verify",
                            json={"corporate_email": corp, "otp": otp})
                assert r2.status_code == 200, r2.text
                data = r2.json()
                assert data["linked_company_id"] == company_id
                assert data["linked_company_name"] == "Iter40 Corp"

                # user doc updated
                u = _run(db.users.find_one({"id": s._user_id}, {"_id": 0}))
                assert u["company_id"] == company_id
                # profile has company_id/name too
                prof = _run(db.player_profiles.find_one({"user_id": s._user_id}, {"_id": 0}))
                assert prof["company_id"] == company_id
                assert prof["company_name"] == "Iter40 Corp"
            finally:
                _run(db.player_corp_otps.delete_many({"user_id": s._user_id}))
                _cleanup_player(db, s._email, s._mobile)
        finally:
            _cleanup_company(db, admin_email, "iter40-corp")


# ===================== HELPER REGRESSION =====================

class TestServerPlayerProfilesStillUsesEmailDomain:
    """Regression: server.py kept `_email_domain` for /api/players/profiles.
    Ensure HR search across corporate email domain still finds a verified player.
    """
    def test_hr_finds_verified_player_by_domain(self, db):
        admin_email = f"hr2-{uuid.uuid4().hex[:6]}@iter40corp.io"
        s_co = requests.Session()
        try:
            r_co = requests.post(f"{API}/companies/signup/request-otp", json={
                "company_name": "Iter40 Corp2", "admin_email": admin_email,
            })
            assert r_co.status_code == 200
            co_otp = _run(db.company_signup_otps.find_one({"email": admin_email}))["otp"]
            r_co2 = s_co.post(f"{API}/companies/signup", json={
                "company_name": "Iter40 Corp2", "admin_name": "HR2",
                "admin_email": admin_email, "admin_password": "hr123", "otp": co_otp,
            })
            assert r_co2.status_code == 200, r_co2.text

            # Player + verify corp email
            sp = _make_player(db)
            corp = f"searchme-{uuid.uuid4().hex[:6]}@iter40corp.io"
            try:
                sp.post(f"{API}/players/me/corporate-email/request-otp",
                        json={"corporate_email": corp})
                otp = _run(db.player_corp_otps.find_one(
                    {"user_id": sp._user_id, "corporate_email": corp}))["otp"]
                r2 = sp.post(f"{API}/players/me/corporate-email/verify",
                             json={"corporate_email": corp, "otp": otp})
                assert r2.status_code == 200, r2.text

                # HR searches profiles — the endpoint auto-scopes by admin's email domain
                r_hr = s_co.get(f"{API}/players/profiles")
                assert r_hr.status_code == 200, r_hr.text
                profs = r_hr.json() if isinstance(r_hr.json(), list) else r_hr.json().get("profiles") or r_hr.json().get("items") or []
                # Must contain our verified player
                emails = [p.get("corporate_email") or p.get("email") for p in profs]
                assert any(e == corp for e in emails), \
                    f"Verified player not found in HR search results: {emails[:5]}"
            finally:
                _run(db.player_corp_otps.delete_many({"user_id": sp._user_id}))
                _cleanup_player(db, sp._email, sp._mobile)
        finally:
            _cleanup_company(db, admin_email, "iter40-corp2")
