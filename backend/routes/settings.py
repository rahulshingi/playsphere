"""Site-wide settings endpoints: /settings, /about, /companies/public, /contact, /contact-messages."""
import uuid
import logging
from datetime import datetime, timezone
from fastapi import Depends, HTTPException

logger = logging.getLogger("kreeda.routes.settings")


def register(api, db, SiteSettings, require_platform_admin):
    @api.get("/companies/public")
    async def list_public_companies():
        docs = await db.companies.find(
            {}, {"_id": 0, "id": 1, "name": 1, "slug": 1, "logo_url": 1}
        ).sort("name", 1).to_list(500)
        return docs

    @api.get("/settings")
    async def get_settings():
        doc = await db.settings.find_one({"id": "site"}, {"_id": 0}) or {}
        out = SiteSettings(**doc).model_dump()
        out["id"] = "site"
        return out

    @api.patch("/settings")
    async def update_settings(body: dict, _: dict = Depends(require_platform_admin)):
        body.pop("id", None)
        await db.settings.update_one({"id": "site"}, {"$set": body}, upsert=True)
        doc = await db.settings.find_one({"id": "site"}, {"_id": 0}) or {}
        out = SiteSettings(**doc).model_dump()
        out["id"] = "site"
        return out

    @api.get("/about")
    async def get_about():
        doc = await db.about_settings.find_one({"id": "about"}, {"_id": 0})
        if not doc:
            doc = {
                "id": "about",
                "company_description": "",
                "mission": "",
                "vision": "",
                "founders": [],
                "directors": [],
            }
        return doc

    @api.patch("/about")
    async def update_about(body: dict, _: dict = Depends(require_platform_admin)):
        body.pop("id", None)
        await db.about_settings.update_one({"id": "about"}, {"$set": body}, upsert=True)
        return await db.about_settings.find_one({"id": "about"}, {"_id": 0})

    @api.post("/contact")
    async def submit_contact(body: dict):
        name = (body.get("name") or "").strip()
        email = (body.get("email") or "").strip().lower()
        message = (body.get("message") or "").strip()
        phone = (body.get("phone") or "").strip()
        if not (name and email and message):
            raise HTTPException(400, "name, email, message required")
        settings = await db.settings.find_one({"id": "site"}, {"_id": 0}) or {}
        to = settings.get("contact_email") or "contact@kreedanation.com"
        doc = {
            "id": str(uuid.uuid4()),
            "name": name, "email": email, "phone": phone, "message": message,
            "delivered_to": to, "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.contact_messages.insert_one(doc)
        logger.warning("CONTACT MESSAGE for %s | from=%s <%s> phone=%s | %s",
                       to, name, email, phone or "-", message[:200])
        return {"ok": True}

    @api.get("/contact-messages")
    async def list_contact_messages(_: dict = Depends(require_platform_admin)):
        docs = await db.contact_messages.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
        return docs

    @api.patch("/contact-messages/{msg_id}")
    async def update_contact_message(msg_id: str, body: dict, _: dict = Depends(require_platform_admin)):
        allowed = {k: body[k] for k in ("read",) if k in body}
        await db.contact_messages.update_one({"id": msg_id}, {"$set": allowed})
        return {"ok": True}
