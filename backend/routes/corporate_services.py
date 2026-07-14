"""Corporate Services (RFQ) — admin-configurable event package catalogue.

Phase 1 delivers admin CRUD only. No customer-facing endpoints yet — those
land in Phase 2 (storefront) and Phase 3 (quotation + negotiation).

Model (all Mongo collections, no PII beyond user_id):
  • service_categories        — top-level buckets ("Internal Tournament", "Yoga")
  • cs_services               — the atomic inclusions ("Referee", "Water bottles")
  • cs_addons                 — optional line-items ("Photography", "Live streaming")
  • cs_packages               — a category's tier ("Starter", "Standard", "Premium")
  • cs_package_services       — many-to-many: which services a package includes
  • cs_package_addons         — many-to-many: which add-ons a package offers
  • cs_rfqs                   — HR-submitted request (created in Phase 2)
  • cs_rfq_items              — services + addons snapshot at RFQ time (Phase 2)
  • cs_quotations             — admin's quote (Phase 3)
  • cs_quotation_items        — quotation line items with admin-set amounts (Phase 3)
  • cs_rfq_messages           — negotiation chat (Phase 3)
  • cs_status_history         — audit trail (Phase 3)

CRITICAL: NO PRICING ever surfaces to HR/Organiser before Admin sends a
quotation. Admin sets prices only inside cs_quotation_items.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field


# ─────────────────────────── Models ───────────────────────────

class ServiceCategory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    slug: str = ""
    description: str = ""
    icon_url: Optional[str] = None
    cover_url: Optional[str] = None
    active: bool = True
    sort_order: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CSService(BaseModel):
    """An atomic inclusion — e.g. 'Referee', 'Water bottles', 'First aid'."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    icon_url: Optional[str] = None
    image_url: Optional[str] = None
    category_id: Optional[str] = None  # loose grouping (not the top-level ServiceCategory)
    unit_type: str = "per event"       # per event / per person / per team / per hour / per day / per match
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CSAddon(BaseModel):
    """Optional add-on — 'Photography', 'Trophies', 'DJ', etc."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str = ""
    image_url: Optional[str] = None
    unit_type: str = "per event"
    custom_quantity_enabled: bool = True
    active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CSPackage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category_id: str
    name: str
    description: str = ""
    tier: str = "standard"  # starter / standard / premium / enterprise (free-form)
    banner_url: Optional[str] = None
    cover_url: Optional[str] = None
    gallery: List[str] = Field(default_factory=list)
    video_urls: List[str] = Field(default_factory=list)
    included_service_ids: List[str] = Field(default_factory=list)
    optional_addon_ids: List[str] = Field(default_factory=list)
    active: bool = True
    sort_order: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─────────────────────────── Registration ───────────────────────────

def register(api: Any, db: Any, deps: Any) -> None:
    get_current_user = deps.get_current_user
    require_platform_admin = deps.require_platform_admin

    def _serialise(doc: dict) -> dict:
        return {k: v for k, v in doc.items() if k != "_id"}

    def _slugify(name: str) -> str:
        return "".join(c if c.isalnum() else "-" for c in (name or "").lower()).strip("-")[:64]

    # ─────────────── Service Categories ───────────────
    @api.get("/corporate-services/categories", response_model=List[ServiceCategory])
    async def list_categories(include_inactive: bool = False):
        flt: dict = {} if include_inactive else {"active": True}
        docs = await db.service_categories.find(flt, {"_id": 0}).sort([("sort_order", 1), ("name", 1)]).to_list(500)
        return [ServiceCategory(**d) for d in docs]

    @api.post("/admin/corporate-services/categories", response_model=ServiceCategory)
    async def create_category(body: dict, _: dict = Depends(require_platform_admin)):
        cat = ServiceCategory(**{k: body[k] for k in body if k in ServiceCategory.model_fields})
        if not cat.slug:
            cat.slug = _slugify(cat.name)
        await db.service_categories.insert_one(cat.model_dump())
        return cat

    @api.patch("/admin/corporate-services/categories/{cat_id}", response_model=ServiceCategory)
    async def update_category(cat_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = {"name", "slug", "description", "icon_url", "cover_url", "active", "sort_order"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No updatable fields")
        res = await db.service_categories.update_one({"id": cat_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Category not found")
        doc = await db.service_categories.find_one({"id": cat_id}, {"_id": 0})
        return ServiceCategory(**doc)

    @api.delete("/admin/corporate-services/categories/{cat_id}")
    async def delete_category(cat_id: str, _: dict = Depends(require_platform_admin)):
        # Guard: refuse deletion if packages still reference this category.
        in_use = await db.cs_packages.count_documents({"category_id": cat_id})
        if in_use:
            raise HTTPException(409, f"Category is used by {in_use} package(s). Deactivate or reassign first.")
        await db.service_categories.delete_one({"id": cat_id})
        return {"ok": True}

    # ─────────────── Services ───────────────
    @api.get("/corporate-services/services", response_model=List[CSService])
    async def list_services(include_inactive: bool = False):
        flt: dict = {} if include_inactive else {"active": True}
        docs = await db.cs_services.find(flt, {"_id": 0}).sort("name", 1).to_list(1000)
        return [CSService(**d) for d in docs]

    @api.post("/admin/corporate-services/services", response_model=CSService)
    async def create_service(body: dict, _: dict = Depends(require_platform_admin)):
        svc = CSService(**{k: body[k] for k in body if k in CSService.model_fields})
        await db.cs_services.insert_one(svc.model_dump())
        return svc

    @api.patch("/admin/corporate-services/services/{svc_id}", response_model=CSService)
    async def update_service(svc_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = set(CSService.model_fields.keys()) - {"id", "created_at"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No updatable fields")
        res = await db.cs_services.update_one({"id": svc_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Service not found")
        doc = await db.cs_services.find_one({"id": svc_id}, {"_id": 0})
        return CSService(**doc)

    @api.delete("/admin/corporate-services/services/{svc_id}")
    async def delete_service(svc_id: str, _: dict = Depends(require_platform_admin)):
        # Remove references from any packages first
        await db.cs_packages.update_many({}, {"$pull": {"included_service_ids": svc_id}})
        await db.cs_services.delete_one({"id": svc_id})
        return {"ok": True}

    # ─────────────── Add-ons ───────────────
    @api.get("/corporate-services/addons", response_model=List[CSAddon])
    async def list_addons(include_inactive: bool = False):
        flt: dict = {} if include_inactive else {"active": True}
        docs = await db.cs_addons.find(flt, {"_id": 0}).sort("name", 1).to_list(1000)
        return [CSAddon(**d) for d in docs]

    @api.post("/admin/corporate-services/addons", response_model=CSAddon)
    async def create_addon(body: dict, _: dict = Depends(require_platform_admin)):
        addon = CSAddon(**{k: body[k] for k in body if k in CSAddon.model_fields})
        await db.cs_addons.insert_one(addon.model_dump())
        return addon

    @api.patch("/admin/corporate-services/addons/{addon_id}", response_model=CSAddon)
    async def update_addon(addon_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = set(CSAddon.model_fields.keys()) - {"id", "created_at"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No updatable fields")
        res = await db.cs_addons.update_one({"id": addon_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Add-on not found")
        doc = await db.cs_addons.find_one({"id": addon_id}, {"_id": 0})
        return CSAddon(**doc)

    @api.delete("/admin/corporate-services/addons/{addon_id}")
    async def delete_addon(addon_id: str, _: dict = Depends(require_platform_admin)):
        await db.cs_packages.update_many({}, {"$pull": {"optional_addon_ids": addon_id}})
        await db.cs_addons.delete_one({"id": addon_id})
        return {"ok": True}

    # ─────────────── Packages ───────────────
    @api.get("/corporate-services/packages")
    async def list_packages(category_id: Optional[str] = None, include_inactive: bool = False):
        flt: dict = {}
        if not include_inactive:
            flt["active"] = True
        if category_id:
            flt["category_id"] = category_id
        docs = await db.cs_packages.find(flt, {"_id": 0}).sort([("sort_order", 1), ("name", 1)]).to_list(500)
        # Hydrate included services + optional addons so the storefront doesn't
        # need to make N+1 requests per package tile.
        svc_ids = list({sid for d in docs for sid in d.get("included_service_ids", [])})
        add_ids = list({aid for d in docs for aid in d.get("optional_addon_ids", [])})
        svcs = await db.cs_services.find({"id": {"$in": svc_ids}}, {"_id": 0}).to_list(len(svc_ids) or 1)
        adds = await db.cs_addons.find({"id": {"$in": add_ids}}, {"_id": 0}).to_list(len(add_ids) or 1)
        svc_map = {s["id"]: s for s in svcs}
        add_map = {a["id"]: a for a in adds}
        for d in docs:
            d["included_services"] = [svc_map[i] for i in d.get("included_service_ids", []) if i in svc_map]
            d["optional_addons"] = [add_map[i] for i in d.get("optional_addon_ids", []) if i in add_map]
        return docs

    @api.post("/admin/corporate-services/packages", response_model=CSPackage)
    async def create_package(body: dict, _: dict = Depends(require_platform_admin)):
        if not body.get("category_id"):
            raise HTTPException(400, "category_id required")
        pkg = CSPackage(**{k: body[k] for k in body if k in CSPackage.model_fields})
        await db.cs_packages.insert_one(pkg.model_dump())
        return pkg

    @api.patch("/admin/corporate-services/packages/{pkg_id}", response_model=CSPackage)
    async def update_package(pkg_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = set(CSPackage.model_fields.keys()) - {"id", "created_at"}
        upd = {k: v for k, v in body.items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No updatable fields")
        res = await db.cs_packages.update_one({"id": pkg_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Package not found")
        doc = await db.cs_packages.find_one({"id": pkg_id}, {"_id": 0})
        return CSPackage(**doc)

    @api.delete("/admin/corporate-services/packages/{pkg_id}")
    async def delete_package(pkg_id: str, _: dict = Depends(require_platform_admin)):
        # Guard: refuse if any RFQs already reference this package
        in_use = await db.cs_rfqs.count_documents({"package_id": pkg_id})
        if in_use:
            raise HTTPException(409, f"Package is referenced by {in_use} RFQ(s). Deactivate instead of deleting.")
        await db.cs_packages.delete_one({"id": pkg_id})
        return {"ok": True}

    # ─────────────── Admin summary (for dashboard KPIs later) ───────────────
    @api.get("/admin/corporate-services/summary")
    async def cs_summary(_: dict = Depends(require_platform_admin)):
        return {
            "categories":  await db.service_categories.count_documents({}),
            "categories_active": await db.service_categories.count_documents({"active": True}),
            "services":    await db.cs_services.count_documents({}),
            "addons":      await db.cs_addons.count_documents({}),
            "packages":    await db.cs_packages.count_documents({}),
            "packages_active": await db.cs_packages.count_documents({"active": True}),
            "rfqs_total":  await db.cs_rfqs.count_documents({}),
            "rfqs_pending":  await db.cs_rfqs.count_documents({"status": {"$in": ["submitted", "under_review"]}}),
        }

    # ─────────────── RFQs (Phase 2 — HR/Organiser submit + track) ───────────────
    def _hr_only(user: dict):
        if user.get("role") not in ("company_admin", "organiser"):
            raise HTTPException(403, "Corporate Services RFQ is for HR / Organiser accounts only")

    ALLOWED_STATUSES = {"draft", "submitted", "under_review", "quoted", "negotiation", "approved", "rejected", "completed", "cancelled"}

    @api.post("/rfqs")
    async def create_rfq(body: dict, user: dict = Depends(get_current_user)):
        _hr_only(user)
        pkg_id = (body or {}).get("package_id")
        if not pkg_id:
            raise HTTPException(400, "package_id required")
        pkg = await db.cs_packages.find_one({"id": pkg_id}, {"_id": 0})
        if not pkg:
            raise HTTPException(404, "Package not found")
        # Snapshot the package + selections so subsequent catalogue edits don't
        # mutate a submitted RFQ. Frontend passes the selected subset of service
        # IDs and addon quantities.
        sel_services = list(dict.fromkeys((body or {}).get("selected_service_ids") or pkg.get("included_service_ids") or []))
        sel_addons = (body or {}).get("selected_addons") or []  # [{addon_id, quantity}]
        # Validate references
        svc_docs = await db.cs_services.find({"id": {"$in": sel_services}}, {"_id": 0}).to_list(len(sel_services) or 1)
        add_ids = [a.get("addon_id") for a in sel_addons if a.get("addon_id")]
        add_docs = await db.cs_addons.find({"id": {"$in": add_ids}}, {"_id": 0}).to_list(len(add_ids) or 1)
        add_map = {a["id"]: a for a in add_docs}
        addon_snapshots = []
        for a in sel_addons:
            if a.get("addon_id") not in add_map:
                continue
            meta = add_map[a["addon_id"]]
            addon_snapshots.append({
                "addon_id": a["addon_id"],
                "name": meta["name"],
                "unit_type": meta.get("unit_type"),
                "quantity": max(1, int(a.get("quantity") or 1)),
            })
        # Event details — free-form dict, validate a few required keys.
        event = (body or {}).get("event") or {}
        if not (event.get("event_name") and event.get("preferred_date")):
            raise HTTPException(400, "event.event_name and event.preferred_date are required")
        now = datetime.now(timezone.utc).isoformat()
        submit_now = (body or {}).get("submit", True)
        rfq = {
            "id": str(uuid.uuid4()),
            "hr_user_id": user["id"],
            "hr_email": user.get("email"),
            "hr_name": user.get("name"),
            "company_id": user.get("company_id"),
            "company_name": user.get("company_name"),
            "package_id": pkg_id,
            "package_name": pkg["name"],
            "category_id": pkg["category_id"],
            "selected_service_ids": sel_services,
            "included_services_snapshot": [{"id": s["id"], "name": s["name"], "unit_type": s.get("unit_type")} for s in svc_docs],
            "selected_addons": addon_snapshots,
            "event": event,
            "expected_budget": (body or {}).get("expected_budget") or "",
            "special_instructions": (body or {}).get("special_instructions") or "",
            "status": "submitted" if submit_now else "draft",
            "created_at": now,
            "updated_at": now,
            "submitted_at": now if submit_now else None,
        }
        await db.cs_rfqs.insert_one(rfq)
        # Audit trail
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq["id"], "actor_id": user["id"],
            "from_status": None, "to_status": rfq["status"], "at": now,
        })
        rfq.pop("_id", None)
        return rfq

    @api.get("/rfqs/mine")
    async def my_rfqs(status: Optional[str] = None, user: dict = Depends(get_current_user)):
        _hr_only(user)
        flt = {"hr_user_id": user["id"]}
        if status and status != "all":
            flt["status"] = status
        docs = await db.cs_rfqs.find(flt, {"_id": 0}).sort("created_at", -1).to_list(500)
        return docs

    @api.get("/rfqs/{rfq_id}")
    async def get_rfq(rfq_id: str, user: dict = Depends(get_current_user)):
        doc = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "RFQ not found")
        role = user.get("role")
        if role in ("platform_admin", "admin"):
            return doc
        if doc["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        return doc

    @api.post("/rfqs/{rfq_id}/cancel")
    async def cancel_rfq(rfq_id: str, user: dict = Depends(get_current_user)):
        doc = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not doc or doc["hr_user_id"] != user["id"]:
            raise HTTPException(404, "RFQ not found")
        if doc["status"] in ("approved", "completed", "cancelled"):
            raise HTTPException(400, f"Cannot cancel an RFQ in status '{doc['status']}'")
        now = datetime.now(timezone.utc).isoformat()
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "cancelled", "updated_at": now}})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": doc["status"], "to_status": "cancelled", "at": now,
        })
        return {"ok": True}

    # ═══════════════════════════════════════════════════════════════════
    # PHASE 3 — Internal Service Vendors + Admin RFQ inbox + Quotations
    # ═══════════════════════════════════════════════════════════════════
    #
    # STRICT separation from Venue Vendors:
    #   • `service_vendors` collection is Admin-internal only.
    #   • Vendors have NO login/portal/notifications.
    #   • Only surfaces on the admin's RFQ workflow to compute internal cost.
    #
    # Pricing visibility rule:
    #   • HR/Organiser never sees cs_internal_cost_sheets or per-vendor rates.
    #   • They only see cs_quotations *after* Admin sends them (status=sent).

    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _admin_only(user: dict) -> None:
        if user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Admin only")

    # ─────────────── Service Vendors CRUD ───────────────
    @api.get("/admin/service-vendors")
    async def list_service_vendors(
        include_inactive: bool = False,
        city: Optional[str] = None,
        service_id: Optional[str] = None,
        _: dict = Depends(require_platform_admin),
    ):
        flt: dict = {} if include_inactive else {"active": True}
        if city:
            flt["city"] = {"$regex": f"^{city}$", "$options": "i"}
        docs = await db.service_vendors.find(flt, {"_id": 0}).sort([("preferred", -1), ("name", 1)]).to_list(1000)
        if service_id:
            docs = [d for d in docs if service_id in (d.get("service_ids") or [])]
        # Attach rate-card count per vendor (fast: one aggregation)
        vids = [d["id"] for d in docs]
        if vids:
            cursor = db.cs_vendor_rates.aggregate([
                {"$match": {"vendor_id": {"$in": vids}}},
                {"$group": {"_id": "$vendor_id", "n": {"$sum": 1}}},
            ])
            rate_counts = {row["_id"]: row["n"] async for row in cursor}
            for d in docs:
                d["rate_count"] = rate_counts.get(d["id"], 0)
        return docs

    @api.post("/admin/service-vendors")
    async def create_service_vendor(body: dict, _: dict = Depends(require_platform_admin)):
        name = (body or {}).get("name")
        if not name:
            raise HTTPException(400, "name required")
        vendor = {
            "id": str(uuid.uuid4()),
            "name": name,
            "contact_person": body.get("contact_person") or "",
            "contact_email": body.get("contact_email") or "",
            "contact_phone": body.get("contact_phone") or "",
            "city": (body.get("city") or "").strip(),
            "state": (body.get("state") or "").strip(),
            "gst_number": body.get("gst_number") or "",
            "address": body.get("address") or "",
            "notes": body.get("notes") or "",
            "service_ids": list(dict.fromkeys(body.get("service_ids") or [])),
            "preferred": bool(body.get("preferred") or False),
            "active": bool(body.get("active", True)),
            "created_at": _now(),
            "updated_at": _now(),
        }
        await db.service_vendors.insert_one(vendor)
        return _serialise(vendor)

    @api.patch("/admin/service-vendors/{vendor_id}")
    async def update_service_vendor(vendor_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = {"name", "contact_person", "contact_email", "contact_phone", "city", "state",
                   "gst_number", "address", "notes", "service_ids", "preferred", "active"}
        upd = {k: v for k, v in (body or {}).items() if k in allowed}
        if not upd:
            raise HTTPException(400, "No updatable fields")
        if "service_ids" in upd:
            upd["service_ids"] = list(dict.fromkeys(upd["service_ids"] or []))
        upd["updated_at"] = _now()
        res = await db.service_vendors.update_one({"id": vendor_id}, {"$set": upd})
        if not res.matched_count:
            raise HTTPException(404, "Vendor not found")
        doc = await db.service_vendors.find_one({"id": vendor_id}, {"_id": 0})
        return doc

    @api.delete("/admin/service-vendors/{vendor_id}")
    async def delete_service_vendor(vendor_id: str, _: dict = Depends(require_platform_admin)):
        # Refuse deletion if vendor is assigned to any active cost sheet
        in_use = await db.cs_internal_cost_sheets.count_documents(
            {"lines.vendor_id": vendor_id}
        )
        if in_use:
            raise HTTPException(409, f"Vendor is referenced by {in_use} cost sheet(s). Deactivate instead.")
        await db.service_vendors.delete_one({"id": vendor_id})
        await db.cs_vendor_rates.delete_many({"vendor_id": vendor_id})
        return {"ok": True}

    # ─────────────── Vendor Rate Cards ───────────────
    # Each rate maps a (vendor, service) tuple to an internal price + unit_type.
    @api.get("/admin/service-vendors/{vendor_id}/rates")
    async def list_vendor_rates(vendor_id: str, _: dict = Depends(require_platform_admin)):
        docs = await db.cs_vendor_rates.find({"vendor_id": vendor_id}, {"_id": 0}).to_list(500)
        return docs

    @api.post("/admin/service-vendors/{vendor_id}/rates")
    async def upsert_vendor_rate(vendor_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        vendor = await db.service_vendors.find_one({"id": vendor_id})
        if not vendor:
            raise HTTPException(404, "Vendor not found")
        svc_id = (body or {}).get("service_id")
        if not svc_id:
            raise HTTPException(400, "service_id required")
        svc = await db.cs_services.find_one({"id": svc_id}, {"_id": 0})
        if not svc:
            raise HTTPException(404, "Service not found")
        rate = {
            "id": str(uuid.uuid4()),
            "vendor_id": vendor_id,
            "service_id": svc_id,
            "service_name": svc["name"],
            "rate": float(body.get("rate") or 0),
            "unit_type": body.get("unit_type") or svc.get("unit_type") or "per event",
            "min_quantity": int(body.get("min_quantity") or 1),
            "notes": body.get("notes") or "",
            "created_at": _now(),
        }
        # upsert on (vendor_id, service_id)
        existing = await db.cs_vendor_rates.find_one({"vendor_id": vendor_id, "service_id": svc_id})
        if existing:
            await db.cs_vendor_rates.update_one(
                {"id": existing["id"]},
                {"$set": {"rate": rate["rate"], "unit_type": rate["unit_type"],
                          "min_quantity": rate["min_quantity"], "notes": rate["notes"]}},
            )
            rate["id"] = existing["id"]
            rate["created_at"] = existing.get("created_at", rate["created_at"])
        else:
            await db.cs_vendor_rates.insert_one(rate)
            # Also auto-append service_id to vendor's service_ids
            if svc_id not in (vendor.get("service_ids") or []):
                await db.service_vendors.update_one(
                    {"id": vendor_id}, {"$addToSet": {"service_ids": svc_id}}
                )
        return _serialise(rate)

    @api.delete("/admin/service-vendors/{vendor_id}/rates/{rate_id}")
    async def delete_vendor_rate(vendor_id: str, rate_id: str, _: dict = Depends(require_platform_admin)):
        await db.cs_vendor_rates.delete_one({"id": rate_id, "vendor_id": vendor_id})
        return {"ok": True}

    # ─────────────── Admin RFQ Inbox ───────────────
    @api.get("/admin/rfqs")
    async def admin_list_rfqs(status: Optional[str] = None, _: dict = Depends(require_platform_admin)):
        flt: dict = {}
        if status and status != "all":
            flt["status"] = status
        docs = await db.cs_rfqs.find(flt, {"_id": 0}).sort("created_at", -1).to_list(1000)
        # Attach latest quote version + total for the list
        rfq_ids = [d["id"] for d in docs]
        if rfq_ids:
            cursor = db.cs_quotations.find({"rfq_id": {"$in": rfq_ids}}, {"_id": 0}).sort("version", -1)
            latest_by_rfq: dict = {}
            async for q in cursor:
                latest_by_rfq.setdefault(q["rfq_id"], q)
            for d in docs:
                q = latest_by_rfq.get(d["id"])
                d["latest_quote"] = {
                    "version": q.get("version"),
                    "total": q.get("total_selling"),
                    "status": q.get("status"),
                    "sent_at": q.get("sent_at"),
                } if q else None
        return docs

    @api.get("/admin/rfqs/summary")
    async def admin_rfq_summary(_: dict = Depends(require_platform_admin)):
        pipeline = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
        counts: dict = {row["_id"]: row["n"] async for row in db.cs_rfqs.aggregate(pipeline)}
        return {
            "total": sum(counts.values()),
            "by_status": counts,
            "action_needed": counts.get("submitted", 0) + counts.get("under_review", 0) + counts.get("negotiation", 0),
        }

    @api.post("/admin/rfqs/{rfq_id}/mark-under-review")
    async def admin_mark_under_review(rfq_id: str, user: dict = Depends(require_platform_admin)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        if rfq["status"] != "submitted":
            raise HTTPException(400, f"RFQ already in status '{rfq['status']}'")
        now = _now()
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "under_review", "updated_at": now}})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": "submitted", "to_status": "under_review", "at": now,
        })
        return {"ok": True}

    # ─────────────── Vendor Auto-Suggest ───────────────
    # Ranking (per user choice): city match first → preferred flag → lowest rate.
    @api.get("/admin/rfqs/{rfq_id}/suggest-vendors")
    async def suggest_vendors_for_rfq(rfq_id: str, _: dict = Depends(require_platform_admin)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        city = ((rfq.get("event") or {}).get("city") or "").strip().lower()
        state = ((rfq.get("event") or {}).get("state") or "").strip().lower()
        results: List[dict] = []
        for svc_id in rfq.get("selected_service_ids") or []:
            svc = await db.cs_services.find_one({"id": svc_id}, {"_id": 0})
            if not svc:
                continue
            # Find all vendor rates for this service, join vendor metadata.
            rates = await db.cs_vendor_rates.find({"service_id": svc_id}, {"_id": 0}).to_list(500)
            vendor_ids = [r["vendor_id"] for r in rates]
            vendors = await db.service_vendors.find(
                {"id": {"$in": vendor_ids}, "active": True}, {"_id": 0}
            ).to_list(len(vendor_ids) or 1)
            vmap = {v["id"]: v for v in vendors}
            suggestions = []
            for r in rates:
                v = vmap.get(r["vendor_id"])
                if not v:
                    continue
                city_match = (v.get("city") or "").strip().lower() == city and city != ""
                state_match = (v.get("state") or "").strip().lower() == state and state != ""
                suggestions.append({
                    "vendor_id": v["id"],
                    "vendor_name": v["name"],
                    "city": v.get("city"),
                    "state": v.get("state"),
                    "preferred": bool(v.get("preferred")),
                    "rate": r["rate"],
                    "unit_type": r.get("unit_type"),
                    "min_quantity": r.get("min_quantity", 1),
                    "city_match": city_match,
                    "state_match": state_match,
                })
            # Rank: city_match desc → preferred desc → state_match desc → rate asc
            suggestions.sort(key=lambda s: (
                not s["city_match"],
                not s["preferred"],
                not s["state_match"],
                s["rate"],
            ))
            results.append({
                "service_id": svc_id,
                "service_name": svc["name"],
                "unit_type": svc.get("unit_type"),
                "suggestions": suggestions,
            })
        return {"rfq_id": rfq_id, "services": results}

    # ─────────────── Internal Cost Sheet ───────────────
    # Structure:
    #   { id, rfq_id, lines:[{line_id, kind, service_id/addon_id, name,
    #     vendor_id, vendor_name, quantity, unit_rate, unit_type, cost}],
    #     total_cost, updated_at, updated_by }
    @api.get("/admin/rfqs/{rfq_id}/cost-sheet")
    async def get_cost_sheet(rfq_id: str, _: dict = Depends(require_platform_admin)):
        sheet = await db.cs_internal_cost_sheets.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not sheet:
            # Auto-seed: one line per selected service + each selected addon, no vendor.
            rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
            if not rfq:
                raise HTTPException(404, "RFQ not found")
            svc_docs = await db.cs_services.find(
                {"id": {"$in": rfq.get("selected_service_ids") or []}}, {"_id": 0}
            ).to_list(200)
            svc_map = {s["id"]: s for s in svc_docs}
            lines: List[dict] = []
            for sid in rfq.get("selected_service_ids") or []:
                s = svc_map.get(sid)
                if not s:
                    continue
                lines.append({
                    "line_id": str(uuid.uuid4()),
                    "kind": "service",
                    "service_id": sid,
                    "name": s["name"],
                    "vendor_id": None,
                    "vendor_name": None,
                    "quantity": 1,
                    "unit_rate": 0.0,
                    "unit_type": s.get("unit_type"),
                    "cost": 0.0,
                })
            for a in rfq.get("selected_addons") or []:
                lines.append({
                    "line_id": str(uuid.uuid4()),
                    "kind": "addon",
                    "addon_id": a["addon_id"],
                    "name": a["name"],
                    "vendor_id": None,
                    "vendor_name": None,
                    "quantity": int(a.get("quantity") or 1),
                    "unit_rate": 0.0,
                    "unit_type": a.get("unit_type"),
                    "cost": 0.0,
                })
            sheet = {
                "id": str(uuid.uuid4()),
                "rfq_id": rfq_id,
                "lines": lines,
                "total_cost": 0.0,
                "created_at": _now(),
                "updated_at": _now(),
            }
            await db.cs_internal_cost_sheets.insert_one(sheet)
            sheet.pop("_id", None)
        return sheet

    @api.put("/admin/rfqs/{rfq_id}/cost-sheet")
    async def save_cost_sheet(rfq_id: str, body: dict, user: dict = Depends(require_platform_admin)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        lines = (body or {}).get("lines") or []
        # Enrich each line with fresh vendor_name and recompute cost.
        vendor_ids = list({ln.get("vendor_id") for ln in lines if ln.get("vendor_id")})
        vmap: dict = {}
        if vendor_ids:
            vdocs = await db.service_vendors.find({"id": {"$in": vendor_ids}}, {"_id": 0}).to_list(len(vendor_ids))
            vmap = {v["id"]: v for v in vdocs}
        total = 0.0
        clean_lines: List[dict] = []
        for ln in lines:
            qty = max(0, int(ln.get("quantity") or 0))
            rate = max(0.0, float(ln.get("unit_rate") or 0))
            cost = round(qty * rate, 2)
            vid = ln.get("vendor_id")
            clean_lines.append({
                "line_id": ln.get("line_id") or str(uuid.uuid4()),
                "kind": ln.get("kind") or "service",
                "service_id": ln.get("service_id"),
                "addon_id": ln.get("addon_id"),
                "name": ln.get("name") or "",
                "vendor_id": vid,
                "vendor_name": (vmap.get(vid, {}) or {}).get("name") if vid else None,
                "quantity": qty,
                "unit_rate": rate,
                "unit_type": ln.get("unit_type"),
                "cost": cost,
            })
            total += cost
        upd = {
            "lines": clean_lines,
            "total_cost": round(total, 2),
            "updated_at": _now(),
            "updated_by": user["id"],
        }
        existing = await db.cs_internal_cost_sheets.find_one({"rfq_id": rfq_id})
        if existing:
            await db.cs_internal_cost_sheets.update_one({"rfq_id": rfq_id}, {"$set": upd})
        else:
            upd["id"] = str(uuid.uuid4())
            upd["rfq_id"] = rfq_id
            upd["created_at"] = _now()
            await db.cs_internal_cost_sheets.insert_one(upd)
        sheet = await db.cs_internal_cost_sheets.find_one({"rfq_id": rfq_id}, {"_id": 0})
        return sheet

    # ─────────────── Quotations ───────────────
    # Pricing model: line item level, per user choice: BOTH markup % and
    # fixed selling price allowed per line. `pricing_mode`: "markup" | "fixed".
    def _quote_line_from_body(cost_line: dict, ql: dict) -> dict:
        mode = (ql or {}).get("pricing_mode") or "markup"
        cost = float(cost_line.get("cost") or 0)
        if mode == "fixed":
            selling = round(float(ql.get("selling_price") or 0), 2)
            margin_pct = round(((selling - cost) / cost * 100) if cost > 0 else 0, 2)
        else:
            margin_pct = float(ql.get("margin_percent") or 0)
            selling = round(cost * (1 + margin_pct / 100), 2)
        return {
            "line_id": cost_line["line_id"],
            "name": cost_line.get("name"),
            "kind": cost_line.get("kind"),
            "quantity": cost_line.get("quantity"),
            "unit_type": cost_line.get("unit_type"),
            "internal_cost": cost,   # NEVER surfaced to HR (server-side filter below)
            "pricing_mode": mode,
            "margin_percent": margin_pct,
            "selling_price": selling,
        }

    @api.get("/admin/rfqs/{rfq_id}/quotations")
    async def admin_list_quotations(rfq_id: str, _: dict = Depends(require_platform_admin)):
        docs = await db.cs_quotations.find({"rfq_id": rfq_id}, {"_id": 0}).sort("version", -1).to_list(50)
        return docs

    @api.post("/admin/rfqs/{rfq_id}/quotations")
    async def admin_create_quotation(rfq_id: str, body: dict, user: dict = Depends(require_platform_admin)):
        """Compose a draft quotation from the current cost sheet + admin pricing overrides.

        body = {
          "lines": [{ "line_id", "pricing_mode": "markup|fixed",
                      "margin_percent"?, "selling_price"? }, ...],
          "default_margin_percent": 25,           # applied to lines missing pricing
          "tax_percent": 18, "discount": 500,     # optional
          "notes": "...", "valid_until": "2026-03-01"
        }
        """
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        sheet = await db.cs_internal_cost_sheets.find_one({"rfq_id": rfq_id}, {"_id": 0})
        if not sheet or not sheet.get("lines"):
            raise HTTPException(400, "Build the cost sheet before quoting")

        overrides = { (ln.get("line_id") or ""): ln for ln in ((body or {}).get("lines") or []) }
        default_margin = float((body or {}).get("default_margin_percent") or 25)
        quote_lines: List[dict] = []
        for cl in sheet["lines"]:
            ov = overrides.get(cl["line_id"]) or {"pricing_mode": "markup", "margin_percent": default_margin}
            quote_lines.append(_quote_line_from_body(cl, ov))

        subtotal = round(sum(q["selling_price"] for q in quote_lines), 2)
        discount = round(float((body or {}).get("discount") or 0), 2)
        tax_pct  = float((body or {}).get("tax_percent") or 0)
        tax_amt  = round(max(0, subtotal - discount) * tax_pct / 100, 2)
        total    = round(max(0, subtotal - discount) + tax_amt, 2)
        # `internal_cost` in each quote line is already the LINE total from
        # the cost sheet (quantity × unit_rate), so we sum it directly.
        internal_total = round(sum(q["internal_cost"] for q in quote_lines), 2)

        # Version = latest + 1
        latest = await db.cs_quotations.find_one({"rfq_id": rfq_id}, sort=[("version", -1)])
        version = int((latest or {}).get("version") or 0) + 1
        quote = {
            "id": str(uuid.uuid4()),
            "rfq_id": rfq_id,
            "version": version,
            "status": "draft",   # draft → sent → accepted/rejected/superseded
            "lines": quote_lines,
            "subtotal": subtotal,
            "discount": discount,
            "tax_percent": tax_pct,
            "tax_amount": tax_amt,
            "total_selling": total,
            "internal_total_cost": internal_total,
            "gross_margin": round(total - internal_total, 2),
            "gross_margin_percent": round(((total - internal_total) / total * 100) if total > 0 else 0, 2),
            "notes": (body or {}).get("notes") or "",
            "valid_until": (body or {}).get("valid_until") or "",
            "created_by": user["id"],
            "created_at": _now(),
            "sent_at": None,
        }
        await db.cs_quotations.insert_one(quote)
        quote.pop("_id", None)
        return quote

    @api.post("/admin/rfqs/{rfq_id}/quotations/{quote_id}/send")
    async def admin_send_quotation(rfq_id: str, quote_id: str, user: dict = Depends(require_platform_admin)):
        quote = await db.cs_quotations.find_one({"id": quote_id, "rfq_id": rfq_id}, {"_id": 0})
        if not quote:
            raise HTTPException(404, "Quotation not found")
        if quote["status"] not in ("draft",):
            raise HTTPException(400, f"Quotation is '{quote['status']}', cannot resend")
        now = _now()
        # Mark all prior *sent* quotes on this RFQ as superseded
        await db.cs_quotations.update_many(
            {"rfq_id": rfq_id, "status": {"$in": ["sent"]}},
            {"$set": {"status": "superseded", "superseded_at": now}},
        )
        await db.cs_quotations.update_one(
            {"id": quote_id},
            {"$set": {"status": "sent", "sent_at": now, "sent_by": user["id"]}},
        )
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        prev_status = rfq.get("status") if rfq else None
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "quoted", "updated_at": now}})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": prev_status, "to_status": "quoted", "at": now,
            "note": f"Quotation v{quote['version']} sent",
        })
        return {"ok": True, "quotation_id": quote_id, "version": quote["version"]}

    @api.delete("/admin/rfqs/{rfq_id}/quotations/{quote_id}")
    async def admin_delete_draft_quote(rfq_id: str, quote_id: str, _: dict = Depends(require_platform_admin)):
        # Only drafts can be deleted; sent/accepted quotes are immutable audit trail.
        q = await db.cs_quotations.find_one({"id": quote_id, "rfq_id": rfq_id}, {"_id": 0})
        if not q:
            raise HTTPException(404, "Not found")
        if q["status"] != "draft":
            raise HTTPException(400, "Only draft quotes can be deleted")
        await db.cs_quotations.delete_one({"id": quote_id})
        return {"ok": True}

    # ─────────────── HR-side Quote view + Accept/Reject ───────────────
    def _hr_safe_quote(q: dict) -> dict:
        """Strip internal cost & margin fields — HR must never see them."""
        safe = {k: v for k, v in q.items() if k not in
                ("internal_total_cost", "gross_margin", "gross_margin_percent", "created_by", "sent_by")}
        safe["lines"] = [
            {k: v for k, v in ln.items() if k not in ("internal_cost", "margin_percent", "pricing_mode")}
            for ln in q.get("lines", [])
        ]
        return safe

    @api.get("/rfqs/{rfq_id}/quotation")
    async def hr_get_active_quotation(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        if user.get("role") not in ("platform_admin", "admin") and rfq["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        # HR sees only the latest SENT (or accepted/rejected) quote — never drafts.
        q = await db.cs_quotations.find_one(
            {"rfq_id": rfq_id, "status": {"$in": ["sent", "accepted", "rejected", "superseded"]}},
            {"_id": 0}, sort=[("version", -1)],
        )
        if not q:
            return None
        # Admin gets full detail, HR gets sanitised.
        if user.get("role") in ("platform_admin", "admin"):
            return q
        return _hr_safe_quote(q)

    @api.post("/rfqs/{rfq_id}/quotation/accept")
    async def hr_accept_quotation(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq or rfq["hr_user_id"] != user["id"]:
            raise HTTPException(404, "RFQ not found")
        q = await db.cs_quotations.find_one({"rfq_id": rfq_id, "status": "sent"}, sort=[("version", -1)])
        if not q:
            raise HTTPException(400, "No active quotation to accept")
        now = _now()
        await db.cs_quotations.update_one({"id": q["id"]}, {"$set": {"status": "accepted", "accepted_at": now}})
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "approved", "updated_at": now}})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": rfq["status"], "to_status": "approved", "at": now,
            "note": f"HR accepted quotation v{q['version']}",
        })
        # Auto-create invoice (with Razorpay pay-link if keys are configured).
        invoice = None
        try:
            from routes import cs_invoices
            invoice = await cs_invoices.create_invoice_for_quote(db, rfq_id, q["id"])
        except Exception as exc:  # noqa: BLE001
            print(f"[cs_invoices] auto-create failed: {exc}")
        return {"ok": True, "invoice": invoice}

    @api.post("/rfqs/{rfq_id}/quotation/reject")
    async def hr_reject_quotation(rfq_id: str, body: dict, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq or rfq["hr_user_id"] != user["id"]:
            raise HTTPException(404, "RFQ not found")
        q = await db.cs_quotations.find_one({"rfq_id": rfq_id, "status": "sent"}, sort=[("version", -1)])
        if not q:
            raise HTTPException(400, "No active quotation to reject")
        reason = ((body or {}).get("reason") or "").strip()
        now = _now()
        await db.cs_quotations.update_one({"id": q["id"]}, {"$set": {"status": "rejected", "rejected_at": now, "rejection_reason": reason}})
        # Move RFQ to negotiation so admin can send a revised quote.
        await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "negotiation", "updated_at": now}})
        await db.cs_status_history.insert_one({
            "id": str(uuid.uuid4()), "rfq_id": rfq_id, "actor_id": user["id"],
            "from_status": rfq["status"], "to_status": "negotiation", "at": now,
            "note": f"HR rejected quotation v{q['version']}: {reason[:120]}",
        })
        # Auto-post rejection reason into chat for admin visibility.
        if reason:
            await db.cs_rfq_messages.insert_one({
                "id": str(uuid.uuid4()), "rfq_id": rfq_id, "sender_id": user["id"],
                "sender_role": "hr", "sender_name": user.get("name") or user.get("email"),
                "body": f"Rejected quotation v{q['version']}: {reason}",
                "created_at": now,
            })
        return {"ok": True}

    # ─────────────── Negotiation Chat ───────────────
    # Opens ONLY after admin sends first quote (RFQ status transitions to
    # 'quoted' or 'negotiation'). Enforced server-side below.
    def _chat_open(rfq: dict) -> bool:
        return rfq.get("status") in ("quoted", "negotiation", "approved", "completed")

    @api.get("/rfqs/{rfq_id}/messages")
    async def list_rfq_messages(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        if user.get("role") not in ("platform_admin", "admin") and rfq["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        if not _chat_open(rfq):
            return []
        docs = await db.cs_rfq_messages.find({"rfq_id": rfq_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
        return docs

    @api.post("/rfqs/{rfq_id}/messages")
    async def post_rfq_message(rfq_id: str, body: dict, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        is_admin = user.get("role") in ("platform_admin", "admin")
        if not is_admin and rfq["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        if not _chat_open(rfq):
            raise HTTPException(400, "Chat opens after the first quotation is sent")
        text = ((body or {}).get("body") or "").strip()
        if not text:
            raise HTTPException(400, "Empty message")
        msg = {
            "id": str(uuid.uuid4()),
            "rfq_id": rfq_id,
            "sender_id": user["id"],
            "sender_role": "admin" if is_admin else "hr",
            "sender_name": user.get("name") or user.get("email"),
            "body": text[:4000],
            "created_at": _now(),
        }
        await db.cs_rfq_messages.insert_one(msg)
        # If admin messages a quoted RFQ, transition to 'negotiation' for clarity.
        if is_admin and rfq["status"] == "quoted":
            await db.cs_rfqs.update_one({"id": rfq_id}, {"$set": {"status": "negotiation", "updated_at": msg["created_at"]}})
        msg.pop("_id", None)
        return msg

    # ─────────────── Status history (audit) ───────────────
    @api.get("/rfqs/{rfq_id}/history")
    async def rfq_history(rfq_id: str, user: dict = Depends(get_current_user)):
        rfq = await db.cs_rfqs.find_one({"id": rfq_id}, {"_id": 0})
        if not rfq:
            raise HTTPException(404, "RFQ not found")
        if user.get("role") not in ("platform_admin", "admin") and rfq["hr_user_id"] != user["id"]:
            raise HTTPException(403, "Not your RFQ")
        docs = await db.cs_status_history.find({"rfq_id": rfq_id}, {"_id": 0}).sort("at", 1).to_list(500)
        return docs
