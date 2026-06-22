"""One-shot migration: enrich existing awarded_to entries with logo_url/website/industry.

Earlier accept flow only stored sponsor_id + name on `event.sponsorship_opportunities[].awarded_to[]`.
This script fills in logo_url, website and industry from each sponsor's profile so the
Sponsors tab on the event page can render the brand cards properly.

Idempotent — entries that already have a logo_url are left alone.
"""
import asyncio
import os

from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    profiles = {}
    async for p in db.sponsor_profiles.find({}, {"_id": 0, "id": 1, "logo_url": 1, "website": 1, "industry": 1}):
        profiles[p["id"]] = p
    changed = 0
    async for ev in db.events.find({"sponsorship_opportunities": {"$exists": True, "$ne": []}}, {"_id": 0, "id": 1, "sponsorship_opportunities": 1}):
        opps = ev.get("sponsorship_opportunities") or []
        dirty = False
        for opp in opps:
            for aw in (opp.get("awarded_to") or []):
                if aw.get("logo_url"):
                    continue
                p = profiles.get(aw.get("sponsor_id"))
                if not p:
                    continue
                aw["logo_url"] = p.get("logo_url") or ""
                aw["website"] = p.get("website") or ""
                aw["industry"] = p.get("industry") or ""
                dirty = True
        if dirty:
            await db.events.update_one({"id": ev["id"]}, {"$set": {"sponsorship_opportunities": opps}})
            changed += 1
            print(f"  healed event {ev['id']}")
    print(f"\nDone. Updated {changed} event(s).")


if __name__ == "__main__":
    asyncio.run(main())
