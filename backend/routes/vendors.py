"""Vendor signup, listings (public + my), and admin listing approval routes.

Wired via `register(api, db, deps)` from server.py.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Response

from routes.auth import _consume_signup_otp_sync

logger = logging.getLogger("kreeda.routes.vendors")


def _public_app_url() -> str:
    return os.environ.get("PUBLIC_APP_URL", "https://kreedanation.com").rstrip("/")


def _vendor_decision_email_html(*, business_name: str, kind: str, status: str, reason: str = "") -> str:
    """Branded approval / rejection email body.
    kind: 'vendor' (the vendor business) or 'listing' (a specific listing).
    status: 'approved' or 'rejected'.
    """
    base_url = _public_app_url()
    if status == "approved":
        headline = "VENDOR APPROVED" if kind == "vendor" else "LISTING APPROVED"
        accent = "#EC4899" if kind == "vendor" else "#84CC16"
        body_html = (
            f"<p>Your {'vendor account' if kind == 'vendor' else 'listing'} <b style='color:{accent};'>{business_name}</b> "
            "has been approved by the Kreeda Nation team.</p>"
            + ("<p>You can now publish listings and start accepting bookings.</p>"
               if kind == "vendor" else
               "<p>It's now live on the public marketplace — players and HRs can discover and book it.</p>")
        )
        cta_label = "OPEN DASHBOARD"
        cta_path = "/vendor/dashboard"
    else:
        headline = "VENDOR NOT APPROVED" if kind == "vendor" else "LISTING NOT APPROVED"
        accent = "#FF3B30"
        safe_reason = reason or "No specific reason provided."
        body_html = (
            f"<p>Your {'vendor account' if kind == 'vendor' else 'listing'} <b style='color:#FF3B30;'>{business_name}</b> "
            "was not approved.</p>"
            "<p style='font-size:13px;color:#a3a3a3;'>Reason from the platform admin:</p>"
            f"<div style='background:#0a0a0a;border:1px solid #ffffff14;border-radius:4px;padding:14px;margin:8px 0 18px;font-family:ui-monospace,monospace;font-size:13px;color:#e5e5e5;'>{safe_reason}</div>"
            "<p>Update the details based on the feedback and resubmit when ready.</p>"
        )
        cta_label = "REVIEW DETAILS"
        cta_path = "/vendor/dashboard"
    return f"""
    <div style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;'>
      <div style='max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;'>
        <div style='font-size:11px;letter-spacing:.3em;color:{accent};text-transform:uppercase;font-family:ui-monospace,monospace;'>/ Approval update</div>
        <h1 style='font-size:28px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;'>{headline}</h1>
        {body_html}
        <p style='text-align:center;margin:28px 0;'>
          <a href='{base_url}{cta_path}' style='display:inline-block;background:{accent};color:#000;font-weight:700;padding:12px 28px;border-radius:4px;text-decoration:none;letter-spacing:.05em;'>{cta_label}</a>
        </p>
        <hr style='border:none;border-top:1px solid #ffffff14;margin:28px 0;'/>
        <p style='font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;'>Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """


async def _notify_vendor_decision(db, *, vendor_doc: dict, kind: str, status: str, reason: str = "", subject_object_name: Optional[str] = None):
    """Best-effort send. `vendor_doc` is a `vendors` record; uses its `email` field (or the
    user account email as fallback). Failures are swallowed."""
    email = (vendor_doc or {}).get("email")
    if not email and vendor_doc and vendor_doc.get("user_id"):
        u = await db.users.find_one({"id": vendor_doc["user_id"]}, {"_id": 0, "email": 1})
        email = (u or {}).get("email")
    if not email:
        return
    business_name = subject_object_name or vendor_doc.get("business_name", "your vendor account")
    object_label = "vendor account" if kind == "vendor" else f"listing '{business_name}'"
    subject = (
        f"[Kreeda Nation] Your {object_label} has been approved"
        if status == "approved"
        else f"[Kreeda Nation] Your {object_label} was not approved"
    )
    try:
        from email_service import send_email  # type: ignore
        send_email(
            to=email,
            subject=subject,
            html=_vendor_decision_email_html(business_name=business_name, kind=kind, status=status, reason=reason),
        )
    except Exception:
        logger.exception("Failed to dispatch vendor decision email")


def register(api, db, deps):
    UserPublic = deps.UserPublic
    VendorSignupBody = deps.VendorSignupBody
    Vendor = deps.Vendor
    VendorListing = deps.VendorListing
    VendorListingCreate = deps.VendorListingCreate
    hash_password = deps.hash_password
    create_access_token = deps.create_access_token
    set_auth_cookie = deps.set_auth_cookie
    get_current_user = deps.get_current_user
    require_platform_admin = deps.require_platform_admin
    require_permission = deps.require_permission

    consume_vendor_otp = _consume_signup_otp_sync(db, "vendor_signup_otps")

    # ---------- Vendor signup / self ----------
    @api.post("/vendors/signup", response_model=UserPublic)
    async def vendor_signup(body: VendorSignupBody, response: Response):
        email = body.email.lower()
        if await db.users.find_one({"email": email}):
            raise HTTPException(400, "Email already in use")

        otp_input = (getattr(body, "otp", None) or "").strip()
        if not otp_input:
            raise HTTPException(400, "Email verification code is required. Request one before signing up.")
        await consume_vendor_otp(email, otp_input)

        user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": user_id, "email": email, "name": body.contact_name, "role": "vendor",
            "company_id": None, "mobile": body.mobile,
            "password_hash": hash_password(body.password),
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        # Normalise multi-type: prefer client-supplied vendor_types, fall back to [vendor_type].
        types = list(dict.fromkeys([t for t in (body.vendor_types or []) if t])) or [body.vendor_type]
        primary = types[0]
        vendor = Vendor(
            user_id=user_id, business_name=body.business_name,
            vendor_type=primary, vendor_types=types,
            contact_name=body.contact_name, mobile=body.mobile, email=email, city=body.city,
        )
        await db.vendors.insert_one(vendor.model_dump())
        await db.vendor_signup_otps.update_one(
            {"email": email}, {"$set": {"verified": True, "used_at": datetime.now(timezone.utc).isoformat()}}
        )
        token = create_access_token(user_id, email, "vendor", None)
        set_auth_cookie(response, token)
        return UserPublic(id=user_id, email=email, name=body.contact_name, role="vendor",
                          company_id=None, company_name=None)

    @api.get("/vendors/me")
    async def get_my_vendor(user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        doc = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Vendor not found")
        return doc

    # ---------- Platform admin vendor management ----------
    @api.get("/vendors")
    async def list_vendors(approved: Optional[bool] = None, _: dict = Depends(require_platform_admin)):
        flt = {}
        if approved is not None:
            flt["approved"] = approved
        return await db.vendors.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)

    @api.patch("/vendors/{vendor_id}/approve")
    async def approve_vendor(vendor_id: str, body: dict, _: dict = Depends(require_permission("manage_vendors"))):
        approved = bool(body.get("approved", True))
        reason = (body.get("reason") or "").strip()
        ev = await db.vendors.find_one({"id": vendor_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Vendor not found")
        await db.vendors.update_one({"id": vendor_id}, {"$set": {"approved": approved}})
        # Approved → always notify. Rejected → notify only if a reason is provided
        # (avoids spamming on internal toggles).
        if approved:
            await _notify_vendor_decision(db, vendor_doc=ev, kind="vendor", status="approved")
        elif reason:
            await _notify_vendor_decision(db, vendor_doc=ev, kind="vendor", status="rejected", reason=reason)
        return {"ok": True, "approved": approved}

    # ---------- Public vendor listings ----------
    @api.get("/vendor-listings")
    async def list_public_listings(
        vendor_type: Optional[str] = None,
        city: Optional[str] = None,
        sport: Optional[str] = None,
    ):
        flt = {"approved": True, "active": True}
        if vendor_type:
            flt["vendor_type"] = vendor_type
        if city:
            flt["city"] = {"$regex": f"^{city}$", "$options": "i"}
        if sport:
            flt["sports"] = sport
        docs = await db.vendor_listings.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
        listing_ids = [L["id"] for L in docs]
        vendor_ids = list({L.get("vendor_id") for L in docs if L.get("vendor_id")})
        summaries = {}
        if listing_ids:
            async for s in db.reviews.aggregate([
                {"$match": {"listing_id": {"$in": listing_ids}, "status": "visible"}},
                {"$group": {"_id": "$listing_id", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
            ]):
                summaries[s["_id"]] = {"average": round(s["avg"] or 0, 2), "count": s["count"] or 0}

        # Pull every active membership for the relevant vendors so we can attach a
        # cheapest-plan summary to each listing — that's what powers the
        # "Recommended membership" badge in the UI.
        membership_by_listing: dict = {}
        membership_by_vendor_open: dict = {}
        if vendor_ids:
            async for plan in db.membership_plans.find(
                {"vendor_id": {"$in": vendor_ids}, "active": True, "paused": False},
                {"_id": 0, "vendor_id": 1, "listing_ids": 1, "price": 1, "currency": 1, "plan_type": 1},
            ):
                p = {"price": plan["price"], "currency": plan.get("currency", "INR"), "plan_type": plan["plan_type"]}
                if plan.get("listing_ids"):
                    for lid in plan["listing_ids"]:
                        cur = membership_by_listing.get(lid)
                        if not cur or p["price"] < cur["price"]:
                            membership_by_listing[lid] = p
                else:
                    # Empty listing_ids = plan covers every listing this vendor owns.
                    cur = membership_by_vendor_open.get(plan["vendor_id"])
                    if not cur or p["price"] < cur["price"]:
                        membership_by_vendor_open[plan["vendor_id"]] = p

        for L in docs:
            s = summaries.get(L["id"], {"average": 0, "count": 0})
            L["rating_average"] = s["average"]
            L["rating_count"] = s["count"]
            L["verified"] = s["count"] >= 5 and s["average"] >= 4.0
            specific = membership_by_listing.get(L["id"])
            open_plan = membership_by_vendor_open.get(L.get("vendor_id"))
            cheapest = None
            for cand in (specific, open_plan):
                if cand and (not cheapest or cand["price"] < cheapest["price"]):
                    cheapest = cand
            if cheapest:
                L["cheapest_membership"] = cheapest
        return docs

    @api.get("/vendor-listings/cities")
    async def list_listing_cities(sport: Optional[str] = None, vendor_type: Optional[str] = None):
        flt = {"approved": True, "active": True}
        if vendor_type:
            flt["vendor_type"] = vendor_type
        if sport:
            flt["sports"] = sport
        cities = await db.vendor_listings.distinct("city", flt)
        return sorted([c for c in cities if c])

    @api.get("/vendor-listings/{listing_id}")
    async def get_public_listing(listing_id: str):
        doc = await db.vendor_listings.find_one({"id": listing_id, "approved": True, "active": True}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Listing not available")
        # Attach the cheapest active membership covering this listing (or vendor-wide).
        vendor_id = doc.get("vendor_id")
        if vendor_id:
            cheapest = None
            async for plan in db.membership_plans.find({
                "vendor_id": vendor_id, "active": True, "paused": False,
                "$or": [{"listing_ids": listing_id}, {"listing_ids": {"$size": 0}}],
            }, {"_id": 0, "price": 1, "currency": 1, "plan_type": 1}):
                if cheapest is None or plan["price"] < cheapest["price"]:
                    cheapest = {"price": plan["price"], "currency": plan.get("currency", "INR"), "plan_type": plan["plan_type"]}
            if cheapest:
                doc["cheapest_membership"] = cheapest
        return doc

    # ---------- Vendor's own listings CRUD ----------
    @api.get("/vendors/me/listings")
    async def vendor_my_listings(user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor not registered")
        return await db.vendor_listings.find({"vendor_id": vendor["id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

    @api.post("/vendors/me/listings", response_model=VendorListing)
    async def create_listing(body: VendorListingCreate, user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        if not vendor:
            raise HTTPException(404, "Vendor not registered")
        payload = body.model_dump()
        listing_type = payload.pop("vendor_type", None) or vendor["vendor_type"]
        listing = VendorListing(
            vendor_id=vendor["id"], vendor_type=listing_type,
            **payload, approved=False,
        )
        await db.vendor_listings.insert_one(listing.model_dump())
        return listing

    @api.patch("/vendors/me/listings/{listing_id}")
    async def update_vendor_listing(listing_id: str, body: dict, user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
        if not vendor or not listing or listing["vendor_id"] != vendor["id"]:
            raise HTTPException(404, "Not found")
        body.pop("id", None)
        body.pop("vendor_id", None)
        body.pop("approved", None)
        if body.get("vendor_type") and body["vendor_type"] != listing.get("vendor_type"):
            body["approved"] = False
        await db.vendor_listings.update_one({"id": listing_id}, {"$set": body})
        return await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})

    @api.delete("/vendors/me/listings/{listing_id}")
    async def delete_vendor_listing(listing_id: str, user: dict = Depends(get_current_user)):
        if user.get("role") != "vendor":
            raise HTTPException(403, "Vendor only")
        vendor = await db.vendors.find_one({"user_id": user["id"]}, {"_id": 0})
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
        if vendor and listing and listing["vendor_id"] == vendor["id"]:
            await db.vendor_listings.delete_one({"id": listing_id})
        return {"ok": True}

    @api.get("/admin/listings")
    async def admin_list_listings(approved: Optional[bool] = None, _: dict = Depends(require_platform_admin)):
        flt = {}
        if approved is not None:
            flt["approved"] = approved
        return await db.vendor_listings.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)

    @api.patch("/admin/listings/{listing_id}/approve")
    async def approve_listing(listing_id: str, body: dict, _: dict = Depends(require_permission("manage_listings"))):
        approved = bool(body.get("approved", True))
        reason = (body.get("reason") or "").strip()
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(404, "Listing not found")
        await db.vendor_listings.update_one({"id": listing_id}, {"$set": {"approved": approved}})
        # Lookup the owning vendor so we can route the email to the right address.
        vendor_doc = await db.vendors.find_one({"id": listing.get("vendor_id")}, {"_id": 0}) or {}
        listing_title = listing.get("title") or listing.get("name") or "your listing"
        if approved:
            await _notify_vendor_decision(
                db, vendor_doc=vendor_doc, kind="listing", status="approved",
                subject_object_name=listing_title,
            )
        elif reason:
            await _notify_vendor_decision(
                db, vendor_doc=vendor_doc, kind="listing", status="rejected", reason=reason,
                subject_object_name=listing_title,
            )
        return {"ok": True, "approved": approved}
