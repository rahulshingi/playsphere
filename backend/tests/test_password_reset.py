"""Tests for player forgot/reset password flow."""
import os
import re
import time
import subprocess
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = f"{BASE_URL}/api"

PLAYER = {"mobile": "+919000000001", "password": "player123"}


def _read_backend_log_for_token(email: str, since: int = 0):
    """Tail backend logs to find the latest reset URL for an email."""
    paths = [
        "/var/log/supervisor/backend.err.log",
        "/var/log/supervisor/backend.out.log",
    ]
    pat = re.compile(r"PASSWORD RESET LINK for " + re.escape(email) + r":\s*(\S+)")
    latest = None
    for p in paths:
        try:
            out = subprocess.check_output(["tail", "-n", "500", p], text=True)
        except Exception:
            continue
        for line in out.splitlines():
            m = pat.search(line)
            if m:
                latest = m.group(1)
    if not latest:
        return None
    # extract token=...  (token is URL-safe base64; may contain a-zA-Z0-9_-)
    tm = re.search(r"token=([A-Za-z0-9_\-]+)", latest)
    return tm.group(1) if tm else None


def test_forgot_password_unknown_email_returns_ok():
    """No enumeration: unknown emails still return 200."""
    r = requests.post(f"{API}/players/forgot-password",
                      json={"email": f"nope_{int(time.time())}@nowhere.test"})
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_forgot_password_missing_email_400():
    r = requests.post(f"{API}/players/forgot-password", json={})
    assert r.status_code == 400


def test_reset_password_full_flow():
    """Forgot -> log scrape -> reset -> login with new password -> restore."""
    # First ensure the seeded player exists by signing in
    login = requests.post(f"{API}/players/login", json=PLAYER)
    if login.status_code != 200:
        pytest.skip("seeded player not present")
    # Get email by hitting /players/me
    me = requests.get(f"{API}/players/me", cookies=login.cookies).json()
    email = me["email"]

    r = requests.post(f"{API}/players/forgot-password", json={"email": email})
    assert r.status_code == 200

    time.sleep(0.5)
    token = _read_backend_log_for_token(email)
    assert token, f"Reset token for {email} not found in backend logs"

    new_pw = "newpass123"
    rr = requests.post(f"{API}/players/reset-password",
                       json={"token": token, "new_password": new_pw})
    assert rr.status_code == 200, rr.text

    # Login with the new password
    li = requests.post(f"{API}/players/login",
                       json={"mobile": PLAYER["mobile"], "password": new_pw})
    assert li.status_code == 200, li.text

    # Reused token -> 400
    again = requests.post(f"{API}/players/reset-password",
                          json={"token": token, "new_password": "xxxxxxx"})
    assert again.status_code == 400

    # Restore original password by going through the flow again
    requests.post(f"{API}/players/forgot-password", json={"email": email})
    time.sleep(0.5)
    t2 = _read_backend_log_for_token(email)
    assert t2 and t2 != token
    rr2 = requests.post(f"{API}/players/reset-password",
                        json={"token": t2, "new_password": PLAYER["password"]})
    assert rr2.status_code == 200


def test_reset_password_invalid_token_400():
    r = requests.post(f"{API}/players/reset-password",
                      json={"token": "nonexistent_token_xxxx", "new_password": "abcdef"})
    assert r.status_code == 400


def test_reset_password_short_password_400():
    r = requests.post(f"{API}/players/reset-password",
                      json={"token": "x" * 64, "new_password": "abc"})
    assert r.status_code == 400


def test_auth_forgot_reset_works_for_company_admin():
    """HR / company_admin can use /auth/forgot-password + /auth/reset-password."""
    hr_email = os.environ.get("TEST_ACME_EMAIL", "acme@example.com")
    hr_pw = os.environ.get("TEST_ACME_PASSWORD", "acme123")

    # Baseline: HR can log in with current password
    base = requests.post(f"{API}/auth/login", json={"email": hr_email, "password": hr_pw})
    assert base.status_code == 200, base.text

    # Trigger forgot via /auth/* (not /players/*)
    r = requests.post(f"{API}/auth/forgot-password", json={"email": hr_email})
    assert r.status_code == 200
    assert r.json().get("ok") is True

    time.sleep(0.5)
    token = _read_backend_log_for_token(hr_email)
    assert token, f"Reset token for {hr_email} not found in backend logs"

    new_pw = "newhr2026"
    rr = requests.post(f"{API}/auth/reset-password", json={"token": token, "new_password": new_pw})
    assert rr.status_code == 200, rr.text

    # Login with new password
    li = requests.post(f"{API}/auth/login", json={"email": hr_email, "password": new_pw})
    assert li.status_code == 200, li.text

    # Restore
    r2 = requests.post(f"{API}/auth/forgot-password", json={"email": hr_email})
    assert r2.status_code == 200
    time.sleep(0.5)
    t2 = _read_backend_log_for_token(hr_email)
    assert t2 and t2 != token
    rr2 = requests.post(f"{API}/auth/reset-password",
                        json={"token": t2, "new_password": hr_pw})
    assert rr2.status_code == 200


def test_auth_forgot_password_unknown_email_returns_ok():
    """Generic /auth/forgot-password also does not leak existence."""
    r = requests.post(f"{API}/auth/forgot-password",
                      json={"email": f"nope_{int(time.time())}@nowhere.test"})
    assert r.status_code == 200
    assert r.json().get("ok") is True
