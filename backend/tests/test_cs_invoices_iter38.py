"""Corporate Services Invoice + Razorpay pay-link + Manuals — iteration 38.

Follow-up to Phase 3: verifies invoice auto-creation on HR accept, admin
manual generation (idempotent), PDF download, mock pay-link (Razorpay keys
absent), mark-paid, webhook signature handling, admin aging list, and the
7 role manuals under /manuals.
"""
import os
import uuid
import json
import hmac
import hashlib

import pytest
import requests

_FE_ENV = "/app/frontend/.env"
if os.path.exists(_FE_ENV):
    for _line in open(_FE_ENV):
        if _line.startswith("REACT_APP_BACKEND_URL="):
            os.environ.setdefault("REACT_APP_BACKEND_URL", _line.split("=", 1)[1].strip())
            break
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"


# ─── Auth helpers ──────────────────────────────────────────────────────────
def _login(session: requests.Session, email: str, password: str) -> dict:
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    _login(s, "admin@kreedanation.com", "admin123")
    return s


@pytest.fixture(scope="module")
def hr_client():
    s = requests.Session()
    _login(s, "testorg@example.com", "orgpass123")
    return s


# ─── Fresh end-to-end RFQ (HR accept auto-invoice path) ────────────────────
@pytest.fixture(scope="module")
def catalog(admin_client):
    r = admin_client.get(f"{API}/corporate-services/services?include_inactive=true")
    services = r.json()
    while len(services) < 2:
        cr = admin_client.post(
            f"{API}/admin/corporate-services/services",
            json={"name": f"TEST_svc_{uuid.uuid4().hex[:6]}", "unit_type": "per event"},
        )
        assert cr.status_code == 200
        services.append(cr.json())
    r = admin_client.get(f"{API}/corporate-services/categories?include_inactive=true")
    cats = r.json()
    if not cats:
        cr = admin_client.post(
            f"{API}/admin/corporate-services/categories", json={"name": "TEST_cat"}
        )
        cats = [cr.json()]
    cat_id = cats[0]["id"]
    r = admin_client.get(f"{API}/corporate-services/packages?include_inactive=true")
    pkgs = r.json()
    pkg = None
    for p in pkgs:
        if p.get("category_id") == cat_id and len(p.get("included_service_ids") or []) >= 2:
            pkg = p
            break
    if not pkg:
        cr = admin_client.post(
            f"{API}/admin/corporate-services/packages",
            json={
                "category_id": cat_id,
                "name": f"TEST_pkg_{uuid.uuid4().hex[:6]}",
                "included_service_ids": [services[0]["id"], services[1]["id"]],
            },
        )
        pkg = cr.json()
    return {"services": services[:2], "package": pkg}


@pytest.fixture(scope="module")
def fresh_rfq(admin_client, hr_client, catalog):
    """Full HR → admin quote → HR accept flow. Returns rfq_id + quote_id + invoice."""
    pkg = catalog["package"]
    payload = {
        "package_id": pkg["id"],
        "selected_service_ids": pkg["included_service_ids"],
        "event": {
            "event_name": f"TEST_inv_{uuid.uuid4().hex[:6]}",
            "preferred_date": "2026-08-20",
            "city": "Bengaluru",
            "guest_count": 80,
        },
    }
    r = hr_client.post(f"{API}/rfqs", json=payload)
    assert r.status_code == 200
    rfq_id = r.json()["id"]

    # Cost sheet (assign vendor + rate to seed cost)
    sheet = admin_client.get(f"{API}/admin/rfqs/{rfq_id}/cost-sheet").json()
    lines = sheet["lines"]
    for ln in lines:
        ln.update({"quantity": 1, "unit_rate": 5000})
    admin_client.put(f"{API}/admin/rfqs/{rfq_id}/cost-sheet", json={"lines": lines})

    # Admin creates + sends quote v1 (25% margin, 18% tax)
    q = admin_client.post(
        f"{API}/admin/rfqs/{rfq_id}/quotations",
        json={"default_margin_percent": 25, "tax_percent": 18, "discount": 0},
    ).json()
    admin_client.post(f"{API}/admin/rfqs/{rfq_id}/quotations/{q['id']}/send")

    # HR accepts → auto-invoice
    acc = hr_client.post(f"{API}/rfqs/{rfq_id}/quotation/accept")
    assert acc.status_code == 200
    body = acc.json()
    return {"rfq_id": rfq_id, "quote_id": q["id"], "accept_response": body}


# ═══════════════════════════════════════════════════════════════════════════
# 1. HR accept flow auto-creates invoice
# ═══════════════════════════════════════════════════════════════════════════
class TestAcceptCreatesInvoice:
    def test_accept_response_shape(self, fresh_rfq):
        body = fresh_rfq["accept_response"]
        assert body.get("ok") is True
        inv = body.get("invoice")
        assert inv is not None, f"No invoice returned in accept response: {body}"
        assert inv["invoice_number"].startswith("INV-KN-")
        assert inv["status"] == "unpaid"
        assert float(inv["amount"]) > 0
        assert inv["currency"] == "INR"
        assert inv["rfq_id"] == fresh_rfq["rfq_id"]
        assert inv["quote_id"] == fresh_rfq["quote_id"]
        assert "_id" not in inv

    def test_hr_can_get_invoice(self, hr_client, fresh_rfq):
        r = hr_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice")
        assert r.status_code == 200
        inv = r.json()
        assert inv is not None
        assert inv["invoice_number"].startswith("INV-KN-")
        # HR must not see admin-only sensitive fields (none defined right now
        # but ensure _id and razorpay_payment_id (if paid) either absent or None)
        assert "_id" not in inv

    def test_admin_can_get_invoice(self, admin_client, fresh_rfq):
        r = admin_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice")
        assert r.status_code == 200
        assert r.json()["invoice_number"].startswith("INV-KN-")


# ═══════════════════════════════════════════════════════════════════════════
# 2. GET /rfqs/{id}/invoice — null when none, 403 for foreign HR
# ═══════════════════════════════════════════════════════════════════════════
class TestInvoiceReadContract:
    def test_returns_null_when_no_invoice(self, hr_client, admin_client, catalog):
        # Fresh RFQ (no quote yet) → invoice must be None
        pkg = catalog["package"]
        r = hr_client.post(
            f"{API}/rfqs",
            json={
                "package_id": pkg["id"],
                "selected_service_ids": pkg["included_service_ids"],
                "event": {"event_name": f"TEST_noinv_{uuid.uuid4().hex[:6]}",
                          "preferred_date": "2026-09-15"},
            },
        )
        rid = r.json()["id"]
        r2 = hr_client.get(f"{API}/rfqs/{rid}/invoice")
        assert r2.status_code == 200
        assert r2.json() is None

    def test_unauth_returns_401(self, fresh_rfq):
        r = requests.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice")
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Admin manual generate — idempotent
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminGenerate:
    def test_generate_returns_existing_invoice(self, admin_client, fresh_rfq):
        # RFQ already has an invoice from HR accept. Calling admin_generate
        # again should return the SAME invoice_number (idempotent).
        r1 = admin_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice").json()
        r2 = admin_client.post(f"{API}/admin/rfqs/{fresh_rfq['rfq_id']}/invoice")
        assert r2.status_code == 200
        assert r2.json()["invoice_number"] == r1["invoice_number"]
        assert r2.json()["id"] == r1["id"]

    def test_generate_from_sent_quote_flips_states(self, admin_client, hr_client, catalog):
        """New RFQ, quote sent (not accepted). Admin_generate should also flip
        quote → accepted and RFQ → approved."""
        pkg = catalog["package"]
        r = hr_client.post(
            f"{API}/rfqs",
            json={
                "package_id": pkg["id"],
                "selected_service_ids": pkg["included_service_ids"],
                "event": {"event_name": f"TEST_admgen_{uuid.uuid4().hex[:6]}",
                          "preferred_date": "2026-10-01"},
            },
        )
        rid = r.json()["id"]
        # seed cost sheet
        sheet = admin_client.get(f"{API}/admin/rfqs/{rid}/cost-sheet").json()
        lines = sheet["lines"]
        for ln in lines:
            ln.update({"quantity": 1, "unit_rate": 3000})
        admin_client.put(f"{API}/admin/rfqs/{rid}/cost-sheet", json={"lines": lines})
        # draft + send
        q = admin_client.post(
            f"{API}/admin/rfqs/{rid}/quotations",
            json={"default_margin_percent": 20, "tax_percent": 0},
        ).json()
        admin_client.post(f"{API}/admin/rfqs/{rid}/quotations/{q['id']}/send")
        # Verify current state — sent + quoted
        assert admin_client.get(f"{API}/rfqs/{rid}").json()["status"] == "quoted"
        # Admin generates invoice on 'sent' quote
        r = admin_client.post(f"{API}/admin/rfqs/{rid}/invoice")
        assert r.status_code == 200
        inv = r.json()
        assert inv["status"] == "unpaid"
        # RFQ → approved, quote → accepted
        assert admin_client.get(f"{API}/rfqs/{rid}").json()["status"] == "approved"
        quotes = admin_client.get(f"{API}/admin/rfqs/{rid}/quotations").json()
        assert any(qq["id"] == q["id"] and qq["status"] == "accepted" for qq in quotes)

    def test_generate_without_quote_returns_400(self, admin_client, hr_client, catalog):
        pkg = catalog["package"]
        r = hr_client.post(
            f"{API}/rfqs",
            json={
                "package_id": pkg["id"],
                "selected_service_ids": pkg["included_service_ids"],
                "event": {"event_name": f"TEST_noquote_{uuid.uuid4().hex[:6]}",
                          "preferred_date": "2026-10-10"},
            },
        )
        rid = r.json()["id"]
        r2 = admin_client.post(f"{API}/admin/rfqs/{rid}/invoice")
        assert r2.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# 4. PDF download — magic bytes + auth
# ═══════════════════════════════════════════════════════════════════════════
class TestInvoicePDF:
    def test_admin_downloads_pdf(self, admin_client, fresh_rfq):
        r = admin_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/pdf")
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"
        assert len(r.content) > 1024  # not empty

    def test_hr_owner_downloads_pdf(self, hr_client, fresh_rfq):
        r = hr_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/pdf")
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_other_hr_gets_403(self, fresh_rfq):
        # Sign in as the seeded test player (bypasses OTP). Player is not admin
        # and does not own the RFQ → should be 403.
        s = requests.Session()
        login = s.post(f"{API}/auth/login", json={
            "email": "testplayer@example.com", "password": "player123",
        })
        if login.status_code != 200:
            pytest.skip(f"testplayer login unavailable: {login.status_code}")
        r = s.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/pdf")
        assert r.status_code == 403, f"Expected 403 for non-owner, got {r.status_code}"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Pay-link (mock — no Razorpay keys configured)
# ═══════════════════════════════════════════════════════════════════════════
class TestPayLinkMock:
    def test_paylink_returns_mock_url_and_persists(self, hr_client, fresh_rfq):
        r = hr_client.post(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/paylink")
        assert r.status_code == 200
        inv = r.json()
        assert inv["pay_link_url"], "pay_link_url should be set"
        assert inv["pay_link_id"] == "mock"
        assert inv["pay_link_url"].startswith("https://razorpay.example/mock/")
        # Verify persistence — subsequent GET returns same URL
        inv2 = hr_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice").json()
        assert inv2["pay_link_url"] == inv["pay_link_url"]
        assert inv2["pay_link_id"] == "mock"

    def test_paylink_idempotent(self, hr_client, fresh_rfq):
        # Second call should return same URL (not create a new one)
        r1 = hr_client.post(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/paylink").json()
        r2 = hr_client.post(f"{API}/rfqs/{fresh_rfq['rfq_id']}/invoice/paylink").json()
        assert r1["pay_link_url"] == r2["pay_link_url"]


# ═══════════════════════════════════════════════════════════════════════════
# 6. Mark paid
# ═══════════════════════════════════════════════════════════════════════════
class TestMarkPaid:
    def test_mark_paid_flips_states(self, admin_client, fresh_rfq):
        r = admin_client.post(
            f"{API}/admin/rfqs/{fresh_rfq['rfq_id']}/invoice/mark-paid",
            json={"note": "TEST cheque #INV_iter38"},
        )
        assert r.status_code == 200
        inv = r.json()
        assert inv["status"] == "paid"
        assert inv["paid_at"] is not None
        # RFQ transitions to completed
        rfq = admin_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}").json()
        assert rfq["status"] == "completed"
        # Status history row added
        hist = admin_client.get(f"{API}/rfqs/{fresh_rfq['rfq_id']}/history").json()
        assert any(h["to_status"] == "completed" for h in hist)

    def test_mark_paid_idempotent(self, admin_client, fresh_rfq):
        # Second call returns paid invoice unchanged
        r = admin_client.post(
            f"{API}/admin/rfqs/{fresh_rfq['rfq_id']}/invoice/mark-paid",
            json={"note": "again"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "paid"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Razorpay webhook — no secret set → accepts unsigned
# ═══════════════════════════════════════════════════════════════════════════
class TestRazorpayWebhook:
    def test_webhook_accepts_when_secret_absent(self):
        # RAZORPAY_WEBHOOK_SECRET absent → signature check skipped
        payload = {"event": "payment_link.paid", "payload": {"payment_link": {"entity": {"id": "plink_test"}}}}
        r = requests.post(f"{API}/razorpay/webhook", json=payload)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    def test_webhook_bad_payload_400(self):
        r = requests.post(
            f"{API}/razorpay/webhook",
            data=b"not json",
            headers={"Content-Type": "application/json"},
        )
        # With no secret, payload is parsed and bad JSON returns 400
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
# 8. Admin aging list
# ═══════════════════════════════════════════════════════════════════════════
class TestAdminInvoicesList:
    def test_admin_lists_invoices(self, admin_client, fresh_rfq):
        r = admin_client.get(f"{API}/admin/cs-invoices")
        assert r.status_code == 200
        docs = r.json()
        assert isinstance(docs, list)
        assert len(docs) >= 1
        # Sorted by issued_at desc — verify roughly
        if len(docs) >= 2:
            assert docs[0]["issued_at"] >= docs[1]["issued_at"]
        assert any(d["rfq_id"] == fresh_rfq["rfq_id"] for d in docs)

    def test_hr_cannot_list_invoices(self, hr_client):
        r = hr_client.get(f"{API}/admin/cs-invoices")
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
# 9. Role manuals — all 7 must be accessible + PDF magic bytes
# ═══════════════════════════════════════════════════════════════════════════
class TestRoleManuals:
    ROLES = [
        "platform-admin", "company", "organiser", "vendor",
        "player", "sponsor", "scorer",
    ]

    @pytest.mark.parametrize("role", ROLES)
    def test_manual_accessible(self, role):
        url = f"{BASE_URL}/manuals/kreeda-nation-{role}-manual.pdf"
        r = requests.get(url, timeout=30)
        assert r.status_code == 200, f"{role}: expected 200 got {r.status_code}"
        assert r.content[:8].startswith(b"%PDF-1."), \
            f"{role}: PDF magic bytes missing (got {r.content[:8]!r})"
        assert len(r.content) > 100 * 1024, \
            f"{role}: expected >100KB got {len(r.content)}"


# ═══════════════════════════════════════════════════════════════════════════
# 10. Prior RFQ from earlier iterations — idempotency verification
# ═══════════════════════════════════════════════════════════════════════════
PRIOR_RFQ_ID = "2800348d-b1b2-41ab-8a22-08ad703a6667"


class TestPriorRFQIdempotency:
    def test_prior_rfq_invoice_lookup(self, admin_client):
        # Per the review note, this RFQ has INV-KN-202607-0001 already generated.
        r = admin_client.get(f"{API}/rfqs/{PRIOR_RFQ_ID}/invoice")
        if r.status_code == 404:
            pytest.skip("Prior RFQ not present in this environment")
        assert r.status_code == 200
        inv = r.json()
        if inv is None:
            pytest.skip("Prior RFQ has no invoice yet")
        first_number = inv["invoice_number"]
        # Idempotent: calling admin_generate again must return same number
        r2 = admin_client.post(f"{API}/admin/rfqs/{PRIOR_RFQ_ID}/invoice")
        assert r2.status_code in (200, 400)
        if r2.status_code == 200:
            assert r2.json()["invoice_number"] == first_number
