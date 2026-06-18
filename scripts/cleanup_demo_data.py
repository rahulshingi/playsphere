"""One-off cleanup script: reduce demo data to 1 representative record per collection.
Run with: python -m scripts.cleanup_demo_data
Preserves: services, sports, settings, about_settings, admin user(s), TEST_* artefacts already gone.
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


KEEP_RULES = {
    # collection: (sort_field, keep_count, additional_filter)
    "companies": ("created_at", 1, {}),
    "vendors": ("created_at", 1, {}),
    "player_profiles": ("created_at", 1, {}),
    "events": ("created_at", 1, {}),
    "teams": ("created_at", 1, {}),  # we'll filter to teams under kept events later
    "vendor_listings": ("created_at", 1, {}),
    "vendor_bookings": ("created_at", 1, {}),
    "fixtures": ("created_at", 1, {}),
    "bookings": ("created_at", 1, {}),  # legacy/historical
    "contact_messages": ("created_at", 1, {}),
}

PRESERVE_FULLY = {"services", "sports", "settings", "about_settings", "venue_schedules"}


async def cleanup():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]

    # Find one canonical company (prefer Acme), vendor (prefer Ravi), and HR user
    canon = {}
    canon["company"] = await db.companies.find_one({"name": {"$regex": "Acme", "$options": "i"}}, {"_id": 0})
    canon["company"] = canon["company"] or await db.companies.find_one({}, {"_id": 0})
    canon["vendor"] = await db.vendors.find_one({"contact_email": "ravi@turf.in"}, {"_id": 0})
    canon["vendor"] = canon["vendor"] or await db.vendors.find_one({}, {"_id": 0})

    keep_company_id = canon["company"]["id"] if canon["company"] else None
    keep_vendor_id = canon["vendor"]["id"] if canon["vendor"] else None

    # 1. Companies: keep only the canonical one
    if keep_company_id:
        r = await db.companies.delete_many({"id": {"$ne": keep_company_id}})
        print(f"companies deleted: {r.deleted_count}")

    # 2. Vendors: keep only the canonical one
    if keep_vendor_id:
        r = await db.vendors.delete_many({"id": {"$ne": keep_vendor_id}})
        print(f"vendors deleted: {r.deleted_count}")

    # 3. Player profiles: keep 1 player linked to the canonical company
    if keep_company_id:
        kp = await db.player_profiles.find_one({"company_id": keep_company_id}, {"_id": 0})
        kp = kp or await db.player_profiles.find_one({}, {"_id": 0})
        if kp:
            r = await db.player_profiles.delete_many({"id": {"$ne": kp["id"]}})
            print(f"player_profiles deleted: {r.deleted_count}")
            # Also delete users associated with removed profiles
            r2 = await db.users.delete_many({"role": "player", "id": {"$ne": kp["user_id"]}})
            print(f"player users deleted: {r2.deleted_count}")

    # 4. Vendor listings: keep 1 for the canonical vendor
    if keep_vendor_id:
        kl = await db.vendor_listings.find_one({"vendor_id": keep_vendor_id, "approved": True}, {"_id": 0})
        kl = kl or await db.vendor_listings.find_one({"vendor_id": keep_vendor_id}, {"_id": 0})
        if kl:
            r = await db.vendor_listings.delete_many({"id": {"$ne": kl["id"]}})
            print(f"vendor_listings deleted: {r.deleted_count}")

    # 5. Events: keep 1 — preferably one with fixtures + teams attached
    ev_with_fx = None
    async for ev in db.events.find({}, {"_id": 0, "id": 1, "name": 1}):
        fxc = await db.fixtures.count_documents({"event_id": ev["id"]})
        tmc = await db.teams.count_documents({"event_id": ev["id"]})
        if fxc and tmc:
            ev_with_fx = ev
            break
    keep_event = ev_with_fx or await db.events.find_one({}, {"_id": 0})
    if keep_event:
        r = await db.events.delete_many({"id": {"$ne": keep_event["id"]}})
        print(f"events deleted: {r.deleted_count}")
        # Cascade delete teams + fixtures for removed events
        rt = await db.teams.delete_many({"event_id": {"$ne": keep_event["id"]}})
        rf = await db.fixtures.delete_many({"event_id": {"$ne": keep_event["id"]}})
        print(f"orphan teams deleted: {rt.deleted_count}; orphan fixtures deleted: {rf.deleted_count}")

    # 6. Vendor bookings: keep 1 — preferably for the canonical company + listing
    kb = None
    if keep_company_id:
        kb = await db.vendor_bookings.find_one({"company_id": keep_company_id}, {"_id": 0})
    kb = kb or await db.vendor_bookings.find_one({}, {"_id": 0})
    if kb:
        r = await db.vendor_bookings.delete_many({"id": {"$ne": kb["id"]}})
        print(f"vendor_bookings deleted: {r.deleted_count}")

    # 7. Legacy bookings collection (if present)
    r = await db.bookings.delete_many({})
    print(f"legacy bookings deleted: {r.deleted_count}")

    # 8. Contact messages: keep latest 1
    cm = await db.contact_messages.find_one({}, sort=[("created_at", -1)])
    if cm:
        r = await db.contact_messages.delete_many({"id": {"$ne": cm["id"]}})
        print(f"contact_messages deleted: {r.deleted_count}")

    # 9. Reviews: clean fully (will repopulate via natural use)
    r = await db.reviews.delete_many({})
    print(f"reviews deleted: {r.deleted_count}")

    # 10. Show remaining counts
    print("\nRemaining counts:")
    for coll in ["companies", "vendors", "player_profiles", "events", "teams", "fixtures",
                 "vendor_listings", "vendor_bookings", "services", "sports", "users",
                 "settings", "about_settings", "contact_messages", "reviews"]:
        n = await db[coll].count_documents({})
        print(f"  {coll}: {n}")


if __name__ == "__main__":
    asyncio.run(cleanup())
