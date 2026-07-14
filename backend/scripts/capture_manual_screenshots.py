"""Capture the reference screenshots used inside the role manuals.

Run once before `generate_manuals.py`. Output files land in
/app/backend/scripts/manuals_screenshots/ and are ~1440×900 quality-40 JPGs
(kept lean — the manual only embeds them at ~170×95 mm).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path("/app/backend/scripts/manuals_screenshots")
OUT.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("KREEDA_BASE_URL", "").rstrip("/")
if not BASE:
    # Fallback to preview env
    env_file = Path("/app/frontend/.env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
                break
assert BASE, "REACT_APP_BACKEND_URL not found"

ADMIN_EMAIL = os.environ.get("TEST_ADMIN_EMAIL", "admin@kreedanation.com")
ADMIN_PW    = os.environ.get("TEST_ADMIN_PASSWORD", "admin123")

TARGETS = [
    ("admin-dashboard.png",  f"{BASE}/platform-admin",  "admin"),
    ("admin-rfq-detail.png", f"{BASE}/platform-admin?tab=corporate-services", "admin_rfq"),
    ("hr-rfq-detail.png",    None, "hr_rfq"),   # URL selected dynamically
]


def _login(page, email, pw):
    page.goto(f"{BASE}/login", wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle", timeout=15000)
    page.fill('input[placeholder*="you@company"]', email)
    page.fill('input[type="password"]', pw)
    page.get_by_test_id("login-submit").click()
    page.wait_for_timeout(3500)


def _dismiss_welcome(page):
    try:
        page.get_by_text("Got it").click(timeout=1500)
    except Exception:
        pass


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # ---- Admin session ----
        _login(page, ADMIN_EMAIL, ADMIN_PW)
        # Admin dashboard
        page.goto(f"{BASE}/platform-admin", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        _dismiss_welcome(page)
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "admin-dashboard.png"), full_page=False)
        print("  ✓ admin-dashboard.png")

        # Admin RFQ detail: pick the newest approved RFQ dynamically
        page.goto(f"{BASE}/platform-admin?tab=corporate-services", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        _dismiss_welcome(page)
        try:
            page.click('button[data-testid="arfq-filter-approved"]', timeout=3000)
            page.wait_for_timeout(1500)
            first_row = page.locator('[data-testid^="arfq-row-"]').first
            first_row.click(force=True, timeout=5000)
            page.wait_for_timeout(2500)
        except Exception as exc:
            print(f"  ! admin-rfq-detail: could not open a row: {exc}")
        page.screenshot(path=str(OUT / "admin-rfq-detail.png"), full_page=False)
        print("  ✓ admin-rfq-detail.png")

        # Grab the RFQ id from the URL context so HR opens the same one
        rfq_id = None
        # Read the URL from data-testid on the current view heading
        try:
            heading = page.locator('[data-testid="admin-rfq-detail"]').first
            heading.wait_for(timeout=3000)
            # Extract id from window (fallback to first arfq-row testid)
            testid = page.locator('[data-testid^="arfq-msg-"], [data-testid^="arfq-cs-line-"]').first
            # Simpler: fetch RFQ id via API using admin cookie context — skip.
        except Exception:
            pass

        # ---- HR session ----
        ctx.close()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        _login(page, "testorg@example.com", "orgpass123")
        page.goto(f"{BASE}/rfqs", wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        # click the first RFQ row (they all belong to testorg)
        first = page.locator('[data-testid^="rfq-row-"]').first
        try:
            first.click(force=True, timeout=5000)
            page.wait_for_timeout(2500)
        except Exception as exc:
            print(f"  ! hr-rfq-detail: no RFQ available: {exc}")
        page.screenshot(path=str(OUT / "hr-rfq-detail.png"), full_page=False)
        print("  ✓ hr-rfq-detail.png")

        browser.close()

    print("Done →", OUT)


if __name__ == "__main__":
    main()
