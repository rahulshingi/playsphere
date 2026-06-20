"""Vendor signup, listings (public + my), and admin listing approval routes.

Wired via `register(api, db, deps)` from server.py.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, Response

from routes.auth import _consume_signup_otp_sync


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
        vendor = Vendor(
            user_id=user_id, business_name=body.business_name, vendor_type=body.vendor_type,
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
        await db.vendors.update_one({"id": vendor_id}, {"$set": {"approved": approved}})
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
        docs = await db.vendor_listings.find(flt, {"_id": 0, "vendor_id": 0}).sort("created_at", -1).to_list(500)
        listing_ids = [L["id"] for L in docs]
        summaries = {}
        if listing_ids:
            async for s in db.reviews.aggregate([
                {"$match": {"listing_id": {"$in": listing_ids}, "status": "visible"}},
                {"$group": {"_id": "$listing_id", "avg": {"$avg": "$rating"}, "count": {"$sum": 1}}},
            ]):
                summaries[s["_id"]] = {"average": round(s["avg"] or 0, 2), "count": s["count"] or 0}
        for L in docs:
            s = summaries.get(L["id"], {"average": 0, "count": 0})
            L["rating_average"] = s["average"]
            L["rating_count"] = s["count"]
            L["verified"] = s["count"] >= 5 and s["average"] >= 4.0
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
        doc = await db.vendor_listings.find_one({"id": listing_id, "approved": True, "active": True}, {"_id": 0, "vendor_id": 0})
        if not doc:
            raise HTTPException(404, "Listing not available")
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
        await db.vendor_listings.update_one({"id": listing_id}, {"$set": {"approved": approved}})
        return {"ok": True, "approved": approved}
