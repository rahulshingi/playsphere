"""Phase 5A + 5C — business-model routes.

* Venue leads (HR/organiser suggests a venue not yet on the platform; admin follows up).
* Vendor offline-mode subscription (vendor pays KN to unlock the private-bookings module).
* Vendor private bookings (offline bookings not coming through Kreeda Nation marketplace).
* Commission settings + helper that admins can wire into their accounting layer later.
* Public meta endpoint that exposes the category→activity map for adaptive UI dropdowns.

Wired from server.py via `register(api, db, deps)`. The `deps` namespace bundles:
  - get_current_user
  - require_platform_admin
  - VENDOR_CATEGORY_SPORTS dict
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("kreeda.routes.business")


# ---------- Models ----------
class VenueLead(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    venue_name: str
    street: Optional[str] = ""
    locality: Optional[str] = ""
    city: str
    state: Optional[str] = ""
    pincode: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_phone: Optional[str] = ""
    contact_email: Optional[str] = ""
    notes: Optional[str] = ""
    submitted_by_user_id: str
    submitted_by_email: Optional[str] = ""
    submitted_by_role: Optional[str] = ""
    event_id: Optional[str] = None  # if this lead was raised from an event-create flow
    status: str = "open"  # open | contacted | converted | archived
    admin_notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: Optional[str] = None


class VenueLeadCreate(BaseModel):
    venue_name: str
    city: str
    street: Optional[str] = ""
    locality: Optional[str] = ""
    state: Optional[str] = ""
    pincode: Optional[str] = ""
    contact_name: Optional[str] = ""
    contact_phone: Optional[str] = ""
    contact_email: Optional[str] = ""
    notes: Optional[str] = ""
    event_id: Optional[str] = None


class OfflineSubscription(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    vendor_email: str = ""
    plan_type: str  # "monthly" | "yearly"
    amount: float
    currency: str = "INR"
    status: str = "pending_payment"  # pending_payment | active | paused | expired | cancelled
    started_at: Optional[str] = None
    expires_at: Optional[str] = None
    payment_method: str = "offline"
    activated_by_admin_id: Optional[str] = None
    cancelled_reason: Optional[str] = None
    paused_reason: Optional[str] = None
    paused_at: Optional[str] = None
    paused_by_admin_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OfflineSubscriptionRequest(BaseModel):
    plan_type: str  # "monthly" | "yearly"


class PrivateBooking(BaseModel):
    """Vendor's offline (non-Kreeda-Nation) bookings. PII is vendor-only."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    listing_id: str
    customer_id: Optional[str] = None  # links to VendorCustomer directory
    client_name: str
    client_phone: Optional[str] = ""
    client_email: Optional[str] = ""
    requested_date: str  # YYYY-MM-DD (first occurrence for recurring)
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    hours: int = 1
    rate_type: str = "total"  # "total" (flat amount) | "hourly" (rate * hours)
    rate_per_hour: Optional[float] = 0
    amount: float = 0  # final total to be paid — always the source of truth for revenue
    currency: str = "INR"
    notes: Optional[str] = ""
    status: str = "active"  # active | completed | cancelled
    invoice_id: Optional[str] = None
    # Recurrence (Phase 5 — basic weekly pattern)
    recurrence: Optional[str] = None  # None | "weekly"
    recurrence_until: Optional[str] = None  # YYYY-MM-DD
    recurrence_days_of_week: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PrivateBookingCreate(BaseModel):
    listing_id: str
    customer_id: Optional[str] = None
    client_name: str
    client_phone: Optional[str] = ""
    client_email: Optional[str] = ""
    requested_date: str
    start_time: str
    end_time: str
    hours: Optional[int] = 1
    rate_type: Optional[str] = "total"
    rate_per_hour: Optional[float] = 0
    amount: Optional[float] = 0
    currency: Optional[str] = "INR"
    notes: Optional[str] = ""
    recurrence: Optional[str] = None
    recurrence_until: Optional[str] = None
    recurrence_days_of_week: List[int] = Field(default_factory=list)


class VendorCustomer(BaseModel):
    """Reusable customer directory for a vendor's offline business."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    gstin: Optional[str] = ""
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorCustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    address: Optional[str] = ""
    gstin: Optional[str] = ""
    notes: Optional[str] = ""


class VendorInvoice(BaseModel):
    """A generated invoice against one or more private bookings.

    Snapshots vendor + customer details at issue time so future edits to the
    directory don't retroactively change already-issued invoices.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    invoice_number: str  # V-YYYY-000123, per-vendor auto-increment
    booking_id: str
    customer_id: Optional[str] = None
    customer_snapshot: dict = Field(default_factory=dict)  # {name, phone, email, gstin, address}
    vendor_snapshot: dict = Field(default_factory=dict)    # {business_name, gstin, address, phone, email, logo_url}
    line_items: List[dict] = Field(default_factory=list)   # [{description, hours, rate, amount}]
    subtotal: float
    tax_percent: float
    tax_amount: float
    total: float
    currency: str = "INR"
    notes: Optional[str] = ""
    status: str = "issued"  # draft | issued | paid | void
    issued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    paid_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def register(api, db, deps):
    get_current_user = deps.get_current_user
    require_platform_admin = deps.require_platform_admin
    VENDOR_CATEGORY_SPORTS = deps.VENDOR_CATEGORY_SPORTS

    # ============================================================
    # Meta — exposed publicly for the adaptive UI
    # ============================================================
    @api.get("/meta/vendor-categories")
    async def vendor_categories():
        """Return the category → list-of-activities mapping powering the listing form."""
        return {"categories": VENDOR_CATEGORY_SPORTS}

    # ============================================================
    # Venue Leads (Phase 5A) — HR/organiser/admin suggests unlisted venue
    # ============================================================
    @api.post("/venue-leads", response_model=VenueLead)
    async def submit_venue_lead(body: VenueLeadCreate, user: dict = Depends(get_current_user)):
        if user.get("role") not in ("company_admin", "organiser", "platform_admin", "admin"):
            raise HTTPException(403, "Only HR, organisers, or platform admins can suggest a venue")
        lead = VenueLead(
            **body.model_dump(),
            submitted_by_user_id=user["id"],
            submitted_by_email=user.get("email") or "",
            submitted_by_role=user.get("role") or "",
        )
        await db.venue_leads.insert_one(lead.model_dump())
        logger.info("venue lead submitted | by=%s venue=%s city=%s", user.get("email"), body.venue_name, body.city)
        return lead

    @api.get("/admin/venue-leads", response_model=List[VenueLead])
    async def list_venue_leads(status: Optional[str] = None, _: dict = Depends(require_platform_admin)):
        flt = {}
        if status:
            flt["status"] = status
        docs = await db.venue_leads.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [VenueLead(**d) for d in docs]

    @api.patch("/admin/venue-leads/{lead_id}", response_model=VenueLead)
    async def update_venue_lead(lead_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = {"status", "admin_notes"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No allowed fields to update (status / admin_notes)")
        upd["updated_at"] = datetime.now(timezone.utc).isoformat()
        if upd.get("status") and upd["status"] not in ("open", "contacted", "converted", "archived"):
            raise HTTPException(400, "Invalid status")
        await db.venue_leads.update_one({"id": lead_id}, {"$set": upd})
        doc = await db.venue_leads.find_one({"id": lead_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Lead not found")
        return VenueLead(**doc)

    # ============================================================
    # Vendor offline-mode subscription (Phase 5C)
    # ============================================================
    async def _vendor_for_user(user: dict) -> dict:
        if user.get("role") != "vendor":
            raise HTTPException(403, "Only vendors can manage offline subscriptions")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor record not found")
        return vendor

    async def _site_settings_doc() -> dict:
        # settings.py persists with `id: 'site'` (NOT MongoDB's `_id`), so we must
        # query the same key here. Otherwise admin price overrides never apply.
        s = await db.settings.find_one({"id": "site"}) or {}
        return s

    def _sub_dates(plan_type: str) -> tuple:
        now = datetime.now(timezone.utc)
        if plan_type == "yearly":
            return now.isoformat(), (now + timedelta(days=365)).isoformat()
        return now.isoformat(), (now + timedelta(days=30)).isoformat()

    @api.post("/offline-subscriptions/request", response_model=OfflineSubscription)
    async def request_offline_subscription(body: OfflineSubscriptionRequest, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        if body.plan_type not in ("monthly", "yearly"):
            raise HTTPException(400, "plan_type must be 'monthly' or 'yearly'")
        # Block duplicate pending requests
        dup = await db.offline_subscriptions.find_one({
            "vendor_id": vendor["id"], "status": "pending_payment"
        }, {"_id": 0})
        if dup:
            raise HTTPException(400, "You already have a pending offline-mode subscription request.")
        settings = await _site_settings_doc()
        price = float(settings.get(
            "offline_subscription_yearly_price" if body.plan_type == "yearly" else "offline_subscription_monthly_price",
            999.0 if body.plan_type == "yearly" else 99.0,
        ))
        currency = settings.get("offline_subscription_currency", "INR")
        sub = OfflineSubscription(
            vendor_id=vendor["id"], vendor_email=vendor.get("email", ""),
            plan_type=body.plan_type, amount=price, currency=currency,
        )
        await db.offline_subscriptions.insert_one(sub.model_dump())
        return sub

    @api.get("/offline-subscriptions/mine", response_model=List[OfflineSubscription])
    async def list_my_offline_subscriptions(user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        docs = await db.offline_subscriptions.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return [OfflineSubscription(**d) for d in docs]

    @api.get("/admin/offline-subscriptions", response_model=List[OfflineSubscription])
    async def admin_list_subscriptions(status: Optional[str] = None, _: dict = Depends(require_platform_admin)):
        flt = {}
        if status:
            flt["status"] = status
        docs = await db.offline_subscriptions.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [OfflineSubscription(**d) for d in docs]

    @api.post("/admin/offline-subscriptions/{sub_id}/activate", response_model=OfflineSubscription)
    async def admin_activate_subscription(sub_id: str, user: dict = Depends(require_platform_admin)):
        doc = await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Subscription not found")
        if doc["status"] != "pending_payment":
            raise HTTPException(400, f"Cannot activate from status '{doc['status']}'")
        starts, expires = _sub_dates(doc["plan_type"])
        await db.offline_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {
                "status": "active", "started_at": starts, "expires_at": expires,
                "activated_by_admin_id": user["id"],
            }},
        )
        # Flip the vendor's offline_mode flag + expiry
        await db.vendors.update_one(
            {"id": doc["vendor_id"]},
            {"$set": {"offline_mode": True, "offline_subscription_expires_at": expires}},
        )
        return OfflineSubscription(**(await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})))

    @api.post("/admin/offline-subscriptions/{sub_id}/reject", response_model=OfflineSubscription)
    async def admin_reject_subscription(sub_id: str, body: dict = None, _: dict = Depends(require_platform_admin)):
        doc = await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Subscription not found")
        if doc["status"] != "pending_payment":
            raise HTTPException(400, "Only pending requests can be rejected")
        reason = (body or {}).get("reason", "Rejected by admin")
        await db.offline_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {"status": "cancelled", "cancelled_reason": reason}},
        )
        return OfflineSubscription(**(await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})))

    @api.post("/admin/offline-subscriptions/{sub_id}/pause", response_model=OfflineSubscription)
    async def admin_pause_subscription(sub_id: str, body: dict = None, user: dict = Depends(require_platform_admin)):
        """Pause an active subscription — vendor immediately loses offline_mode access.
        Use for discrepancies (payment bounced, ToS breach, dispute in progress)."""
        doc = await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Subscription not found")
        if doc["status"] != "active":
            raise HTTPException(400, f"Cannot pause from status '{doc['status']}'")
        reason = (body or {}).get("reason", "Paused by admin")
        now = datetime.now(timezone.utc).isoformat()
        await db.offline_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {
                "status": "paused", "paused_reason": reason, "paused_at": now,
                "paused_by_admin_id": user["id"],
            }},
        )
        # Revoke offline_mode immediately so the vendor can't add new private bookings.
        await db.vendors.update_one(
            {"id": doc["vendor_id"]},
            {"$set": {"offline_mode": False}},
        )
        return OfflineSubscription(**(await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})))

    @api.post("/admin/offline-subscriptions/{sub_id}/resume", response_model=OfflineSubscription)
    async def admin_resume_subscription(sub_id: str, _: dict = Depends(require_platform_admin)):
        """Resume a paused subscription — restores offline_mode, keeps original expiry."""
        doc = await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Subscription not found")
        if doc["status"] != "paused":
            raise HTTPException(400, f"Cannot resume from status '{doc['status']}'")
        # Guard against resuming after expiry.
        if doc.get("expires_at") and doc["expires_at"] < datetime.now(timezone.utc).isoformat():
            raise HTTPException(400, "Subscription has expired — vendor must renew")
        await db.offline_subscriptions.update_one(
            {"id": sub_id},
            {"$set": {"status": "active"},
             "$unset": {"paused_reason": "", "paused_at": "", "paused_by_admin_id": ""}},
        )
        await db.vendors.update_one(
            {"id": doc["vendor_id"]},
            {"$set": {"offline_mode": True, "offline_subscription_expires_at": doc.get("expires_at")}},
        )
        return OfflineSubscription(**(await db.offline_subscriptions.find_one({"id": sub_id}, {"_id": 0})))

    # ============================================================
    # Vendor private (offline) bookings — only available when offline_mode=true
    # ============================================================
    async def _ensure_offline_mode(vendor: dict) -> None:
        if not vendor.get("offline_mode"):
            raise HTTPException(403, "Unlock offline mode (subscribe) before adding private bookings")
        exp = vendor.get("offline_subscription_expires_at")
        if exp and exp < datetime.now(timezone.utc).isoformat():
            raise HTTPException(403, "Your offline-mode subscription has expired — please renew")

    async def _own_listing(vendor_id: str, listing_id: str) -> dict:
        listing = await db.vendor_listings.find_one({"id": listing_id, "vendor_id": vendor_id}, {"_id": 0})
        if not listing:
            raise HTTPException(404, "Listing not found in your catalogue")
        return listing

    async def _check_within_hours(listing_id: str, start: str, end: str):
        """Enforce the listing's opening/closing window on private bookings unless
        the vendor has explicitly enabled after-hours bookings on that listing's
        schedule (`allow_after_hours=True`)."""
        sched = await db.venue_schedules.find_one({"listing_id": listing_id}, {"_id": 0}) or {}
        if sched.get("allow_after_hours"):
            return
        opening = sched.get("opening_time") or "06:00"
        closing = sched.get("closing_time") or "22:00"
        # Time strings are always HH:MM so lexicographic comparison works.
        if start < opening or end > closing:
            raise HTTPException(
                400,
                f"Booking window {start}–{end} falls outside opening hours ({opening}–{closing}). "
                f"Enable 'Allow after-hours bookings' in the venue schedule to override."
            )
    async def _upsert_customer_from_booking(vendor_id: str, data: dict) -> Optional[str]:
        """When a private booking is created/edited with an inline client_name (no
        customer_id yet), silently upsert a matching row in `vendor_customers`
        so the Customers tab stays in sync. Match by phone first, then by lowercase name.
        Returns the resolved customer_id or None if not enough info."""
        name = (data.get("client_name") or "").strip()
        phone = (data.get("client_phone") or "").strip()
        email = (data.get("client_email") or "").strip()
        if not name and not phone:
            return None
        q: dict = {"vendor_id": vendor_id}
        if phone:
            q["phone"] = phone
        else:
            q["name"] = {"$regex": f"^{name}$", "$options": "i"}
        existing = await db.vendor_customers.find_one(q, {"_id": 0})
        if existing:
            # Fill missing fields silently — vendor typed a phone/email we didn't have.
            patch = {k: v for k, v in {"email": email, "phone": phone, "name": name}.items()
                     if v and not existing.get(k)}
            if patch:
                await db.vendor_customers.update_one({"id": existing["id"]}, {"$set": patch})
            return existing["id"]
        # Create a lightweight customer entry.
        cust = VendorCustomer(vendor_id=vendor_id, name=name or phone, phone=phone or "", email=email or "")
        await db.vendor_customers.insert_one(cust.model_dump())
        return cust.id

    @api.post("/vendor/private-bookings", response_model=PrivateBooking)
    async def create_private_booking(body: PrivateBookingCreate, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        await _ensure_offline_mode(vendor)
        await _own_listing(vendor["id"], body.listing_id)
        if body.recurrence and body.recurrence not in ("weekly",):
            raise HTTPException(400, "recurrence must be 'weekly' or omitted")
        # Enforce venue opening/closing window unless the vendor has explicitly
        # enabled after-hours bookings for this listing.
        await _check_within_hours(body.listing_id, body.start_time, body.end_time)
        # Normalise the payload BEFORE constructing PrivateBooking to avoid the
        # "got multiple values for keyword argument" TypeError when defaults
        # collide with explicit kwargs.
        data = body.model_dump()
        data["hours"] = data.get("hours") or 1
        data["amount"] = data.get("amount") or 0
        data["currency"] = data.get("currency") or "INR"
        # Auto-populate the customer directory so the Customers tab reflects
        # every walk-in the vendor books, even without an explicit "add customer" step.
        if not data.get("customer_id"):
            resolved = await _upsert_customer_from_booking(vendor["id"], data)
            if resolved:
                data["customer_id"] = resolved
        pb = PrivateBooking(vendor_id=vendor["id"], **data)
        await db.private_bookings.insert_one(pb.model_dump())
        return pb

    @api.get("/vendor/private-bookings", response_model=List[PrivateBooking])
    async def list_private_bookings(listing_id: Optional[str] = None, status: Optional[str] = None, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        flt = {"vendor_id": vendor["id"]}
        if listing_id:
            flt["listing_id"] = listing_id
        if status:
            flt["status"] = status
        docs = await db.private_bookings.find(flt, {"_id": 0}).sort("requested_date", -1).to_list(500)
        return [PrivateBooking(**d) for d in docs]

    @api.patch("/vendor/private-bookings/{booking_id}", response_model=PrivateBooking)
    async def update_private_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        allowed = {
            "status", "notes", "amount", "rate_per_hour", "rate_type",
            "requested_date", "start_time", "end_time", "hours",
            "client_name", "client_phone", "client_email", "customer_id",
            "recurrence", "recurrence_until", "recurrence_days_of_week",
        }
        upd = {k: v for k, v in body.items() if k in allowed}
        if upd.get("status") and upd["status"] not in ("active", "completed", "cancelled"):
            raise HTTPException(400, "Invalid status")
        if upd.get("recurrence") and upd["recurrence"] not in ("weekly", "", None):
            raise HTTPException(400, "recurrence must be 'weekly' or omitted")
        if not upd:
            raise HTTPException(400, "Nothing to update")
        existing = await db.private_bookings.find_one({"id": booking_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Booking not found")
        # Completed bookings are immutable — the only allowed transition is
        # cancellation. Vendors must clone into a new booking to change details.
        if existing.get("status") == "completed":
            keys = set(upd.keys())
            if keys - {"status"} or upd.get("status") != "cancelled":
                raise HTTPException(400, "Completed bookings cannot be edited. Cancel it and create a new one if needed.")
        # If start/end changed, re-validate the opening/closing window.
        new_start = upd.get("start_time", existing["start_time"])
        new_end = upd.get("end_time", existing["end_time"])
        if "start_time" in upd or "end_time" in upd:
            await _check_within_hours(existing["listing_id"], new_start, new_end)
        await db.private_bookings.update_one({"id": booking_id, "vendor_id": vendor["id"]}, {"$set": upd})
        doc = await db.private_bookings.find_one({"id": booking_id, "vendor_id": vendor["id"]}, {"_id": 0})
        return PrivateBooking(**doc)

    @api.delete("/vendor/private-bookings/{booking_id}")
    async def delete_private_booking(booking_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        res = await db.private_bookings.delete_one({"id": booking_id, "vendor_id": vendor["id"]})
        if not res.deleted_count:
            raise HTTPException(404, "Booking not found")
        return {"ok": True}

    # ============================================================
    # Customer directory (Phase 5D)
    # ============================================================
    @api.get("/vendor/customers", response_model=List[VendorCustomer])
    async def list_customers(user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        # Self-healing backfill: for legacy bookings created before the
        # auto-upsert landed, reconcile inline client_name/phone into the
        # customer directory the first time the vendor opens this tab.
        legacy = await db.private_bookings.find(
            {"vendor_id": vendor["id"], "$or": [{"customer_id": {"$exists": False}}, {"customer_id": ""}, {"customer_id": None}]},
            {"_id": 0, "id": 1, "client_name": 1, "client_phone": 1, "client_email": 1}
        ).to_list(500)
        for b in legacy:
            cid = await _upsert_customer_from_booking(vendor["id"], b)
            if cid:
                await db.private_bookings.update_one({"id": b["id"]}, {"$set": {"customer_id": cid}})
        docs = await db.vendor_customers.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("name", 1).to_list(1000)
        return [VendorCustomer(**d) for d in docs]

    @api.post("/vendor/customers", response_model=VendorCustomer)
    async def create_customer(body: VendorCustomerCreate, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        await _ensure_offline_mode(vendor)
        if not body.name.strip():
            raise HTTPException(400, "Customer name is required")
        # Dedupe by phone within a vendor (soft — vendors may still create if they intend)
        cust = VendorCustomer(vendor_id=vendor["id"], **body.model_dump())
        await db.vendor_customers.insert_one(cust.model_dump())
        return cust

    @api.patch("/vendor/customers/{customer_id}", response_model=VendorCustomer)
    async def update_customer(customer_id: str, body: dict, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        allowed = {"name", "phone", "email", "address", "gstin", "notes"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "Nothing to update")
        await db.vendor_customers.update_one({"id": customer_id, "vendor_id": vendor["id"]}, {"$set": upd})
        doc = await db.vendor_customers.find_one({"id": customer_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Customer not found")
        return VendorCustomer(**doc)

    @api.delete("/vendor/customers/{customer_id}")
    async def delete_customer(customer_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        res = await db.vendor_customers.delete_one({"id": customer_id, "vendor_id": vendor["id"]})
        if not res.deleted_count:
            raise HTTPException(404, "Customer not found")
        return {"ok": True}

    # ============================================================
    # Invoices (Phase 5D)
    # ============================================================
    @api.post("/vendor/invoices", response_model=VendorInvoice)
    async def create_invoice(body: dict, user: dict = Depends(get_current_user)):
        """Generate an invoice from a private booking.

        Body: {booking_id, tax_percent?, notes?, description?}
        Vendor's stored invoice_business_name / GSTIN / address / logo become
        the vendor snapshot; the customer directory row (if linked) or the
        booking's inline fields become the customer snapshot.
        """
        vendor = await _vendor_for_user(user)
        await _ensure_offline_mode(vendor)
        booking_id = body.get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id is required")
        booking = await db.private_bookings.find_one({"id": booking_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking.get("invoice_id"):
            raise HTTPException(400, "Invoice already generated for this booking")

        # Customer snapshot: prefer directory row if linked
        cust_snap = {}
        if booking.get("customer_id"):
            cd = await db.vendor_customers.find_one({"id": booking["customer_id"]}, {"_id": 0}) or {}
            cust_snap = {"name": cd.get("name"), "phone": cd.get("phone"), "email": cd.get("email"),
                         "gstin": cd.get("gstin"), "address": cd.get("address")}
        else:
            cust_snap = {"name": booking.get("client_name"), "phone": booking.get("client_phone"),
                         "email": booking.get("client_email"), "gstin": "", "address": ""}

        vendor_snap = {
            "business_name": vendor.get("invoice_business_name") or vendor.get("business_name"),
            "gstin": vendor.get("gstin") or "",
            "address": vendor.get("invoice_address") or "",
            "phone": vendor.get("invoice_phone") or vendor.get("mobile"),
            "email": vendor.get("invoice_email") or vendor.get("email"),
            "logo_url": vendor.get("invoice_logo_url") or "",
            "footer_note": vendor.get("invoice_footer_note") or "",
        }

        subtotal = float(booking.get("amount", 0))
        tax_percent = float(body.get("tax_percent", vendor.get("invoice_tax_percent") or 0))
        tax_amount = round(subtotal * tax_percent / 100, 2)
        total = round(subtotal + tax_amount, 2)

        description = body.get("description") or f"{booking.get('start_time','')}–{booking.get('end_time','')} on {booking.get('requested_date','')} · {booking.get('hours',1)}h"
        line_items = [{
            "description": description,
            "hours": booking.get("hours", 1),
            "rate": booking.get("rate_per_hour") or subtotal,
            "amount": subtotal,
        }]

        # Serial invoice number, per vendor
        year = datetime.now(timezone.utc).strftime("%Y")
        count = await db.vendor_invoices.count_documents({"vendor_id": vendor["id"]})
        invoice_number = f"KN-{year}-{str(count + 1).zfill(5)}"

        inv = VendorInvoice(
            vendor_id=vendor["id"], invoice_number=invoice_number, booking_id=booking_id,
            customer_id=booking.get("customer_id"), customer_snapshot=cust_snap,
            vendor_snapshot=vendor_snap, line_items=line_items,
            subtotal=subtotal, tax_percent=tax_percent, tax_amount=tax_amount, total=total,
            currency=booking.get("currency", "INR"), notes=body.get("notes", ""),
        )
        await db.vendor_invoices.insert_one(inv.model_dump())
        await db.private_bookings.update_one({"id": booking_id}, {"$set": {"invoice_id": inv.id}})
        return inv

    @api.get("/vendor/invoices", response_model=List[VendorInvoice])
    async def list_invoices(user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        docs = await db.vendor_invoices.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("issued_at", -1).to_list(1000)
        return [VendorInvoice(**d) for d in docs]

    @api.get("/vendor/invoices/{invoice_id}", response_model=VendorInvoice)
    async def get_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        doc = await db.vendor_invoices.find_one({"id": invoice_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Invoice not found")
        return VendorInvoice(**doc)

    @api.post("/vendor/invoices/{invoice_id}/mark-paid", response_model=VendorInvoice)
    async def mark_invoice_paid(invoice_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        res = await db.vendor_invoices.update_one(
            {"id": invoice_id, "vendor_id": vendor["id"], "status": {"$ne": "paid"}},
            {"$set": {"status": "paid", "paid_at": datetime.now(timezone.utc).isoformat()}},
        )
        if not res.matched_count:
            raise HTTPException(404, "Invoice not found or already paid")
        doc = await db.vendor_invoices.find_one({"id": invoice_id}, {"_id": 0})
        return VendorInvoice(**doc)

    # ============================================================
    # Admin — per-vendor offline stats (Phase 5D)
    # ============================================================
    @api.get("/admin/vendors/{vendor_id}/offline-stats")
    async def admin_vendor_offline_stats(vendor_id: str, _: dict = Depends(require_platform_admin)):
        vendor = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor not found")
        now_iso = datetime.now(timezone.utc).isoformat()
        month_start = datetime.now(timezone.utc).strftime("%Y-%m-01")
        total_customers = await db.vendor_customers.count_documents({"vendor_id": vendor_id})
        total_bookings = await db.private_bookings.count_documents({"vendor_id": vendor_id})
        active_bookings = await db.private_bookings.count_documents({"vendor_id": vendor_id, "status": "active"})
        completed_bookings = await db.private_bookings.count_documents({"vendor_id": vendor_id, "status": "completed"})
        # This-month + upcoming lists (calendar) — small limits so response stays snappy.
        month_bookings = await db.private_bookings.find(
            {"vendor_id": vendor_id, "requested_date": {"$gte": month_start}},
            {"_id": 0, "requested_date": 1, "start_time": 1, "end_time": 1, "client_name": 1, "amount": 1, "status": 1},
        ).sort("requested_date", 1).to_list(120)
        # Revenue rolls
        agg = await db.private_bookings.aggregate([
            {"$match": {"vendor_id": vendor_id}},
            {"$group": {"_id": None, "total_revenue": {"$sum": "$amount"}}},
        ]).to_list(1)
        total_revenue = float(agg[0]["total_revenue"]) if agg else 0.0
        invoices_issued = await db.vendor_invoices.count_documents({"vendor_id": vendor_id})
        invoices_paid = await db.vendor_invoices.count_documents({"vendor_id": vendor_id, "status": "paid"})
        return {
            "vendor": {
                "id": vendor["id"], "business_name": vendor.get("business_name"),
                "email": vendor.get("email"), "city": vendor.get("city"),
                "offline_mode": vendor.get("offline_mode", False),
                "offline_subscription_expires_at": vendor.get("offline_subscription_expires_at"),
            },
            "totals": {
                "customers": total_customers,
                "bookings": total_bookings,
                "active_bookings": active_bookings,
                "completed_bookings": completed_bookings,
                "invoices_issued": invoices_issued,
                "invoices_paid": invoices_paid,
                "total_revenue": total_revenue,
            },
            "calendar": month_bookings,
            "generated_at": now_iso,
        }
