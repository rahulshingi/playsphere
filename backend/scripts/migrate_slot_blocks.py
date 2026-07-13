"""One-time migration — merge the legacy `slot_blocks` collection into
`venue_blocks` and then drop `slot_blocks`.

Idempotent: skips rows already migrated (matched by `id`). Safe to re-run.

Usage:
    cd /app/backend && python scripts/migrate_slot_blocks.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    legacy = await db.slot_blocks.find({}, {"_id": 0}).to_list(10000)
    print(f"[migrate] Found {len(legacy)} rows in slot_blocks")

    if not legacy:
        print("[migrate] Nothing to migrate — done.")
        return

    existing_ids = {d["id"] for d in await db.venue_blocks.find(
        {"id": {"$in": [x["id"] for x in legacy]}}, {"_id": 0, "id": 1}
    ).to_list(len(legacy))}
    to_move = [d for d in legacy if d["id"] not in existing_ids]
    print(f"[migrate] {len(to_move)} new rows to insert into venue_blocks")
    if to_move:
        # Ensure required venue_blocks fields exist.
        for d in to_move:
            d.setdefault("reason", "maintenance")
            d.setdefault("notes", "")
            d.setdefault("sub_unit_id", None)
        await db.venue_blocks.insert_many(to_move)
        print(f"[migrate] Inserted {len(to_move)} rows")

    # Drop the legacy collection now that everything is safely mirrored.
    dropped = await db.slot_blocks.drop()
    print(f"[migrate] Dropped slot_blocks: {dropped}")

    total = await db.venue_blocks.count_documents({})
    print(f"[migrate] venue_blocks now holds {total} rows")


if __name__ == "__main__":
    asyncio.run(main())
