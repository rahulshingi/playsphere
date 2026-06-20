"""Services catalog + company/HR bookings (the original demand side, distinct from vendor-bookings).

Wired via `register(api, db, deps)` from server.py.
"""
from typing import List, Optional
from fastapi import Depends, HTTPException


def register(api, db, deps):
    Service = deps.Service
    ServiceCreate = deps.ServiceCreate
    Booking = deps.Booking
    BookingCreate = deps.BookingCreate
    get_current_user = deps.get_current_user
    require_company_admin = deps.require_company_admin
    require_super_admin = deps.require_super_admin

    # ---------- Services (catalog) ----------
    @api.get("/services", response_model=List[Service])
    async def list_services(category: Optional[str] = None, include_inactive: bool = False):
        q = {}
        if category:
            q["category"] = category
        if not include_inactive:
            q["active"] = True
        docs = await db.services.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
        return [Service(**d) for d in docs]

    @api.get("/services/{service_id}", response_model=Service)
    async def get_service(service_id: str):
        doc = await db.services.find_one({"id": service_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Service not found")
        return Service(**doc)

    @api.post("/services", response_model=Service)
    async def create_service(body: ServiceCreate, _: dict = Depends(require_super_admin)):
        s = Service(**body.model_dump())
        await db.services.insert_one(s.model_dump())
        return s

    @api.patch("/services/{service_id}", response_model=Service)
    async def update_service(service_id: str, body: dict, _: dict = Depends(require_super_admin)):
        body.pop("id", None)
        await db.services.update_one({"id": service_id}, {"$set": body})
        doc = await db.services.find_one({"id": service_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Service not found")
        return Service(**doc)

    @api.delete("/services/{service_id}")
    async def delete_service(service_id: str, _: dict = Depends(require_super_admin)):
        await db.services.delete_one({"id": service_id})
        return {"ok": True}

    # ---------- Bookings ----------
    @api.get("/bookings", response_model=List[Booking])
    async def list_bookings(user: dict = Depends(get_current_user)):
        if user.get("role") in ("platform_admin", "admin"):
            q = {}
        elif user.get("role") in ("company_admin", "organiser"):
            q = {"company_id": user.get("company_id")}
        else:
            raise HTTPException(403, "Forbidden")
        docs = await db.bookings.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [Booking(**d) for d in docs]

    @api.get("/bookings/{booking_id}", response_model=Booking)
    async def get_booking(booking_id: str, user: dict = Depends(get_current_user)):
        doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Booking not found")
        if user.get("role") in ("company_admin", "organiser") and doc["company_id"] != user.get("company_id"):
            raise HTTPException(403, "Forbidden")
        return Booking(**doc)

    @api.post("/bookings", response_model=Booking)
    async def create_booking(body: BookingCreate, user: dict = Depends(require_company_admin)):
        svc = await db.services.find_one({"id": body.service_id}, {"_id": 0})
        if not svc:
            raise HTTPException(404, "Service not found")
        company = await db.companies.find_one({"id": user.get("company_id")}, {"_id": 0})
        if not company:
            raise HTTPException(400, "Company missing")

        variant_price = 0.0
        variant_name = None
        if body.variant_id:
            v = next((v for v in svc.get("variants", []) if v["id"] == body.variant_id), None)
            if v:
                variant_price = float(v.get("extra_price", 0))
                variant_name = v.get("name")

        qty = max(1, int(body.quantity or 1))
        base_price = float(svc.get("base_price", 0))
        total = (base_price + variant_price) * qty

        booking = Booking(
            company_id=user["company_id"],
            company_name=company.get("name", ""),
            service_id=svc["id"],
            service_name=svc["name"],
            event_id=body.event_id,
            quantity=qty,
            config=body.config or {},
            variant_id=body.variant_id,
            variant_name=variant_name,
            custom_text=body.custom_text or "",
            notes=body.notes or "",
            base_price=base_price,
            variant_price=variant_price,
            total_price=total,
            currency=svc.get("currency", "USD"),
            status="pending",
            created_by=user["id"],
        )
        await db.bookings.insert_one(booking.model_dump())
        return booking

    @api.patch("/bookings/{booking_id}", response_model=Booking)
    async def update_booking(booking_id: str, body: dict, user: dict = Depends(get_current_user)):
        doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Booking not found")
        is_platform = user.get("role") in ("platform_admin", "admin")
        is_owner = user.get("role") in ("company_admin", "organiser") and doc["company_id"] == user.get("company_id")
        if not (is_platform or is_owner):
            raise HTTPException(403, "Forbidden")
        if is_owner and not is_platform and doc.get("status") != "pending":
            raise HTTPException(400, "Booking already processed")
        if not is_platform:
            body.pop("status", None)
        body.pop("id", None)
        body.pop("company_id", None)
        body.pop("total_price", None)
        await db.bookings.update_one({"id": booking_id}, {"$set": body})
        updated = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        return Booking(**updated)

    @api.delete("/bookings/{booking_id}")
    async def delete_booking(booking_id: str, user: dict = Depends(get_current_user)):
        doc = await db.bookings.find_one({"id": booking_id}, {"_id": 0})
        if not doc:
            return {"ok": True}
        if user.get("role") not in ("platform_admin", "admin"):
            if user.get("role") != "company_admin" or doc["company_id"] != user.get("company_id"):
                raise HTTPException(403, "Forbidden")
        await db.bookings.delete_one({"id": booking_id})
        return {"ok": True}
