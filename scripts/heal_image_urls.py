"""One-shot migration: heal stored image URLs.

Old uploads were stored as ABSOLUTE preview-hostname URLs:
    https://live-scoring-hub-5.preview.emergentagent.com/api/uploads/abc.jpg

When the app is served from kreedanation.com (production), browsers try to fetch the
preview hostname instead of the production backend — and the file is gone anyway because
the preview disk is ephemeral. This script strips the host from every uploaded-image URL
in the DB so it becomes a relative path the frontend can resolve against the CURRENT
REACT_APP_BACKEND_URL via lib/imageUrl.resolveImageUrl().

Idempotent: re-runs do nothing because we only touch values that still contain a
non-relative host before `/api/uploads/`.

Usage:
    cd /app/backend && set -a && source .env && set +a && python3 scripts/heal_image_urls.py
"""
import asyncio
import os
import re

from motor.motor_asyncio import AsyncIOMotorClient

IMG_FIELDS = {
    "player_profiles": ["photo_url"],
    "sponsor_profiles": ["logo_url"],
    "events": ["banner_url"],
    "vendor_listings": ["images"],  # list of urls
    "companies": ["logo_url"],
    "vendors": ["logo_url"],
    "sponsors": ["logo_url"],
    "services": ["images"],
    "users": ["photo_url"],
    "settings": ["logo_url", "favicon_url"],
    "about": ["banner_url"],
}

# Match any absolute URL that contains /api/uploads/ — extract the relative tail.
PATTERN = re.compile(r"^https?://[^/]+(/api/uploads/.+)$")


def heal(value):
    if not isinstance(value, str):
        return value, False
    m = PATTERN.match(value)
    if not m:
        return value, False
    return m.group(1), True


async def main():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    total_changed = 0
    for coll, fields in IMG_FIELDS.items():
        async for doc in db[coll].find({}, {"_id": 0, "id": 1, **{f: 1 for f in fields}}):
            updates = {}
            for f in fields:
                v = doc.get(f)
                if isinstance(v, list):
                    new_list = []
                    list_changed = False
                    for item in v:
                        healed, changed = heal(item)
                        new_list.append(healed)
                        if changed:
                            list_changed = True
                    if list_changed:
                        updates[f] = new_list
                else:
                    healed, changed = heal(v)
                    if changed:
                        updates[f] = healed
            if updates and doc.get("id"):
                await db[coll].update_one({"id": doc["id"]}, {"$set": updates})
                total_changed += 1
                print(f"  {coll}/{doc['id']}: {list(updates)}")
    print(f"\nDone. Healed {total_changed} document(s).")


if __name__ == "__main__":
    asyncio.run(main())
