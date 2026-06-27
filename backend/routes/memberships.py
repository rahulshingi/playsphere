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
