"""Corporate Services invoice + Razorpay pay-link generation.

Kicks in when HR **accepts** a quotation via
`POST /rfqs/{rfq_id}/quotation/accept` in `corporate_services.py`.

Flow:
  1. HR accepts quote → `create_invoice_for_quote(rfq_id, quote_id)` runs.
  2. A `cs_invoices` doc is materialised (idempotent — one invoice per quote).
  3. Admin has a "Generate invoice" button for edge cases (offline acceptance).
  4. HR can:
      • GET /rfqs/{rfq_id}/invoice        → invoice summary (safe fields only)
      • GET /rfqs/{rfq_id}/invoice/pdf    → binary PDF (branded)
      • POST /rfqs/{rfq_id}/invoice/paylink → returns Razorpay short_url
  5. Razorpay webhook POST /razorpay/webhook auto-marks invoice paid.

PDF: ReportLab (already in requirements.txt).
Razorpay: `razorpay` SDK — degrades gracefully with a mock URL if
`RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` env vars are absent (dev mode).
"""
from __future__ import annotations

import io
import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.responses import Response


# ─────────────────────────── PDF (ReportLab) ───────────────────────────

def _build_invoice_pdf(invoice: dict, rfq: dict, quote: dict, site: dict) -> bytes:
    """Compose a dark-branded invoice PDF and return the bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    )
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=16*mm, bottomMargin=16*mm,
        title=f"Invoice {invoice['invoice_number']}",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica",
                         fontSize=9.5, textColor=colors.HexColor("#1f2937"))
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor=colors.HexColor("#6b7280"))
    label = ParagraphStyle("label", parent=body, fontSize=7.5, textColor=colors.HexColor("#6b7280"),
                          leading=10, spaceAfter=1)
    h_title = ParagraphStyle("htitle", parent=body, fontSize=22, textColor=colors.HexColor("#0a0a0a"),
                             fontName="Helvetica-Bold", leading=26)
    accent  = ParagraphStyle("accent", parent=body, fontSize=8, textColor=colors.HexColor("#0e7490"),
                             fontName="Helvetica-Bold", leading=10)
    total_row = ParagraphStyle("tot", parent=body, fontSize=11, alignment=TA_RIGHT,
                               textColor=colors.HexColor("#0a0a0a"), fontName="Helvetica-Bold")
    right_small = ParagraphStyle("rsm", parent=small, alignment=TA_RIGHT)

    elements = []

    # ---- Header: brand + invoice meta ----
    logo_path = "/app/frontend/public/kreeda-mark.png"
    brand_cell = []
    if os.path.exists(logo_path):
        try:
            brand_cell.append(Image(logo_path, width=42, height=42))
        except Exception:
            pass
    brand_cell.append(Paragraph("<b>KREEDA NATION</b>", ParagraphStyle(
        "b", parent=body, fontName="Helvetica-Bold", fontSize=13,
        textColor=colors.HexColor("#0a0a0a"), leading=15,
    )))
    brand_cell.append(Paragraph("Employee engagement · Sports events · Wellness", small))
    brand_cell.append(Paragraph(site.get("contact_email") or "contact@kreedanation.com", small))
    if site.get("contact_phone"):
        brand_cell.append(Paragraph(site["contact_phone"], small))

    meta_cell = [
        Paragraph("INVOICE", h_title),
        Paragraph(f"# {invoice['invoice_number']}", accent),
        Paragraph(f"Issued: {invoice['issued_at'][:10]}", right_small),
        Paragraph(f"Due: {invoice['due_at'][:10]}", right_small),
    ]

    header_tbl = Table([[brand_cell, meta_cell]], colWidths=[100*mm, 74*mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 8*mm))

    # ---- Bill To / Event Info ----
    bill_to = [
        Paragraph("BILL TO", label),
        Paragraph(f"<b>{rfq.get('company_name') or rfq.get('hr_name') or '—'}</b>", body),
        Paragraph(rfq.get("hr_name") or rfq.get("hr_email") or "", small),
        Paragraph(rfq.get("hr_email") or "", small),
    ]
    event_info = [
        Paragraph("FOR EVENT", label),
        Paragraph(f"<b>{(rfq.get('event') or {}).get('event_name', '')}</b>", body),
        Paragraph(f"{rfq.get('package_name', '')}", small),
        Paragraph(f"Date: {(rfq.get('event') or {}).get('preferred_date', '—')}", small),
        Paragraph(f"Venue: {(rfq.get('event') or {}).get('venue') or (rfq.get('event') or {}).get('city') or '—'}", small),
    ]
    parties = Table([[bill_to, event_info]], colWidths=[87*mm, 87*mm])
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(parties)
    elements.append(Spacer(1, 6*mm))

    # ---- Line items table ----
    rows = [["#", "Description", "Qty", "Unit", "Amount ₹"]]
    for i, ln in enumerate(quote.get("lines", []), start=1):
        rows.append([
            str(i),
            Paragraph(f"{ln.get('name', '')}", body),
            str(ln.get("quantity", 1)),
            (ln.get("unit_type") or "").replace("per ", ""),
            f"{float(ln.get('selling_price') or 0):,.2f}",
        ])

    items_tbl = Table(rows, colWidths=[10*mm, 92*mm, 15*mm, 25*mm, 32*mm], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0a0a0a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("ALIGN", (4, 0), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
    ]))
    elements.append(items_tbl)
    elements.append(Spacer(1, 4*mm))

    # ---- Totals block (right-aligned) ----
    totals_rows = [
        ["Subtotal", f"₹ {float(quote.get('subtotal') or 0):,.2f}"],
    ]
    if float(quote.get("discount") or 0) > 0:
        totals_rows.append(["Discount", f"− ₹ {float(quote.get('discount') or 0):,.2f}"])
    if float(quote.get("tax_amount") or 0) > 0:
        totals_rows.append([f"Tax ({quote.get('tax_percent') or 0}%)", f"₹ {float(quote.get('tax_amount') or 0):,.2f}"])
    totals_rows.append(["TOTAL", f"₹ {float(quote.get('total_selling') or 0):,.2f}"])

    totals_tbl = Table(totals_rows, colWidths=[40*mm, 40*mm], hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -2), 9),
        ("FONTSIZE", (0, -1), (-1, -1), 11),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#0e7490")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.white),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_tbl)
    elements.append(Spacer(1, 8*mm))

    # ---- Payment / Notes ----
    if invoice.get("pay_link_url"):
        pay = Paragraph(
            f"<b>Pay online:</b> <link href='{invoice['pay_link_url']}' color='#0e7490'>{invoice['pay_link_url']}</link>",
            ParagraphStyle("pay", parent=body, textColor=colors.HexColor("#0e7490"),
                          fontName="Helvetica-Bold", fontSize=9.5, leading=12,
                          backColor=colors.HexColor("#ecfeff"), borderPadding=8),
        )
        elements.append(pay)
        elements.append(Spacer(1, 5*mm))

    if quote.get("notes"):
        elements.append(Paragraph("NOTES", label))
        elements.append(Paragraph(quote["notes"].replace("\n", "<br/>"), body))
        elements.append(Spacer(1, 4*mm))

    elements.append(Paragraph("TERMS", label))
    elements.append(Paragraph(
        "Payment is due within 14 days of invoice date. All prices are in INR unless otherwise noted. "
        "Kreeda Nation reserves the right to reschedule services if payment is not received before the event date. "
        "For queries, write to " + (site.get("contact_email") or "contact@kreedanation.com") + ".",
        small,
    ))

    doc.build(elements)
    return buf.getvalue()


# ─────────────────────────── Razorpay pay-link ───────────────────────────

def _razorpay_client() -> Any | None:
    key = os.environ.get("RAZORPAY_KEY_ID")
    secret = os.environ.get("RAZORPAY_KEY_SECRET")
    if not (key and secret):
        return None
    try:
        import razorpay
        return razorpay.Client(auth=(key, secret))
    except Exception:
        return None


def _create_paylink(client: Any | None, invoice: dict, rfq: dict) -> dict | None:
    """Create a Razorpay Payment Link. Returns the API response or None on error."""
    if client is None:
        return None
    amount_paise = int(round(float(invoice["amount"]) * 100))
    payload: dict = {
        "amount": amount_paise,
        "currency": "INR",
        "accept_partial": False,
        "description": f"Kreeda Nation invoice {invoice['invoice_number']} · {(rfq.get('event') or {}).get('event_name', '')}",
        "customer": {
            "name": rfq.get("company_name") or rfq.get("hr_name") or "Customer",
            "email": rfq.get("hr_email") or "",
        },
        "notify": {"sms": False, "email": bool(rfq.get("hr_email"))},
        "reminder_enable": True,
        "notes": {
            "invoice_id": invoice["id"],
            "rfq_id": invoice["rfq_id"],
            "quote_id": invoice["quote_id"],
        },
        "reference_id": invoice["invoice_number"][:40],
    }
    try:
        result: dict = client.payment_link.create(payload)
        return result
    except Exception as exc:  # noqa: BLE001
        print(f"[razorpay] payment link create failed: {exc}")
        return None


async def _next_invoice_number(db: Any) -> str:
    """Simple counter — INV-KN-YYYYMM-{seq zero-padded}."""
    yyyymm = datetime.now(timezone.utc).strftime("%Y%m")
    counter = await db.cs_invoice_counters.find_one_and_update(
        {"period": yyyymm},
        {"$inc": {"seq": 1}},
        upsert=True, return_document=True,
    )
    seq = counter.get("seq", 1) if counter else 1
    return f"INV-KN-{yyyymm}-{seq:04d}"


async def create_invoice_for_quote(db: Any, rfq_id: str, quote_id: str) -> dict:
    """Idempotent — returns existing invoice if quote already invoiced."""
    existing: Optional[dict] = await db.cs_invoices.find_one({"quote_id": quote_id}, {"_id": 0})
    if existing:
        return existing
    rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
    if not rfq:
        raise ValueError("RFQ not found")
    quote = await db.cs_quotations.find_one({"id": quote_id, "rfq_id": rfq_id}, {"_id": 0})
    if not quote:
        raise ValueError("Quotation not found")
    now = datetime.now(timezone.utc)
    invoice_number = await _next_invoice_number(db)
    invoice = {
        "id": str(uuid.uuid4()),
        "invoice_number": invoice_number,
        "rfq_id": rfq_id,
        "quote_id": quote_id,
        "quote_version": quote.get("version"),
        "hr_user_id": rfq.get("hr_user_id"),
        "company_id": rfq.get("company_id"),
        "company_name": rfq.get("company_name"),
        "hr_email": rfq.get("hr_email"),
        "amount": float(quote.get("total_selling") or 0),
        "currency": "INR",
        "status": "unpaid",   # unpaid → paid | cancelled
        "issued_at": now.isoformat(),
        "due_at": (now + timedelta(days=14)).isoformat(),
        "pay_link_url": None,
        "pay_link_id": None,
        "paid_at": None,
        "razorpay_payment_id": None,
    }

    # Try to create Razorpay Payment Link
    client = _razorpay_client()
    if client is not None:
        link = _create_paylink(client, invoice, rfq)
        if link:
            invoice["pay_link_url"] = link.get("short_url")
            invoice["pay_link_id"] = link.get("id")

    await db.cs_invoices.insert_one(invoice)
    invoice.pop("_id", None)
    return invoice


# ─────────────────────────── Route registration ───────────────────────────

def register(api: Any, db: Any, deps: Any) -> None:
    get_current_user = deps.get_current_user
    require_platform_admin = deps.require_platform_admin

    def _sanitise_invoice(inv: dict) -> dict:
        return {k: v for k, v in inv.items() if k != "_id"}

    async def _load_rfq_and_check(rfq_id: str, user: dict) -> tuple[dict, bool]:
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})  # type: ignore[attr-defined]
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        is_admin = user.get("role") in ("platform_admin", "admin")
        if not is_admin and rfq["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        return rfq, is_admin

    # HR + Admin — read the invoice metadata (safe view)
    @api.get("/rfqs/{rfq_id}/invoice")
    async def get_invoice(rfq_id: str, user: dict = Depends(get_current_user)):
        await _load_rfq_and_check(rfq_id, user)
        inv = await db.cs_invoices.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not inv:
            return None
        return _sanitise_invoice(inv)

    # Admin — manually generate invoice (in case HR didn't click accept but wants an invoice)
    @api.post("/admin/rfqs/{rfq_id}/invoice")
    async def admin_generate_invoice(rfq_id: str, user: dict = Depends(require_platform_admin)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        quote = await db.cs_quotations.find_one(
            {"rfq_id": rfq_id, "status": {"$in": ["accepted", "sent"]}},
            {"_id": 0}, sort=[("version", -1)],
        )
        if not quote:
            raise HTTPException(400, "Send a quotation first")
        try:
            inv = await create_invoice_for_quote(db, rfq_id, quote["id"])
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        # If quote wasn't yet accepted, mark it accepted (admin fiat) — this
        # aligns the RFQ state so HR sees the invoice + pay link.
        if quote["status"] == "sent":
            now = datetime.now(timezone.utc).isoformat()
            await db.cs_quotations.update_one({"id": quote["id"]}, {"$set": {"status": "accepted", "accepted_at": now}})
            await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "approved", "updated_at": now}})
            await db.cs_status_history.insert_one({
                "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
                "from_status": "quoted", "to_status": "approved", "at": now,
                "note": f"Admin generated invoice {inv['invoice_number']}",
            })
        return inv

    # HR / Admin — regenerate pay link if it was missing (e.g. keys added later)
    @api.post("/rfqs/{rfq_id}/invoice/paylink")
    async def ensure_paylink(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq, _is_admin = await _load_rfq_and_check(rfq_id, user)
        inv = await db.cs_invoices.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found — accept the quotation first")
        if inv.get("pay_link_url"):
            return inv
        client = _razorpay_client()
        if client is None:
            # Return a friendly mock so the UI can render *something* in dev.
            mock = f"https://razorpay.example/mock/{inv['invoice_number']}"
            await db.cs_invoices.update_one({"id": inv["id"]}, {"$set": {
                "pay_link_url": mock, "pay_link_id": "mock",
            }})
            inv["pay_link_url"] = mock
            inv["pay_link_id"] = "mock"
            return inv
        link = _create_paylink(client, inv, rfq)
        if not link:
            raise HTTPException(502, "Failed to create Razorpay pay-link")
        await db.cs_invoices.update_one({"id": inv["id"]}, {"$set": {
            "pay_link_url": link.get("short_url"),
            "pay_link_id": link.get("id"),
        }})
        inv["pay_link_url"] = link.get("short_url")
        inv["pay_link_id"] = link.get("id")
        return inv

    # HR / Admin — download the PDF
    @api.get("/rfqs/{rfq_id}/invoice/pdf")
    async def download_invoice_pdf(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq, _ = await _load_rfq_and_check(rfq_id, user)
        inv = await db.cs_invoices.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        quote = await db.cs_quotations.find_one({"id": inv["quote_id"]}, {"_id": 0})
        if not quote:
            raise HTTPException(404, "Quotation not found")
        site = await db.site_settings.find_one({}, {"_id": 0}) or {}
        pdf_bytes = _build_invoice_pdf(inv, rfq, quote, site)
        filename = f"{inv['invoice_number']}.pdf"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Cache-Control": "no-store",
            },
        )

    # Admin — mark invoice paid manually (offline transfer / cheque)
    @api.post("/admin/rfqs/{rfq_id}/invoice/mark-paid")
    async def admin_mark_paid(rfq_id: str, body: dict, user: dict = Depends(require_platform_admin)):
        inv = await db.cs_invoices.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not inv:
            raise HTTPException(404, "Invoice not found")
        if inv["status"] == "paid":
            return inv
        note = ((body or {}).get("note") or "").strip()
        now = datetime.now(timezone.utc).isoformat()
        await db.cs_invoices.update_one({"id": inv["id"]}, {"$set": {
            "status": "paid", "paid_at": now, "payment_note": note or "Manually marked paid by admin",
        }})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": "approved", "to_status": "completed", "at": now,
            "note": f"Invoice {inv['invoice_number']} marked paid ({note or 'manual'})",
        })
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "completed", "updated_at": now}})
        return await db.cs_invoices.find_one({"id": inv["id"]}, {"_id": 0})

    # Public webhook — Razorpay POSTs here on payment events.
    @api.post("/razorpay/webhook")
    async def razorpay_webhook(request: Request):
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        secret = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
        if secret:
            expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature):
                raise HTTPException(400, "Invalid signature")
        try:
            import json
            evt = json.loads(payload or b"{}")
        except Exception:
            raise HTTPException(400, "Bad payload")
        event_type = evt.get("event", "")
        if event_type in ("payment_link.paid", "payment.captured"):
            plink = ((evt.get("payload") or {}).get("payment_link") or {}).get("entity") or {}
            plink_id = plink.get("id") or ((evt.get("payload") or {}).get("payment") or {}).get("entity", {}).get("id")
            payment = ((evt.get("payload") or {}).get("payment") or {}).get("entity") or {}
            payment_id = payment.get("id")
            if plink_id:
                inv = await db.cs_invoices.find_one({"pay_link_id": plink_id}, {"_id": 0})
                if inv and inv["status"] != "paid":
                    now = datetime.now(timezone.utc).isoformat()
                    await db.cs_invoices.update_one({"id": inv["id"]}, {"$set": {
                        "status": "paid", "paid_at": now,
                        "razorpay_payment_id": payment_id,
                        "payment_note": f"Auto-marked via Razorpay webhook ({event_type})",
                    }})
                    await db.cs_rfqs.update_one({"id": inv["rfq_id"]}, {"$set": {"status": "completed", "updated_at": now}})
        return {"ok": True}

    # Admin — list all invoices (aging view)
    @api.get("/admin/cs-invoices")
    async def admin_list_invoices(status: Optional[str] = None, _: dict = Depends(require_platform_admin)):
        flt: dict = {}
        if status and status != "all":
            flt["status"] = status
        docs = await db.cs_invoices.find(flt, {"_id": 0}).sort("issued_at", -1).to_list(500)
        return docs
