"""Regression tests for iteration 33 — auth + business helper refactor.

Only surface-level: exercise the endpoints that changed structure so we catch
any wiring regression the refactor may have introduced. Deep behavioural
coverage lives in the pre-existing OTP / signup / vendor test suites.
"""
from __future__ import annotations
import os
import secrets

import pytest
import requests

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8001")
API = f"{BASE_URL}/api"


class TestAuthRegisterOrchestration:
    def test_login_and_me_flow(self):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json={"email": "admin@kreedanation.com", "password": "admin123"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["role"] == "platform_admin"
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 200
        assert r.json()["role"] == "platform_admin"
        # Logout clears the cookie
        r = s.post(f"{API}/auth/logout", timeout=10)
        assert r.status_code == 200
        r = s.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": "admin@kreedanation.com", "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_login_missing_email(self):
        r = requests.post(f"{API}/auth/login", json={"email": "", "password": "x"}, timeout=10)
        # Pydantic rejects empty email at validation (422) OR 401 if it slips through — both are safe.
        assert r.status_code in (401, 422)

    def test_free_email_domain_blocked_for_company_signup(self):
        r = requests.post(f"{API}/companies/signup/request-otp",
                          json={"admin_email": "someone@gmail.com", "company_name": "X"}, timeout=10)
        assert r.status_code == 400
        assert "official company email" in r.json()["detail"].lower()

    def test_player_signup_otp_accepts_free_domain(self):
        # Should NOT be blocked for player signup (no corporate rule).
        email = f"pt_iter33_{secrets.token_hex(4)}@gmail.com"
        r = requests.post(f"{API}/players/signup/request-otp",
                          json={"email": email, "name": "iter33"}, timeout=10)
        # We can't guarantee SendGrid works in preview, but the shape of the
        # response should be one of: 200 (real send) OR 502 (send failure) —
        # NOT 400 (validation) because gmail.com is allowed for players.
        assert r.status_code in (200, 502, 503), f"unexpected status {r.status_code}: {r.text}"


class TestCompaniesListingsAndMe:
    def test_companies_endpoint_requires_admin(self):
        r = requests.get(f"{API}/companies", timeout=10)
        assert r.status_code == 401
        # With admin cookie it should work
        s = requests.Session()
        s.post(f"{API}/auth/login", json={"email": "admin@kreedanation.com", "password": "admin123"}, timeout=10)
        r = s.get(f"{API}/companies", timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


class TestBusinessMetaEndpoint:
    def test_vendor_categories_public(self):
        # /meta/vendor-categories is public — no auth required.
        r = requests.get(f"{API}/meta/vendor-categories", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "categories" in data
        assert len(data["categories"]) >= 3


class TestPasswordResetOrchestration:
    def test_forgot_password_never_leaks_email_existence(self):
        # Both a valid and an invalid email must respond OK — otherwise the
        # endpoint would leak whether the email is registered.
        r_known = requests.post(f"{API}/auth/forgot-password",
                                json={"email": "admin@kreedanation.com"}, timeout=10)
        r_unknown = requests.post(f"{API}/auth/forgot-password",
                                  json={"email": "no-such-user@example.com"}, timeout=10)
        assert r_known.status_code == 200
        assert r_unknown.status_code == 200
        assert r_known.json() == {"ok": True}
        assert r_unknown.json() == {"ok": True}

    def test_reset_password_rejects_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password",
                          json={"token": "bogus", "new_password": "newpass1"}, timeout=10)
        assert r.status_code == 400
