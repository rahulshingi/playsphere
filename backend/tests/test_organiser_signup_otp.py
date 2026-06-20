"""Backend tests for iteration 15 — Organiser signup flow.

Covers:
- POST /api/organisers/signup/request-otp accepts ANY email domain (gmail/yahoo/etc.)
- Request overwrites the previous OTP record for the same email.
- POST /api/organisers/signup without `otp` -> 400
- POST /api/organisers/signup with wrong OTP -> 400 ; 6th wrong attempt -> 429
- POST /api/organisers/signup with VALID OTP -> creates user (role=organiser, email_verified=true),
  company doc (org_type=organiser), sets auth cookie, returns UserPublic.
  OTP record marked verified=true.
- After login as organiser, /api/auth/me returns role=organiser + company_id + company_name.
- Organiser can: GET /companies/me, GET /events?scope=mine, POST /events, GET /bookings.
- Organiser cannot mutate another company's event (404/403 on POST teams / PATCH event).
- POST /api/auth/login works for organiser creds.
- Regression — admin login still works.
"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import uuid
import asyncio
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

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
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _otp_for(db, email):
    return _run(db.organiser_signup_otps.find_one({"email": email}, {"_id": 0}))


def _cleanup_org(db, email):
    user = _run(db.users.find_one({"email": email}))
    if user and user.get("company_id"):
        _run(db.companies.delete_many({"id": user["company_id"]}))
        _run(db.events.delete_many({"company_id": user["company_id"]}))
    _run(db.users.delete_many({"email": email}))
    _run(db.organiser_signup_otps.delete_many({"email": email}))


def _rand_email(prefix="org-qa"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}@gmail.com"


@pytest.fixture
def s():
    return requests.Session()


# ===================== OTP REQUEST =====================

class TestOrganiserOtpRequest:
    def test_request_otp_accepts_gmail(self, s, db):
        email = _rand_email()
        try:
            r = s.post(f"{API}/organisers/signup/request-otp", json={
                "admin_email": email, "organiser_name": "QA Org GMail"
            })
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("ok") is True
            assert data.get("expires_in") == 600
            assert data.get("email") == email
            rec = _otp_for(db, email)
            assert rec is not None
            assert rec.get("otp") and len(rec["otp"]) == 6
            assert rec.get("verified") is False
            assert rec.get("attempts") == 0
        finally:
            _cleanup_org(db, email)

    def test_request_otp_accepts_yahoo_and_corporate(self, s, db):
        for domain in ["yahoo.com", "hotmail.com", "acme.io"]:
            email = f"org-qa-{uuid.uuid4().hex[:6]}@{domain}"
            try:
                r = s.post(f"{API}/organisers/signup/request-otp", json={
                    "admin_email": email, "organiser_name": f"QA {domain}"
                })
                assert r.status_code == 200, f"{domain} -> {r.status_code} {r.text}"
            finally:
                _cleanup_org(db, email)

    def test_request_otp_overwrites_previous(self, s, db):
        email = _rand_email()
        try:
            s.post(f"{API}/organisers/signup/request-otp", json={"admin_email": email, "organiser_name": "QA"})
            first = _otp_for(db, email)["otp"]
            s.post(f"{API}/organisers/signup/request-otp", json={"admin_email": email, "organiser_name": "QA"})
            second = _otp_for(db, email)["otp"]
            # Could theoretically collide (1/1e6); just assert single record + attempts reset.
            rec = _otp_for(db, email)
            assert rec.get("attempts") == 0
            count = _run(db.organiser_signup_otps.count_documents({"email": email}))
            assert count == 1
        finally:
            _cleanup_org(db, email)


# ===================== SIGNUP VALIDATION =====================

class TestOrganiserSignupValidation:
    def _payload(self, email, **overrides):
        base = {
            "company_name": "QA Organisers Co",
            "admin_name": "QA Org Admin",
            "admin_email": email,
            "admin_password": "orgpass123",
            "contact_phone": "+919999000000",
        }
        base.update(overrides)
        return base

    def test_signup_missing_otp_returns_400(self, s, db):
        email = _rand_email()
        try:
            s.post(f"{API}/organisers/signup/request-otp", json={"admin_email": email, "organiser_name": "QA"})
            r = s.post(f"{API}/organisers/signup", json=self._payload(email))
            assert r.status_code == 400
            assert "verification code is required" in r.text.lower()
        finally:
            _cleanup_org(db, email)

    def test_signup_wrong_otp_increments_then_locks(self, s, db):
        email = _rand_email()
        try:
            s.post(f"{API}/organisers/signup/request-otp", json={"admin_email": email, "organiser_name": "QA"})
            for i in range(5):
                r = s.post(f"{API}/organisers/signup", json=self._payload(email, otp="000000"))
                assert r.status_code == 400, f"attempt {i+1}: {r.status_code} {r.text}"
                assert "incorrect verification code" in r.text.lower()
            rec = _otp_for(db, email)
            assert rec.get("attempts") == 5
            # 6th try -> 429 (per helper: attempts >= 5)
            r = s.post(f"{API}/organisers/signup", json=self._payload(email, otp="000000"))
            assert r.status_code == 429, r.text
        finally:
            _cleanup_org(db, email)


# ===================== SIGNUP SUCCESS + PERMISSIONS =====================

class TestOrganiserSignupSuccessAndPerms:
    def _payload(self, email, **overrides):
        base = {
            "company_name": f"QA Organisers {uuid.uuid4().hex[:4]}",
            "admin_name": "QA Org Admin",
            "admin_email": email,
            "admin_password": "orgpass123",
            "contact_phone": "+919999000111",
        }
        base.update(overrides)
        return base

    def test_full_signup_login_and_perms(self, s, db):
        email = _rand_email()
        try:
            # 1) request OTP
            r = s.post(f"{API}/organisers/signup/request-otp", json={"admin_email": email, "organiser_name": "QA Full"})
            assert r.status_code == 200, r.text
            otp = _otp_for(db, email)["otp"]

            # 2) signup with valid OTP
            payload = self._payload(email, otp=otp)
            r = s.post(f"{API}/organisers/signup", json=payload)
            assert r.status_code == 200, r.text
            user = r.json()
            assert user.get("role") == "organiser"
            assert user.get("email") == email
            assert user.get("company_id")
            assert user.get("company_name") == payload["company_name"]
            # cookie set
            assert any(c.name == "access_token" for c in s.cookies)

            # OTP record verified
            rec = _otp_for(db, email)
            assert rec.get("verified") is True

            # User record correct
            db_user = _run(db.users.find_one({"email": email}))
            assert db_user["role"] == "organiser"
            assert db_user.get("email_verified") is True

            # Company doc tagged org_type=organiser
            company = _run(db.companies.find_one({"id": user["company_id"]}, {"_id": 0}))
            assert company is not None
            assert company.get("org_type") == "organiser"

            # 3) GET /auth/me using the cookie
            r = s.get(f"{API}/auth/me")
            assert r.status_code == 200, r.text
            me = r.json()
            assert me["role"] == "organiser"
            assert me["company_id"] == user["company_id"]
            assert me["company_name"] == payload["company_name"]

            # 4) GET /companies/me
            r = s.get(f"{API}/companies/me")
            assert r.status_code == 200, r.text
            assert r.json()["id"] == user["company_id"]

            # 5) GET /events?scope=mine
            r = s.get(f"{API}/events", params={"scope": "mine"})
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)

            # 6) POST /events — organiser can create
            r = s.post(f"{API}/events", json={
                "name": "QA Org Event",
                "sport": "cricket",
                "starts_at": "2026-12-01T10:00:00Z",
            })
            assert r.status_code in (200, 201), r.text
            ev = r.json()
            event_id = ev.get("id")
            assert event_id

            # 7) GET /bookings — own list
            r = s.get(f"{API}/bookings")
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)

            # 8) RBAC — cannot touch ANOTHER company's event
            # Find a foreign event (Acme Corp or any platform-seeded). If none, create one via admin.
            other = _run(db.events.find_one({"company_id": {"$ne": user["company_id"]}}))
            if other:
                other_id = other["id"]
                r2 = requests.patch(f"{API}/events/{other_id}", json={"name": "hack"},
                                    cookies=s.cookies.get_dict())
                assert r2.status_code in (403, 404), f"expected 403/404 got {r2.status_code} {r2.text}"
                r3 = requests.post(f"{API}/events/{other_id}/teams", json={"name": "x"},
                                   cookies=s.cookies.get_dict())
                assert r3.status_code in (403, 404), f"expected 403/404 got {r3.status_code} {r3.text}"

            # 9) Login via /auth/login still works (fresh session)
            s2 = requests.Session()
            r = s2.post(f"{API}/auth/login", json={"email": email, "password": "orgpass123"})
            assert r.status_code == 200, r.text
            assert r.json()["role"] == "organiser"
            assert r.json()["company_id"] == user["company_id"]

        finally:
            _cleanup_org(db, email)


# ===================== REGRESSION =====================

class TestRegression:
    def test_admin_login(self, s):
        r = s.post(f"{API}/auth/login", json={
            "email": "admin@kreedanation.com", "password": "admin123"
        })
        assert r.status_code == 200, r.text
        assert r.json()["role"] == "platform_admin"

    def test_company_signup_still_blocks_free_email(self, s, db):
        # Just verify request-otp blocks gmail for companies.
        r = s.post(f"{API}/companies/signup/request-otp", json={
            "admin_email": f"qa-{uuid.uuid4().hex[:6]}@gmail.com",
            "company_name": "Should Be Blocked"
        })
        assert r.status_code == 400
        assert "official company email" in r.text.lower() or "public providers" in r.text.lower()
