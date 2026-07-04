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
import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict
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
    package_id: Optional[str] = None  # optional: pick a custom SubscriptionPackage


class SubscriptionPackage(BaseModel):
    """Admin-authored offline-mode plan. Vendors pick from these at request-time
    if they don't want the default monthly/yearly."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    duration_days: int
    price: float
    currency: str = "INR"
    active: bool = True
    description: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
    payment_method: Optional[str] = None  # cash | upi | card | bank_transfer | online | other
    issued_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    paid_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────────────────────────────────────────────────
# Phase 5c models — Slot blocks, Expenses, Coaches, Batches, Inventory,
# Vendor staff, Customer check-ins.
# ─────────────────────────────────────────────────────────────────────

class SlotBlock(BaseModel):
    """Vendor-owner blocks a court slot so neither marketplace nor private
    bookings can steal it. Reasons: maintenance | tournament | private | staff_practice."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    listing_id: str
    date: str  # YYYY-MM-DD (for recurring, first occurrence; extend later if needed)
    start_time: str
    end_time: str
    reason: str = "maintenance"  # maintenance | tournament | private | staff_practice
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorExpense(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    date: str  # YYYY-MM-DD
    category: str  # rent | electricity | water | salary | equipment | maintenance | misc
    amount: float
    currency: str = "INR"
    vendor_name: Optional[str] = ""  # who was paid
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorCoach(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    name: str
    phone: Optional[str] = ""
    email: Optional[str] = ""
    sports: List[str] = Field(default_factory=list)
    hourly_rate: float = 0
    active: bool = True
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorBatch(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    listing_id: Optional[str] = None
    name: str  # e.g. "Morning Batch"
    sport: Optional[str] = ""
    coach_id: Optional[str] = None
    start_time: str = "06:00"
    end_time: str = "07:00"
    days_of_week: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun
    capacity: int = 20
    student_ids: List[str] = Field(default_factory=list)  # customer_ids
    monthly_fee: float = 0
    currency: str = "INR"
    active: bool = True
    notes: Optional[str] = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorInventoryItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    name: str  # "Shuttlecock (Yonex Mavis 350)"
    category: str = "other"  # shuttle | ball | jersey | equipment | consumable | other
    unit: str = "piece"
    quantity: int = 0
    low_stock_threshold: int = 5
    cost_price: float = 0
    sale_price: float = 0
    currency: str = "INR"
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorStaff(BaseModel):
    """Sub-user under a vendor account (owner adds receptionist / coach logins).
    Auth reuses the shared /auth/login route — this record links a user_id to a
    vendor with a scoped role."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    user_id: str
    email: str
    name: str
    role: str = "receptionist"  # owner | receptionist | coach
    permissions: List[str] = Field(default_factory=list)  # e.g. ["bookings", "customers", "reports"]
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VendorCheckIn(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    booking_id: Optional[str] = None
    customer_id: Optional[str] = None
    method: str = "manual"  # manual | qr | mobile | booking_id
    checked_in_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


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
        if body.plan_type not in ("monthly", "yearly", "custom"):
            raise HTTPException(400, "plan_type must be 'monthly', 'yearly' or 'custom'")
        # Block duplicate pending requests
        dup = await db.offline_subscriptions.find_one({
            "vendor_id": vendor["id"], "status": "pending_payment"
        }, {"_id": 0})
        if dup:
            raise HTTPException(400, "You already have a pending offline-mode subscription request.")
        settings = await _site_settings_doc()

        # (1) If a custom package is chosen, use its price/duration.
        pkg = None
        if body.package_id:
            pkg = await db.subscription_packages.find_one({"id": body.package_id, "active": True}, {"_id": 0})
            if not pkg:
                raise HTTPException(400, "Selected subscription package is not available")

        # (2) Determine base price from either the package or the default plan.
        if pkg:
            price = float(pkg["price"])
            currency = pkg.get("currency", settings.get("offline_subscription_currency", "INR"))
        else:
            price = float(settings.get(
                "offline_subscription_yearly_price" if body.plan_type == "yearly" else "offline_subscription_monthly_price",
                999.0 if body.plan_type == "yearly" else 99.0,
            ))
            currency = settings.get("offline_subscription_currency", "INR")

        # (3) Lock price for existing vendors on renewals if the site-setting says so.
        # We look for the last *approved / activated* subscription for this vendor.
        if settings.get("offline_subscription_locks_existing_price", True):
            prior = await db.offline_subscriptions.find_one(
                {"vendor_id": vendor["id"], "status": {"$in": ["active", "paid", "approved"]}},
                {"_id": 0, "amount": 1, "currency": 1, "plan_type": 1},
                sort=[("created_at", -1)],
            )
            # Only lock when the plan_type matches (so a monthly→yearly upgrade still uses new price).
            if prior and prior.get("plan_type") == body.plan_type:
                price = float(prior.get("amount") or price)
                currency = prior.get("currency", currency)

        sub = OfflineSubscription(
            vendor_id=vendor["id"], vendor_email=vendor.get("email", ""),
            plan_type=body.plan_type, amount=price, currency=currency,
        )
        await db.offline_subscriptions.insert_one(sub.model_dump())
        return sub

    # -------- Subscription packages (admin) --------
    @api.post("/admin/subscription-packages", response_model=SubscriptionPackage)
    async def admin_create_package(body: dict, _: dict = Depends(require_platform_admin)):
        if not body.get("name") or not body.get("duration_days") or "price" not in body:
            raise HTTPException(400, "name, duration_days, price are required")
        pkg = SubscriptionPackage(**{k: body[k] for k in ("name", "duration_days", "price", "currency", "active", "description") if k in body})
        await db.subscription_packages.insert_one(pkg.model_dump())
        return pkg

    @api.get("/admin/subscription-packages", response_model=List[SubscriptionPackage])
    async def admin_list_packages(_: dict = Depends(require_platform_admin)):
        docs = await db.subscription_packages.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return [SubscriptionPackage(**d) for d in docs]

    @api.patch("/admin/subscription-packages/{package_id}", response_model=SubscriptionPackage)
    async def admin_update_package(package_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        body.pop("id", None); body.pop("created_at", None)
        await db.subscription_packages.update_one({"id": package_id}, {"$set": body})
        d = await db.subscription_packages.find_one({"id": package_id}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Package not found")
        return SubscriptionPackage(**d)

    @api.delete("/admin/subscription-packages/{package_id}")
    async def admin_delete_package(package_id: str, _: dict = Depends(require_platform_admin)):
        await db.subscription_packages.delete_one({"id": package_id})
        return {"ok": True}

    @api.get("/offline-subscriptions/packages", response_model=List[SubscriptionPackage])
    async def public_list_active_packages(user: dict = Depends(get_current_user)):
        # Vendors and admins can list active packages when choosing a plan.
        docs = await db.subscription_packages.find({"active": True}, {"_id": 0}).sort("price", 1).to_list(200)
        return [SubscriptionPackage(**d) for d in docs]

    # -------- Vendor referral leaderboard (admin) --------
    @api.get("/admin/vendor-referral-leaderboard")
    async def vendor_referral_leaderboard(_: dict = Depends(require_platform_admin)):
        """Counts player signups per vendor via the offline-source bridge —
        how many pre-existing offline customers each vendor has migrated onto
        the platform. Helps platform HQ reward top-referring vendors."""
        pipeline = [
            {"$match": {"offline_source_vendor_id": {"$ne": None}}},
            {"$group": {"_id": "$offline_source_vendor_id", "referred_count": {"$sum": 1}}},
            {"$sort": {"referred_count": -1}},
            {"$limit": 50},
        ]
        rows = await db.player_profiles.aggregate(pipeline).to_list(50)
        # Enrich with vendor business names + commission earned/waived (approx)
        out = []
        for r in rows:
            vid = r["_id"]
            v = await db.vendors.find_one({"id": vid}, {"_id": 0, "business_name": 1, "city": 1, "email": 1})
            if not v:
                continue
            # Waived commission = sum of commission_amount that would have been charged
            waived = await db.vendor_bookings.aggregate([
                {"$match": {"vendor_id": vid, "offline_source": True}},
                {"$group": {"_id": None, "gross_total": {"$sum": "$total"}}},
            ]).to_list(1)
            gross = float(waived[0]["gross_total"]) if waived else 0.0
            settings = await _site_settings_doc()
            pct = float(settings.get("commission_percentage") or 0)
            out.append({
                "vendor_id": vid,
                "business_name": v.get("business_name"),
                "city": v.get("city"),
                "email": v.get("email"),
                "referred_count": r["referred_count"],
                "offline_source_gross": gross,
                "estimated_commission_waived": round(gross * pct / 100.0, 2),
            })
        return out

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

    async def _check_no_slot_block(listing_id: str, date: str, start: str, end: str):
        """Reject if the requested window overlaps a vendor-declared slot block
        (maintenance / tournament / private / staff_practice)."""
        blocks = await db.slot_blocks.find({"listing_id": listing_id, "date": date}, {"_id": 0}).to_list(200)
        for b in blocks:
            if start < b.get("end_time", "24:00") and end > b.get("start_time", "00:00"):
                raise HTTPException(400, f"Slot {start}–{end} is blocked for {b.get('reason','maintenance')} — clear the block first.")
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
        # Refuse if the vendor has declared a slot block on this window.
        await _check_no_slot_block(body.listing_id, body.requested_date, body.start_time, body.end_time)
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

    # =========================================================================
    # Phase 5c — CRUD endpoints for the vendor's offline business
    # =========================================================================

    async def _ensure_vendor_owner(user: dict) -> dict:
        """The endpoints below run under either the vendor themselves or a
        VendorStaff sub-user with matching vendor_id. Returns the vendor doc."""
        if user.get("role") == "vendor":
            vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
            if not vendor:
                raise HTTPException(404, "Vendor not found")
            return vendor
        if user.get("role") == "vendor_staff":
            staff = await db.vendor_staff.find_one({"user_id": user["id"], "active": True}, {"_id": 0})
            if not staff:
                raise HTTPException(403, "Not a vendor staff")
            vendor = await db.vendors.find_one({"id": staff["vendor_id"]}, {"_id": 0})
            if not vendor:
                raise HTTPException(404, "Vendor not found")
            # Attach staff meta so downstream can check permissions
            vendor["_staff"] = staff
            return vendor
        raise HTTPException(403, "Vendor only")

    def _staff_can(vendor: dict, perm: str) -> bool:
        staff = vendor.get("_staff")
        if not staff:
            return True  # owner
        if staff.get("role") == "owner":
            return True
        return perm in (staff.get("permissions") or [])

    # -------- Slot blocks --------
    @api.post("/vendor/slot-blocks", response_model=SlotBlock)
    async def create_slot_block(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "bookings"):
            raise HTTPException(403, "Not allowed")
        blk = SlotBlock(vendor_id=vendor["id"], **{k: body[k] for k in ("listing_id","date","start_time","end_time","reason","notes") if k in body})
        await db.slot_blocks.insert_one(blk.model_dump())
        return blk

    @api.get("/vendor/slot-blocks", response_model=List[SlotBlock])
    async def list_slot_blocks(listing_id: Optional[str] = None, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        flt = {"vendor_id": vendor["id"]}
        if listing_id:
            flt["listing_id"] = listing_id
        docs = await db.slot_blocks.find(flt, {"_id": 0}).sort("date", -1).to_list(500)
        return [SlotBlock(**d) for d in docs]

    @api.delete("/vendor/slot-blocks/{block_id}")
    async def delete_slot_block(block_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        await db.slot_blocks.delete_one({"id": block_id, "vendor_id": vendor["id"]})
        return {"ok": True}

    # -------- Expenses --------
    @api.post("/vendor/expenses", response_model=VendorExpense)
    async def create_expense(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "expenses"):
            raise HTTPException(403, "Not allowed")
        exp = VendorExpense(vendor_id=vendor["id"], **{k: body[k] for k in ("date","category","amount","currency","vendor_name","notes") if k in body})
        await db.vendor_expenses.insert_one(exp.model_dump())
        return exp

    @api.get("/vendor/expenses", response_model=List[VendorExpense])
    async def list_expenses(month: Optional[str] = None, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "expenses"):
            raise HTTPException(403, "Not allowed")
        flt = {"vendor_id": vendor["id"]}
        if month:
            flt["date"] = {"$regex": f"^{month}"}
        docs = await db.vendor_expenses.find(flt, {"_id": 0}).sort("date", -1).to_list(500)
        return [VendorExpense(**d) for d in docs]

    @api.delete("/vendor/expenses/{expense_id}")
    async def delete_expense(expense_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "expenses"):
            raise HTTPException(403, "Not allowed")
        await db.vendor_expenses.delete_one({"id": expense_id, "vendor_id": vendor["id"]})
        return {"ok": True}

    # -------- Coaches --------
    @api.post("/vendor/coaches", response_model=VendorCoach)
    async def create_coach(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        c = VendorCoach(vendor_id=vendor["id"], **{k: body[k] for k in ("name","phone","email","sports","hourly_rate","active","notes") if k in body})
        await db.vendor_coaches.insert_one(c.model_dump())
        return c

    @api.get("/vendor/coaches", response_model=List[VendorCoach])
    async def list_coaches(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        docs = await db.vendor_coaches.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("name", 1).to_list(200)
        return [VendorCoach(**d) for d in docs]

    @api.patch("/vendor/coaches/{coach_id}", response_model=VendorCoach)
    async def update_coach(coach_id: str, body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        body.pop("id", None); body.pop("vendor_id", None)
        await db.vendor_coaches.update_one({"id": coach_id, "vendor_id": vendor["id"]}, {"$set": body})
        d = await db.vendor_coaches.find_one({"id": coach_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Coach not found")
        return VendorCoach(**d)

    @api.delete("/vendor/coaches/{coach_id}")
    async def delete_coach(coach_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        await db.vendor_coaches.delete_one({"id": coach_id, "vendor_id": vendor["id"]})
        return {"ok": True}

    # -------- Batches --------
    @api.post("/vendor/batches", response_model=VendorBatch)
    async def create_batch(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        b = VendorBatch(vendor_id=vendor["id"], **{k: body[k] for k in ("listing_id","name","sport","coach_id","start_time","end_time","days_of_week","capacity","student_ids","monthly_fee","currency","active","notes") if k in body})
        await db.vendor_batches.insert_one(b.model_dump())
        return b

    @api.get("/vendor/batches", response_model=List[VendorBatch])
    async def list_batches(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        docs = await db.vendor_batches.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("name", 1).to_list(200)
        return [VendorBatch(**d) for d in docs]

    @api.patch("/vendor/batches/{batch_id}", response_model=VendorBatch)
    async def update_batch(batch_id: str, body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        body.pop("id", None); body.pop("vendor_id", None)
        await db.vendor_batches.update_one({"id": batch_id, "vendor_id": vendor["id"]}, {"$set": body})
        d = await db.vendor_batches.find_one({"id": batch_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Batch not found")
        return VendorBatch(**d)

    @api.delete("/vendor/batches/{batch_id}")
    async def delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        await db.vendor_batches.delete_one({"id": batch_id, "vendor_id": vendor["id"]})
        return {"ok": True}

    # -------- Inventory --------
    @api.post("/vendor/inventory", response_model=VendorInventoryItem)
    async def create_inventory(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        it = VendorInventoryItem(vendor_id=vendor["id"], **{k: body[k] for k in ("name","category","unit","quantity","low_stock_threshold","cost_price","sale_price","currency") if k in body})
        await db.vendor_inventory.insert_one(it.model_dump())
        return it

    @api.get("/vendor/inventory", response_model=List[VendorInventoryItem])
    async def list_inventory(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        docs = await db.vendor_inventory.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("name", 1).to_list(500)
        return [VendorInventoryItem(**d) for d in docs]

    @api.patch("/vendor/inventory/{item_id}", response_model=VendorInventoryItem)
    async def update_inventory(item_id: str, body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        body.pop("id", None); body.pop("vendor_id", None)
        body["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.vendor_inventory.update_one({"id": item_id, "vendor_id": vendor["id"]}, {"$set": body})
        d = await db.vendor_inventory.find_one({"id": item_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not d:
            raise HTTPException(404, "Item not found")
        return VendorInventoryItem(**d)

    @api.delete("/vendor/inventory/{item_id}")
    async def delete_inventory(item_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        await db.vendor_inventory.delete_one({"id": item_id, "vendor_id": vendor["id"]})
        return {"ok": True}

    # -------- Vendor staff --------
    @api.post("/vendor/staff", response_model=VendorStaff)
    async def create_staff(body: dict, user: dict = Depends(get_current_user)):
        # Only the vendor owner (not a sub-staff) may add staff.
        if user.get("role") != "vendor":
            raise HTTPException(403, "Only the vendor owner can add staff")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor not found")
        email = (body.get("email") or "").strip().lower()
        password = (body.get("password") or "").strip()
        role = body.get("role") or "receptionist"
        if role not in ("owner", "receptionist", "coach"):
            raise HTTPException(400, "Invalid role")
        if not email or not password or len(password) < 6:
            raise HTTPException(400, "email + password (>=6 chars) required")
        existing = await db.users.find_one({"email": email})
        if existing:
            raise HTTPException(400, "Email already registered as another user")
        # Default permission masks per role
        perms_default = {
            "owner": ["bookings", "customers", "expenses", "reports", "staff", "inventory", "coaches", "batches"],
            "receptionist": ["bookings", "customers", "checkin", "inventory"],  # NO expenses/reports
            "coach": ["batches", "checkin"],
        }
        # Create the user record
        import bcrypt
        pwd_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": user_id, "email": email, "name": body.get("name") or email,
            "role": "vendor_staff", "password_hash": pwd_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        staff = VendorStaff(
            vendor_id=vendor["id"], user_id=user_id, email=email,
            name=body.get("name") or email, role=role,
            permissions=body.get("permissions") or perms_default[role],
        )
        await db.vendor_staff.insert_one(staff.model_dump())
        return staff

    @api.get("/vendor/staff", response_model=List[VendorStaff])
    async def list_staff(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "staff"):
            raise HTTPException(403, "Not allowed")
        docs = await db.vendor_staff.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
        return [VendorStaff(**d) for d in docs]

    @api.delete("/vendor/staff/{staff_id}")
    async def delete_staff(staff_id: str, user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Only the vendor owner can remove staff")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor not found")
        staff = await db.vendor_staff.find_one({"id": staff_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not staff:
            raise HTTPException(404, "Staff not found")
        await db.vendor_staff.delete_one({"id": staff_id})
        await db.users.delete_one({"id": staff["user_id"]})
        return {"ok": True}

    # -------- Check-in --------
    @api.post("/vendor/checkin", response_model=VendorCheckIn)
    async def vendor_checkin(body: dict, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "checkin"):
            raise HTTPException(403, "Not allowed")
        code = (body.get("code") or "").strip()
        method = body.get("method") or "manual"
        booking = None
        customer = None
        if code:
            # Try booking_id → private_bookings then vendor_bookings; then customer by phone
            booking = await db.private_bookings.find_one({"id": code, "vendor_id": vendor["id"]}, {"_id": 0})
            if not booking:
                booking = await db.vendor_bookings.find_one({"id": code, "vendor_id": vendor["id"]}, {"_id": 0})
            if not booking and code.isdigit():
                customer = await db.vendor_customers.find_one({"vendor_id": vendor["id"], "phone": {"$regex": code}}, {"_id": 0})
            if not booking:
                cust = await db.vendor_customers.find_one({"id": code, "vendor_id": vendor["id"]}, {"_id": 0})
                if cust:
                    customer = cust
        if not booking and not customer:
            raise HTTPException(404, "No matching booking or customer for that code")
        ci = VendorCheckIn(
            vendor_id=vendor["id"],
            booking_id=(booking or {}).get("id"),
            customer_id=(customer or {}).get("id") or (booking or {}).get("customer_id"),
            method=method,
        )
        await db.vendor_checkins.insert_one(ci.model_dump())
        # Mark booking as checked_in
        if booking:
            await db.private_bookings.update_one({"id": booking["id"]}, {"$set": {"checked_in_at": ci.checked_in_at}})
            await db.vendor_bookings.update_one({"id": booking["id"]}, {"$set": {"checked_in_at": ci.checked_in_at}})
        return ci

    # -------- Customer detail (visit history + spend) --------
    @api.get("/vendor/customers/{customer_id}")
    async def get_customer_detail(customer_id: str, user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        c = await db.vendor_customers.find_one({"id": customer_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Customer not found")
        # Aggregate visit history from bookings + invoices
        bookings = await db.private_bookings.find({"vendor_id": vendor["id"], "customer_id": customer_id}, {"_id": 0}).sort("requested_date", -1).to_list(200)
        invoices = await db.vendor_invoices.find({"vendor_id": vendor["id"], "customer_id": customer_id}, {"_id": 0}).sort("issued_at", -1).to_list(200)
        total_spent = sum(float(i.get("total") or 0) for i in invoices if i.get("status") == "paid")
        outstanding = sum(float(i.get("total") or 0) for i in invoices if i.get("status") not in ("paid", "void"))
        visits = len(bookings)
        # Membership status
        memberships = await db.membership_purchases.find({"vendor_id": vendor["id"], "customer_id": customer_id, "status": {"$in": ["active", "paid"]}}, {"_id": 0}).to_list(50)
        return {
            **c,
            "visits": visits,
            "total_spent": total_spent,
            "outstanding_balance": outstanding,
            "bookings": bookings[:20],
            "invoices": invoices[:20],
            "memberships": memberships,
        }

    # -------- Dashboard stats --------
    @api.get("/vendor/dashboard-stats")
    async def vendor_dashboard_stats(user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        vid = vendor["id"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Today's revenue = paid invoices issued today + marketplace booking totals today (confirmed)
        today_priv = await db.private_bookings.find({"vendor_id": vid, "requested_date": today}, {"_id": 0}).to_list(200)
        today_online = await db.vendor_bookings.find({"vendor_id": vid, "requested_date": today, "status": {"$in": ["confirmed", "fulfilled"]}}, {"_id": 0}).to_list(200)
        today_revenue = sum(float(b.get("amount") or 0) for b in today_priv) + sum(float(b.get("total") or 0) for b in today_online)
        today_bookings = len(today_priv) + len(today_online)
        walk_in_customers = await db.vendor_customers.count_documents({"vendor_id": vid})
        online_customers = await db.vendor_bookings.distinct("created_by", {"vendor_id": vid})
        active_members = await db.membership_purchases.count_documents({"vendor_id": vid, "status": {"$in": ["active", "paid"]}})
        # Pending payments = issued unpaid invoices
        pending_invoices = await db.vendor_invoices.find({"vendor_id": vid, "status": "issued"}, {"_id": 0}).to_list(200)
        pending_payment_amount = sum(float(i.get("total") or 0) for i in pending_invoices)
        # Court utilisation: how many slot-hours of today are booked / capacity heuristic (10h/day per listing)
        listings = await db.vendor_listings.find({"vendor_id": vid}, {"_id": 0, "id": 1}).to_list(100)
        cap_hours = max(1, 10 * len(listings))
        booked_hours = sum(int(b.get("hours") or 0) for b in today_priv) + sum(int(b.get("hours") or 0) for b in today_online)
        utilisation = min(100, round(100 * booked_hours / cap_hours))
        # New leads (last 7 days)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        new_leads_count = await db.venue_leads.count_documents({"created_at": {"$gte": seven_days_ago}})
        return {
            "today_revenue": today_revenue,
            "today_bookings": today_bookings,
            "walk_in_customers": walk_in_customers,
            "online_customers": len([u for u in online_customers if u]),
            "active_members": active_members,
            "court_utilisation_percent": utilisation,
            "pending_payment_amount": pending_payment_amount,
            "pending_payment_count": len(pending_invoices),
            "todays_schedule": sorted(
                [{"id": b["id"], "kind": "private", "start_time": b["start_time"], "end_time": b["end_time"], "who": b.get("client_name")} for b in today_priv] +
                [{"id": b["id"], "kind": "online", "start_time": b["start_time"], "end_time": b["end_time"], "who": b.get("company_name")} for b in today_online],
                key=lambda x: x["start_time"]
            ),
            "new_leads_count": new_leads_count,
        }

    # -------- Reports --------
    @api.get("/vendor/reports")
    async def vendor_reports(range: str = "monthly", user: dict = Depends(get_current_user)):
        vendor = await _ensure_vendor_owner(user)
        if not _staff_can(vendor, "reports"):
            raise HTTPException(403, "Not allowed")
        now = datetime.now(timezone.utc)
        if range == "daily":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "weekly":
            start = now - timedelta(days=7)
        else:
            start = now - timedelta(days=30)
        start_iso = start.isoformat()
        start_date = start.strftime("%Y-%m-%d")
        vid = vendor["id"]
        # Paid invoices in range
        paid_invs = await db.vendor_invoices.find({"vendor_id": vid, "status": "paid", "paid_at": {"$gte": start_iso}}, {"_id": 0}).to_list(1000)
        revenue = sum(float(i.get("total") or 0) for i in paid_invs)
        # Expenses in range
        exps = await db.vendor_expenses.find({"vendor_id": vid, "date": {"$gte": start_date}}, {"_id": 0}).to_list(1000)
        total_expenses = sum(float(e.get("amount") or 0) for e in exps)
        profit = revenue - total_expenses
        # Booking counts
        priv = await db.private_bookings.count_documents({"vendor_id": vid, "requested_date": {"$gte": start_date}})
        online = await db.vendor_bookings.count_documents({"vendor_id": vid, "requested_date": {"$gte": start_date}})
        # Membership sales
        mem_sales = await db.membership_purchases.count_documents({"vendor_id": vid, "created_at": {"$gte": start_iso}})
        # Peak-hours histogram (00-23)
        peak = [0] * 24
        for b in (await db.private_bookings.find({"vendor_id": vid, "requested_date": {"$gte": start_date}}, {"_id": 0, "start_time": 1}).to_list(1000)):
            try:
                peak[int((b.get("start_time") or "00:00").split(":")[0])] += 1
            except (ValueError, IndexError):
                pass
        # Top customers by spend
        cust_totals: Dict[str, float] = {}
        for inv in paid_invs:
            cid = inv.get("customer_id")
            if cid:
                cust_totals[cid] = cust_totals.get(cid, 0) + float(inv.get("total") or 0)
        top_ids = sorted(cust_totals.items(), key=lambda x: -x[1])[:5]
        top_customers = []
        for cid, amt in top_ids:
            c = await db.vendor_customers.find_one({"id": cid}, {"_id": 0, "name": 1, "phone": 1, "id": 1})
            if c:
                top_customers.append({**c, "spent": amt})
        return {
            "range": range,
            "since": start_iso,
            "revenue": revenue,
            "expenses": total_expenses,
            "profit": profit,
            "bookings": {"private": priv, "online": online, "total": priv + online},
            "membership_sales": mem_sales,
            "peak_hours": peak,
            "top_customers": top_customers,
            "expenses_by_category": {
                cat: sum(float(e.get("amount") or 0) for e in exps if e.get("category") == cat)
                for cat in {e.get("category") or "misc" for e in exps}
            },
        }

    # -------- Invite offline customer to platform (business-model bridge) --------
    @api.post("/vendor/invite-customer")
    async def invite_offline_customer(body: dict, user: dict = Depends(get_current_user)):
        """Generates a signup link that stamps ?ref_vendor=<vendor_id> so when the
        offline customer signs up as a player, their `offline_source_vendor_id`
        is set. Future bookings from that player to THIS vendor skip platform
        commission (business model)."""
        vendor = await _ensure_vendor_owner(user)
        customer_id = body.get("customer_id")
        if not customer_id:
            raise HTTPException(400, "customer_id required")
        c = await db.vendor_customers.find_one({"id": customer_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not c:
            raise HTTPException(404, "Customer not found")
        frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
        signup_url = f"{frontend}/player/signup?ref_vendor={vendor['id']}" if frontend else f"/player/signup?ref_vendor={vendor['id']}"
        # Compose a WhatsApp-ready message
        biz = vendor.get("invoice_business_name") or vendor.get("business_name") or "Kreeda Nation venue"
        wa_text = (
            f"Hi {c.get('name','')}, {biz} is now on Kreeda Nation. "
            f"Sign up here so we can send you booking confirmations and receipts online: {signup_url}"
        )
        digits = "".join(ch for ch in (c.get("phone") or "") if ch.isdigit())
        if len(digits) == 10:
            digits = "91" + digits
        wa_url = f"https://wa.me/{digits}?text={wa_text.replace(' ', '%20')}"
        return {"signup_url": signup_url, "wa_url": wa_url, "message": wa_text}

