"""Vendor memberships — Phase 1 (no payment yet).

A vendor can define recurring access products (monthly, daily pass, gym, weekend-only,
fixed time slot, open with N-hour advance booking). Players / companies will be able to
purchase them in Phase 2 once Razorpay credentials are wired.

Wired via `register(api, db, deps)` from server.py.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("kreeda.routes.memberships")


# ---------- Models ----------
PLAN_TYPES = {"monthly", "daily_pass", "gym", "weekend", "fixed_slot", "open"}


class MembershipPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vendor_id: str
    listing_ids: List[str] = Field(default_factory=list)  # which listings this plan unlocks
    title: str
    description: Optional[str] = ""
    plan_type: str  # one of PLAN_TYPES
    sports: List[str] = Field(default_factory=list)  # cricket / football / badminton / …
    price: float
    currency: str = "INR"
    duration_days: int = 30  # how long after purchase the membership stays valid
    max_bookings: Optional[int] = None  # None = unlimited within duration
    # Slot constraints (only used when plan_type == "fixed_slot")
    slot_days_of_week: List[int] = Field(default_factory=list)  # 0=Mon … 6=Sun
    slot_start_time: Optional[str] = None  # "06:00"
    slot_end_time: Optional[str] = None    # "07:00"
    # Booking rules
    advance_booking_hours: int = 48  # required notice before any session
    cover_image_url: Optional[str] = ""
    active: bool = True
    paused: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MembershipPlanCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    plan_type: str
    sports: List[str] = Field(default_factory=list)
    listing_ids: List[str] = Field(default_factory=list)
    price: float
    currency: str = "INR"
    duration_days: int = 30
    max_bookings: Optional[int] = None
    slot_days_of_week: List[int] = Field(default_factory=list)
    slot_start_time: Optional[str] = None
    slot_end_time: Optional[str] = None
    advance_booking_hours: int = 48
    cover_image_url: Optional[str] = ""


class MembershipPlanUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    plan_type: Optional[str] = None
    sports: Optional[List[str]] = None
    listing_ids: Optional[List[str]] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    duration_days: Optional[int] = None
    max_bookings: Optional[int] = None
    slot_days_of_week: Optional[List[int]] = None
    slot_start_time: Optional[str] = None
    slot_end_time: Optional[str] = None
    advance_booking_hours: Optional[int] = None
    cover_image_url: Optional[str] = None
    paused: Optional[bool] = None
    active: Optional[bool] = None


class MembershipPurchase(BaseModel):
    """A purchase of a membership plan by a player or company HR.

    Lifecycle:
      - status="pending_payment" → created by buyer, awaiting vendor confirmation of payment.
      - status="active" → vendor activated (offline payment received). starts_at set; expires_at = starts_at + plan.duration_days.
      - status="expired" → expires_at passed (computed lazily).
      - status="cancelled" → buyer or vendor cancelled before activation.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    vendor_id: str
    plan_title: str
    plan_type: str
    price: float
    currency: str = "INR"
    duration_days: int = 30
    max_bookings: Optional[int] = None
    # Buyer identity — exactly one of (user_id+role) is enough; convenience fields cached
    buyer_user_id: str
    buyer_role: str  # "company_admin" | "player" | "organiser"
    buyer_name: str = ""
    buyer_email: str = ""
    buyer_company_id: Optional[str] = None
    payment_method: str = "offline"  # "offline" | "online" (online stub for now)
    notes: Optional[str] = ""
    status: str = "pending_payment"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    starts_at: Optional[str] = None
    expires_at: Optional[str] = None
    bookings_used: int = 0
    cancelled_reason: Optional[str] = None
    issued_by_vendor: bool = False  # True if vendor walked-in created the purchase manually
    renewal_reminder_sent_at: Optional[str] = None  # ISO ts when the 7-day expiry reminder went out (idempotency)


class MembershipPurchaseRequest(BaseModel):
    plan_id: str
    payment_method: str = "offline"  # frontend can pass "online" — backend returns pending_payment regardless until Razorpay lands
    notes: Optional[str] = ""


class VendorManualIssueBody(BaseModel):
    """Vendor manually issues a membership to a walk-in customer (HR or player).

    The vendor types the buyer's email; we look up the existing user. If no user
    is found we fail clearly so vendor knows to ask the customer to sign up first.
    """
    plan_id: str
    buyer_email: str
    notes: Optional[str] = ""
    activate_immediately: bool = True


def register(api, db, deps):
    """deps must expose: get_current_user, require_role (`vendor` gate)."""
    get_current_user = deps.get_current_user

    async def _vendor_for_user(user: dict) -> dict:
        if user.get("role") != "vendor":
            raise HTTPException(403, "Only vendors can manage memberships")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor record not found for this user")
        return vendor

    async def _own_plan(plan_id: str, user: dict) -> dict:
        vendor = await _vendor_for_user(user)
        plan = await db.membership_plans.find_one({"id": plan_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "Membership plan not found")
        return plan

    # ---------- Vendor management ----------
    @api.get("/memberships/mine", response_model=List[MembershipPlan])
    async def list_my_memberships(user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        docs = await db.membership_plans.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return [MembershipPlan(**d) for d in docs]

    @api.post("/memberships/mine", response_model=MembershipPlan)
    async def create_my_membership(body: MembershipPlanCreate, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        if body.plan_type not in PLAN_TYPES:
            raise HTTPException(400, f"plan_type must be one of {sorted(PLAN_TYPES)}")
        # Validate listing ids actually belong to this vendor
        if body.listing_ids:
            count = await db.vendor_listings.count_documents(
                {"id": {"$in": body.listing_ids}, "vendor_id": vendor["id"]}
            )
            if count != len(set(body.listing_ids)):
                raise HTTPException(400, "One or more listings don't belong to you")
        plan = MembershipPlan(vendor_id=vendor["id"], **body.model_dump())
        await db.membership_plans.insert_one(plan.model_dump())
        return plan

    @api.patch("/memberships/mine/{plan_id}", response_model=MembershipPlan)
    async def update_my_membership(plan_id: str, body: MembershipPlanUpdate, user: dict = Depends(get_current_user)):
        await _own_plan(plan_id, user)
        upd = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if "plan_type" in upd and upd["plan_type"] not in PLAN_TYPES:
            raise HTTPException(400, f"plan_type must be one of {sorted(PLAN_TYPES)}")
        if upd:
            await db.membership_plans.update_one({"id": plan_id}, {"$set": upd})
        doc = await db.membership_plans.find_one({"id": plan_id}, {"_id": 0})
        return MembershipPlan(**doc)

    @api.delete("/memberships/mine/{plan_id}")
    async def delete_my_membership(plan_id: str, user: dict = Depends(get_current_user)):
        await _own_plan(plan_id, user)
        # Once any purchase exists for this plan we soft-deactivate instead — keeps
        # historic records intact for refunds / reporting.
        existing = await db.membership_purchases.count_documents({"plan_id": plan_id})
        if existing:
            await db.membership_plans.update_one(
                {"id": plan_id}, {"$set": {"active": False, "paused": True}}
            )
            return {"ok": True, "soft_deactivated": True, "purchases": existing}
        await db.membership_plans.delete_one({"id": plan_id})
        return {"ok": True, "soft_deactivated": False}

    # ---------- Public browse ----------
    @api.get("/memberships/vendor/{vendor_id}", response_model=List[MembershipPlan])
    async def list_vendor_memberships(vendor_id: str):
        docs = await db.membership_plans.find(
            {"vendor_id": vendor_id, "active": True, "paused": False}, {"_id": 0}
        ).sort("price", 1).to_list(200)
        return [MembershipPlan(**d) for d in docs]

    @api.get("/memberships/listing/{listing_id}", response_model=List[MembershipPlan])
    async def list_listing_memberships(listing_id: str):
        """Memberships usable at a specific listing. Plans with empty listing_ids cover
        every listing the vendor owns — we resolve that here so the public UI doesn't
        need to know that convention."""
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0, "vendor_id": 1})
        if not listing:
            return []
        docs = await db.membership_plans.find({
            "vendor_id": listing["vendor_id"],
            "active": True,
            "paused": False,
            "$or": [{"listing_ids": listing_id}, {"listing_ids": {"$size": 0}}],
        }, {"_id": 0}).sort("price", 1).to_list(200)
        return [MembershipPlan(**d) for d in docs]

    # ---------- Purchase flow (offline first; online stub for now) ----------
    def _buyer_payload(user: dict) -> dict:
        return {
            "buyer_user_id": user["id"],
            "buyer_role": user.get("role") or "viewer",
            "buyer_name": user.get("name") or "",
            "buyer_email": user.get("email") or "",
            "buyer_company_id": user.get("company_id"),
        }

    def _activation_dates(duration_days: int) -> tuple:
        now = datetime.now(timezone.utc)
        starts = now.isoformat()
        from datetime import timedelta
        expires = (now + timedelta(days=int(duration_days or 30))).isoformat()
        return starts, expires

    @api.post("/memberships/purchase", response_model=MembershipPurchase)
    async def request_purchase(body: MembershipPurchaseRequest, user: dict = Depends(get_current_user)):
        """A signed-in player / company HR requests to purchase a plan.

        Until Razorpay is wired, every request lands as `pending_payment` regardless
        of `payment_method`. The vendor activates from their dashboard after they
        receive cash / UPI / bank transfer.
        """
        if user.get("role") not in ("company_admin", "player", "organiser"):
            raise HTTPException(403, "Only company HR, organisers, or players can buy memberships")
        plan = await db.membership_plans.find_one({"id": body.plan_id, "active": True, "paused": False}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "Plan not available for purchase")
        # Prevent duplicate active OR pending purchase by the same buyer for this plan
        existing = await db.membership_purchases.find_one({
            "plan_id": plan["id"],
            "buyer_user_id": user["id"],
            "status": {"$in": ["pending_payment", "active"]},
        }, {"_id": 0})
        if existing:
            raise HTTPException(400, f"You already have a {existing['status'].replace('_', ' ')} request for this plan.")
        pm = (body.payment_method or "offline").lower()
        if pm not in ("offline", "online"):
            pm = "offline"
        purchase = MembershipPurchase(
            plan_id=plan["id"], vendor_id=plan["vendor_id"],
            plan_title=plan["title"], plan_type=plan["plan_type"],
            price=float(plan["price"]), currency=plan.get("currency", "INR"),
            duration_days=int(plan.get("duration_days", 30)),
            max_bookings=plan.get("max_bookings"),
            payment_method=pm, notes=body.notes or "",
            **_buyer_payload(user),
        )
        await db.membership_purchases.insert_one(purchase.model_dump())
        logger.info("membership purchase requested | buyer=%s plan=%s method=%s", user.get("email"), plan["id"], pm)
        return purchase

    @api.get("/memberships/my-purchases", response_model=List[MembershipPurchase])
    async def list_my_purchases(user: dict = Depends(get_current_user)):
        if user.get("role") not in ("company_admin", "player", "organiser"):
            raise HTTPException(403, "Forbidden")
        docs = await db.membership_purchases.find(
            {"buyer_user_id": user["id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(200)
        return [MembershipPurchase(**d) for d in docs]

    @api.post("/memberships/my-purchases/{purchase_id}/cancel", response_model=MembershipPurchase)
    async def cancel_my_purchase(purchase_id: str, body: dict = None, user: dict = Depends(get_current_user)):
        doc = await db.membership_purchases.find_one({"id": purchase_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Purchase not found")
        if doc["buyer_user_id"] != user["id"]:
            raise HTTPException(403, "Not your purchase")
        if doc["status"] not in ("pending_payment",):
            raise HTTPException(400, "Only pending_payment requests can be cancelled by the buyer")
        reason = (body or {}).get("reason", "Cancelled by buyer")
        await db.membership_purchases.update_one(
            {"id": purchase_id},
            {"$set": {"status": "cancelled", "cancelled_reason": reason}},
        )
        return MembershipPurchase(**(await db.membership_purchases.find_one({"id": purchase_id}, {"_id": 0})))

    # ---------- Vendor-side activation, manual issue, and listing of requests ----------
    @api.get("/memberships/mine/purchases", response_model=List[MembershipPurchase])
    async def list_vendor_purchases(status: Optional[str] = None, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        flt = {"vendor_id": vendor["id"]}
        if status:
            flt["status"] = status
        docs = await db.membership_purchases.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [MembershipPurchase(**d) for d in docs]

    @api.post("/memberships/mine/purchases/{purchase_id}/activate", response_model=MembershipPurchase)
    async def activate_purchase(purchase_id: str, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        doc = await db.membership_purchases.find_one({"id": purchase_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Purchase not found")
        if doc["status"] != "pending_payment":
            raise HTTPException(400, f"Cannot activate from status '{doc['status']}'")
        starts, expires = _activation_dates(doc.get("duration_days") or 30)
        await db.membership_purchases.update_one(
            {"id": purchase_id},
            {"$set": {"status": "active", "starts_at": starts, "expires_at": expires}},
        )
        return MembershipPurchase(**(await db.membership_purchases.find_one({"id": purchase_id}, {"_id": 0})))

    @api.post("/memberships/mine/purchases/{purchase_id}/reject", response_model=MembershipPurchase)
    async def reject_purchase(purchase_id: str, body: dict = None, user: dict = Depends(get_current_user)):
        vendor = await _vendor_for_user(user)
        doc = await db.membership_purchases.find_one({"id": purchase_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Purchase not found")
        if doc["status"] != "pending_payment":
            raise HTTPException(400, "Only pending_payment requests can be rejected")
        reason = (body or {}).get("reason", "Rejected by vendor")
        await db.membership_purchases.update_one(
            {"id": purchase_id},
            {"$set": {"status": "cancelled", "cancelled_reason": reason}},
        )
        return MembershipPurchase(**(await db.membership_purchases.find_one({"id": purchase_id}, {"_id": 0})))

    @api.post("/memberships/mine/issue", response_model=MembershipPurchase)
    async def vendor_issue_purchase(body: VendorManualIssueBody, user: dict = Depends(get_current_user)):
        """Vendor manually issues a membership to a walk-in customer.

        Looks up the customer by email in the users table. If `activate_immediately`
        is True (default) the purchase is created directly with status='active' —
        used when the vendor collected payment offline at the venue desk.
        """
        vendor = await _vendor_for_user(user)
        plan = await db.membership_plans.find_one({"id": body.plan_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not plan:
            raise HTTPException(404, "Plan not found in your catalogue")
        email = (body.buyer_email or "").strip().lower()
        if not email:
            raise HTTPException(400, "buyer_email is required")
        buyer = await db.users.find_one({"email": email}, {"_id": 0})
        if not buyer:
            raise HTTPException(404, f"No Kreeda Nation user with email '{email}' — ask them to sign up first.")
        if buyer.get("role") not in ("company_admin", "player", "organiser"):
            raise HTTPException(400, "Buyer must be a Player, HR, or Organiser account")
        status = "active" if body.activate_immediately else "pending_payment"
        starts, expires = (None, None)
        if body.activate_immediately:
            starts, expires = _activation_dates(plan.get("duration_days") or 30)
        purchase = MembershipPurchase(
            plan_id=plan["id"], vendor_id=vendor["id"],
            plan_title=plan["title"], plan_type=plan["plan_type"],
            price=float(plan["price"]), currency=plan.get("currency", "INR"),
            duration_days=int(plan.get("duration_days", 30)),
            max_bookings=plan.get("max_bookings"),
            payment_method="offline", notes=body.notes or "",
            buyer_user_id=buyer["id"], buyer_role=buyer.get("role") or "player",
            buyer_name=buyer.get("name") or "", buyer_email=buyer.get("email") or "",
            buyer_company_id=buyer.get("company_id"),
            status=status, starts_at=starts, expires_at=expires,
            issued_by_vendor=True,
        )
        await db.membership_purchases.insert_one(purchase.model_dump())
        return purchase

    # ---------- Phase 3 — Apply membership during booking ----------
    @api.get("/memberships/my-eligibility")
    async def my_eligibility(listing_id: str, user: dict = Depends(get_current_user)):
        """Returns the buyer's eligible active membership for a listing (if any).

        UI calls this when the booking modal opens and uses the response to show
        the 'Apply membership' toggle. Returns None inside `eligible` if no match.
        """
        if user.get("role") not in ("company_admin", "player", "organiser"):
            return {"eligible": None}
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0, "vendor_id": 1})
        if not listing:
            return {"eligible": None}
        now = datetime.now(timezone.utc).isoformat()
        actives = await db.membership_purchases.find({
            "buyer_user_id": user["id"],
            "vendor_id": listing["vendor_id"],
            "status": "active",
        }, {"_id": 0}).to_list(50)
        for mem in actives:
            if mem.get("expires_at") and mem["expires_at"] < now:
                continue
            plan = await db.membership_plans.find_one({"id": mem["plan_id"]}, {"_id": 0}) or {}
            plan_listings = plan.get("listing_ids") or []
            if plan_listings and listing_id not in plan_listings:
                continue
            max_b = mem.get("max_bookings")
            used = int(mem.get("bookings_used", 0))
            remaining = None if max_b is None else max(0, int(max_b) - used)
            if remaining is not None and remaining <= 0:
                continue
            return {"eligible": {
                "purchase_id": mem["id"],
                "plan_title": mem["plan_title"],
                "bookings_used": used,
                "bookings_allowed": max_b,
                "bookings_remaining": remaining,
                "expires_at": mem.get("expires_at"),
            }}
        return {"eligible": None}

    # ---------- Phase 4 — Utilization ----------
    @api.get("/memberships/purchase/{purchase_id}/utilization")
    async def purchase_utilization(purchase_id: str, user: dict = Depends(get_current_user)):
        """Side-by-side utilization for a purchase.

        Returns sessions_used vs sessions_allowed AND days_elapsed vs days_total —
        formatted as percentages so the UI can render two progress bars. Visible to
        the purchase owner OR the vendor who owns the plan.
        """
        doc = await db.membership_purchases.find_one({"id": purchase_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Purchase not found")
        # Authorise: buyer OR the vendor (via their vendor record)
        if doc["buyer_user_id"] != user["id"]:
            v = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
            if not v or v.get("id") != doc.get("vendor_id"):
                if user.get("role") not in ("platform_admin", "admin"):
                    raise HTTPException(403, "Forbidden")
        sessions_used = int(doc.get("bookings_used", 0))
        sessions_allowed = doc.get("max_bookings")
        sessions_percent = None if sessions_allowed is None else (
            round(min(100.0, (sessions_used / int(sessions_allowed)) * 100), 1) if int(sessions_allowed) else 0
        )
        days_total = int(doc.get("duration_days") or 30)
        days_elapsed = 0
        days_remaining = days_total
        if doc.get("starts_at"):
            try:
                started = datetime.fromisoformat(doc["starts_at"].replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                delta_days = (now - started).total_seconds() / 86400
                days_elapsed = max(0, min(days_total, int(delta_days)))
                days_remaining = max(0, days_total - days_elapsed)
            except ValueError:
                pass
        days_percent = round((days_elapsed / days_total) * 100, 1) if days_total else 0
        expired = doc.get("status") == "expired" or (
            doc.get("expires_at") and doc["expires_at"] < datetime.now(timezone.utc).isoformat()
        )
        return {
            "purchase_id": doc["id"],
            "status": doc.get("status"),
            "sessions_used": sessions_used,
            "sessions_allowed": sessions_allowed,
            "sessions_percent": sessions_percent,
            "days_elapsed": days_elapsed,
            "days_total": days_total,
            "days_remaining": days_remaining,
            "days_percent": days_percent,
            "expired": bool(expired),
        }


