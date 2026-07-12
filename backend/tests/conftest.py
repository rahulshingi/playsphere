"""Global pytest fixtures / env for the backend test suite.

Sets `EMAIL_MODE=mock` for every test session so `email_service.send_email()`
short-circuits without hitting SendGrid — prevents the CI runner from burning
through the SendGrid free-tier daily quota (P2 fix, Feb 2026).
"""
import os


def pytest_configure(config):
    os.environ.setdefault("EMAIL_MODE", "mock")
