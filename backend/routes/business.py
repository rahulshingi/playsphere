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
    status: str = "pending_payment"  # pending_payment | active | expired | cancelled
    started_at: Optional[str] = None
    expires_at: Optional[str] = None
    payment_method: str = "offline"
    activated_by_admin_id: Optional[str] = None
    cancelled_reason: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OfflineSubscriptionRequest(BaseModel):
    plan_type: str  # "monthly" | "yearly"


class PrivateBooking(BaseModel):
    """Vendor's offline (non-Kreeda-Nation) bookings. PII is vendor-only."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    listing_id: str
    client_name: str
    client_phone: Optional[str] = ""
    client_email: Optional[str] = ""
    requested_date: str  # YYYY-MM-DD (first occurrence for recurring)
    start_time: str  # HH:MM
    end_time: str  # HH:MM
    hours: int = 1
    amount: float = 0
    currency: str = "INR"
    notes: Optional[str] = ""
    # Recurrence (Phase 5 — basic weekly pattern)
    recurrence: Optional[str] = None  # None | "weekly"
    recurrence_until: Optional[str] = None  # YYYY-MM-DD
    recurrence_days_of_week: List[int] = Field(default_factory=list)  # 0=Mon..6=Sun
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PrivateBookingCreate(BaseModel):
    listing_id: str
    client_name: str
    client_phone: Optional[str] = ""
    client_email: Optional[str] = ""
    requested_date: str
    start_time: str
    end_time: str
    hours: Optional[int] = 1
    amount: Optional[float] = 0
    currency: Optional[str] = "INR"
    notes: Optional[str] = ""
    recurrence: Optional[str] = None
    recurrence_until: Optional[str] = None
    recurrence_days_of_week: List[int] = Field(default_factory=list)


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
        s = await db.settings.find_one({"_id": "site"}) or {}
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

    @api.post("/vendor/private-bookings", response_model=PrivateBooking)
    async def create_private_booking(body: PrivateBookingCreate, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        await _ensure_offline_mode(vendor)
        await _own_listing(vendor["id"], body.listing_id)
        if body.recurrence and body.recurrence not in ("weekly",):
            raise HTTPException(400, "recurrence must be 'weekly' or omitted")
        pb = PrivateBooking(
            vendor_id=vendor["id"],
            **body.model_dump(),
            hours=body.hours or 1,
            amount=body.amount or 0,
            currency=body.currency or "INR",
        )
        await db.private_bookings.insert_one(pb.model_dump())
        return pb

    @api.get("/vendor/private-bookings", response_model=List[PrivateBooking])
    async def list_private_bookings(listing_id: Optional[str] = None, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        flt = {"vendor_id": vendor["id"]}
        if listing_id:
            flt["listing_id"] = listing_id
        docs = await db.private_bookings.find(flt, {"_id": 0}).sort("requested_date", -1).to_list(500)
        return [PrivateBooking(**d) for d in docs]

    @api.delete("/vendor/private-bookings/{booking_id}")
    async def delete_private_booking(booking_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        res = await db.private_bookings.delete_one({"id": booking_id, "vendor_id": vendor["id"]})
        if not res.deleted_count:
            raise HTTPException(404, "Booking not found")
        return {"ok": True}
