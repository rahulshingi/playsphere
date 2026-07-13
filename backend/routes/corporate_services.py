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
from typing import Optional, List

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

def register(api, db, deps):
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
        }
