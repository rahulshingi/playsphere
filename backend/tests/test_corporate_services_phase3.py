"""Corporate Services Phase 3 backend tests — Admin RFQ inbox, quotation flow,
negotiation chat, and Internal Service Vendor management.

Runs against the live preview URL from REACT_APP_BACKEND_URL. Uses seeded
credentials from /app/memory/test_credentials.md.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL", "https://live-scoring-hub-5.preview.emergentagent.com"
).rstrip("/")
API = f"{BASE_URL}/api"


# ───────── Auth helpers ─────────
def _login(session: requests.Session, email: str, password: str):
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


# ───────── Catalog fixtures (services + package for e2e) ─────────
@pytest.fixture(scope="module")
def catalog(admin_client):
    """Ensure at least 2 services + 1 package exist. Reuse existing if present."""
    r = admin_client.get(f"{API}/corporate-services/services?include_inactive=true")
    services = r.json()
    while len(services) < 2:
        payload = {"name": f"TEST_svc_{uuid.uuid4().hex[:6]}", "unit_type": "per event"}
        cr = admin_client.post(f"{API}/admin/corporate-services/services", json=payload)
        assert cr.status_code == 200, cr.text
        services.append(cr.json())

    r = admin_client.get(f"{API}/corporate-services/categories?include_inactive=true")
    cats = r.json()
    if not cats:
        cr = admin_client.post(
            f"{API}/admin/corporate-services/categories", json={"name": "TEST_cat"}
        )
        assert cr.status_code == 200
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
        assert cr.status_code == 200, cr.text
        pkg = cr.json()
    return {"services": services[:2], "package": pkg, "category_id": cat_id}


# ═══════════════════════════════════════════════════════════════════
# 1. Service Vendors CRUD
# ═══════════════════════════════════════════════════════════════════
class TestServiceVendors:
    vendor_id = None

    def test_create_vendor(self, admin_client):
        payload = {
            "name": f"TEST_vendor_{uuid.uuid4().hex[:6]}",
            "city": "Bengaluru",
            "state": "Karnataka",
            "preferred": True,
        }
        r = admin_client.post(f"{API}/admin/service-vendors", json=payload)
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["name"] == payload["name"]
        assert v["city"] == "Bengaluru"
        assert v["preferred"] is True
        assert v["active"] is True
        assert "id" in v
        assert "_id" not in v
        TestServiceVendors.vendor_id = v["id"]

    def test_list_vendors_includes_new(self, admin_client):
        r = admin_client.get(f"{API}/admin/service-vendors")
        assert r.status_code == 200
        ids = [v["id"] for v in r.json()]
        assert TestServiceVendors.vendor_id in ids

    def test_patch_vendor(self, admin_client):
        r = admin_client.patch(
            f"{API}/admin/service-vendors/{TestServiceVendors.vendor_id}",
            json={"contact_phone": "+911234567890", "preferred": False},
        )
        assert r.status_code == 200, r.text
        v = r.json()
        assert v["contact_phone"] == "+911234567890"
        assert v["preferred"] is False

    def test_hr_cannot_list_service_vendors(self, hr_client):
        r = hr_client.get(f"{API}/admin/service-vendors")
        assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════
# 2. Vendor Rate Cards (upsert)
# ═══════════════════════════════════════════════════════════════════
class TestVendorRates:
    def test_upsert_creates_rate(self, admin_client, catalog):
        vid = TestServiceVendors.vendor_id
        sid = catalog["services"][0]["id"]
        r = admin_client.post(
            f"{API}/admin/service-vendors/{vid}/rates",
            json={"service_id": sid, "rate": 1500, "min_quantity": 1},
        )
        assert r.status_code == 200, r.text
        rate = r.json()
        assert rate["rate"] == 1500
        assert rate["service_id"] == sid
        assert rate["vendor_id"] == vid

    def test_upsert_updates_existing(self, admin_client, catalog):
        vid = TestServiceVendors.vendor_id
        sid = catalog["services"][0]["id"]
        r = admin_client.post(
            f"{API}/admin/service-vendors/{vid}/rates",
            json={"service_id": sid, "rate": 1800},
        )
        assert r.status_code == 200
        # Verify only one rate exists for this (vendor, service)
        r2 = admin_client.get(f"{API}/admin/service-vendors/{vid}/rates")
        rates_for_svc = [x for x in r2.json() if x["service_id"] == sid]
        assert len(rates_for_svc) == 1
        assert rates_for_svc[0]["rate"] == 1800

    def test_second_service_rate(self, admin_client, catalog):
        vid = TestServiceVendors.vendor_id
        sid2 = catalog["services"][1]["id"]
        r = admin_client.post(
            f"{API}/admin/service-vendors/{vid}/rates",
            json={"service_id": sid2, "rate": 2200},
        )
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 3. HR submits RFQ (Phase 2 regression) + Admin inbox
# ═══════════════════════════════════════════════════════════════════
class TestRFQFlow:
    rfq_id = None
    quote_v1_id = None
    quote_v2_id = None

    def test_hr_submits_rfq(self, hr_client, catalog):
        pkg = catalog["package"]
        payload = {
            "package_id": pkg["id"],
            "selected_service_ids": pkg["included_service_ids"],
            "selected_addons": [],
            "event": {
                "event_name": f"TEST_rfq_{uuid.uuid4().hex[:6]}",
                "preferred_date": "2026-06-15",
                "city": "Bengaluru",
                "state": "Karnataka",
                "guest_count": 100,
            },
            "expected_budget": "1-2 lakh",
            "special_instructions": "Iteration 37 test",
        }
        r = hr_client.post(f"{API}/rfqs", json=payload)
        assert r.status_code == 200, r.text
        rfq = r.json()
        assert rfq["status"] == "submitted"
        assert rfq["package_id"] == pkg["id"]
        assert "_id" not in rfq
        TestRFQFlow.rfq_id = rfq["id"]

    def test_admin_inbox_list_has_new_rfq(self, admin_client):
        r = admin_client.get(f"{API}/admin/rfqs")
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert TestRFQFlow.rfq_id in ids
        our = [x for x in r.json() if x["id"] == TestRFQFlow.rfq_id][0]
        assert "latest_quote" in our
        assert our["latest_quote"] is None  # no quote yet

    def test_admin_rfq_summary(self, admin_client):
        r = admin_client.get(f"{API}/admin/rfqs/summary")
        assert r.status_code == 200
        d = r.json()
        assert "total" in d and "by_status" in d and "action_needed" in d
        assert d["by_status"].get("submitted", 0) >= 1

    def test_mark_under_review(self, admin_client):
        r = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/mark-under-review"
        )
        assert r.status_code == 200
        r2 = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r2.json()["status"] == "under_review"

    def test_mark_under_review_second_time_400(self, admin_client):
        r = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/mark-under-review"
        )
        assert r.status_code == 400

    def test_suggest_vendors(self, admin_client):
        r = admin_client.get(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/suggest-vendors"
        )
        assert r.status_code == 200
        payload = r.json()
        assert payload["rfq_id"] == TestRFQFlow.rfq_id
        assert isinstance(payload["services"], list)
        assert len(payload["services"]) >= 1
        # First service should have our TEST_vendor in suggestions
        first = payload["services"][0]
        assert "suggestions" in first
        vids = [s["vendor_id"] for s in first["suggestions"]]
        assert TestServiceVendors.vendor_id in vids
        # Ranking: city_match=True (Bengaluru) must appear before rows without
        # city_match. Our vendor city is Bengaluru so should be city_match=True.
        our_row = [s for s in first["suggestions"] if s["vendor_id"] == TestServiceVendors.vendor_id][0]
        assert our_row["city_match"] is True

    def test_cost_sheet_autoseed(self, admin_client):
        r = admin_client.get(f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/cost-sheet")
        assert r.status_code == 200
        sheet = r.json()
        assert sheet["rfq_id"] == TestRFQFlow.rfq_id
        assert len(sheet["lines"]) >= 2  # 2 selected services
        assert all(ln["kind"] == "service" for ln in sheet["lines"])
        assert sheet["total_cost"] == 0.0

    def test_cost_sheet_save_recomputes_total(self, admin_client, catalog):
        # Fetch current sheet, assign vendor + qty/rate to each line
        r = admin_client.get(f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/cost-sheet")
        sheet = r.json()
        vid = TestServiceVendors.vendor_id
        lines = sheet["lines"]
        lines[0].update({"vendor_id": vid, "quantity": 2, "unit_rate": 1800})
        if len(lines) > 1:
            lines[1].update({"vendor_id": vid, "quantity": 3, "unit_rate": 2200})
        r2 = admin_client.put(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/cost-sheet",
            json={"lines": lines},
        )
        assert r2.status_code == 200, r2.text
        saved = r2.json()
        expected_line0 = 2 * 1800  # 3600
        expected_line1 = 3 * 2200 if len(lines) > 1 else 0
        assert saved["lines"][0]["cost"] == expected_line0
        assert saved["lines"][0]["vendor_name"]  # enriched
        assert saved["total_cost"] == float(expected_line0 + expected_line1)

    def test_create_quotation_v1(self, admin_client):
        r = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations",
            json={"default_margin_percent": 25, "tax_percent": 18, "discount": 100},
        )
        assert r.status_code == 200, r.text
        q = r.json()
        assert q["version"] == 1
        assert q["status"] == "draft"
        assert q["internal_total_cost"] == 3600 + 6600  # 10200
        # Selling with 25% margin: 3600*1.25 + 6600*1.25 = 4500 + 8250 = 12750
        assert q["subtotal"] == 12750
        # Discount 100, tax 18% on (12750-100)=12650 → 2277
        assert q["tax_amount"] == round((12750 - 100) * 0.18, 2)
        assert q["total_selling"] == round((12750 - 100) + q["tax_amount"], 2)
        assert q["gross_margin"] == round(q["total_selling"] - q["internal_total_cost"], 2)
        TestRFQFlow.quote_v1_id = q["id"]

    def test_hr_cannot_see_draft_quote(self, hr_client):
        r = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation")
        assert r.status_code == 200
        assert r.json() is None  # draft not visible

    def test_delete_draft_quote_creates_new_v1(self, admin_client):
        # Delete v1 to test DELETE endpoint works on drafts
        r = admin_client.delete(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations/{TestRFQFlow.quote_v1_id}"
        )
        assert r.status_code == 200
        # Recreate for downstream tests
        r2 = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations",
            json={"default_margin_percent": 25, "tax_percent": 18, "discount": 100},
        )
        assert r2.status_code == 200
        # NOTE: version keeps incrementing (v2) since latest.version is used.
        # This is intentional per PRD (unlimited revisions, monotonic version).
        TestRFQFlow.quote_v1_id = r2.json()["id"]

    def test_send_quotation(self, admin_client, hr_client):
        r = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations/{TestRFQFlow.quote_v1_id}/send"
        )
        assert r.status_code == 200, r.text
        # RFQ status → quoted
        r2 = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r2.json()["status"] == "quoted"
        # HR now sees the quote
        r3 = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation")
        assert r3.status_code == 200
        hr_q = r3.json()
        assert hr_q is not None
        assert hr_q["status"] == "sent"

    def test_hr_quote_is_sanitised(self, hr_client, admin_client):
        r_hr = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation").json()
        r_ad = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation").json()
        # HR must NOT see these top-level fields
        for k in ("internal_total_cost", "gross_margin", "gross_margin_percent"):
            assert k not in r_hr, f"HR should NOT see {k}"
            assert k in r_ad, f"Admin should see {k}"
        # HR must NOT see per-line internal_cost / margin_percent / pricing_mode
        for ln in r_hr["lines"]:
            for k in ("internal_cost", "margin_percent", "pricing_mode"):
                assert k not in ln, f"HR line should NOT contain {k}"
            assert "selling_price" in ln
        for ln in r_ad["lines"]:
            assert "internal_cost" in ln
            assert "margin_percent" in ln

    def test_cannot_delete_sent_quote(self, admin_client):
        r = admin_client.delete(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations/{TestRFQFlow.quote_v1_id}"
        )
        assert r.status_code == 400

    def test_chat_open_after_quote_sent(self, hr_client, admin_client):
        r = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/messages")
        assert r.status_code == 200
        assert isinstance(r.json(), list)  # empty list ok
        # HR posts
        r2 = hr_client.post(
            f"{API}/rfqs/{TestRFQFlow.rfq_id}/messages",
            json={"body": "TEST_hr_msg — can you reduce photography cost?"},
        )
        assert r2.status_code == 200
        assert r2.json()["sender_role"] == "hr"
        # Admin replies
        r3 = admin_client.post(
            f"{API}/rfqs/{TestRFQFlow.rfq_id}/messages",
            json={"body": "TEST_admin_reply — sure, we can adjust."},
        )
        assert r3.status_code == 200
        # After admin reply on 'quoted' RFQ → status flips to 'negotiation'
        r4 = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r4.json()["status"] == "negotiation"

    def test_hr_rejects_creates_negotiation_and_chat_note(self, hr_client, admin_client):
        # Send another v (draft → send) so there's an active sent quote to reject
        # Currently status = 'negotiation' (chat transitioned it). Reject uses
        # latest 'sent' quote. Send status changed via chat, but the quote's
        # status is still 'sent'. So reject should work.
        r = hr_client.post(
            f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation/reject",
            json={"reason": "TEST_reject: budget still too high"},
        )
        assert r.status_code == 200, r.text
        # RFQ → negotiation, quote status → rejected
        r2 = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r2.json()["status"] == "negotiation"
        # Rejection reason posted into chat
        r3 = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/messages")
        msgs = r3.json()
        assert any("TEST_reject" in m["body"] for m in msgs)

    def test_create_v2_and_send(self, admin_client, hr_client):
        # v2 draft
        r = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations",
            json={"default_margin_percent": 15, "tax_percent": 18},
        )
        assert r.status_code == 200
        q = r.json()
        assert q["version"] >= 2, f"Expected version >= 2 got {q['version']}"
        TestRFQFlow.quote_v2_id = q["id"]
        # Send v2
        r2 = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations/{TestRFQFlow.quote_v2_id}/send"
        )
        assert r2.status_code == 200
        # RFQ back to 'quoted'
        r3 = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r3.json()["status"] == "quoted"
        # Previous 'sent' should now be 'superseded' — but previous was already
        # 'rejected'. Confirm only one 'sent' exists.
        r4 = admin_client.get(f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations")
        sents = [x for x in r4.json() if x["status"] == "sent"]
        assert len(sents) == 1
        assert sents[0]["id"] == TestRFQFlow.quote_v2_id

    def test_pricing_mode_fixed_and_markup_mix(self, admin_client, catalog):
        # Build a fresh cost sheet override with pricing modes and validate
        # margin_percent computation for fixed mode.
        r = admin_client.get(f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/cost-sheet").json()
        lines = r["lines"]
        # line0: fixed selling_price=5000, cost=3600 → margin=(5000-3600)/3600*100 = 38.89
        # line1: markup 40% on cost=6600 → 9240
        overrides = [
            {"line_id": lines[0]["line_id"], "pricing_mode": "fixed", "selling_price": 5000},
        ]
        if len(lines) > 1:
            overrides.append({
                "line_id": lines[1]["line_id"], "pricing_mode": "markup", "margin_percent": 40,
            })
        rc = admin_client.post(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations",
            json={"lines": overrides, "tax_percent": 0, "discount": 0},
        )
        assert rc.status_code == 200
        q = rc.json()
        line0 = [ln for ln in q["lines"] if ln["line_id"] == lines[0]["line_id"]][0]
        assert line0["pricing_mode"] == "fixed"
        assert line0["selling_price"] == 5000
        assert abs(line0["margin_percent"] - 38.89) < 0.1
        if len(lines) > 1:
            line1 = [ln for ln in q["lines"] if ln["line_id"] == lines[1]["line_id"]][0]
            assert line1["pricing_mode"] == "markup"
            assert line1["selling_price"] == 6600 * 1.4
        # Cleanup: delete this extra draft
        admin_client.delete(
            f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations/{q['id']}"
        )

    def test_hr_accepts_final_quote(self, hr_client, admin_client):
        r = hr_client.post(f"{API}/rfqs/{TestRFQFlow.rfq_id}/quotation/accept")
        assert r.status_code == 200
        r2 = hr_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}")
        assert r2.json()["status"] == "approved"
        r3 = admin_client.get(f"{API}/admin/rfqs/{TestRFQFlow.rfq_id}/quotations")
        v2 = [x for x in r3.json() if x["id"] == TestRFQFlow.quote_v2_id][0]
        assert v2["status"] == "accepted"

    def test_rfq_history_shows_transitions(self, admin_client):
        r = admin_client.get(f"{API}/rfqs/{TestRFQFlow.rfq_id}/history")
        assert r.status_code == 200
        statuses = [h["to_status"] for h in r.json()]
        for expected in ("submitted", "under_review", "quoted", "negotiation", "approved"):
            assert expected in statuses, f"Missing {expected} in history: {statuses}"


# ═══════════════════════════════════════════════════════════════════
# 4. Chat blocked before first quote
# ═══════════════════════════════════════════════════════════════════
class TestChatGating:
    def test_chat_blocked_before_quote(self, admin_client, hr_client, catalog):
        # Fresh RFQ (not quoted)
        pkg = catalog["package"]
        r = hr_client.post(
            f"{API}/rfqs",
            json={
                "package_id": pkg["id"],
                "selected_service_ids": pkg["included_service_ids"],
                "event": {"event_name": "TEST_chatgate", "preferred_date": "2026-07-01"},
            },
        )
        assert r.status_code == 200
        rid = r.json()["id"]
        # GET returns []
        r2 = hr_client.get(f"{API}/rfqs/{rid}/messages")
        assert r2.status_code == 200
        assert r2.json() == []
        # POST returns 400
        r3 = hr_client.post(f"{API}/rfqs/{rid}/messages", json={"body": "hi"})
        assert r3.status_code == 400
        r4 = admin_client.post(f"{API}/rfqs/{rid}/messages", json={"body": "hi"})
        assert r4.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 5. Vendor deletion guard
# ═══════════════════════════════════════════════════════════════════
class TestVendorDeleteGuard:
    def test_cannot_delete_vendor_in_use(self, admin_client):
        # TestServiceVendors.vendor_id was assigned to cost sheet in step 3.
        r = admin_client.delete(
            f"{API}/admin/service-vendors/{TestServiceVendors.vendor_id}"
        )
        assert r.status_code == 409, f"Expected 409 but got {r.status_code}: {r.text}"

    def test_can_delete_unused_vendor(self, admin_client):
        # Create a fresh vendor, no rate cards → should delete cleanly.
        r = admin_client.post(
            f"{API}/admin/service-vendors",
            json={"name": f"TEST_del_{uuid.uuid4().hex[:6]}"},
        )
        vid = r.json()["id"]
        r2 = admin_client.delete(f"{API}/admin/service-vendors/{vid}")
        assert r2.status_code == 200
