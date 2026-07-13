"""Commission invoices — track platform commission owed by vendors on their
completed platform (online) bookings.

Design (Feb 2026 · hybrid approach):
  • Every `vendor_bookings` row with status IN ("completed", "fulfilled") and
    non-zero `commission_amount` should have exactly one `commission_invoices`
    row.
  • Row is materialised on-demand — any GET on the vendor or admin listing
    triggers a lightweight sweep so freshly-completed bookings show up.
  • Vendor sees their commission dues (pending / paid).
  • Admin sees all vendors' dues, can send reminder emails, mark paid.
  • Payment collection is manual for now (bank transfer + admin marks paid).
    When Razorpay keys arrive, we'll add `payment_url` + auto-mark from webhook.

Schema of a commission_invoice document:
    {
      id, vendor_id, vendor_business_name, vendor_email,
      booking_id, listing_title, requested_date,
      booking_total, commission_percent, commission_min_flat,
      commission_amount, currency,
      status: "pending" | "paid" | "waived",
      issued_at, due_at, paid_at,
      reminders_sent: int, last_reminder_at,
      payment_note (admin note when marking paid)
    }
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException


async def sweep_commission_invoices(db, vendor_id: Optional[str] = None) -> int:
    """Materialise commission invoices for completed platform bookings.

    Returns count of newly-created rows. Idempotent (booking_id is unique).
    """
    match: dict = {"status": {"$in": ["completed", "fulfilled"]}, "commission_amount": {"$gt": 0}}
    if vendor_id:
        match["vendor_id"] = vendor_id
    bookings = await db.vendor_bookings.find(match, {"_id": 0}).to_list(2000)
    if not bookings:
        return 0
    booking_ids = [b["id"] for b in bookings]
    existing = await db.commission_invoices.find(
        {"booking_id": {"$in": booking_ids}}, {"_id": 0, "booking_id": 1}
    ).to_list(len(booking_ids))
    have = {e["booking_id"] for e in existing}
    to_create = [b for b in bookings if b["id"] not in have]
    if not to_create:
        return 0
    # Cache vendor lookups
    vendor_ids = list({b["vendor_id"] for b in to_create})
    vendors = await db.vendors.find({"id": {"$in": vendor_ids}}, {"_id": 0}).to_list(len(vendor_ids))
    vmap = {v["id"]: v for v in vendors}
    now = datetime.now(timezone.utc)
    rows = []
    for b in to_create:
        v = vmap.get(b["vendor_id"], {})
        rows.append({
            "id": str(uuid.uuid4()),
            "vendor_id": b["vendor_id"],
            "vendor_business_name": v.get("business_name") or "",
            "vendor_email": v.get("email") or "",
            "booking_id": b["id"],
            "listing_title": b.get("listing_title") or "",
            "requested_date": b.get("requested_date") or "",
            "booking_total": float(b.get("total") or b.get("price") or 0),
            "commission_percent": float(b.get("commission_percent") or 0),
            "commission_min_flat": float(b.get("commission_min_flat") or 0),
            "commission_amount": float(b.get("commission_amount") or 0),
            "currency": b.get("currency") or "INR",
            "status": "pending",
            "issued_at": now.isoformat(),
            "due_at": (now + timedelta(days=7)).isoformat(),
            "paid_at": None,
            "reminders_sent": 0,
            "last_reminder_at": None,
            "payment_note": "",
        })
    if rows:
        await db.commission_invoices.insert_many(rows)
    return len(rows)


def register(api, db, deps):
    get_current_user = deps.get_current_user
    require_platform_admin = deps.require_platform_admin
    send_email = getattr(deps, "send_email", None)

    async def _ensure_vendor(user: dict) -> dict:
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        v = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not v:
            raise HTTPException(404, "Vendor not found")
        return v

    def _serialise(doc: dict) -> dict:
        return {k: v for k, v in doc.items() if k != "_id"}

    # ─────────────── Vendor ───────────────
    @api.get("/vendor/commission-invoices")
    async def vendor_commission_invoices(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor(user)
        await sweep_commission_invoices(db, vendor_id=vendor["id"])
        docs = await db.commission_invoices.find(
            {"vendor_id": vendor["id"]}, {"_id": 0}
        ).sort("issued_at", -1).to_list(500)
        totals = {
            "pending_amount": sum(float(d["commission_amount"]) for d in docs if d["status"] == "pending"),
            "paid_amount": sum(float(d["commission_amount"]) for d in docs if d["status"] == "paid"),
            "pending_count": sum(1 for d in docs if d["status"] == "pending"),
            "paid_count": sum(1 for d in docs if d["status"] == "paid"),
        }
        return {"invoices": [_serialise(d) for d in docs], "totals": totals}

    # ─────────────── Admin ───────────────
    @api.get("/admin/commission-invoices")
    async def admin_commission_invoices(
        status: Optional[str] = None,
        vendor_id: Optional[str] = None,
        _: dict = Depends(require_platform_admin),
    ):
        await sweep_commission_invoices(db)  # sweep all
        q: dict = {}
        if status and status != "all":
            q["status"] = status
        if vendor_id:
            q["vendor_id"] = vendor_id
        docs = await db.commission_invoices.find(q, {"_id": 0}).sort("issued_at", -1).to_list(2000)
        # per-vendor rollup
        rollup: dict = {}
        for d in docs:
            v = rollup.setdefault(d["vendor_id"], {
                "vendor_id": d["vendor_id"],
                "vendor_business_name": d["vendor_business_name"],
                "vendor_email": d["vendor_email"],
                "pending_amount": 0.0, "paid_amount": 0.0,
                "pending_count": 0, "paid_count": 0,
                "oldest_pending_at": None,
            })
            if d["status"] == "pending":
                v["pending_amount"] += float(d["commission_amount"])
                v["pending_count"] += 1
                if v["oldest_pending_at"] is None or d["issued_at"] < v["oldest_pending_at"]:
                    v["oldest_pending_at"] = d["issued_at"]
            elif d["status"] == "paid":
                v["paid_amount"] += float(d["commission_amount"])
                v["paid_count"] += 1
        summary = {
            "total_pending": sum(v["pending_amount"] for v in rollup.values()),
            "total_paid": sum(v["paid_amount"] for v in rollup.values()),
            "total_pending_count": sum(v["pending_count"] for v in rollup.values()),
            "vendors_with_dues": sum(1 for v in rollup.values() if v["pending_count"] > 0),
        }
        return {
            "invoices": [_serialise(d) for d in docs],
            "vendors": list(rollup.values()),
            "summary": summary,
        }

    @api.post("/admin/commission-invoices/{invoice_id}/mark-paid")
    async def mark_paid(invoice_id: str, body: dict = None, _: dict = Depends(require_platform_admin)):
        note = (body or {}).get("payment_note", "")
        res = await db.commission_invoices.update_one(
            {"id": invoice_id, "status": {"$ne": "paid"}},
            {"$set": {
                "status": "paid",
                "paid_at": datetime.now(timezone.utc).isoformat(),
                "payment_note": note,
            }},
        )
        if not res.matched_count:
            raise HTTPException(404, "Invoice not found or already paid")
        doc = await db.commission_invoices.find_one({"id": invoice_id}, {"_id": 0})
        return _serialise(doc)

    @api.post("/admin/commission-invoices/{invoice_id}/send-reminder")
    async def send_reminder(invoice_id: str, _: dict = Depends(require_platform_admin)):
        doc = await db.commission_invoices.find_one({"id": invoice_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Invoice not found")
        if doc["status"] == "paid":
            raise HTTPException(400, "Already paid — nothing to remind about")
        if send_email and doc.get("vendor_email"):
            subject = f"[Kreeda Nation] Commission due — ₹{doc['commission_amount']:.0f}"
            body = (
                f"Hi {doc.get('vendor_business_name') or 'partner'},\n\n"
                f"This is a friendly reminder that a platform commission of "
                f"₹{doc['commission_amount']:.2f} is pending for your booking on "
                f"{doc.get('requested_date')} ({doc.get('listing_title')}).\n\n"
                f"Please transfer the amount to Kreeda Nation's registered bank "
                f"account and reply with the UTR number so we can mark this "
                f"invoice as paid.\n\n"
                f"Invoice ID: {doc['id']}\n"
                f"Due date  : {doc.get('due_at', '')[:10]}\n\n"
                f"— Kreeda Nation Ops"
            )
            try:
                send_email(doc["vendor_email"], subject, body, kind="commission_reminder")
            except Exception:
                pass  # Non-fatal — reminder count still increments
        await db.commission_invoices.update_one(
            {"id": invoice_id},
            {"$set": {"last_reminder_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"reminders_sent": 1}},
        )
        doc = await db.commission_invoices.find_one({"id": invoice_id}, {"_id": 0})
        return _serialise(doc)

    @api.post("/admin/commission-invoices/send-reminders-bulk")
    async def bulk_reminders(body: dict, _: dict = Depends(require_platform_admin)):
        """Send reminders for every pending invoice belonging to `vendor_ids`."""
        vendor_ids = (body or {}).get("vendor_ids", [])
        if not vendor_ids:
            raise HTTPException(400, "vendor_ids required")
        docs = await db.commission_invoices.find(
            {"vendor_id": {"$in": vendor_ids}, "status": "pending"}, {"_id": 0}
        ).to_list(2000)
        # Group by vendor — one summary email per vendor
        by_vendor: dict = {}
        for d in docs:
            by_vendor.setdefault(d["vendor_id"], []).append(d)
        sent = 0
        for vid, invs in by_vendor.items():
            total = sum(float(x["commission_amount"]) for x in invs)
            email = invs[0].get("vendor_email")
            if send_email and email:
                subject = f"[Kreeda Nation] {len(invs)} pending commission invoice(s) — ₹{total:.0f} due"
                body_msg = (
                    f"Hi {invs[0].get('vendor_business_name') or 'partner'},\n\n"
                    f"You currently have {len(invs)} pending commission invoice(s) "
                    f"totalling ₹{total:.2f}.\n\n"
                    f"Please settle these at your earliest so we can keep your "
                    f"listings live and payouts uninterrupted.\n\n"
                    f"— Kreeda Nation Ops"
                )
                try:
                    send_email(email, subject, body_msg, kind="commission_bulk_reminder")
                except Exception:
                    pass
            await db.commission_invoices.update_many(
                {"id": {"$in": [x["id"] for x in invs]}},
                {"$set": {"last_reminder_at": datetime.now(timezone.utc).isoformat()},
                 "$inc": {"reminders_sent": 1}},
            )
            sent += len(invs)
        return {"reminders_sent": sent, "vendors_notified": len(by_vendor)}
