"""Wipe all sample/demo data EXCEPT services, sports, the platform admin user, and site config.

Run with: python /app/scripts/wipe_to_clean_slate.py

Preserves:
- users where role == 'platform_admin' (so admin@kreedanation.com keeps working)
- services (catalog the platform UI relies on)
- sports (custom sport list managed via /platform-admin → Sports tab)
- site_settings, about (public /about page + footer content)

Removes everything else:
- companies, HR / vendor / player / viewer users
- vendors, vendor_listings, vendor_bookings, payment_intents
- events, teams, players (legacy team-roster), player_profiles
- fixtures (cricket scoring state included)
- bookings (company → services bookings)
- reviews, notifications, password_resets
"""
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load backend/.env so MONGO_URL + DB_NAME resolve
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

# Make backend importable so we can use the same Motor client
sys.path.insert(0, str(ROOT / "backend"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

# Collections to fully drop (every document removed)
WIPE_COLLECTIONS = [
    "companies",
    "vendors",
    "vendor_listings",
    "vendor_bookings",
    "events",
    "teams",
    "players",            # legacy team-roster players
    "player_profiles",
    "fixtures",
    "bookings",
    "reviews",
    "notifications",
    "password_resets",
    "payment_intents",
    "sponsors",
]

# users: keep platform_admin, delete everyone else
USERS_KEEP_ROLE = "platform_admin"


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print(f"\nConnected to {DB_NAME}")
    print("=" * 60)

    # Snapshot
    services = await db.services.count_documents({})
    sports = await db.sports.count_documents({})
    admin_users = await db.users.count_documents({"role": USERS_KEEP_ROLE})
    print(f"Preserving: services={services}, sports={sports}, "
          f"platform_admin users={admin_users}, site_settings (1), about (1)")
    print()

    # Wipe demo collections
    for coll in WIPE_COLLECTIONS:
        before = await db[coll].count_documents({})
        if before:
            await db[coll].delete_many({})
        print(f"  {coll:<22} cleared  ({before} → 0)")

    # Wipe non-admin users
    before_users = await db.users.count_documents({"role": {"$ne": USERS_KEEP_ROLE}})
    if before_users:
        await db.users.delete_many({"role": {"$ne": USERS_KEEP_ROLE}})
    print(f"  {'users':<22} cleared  ({before_users} non-admin → 0; admin preserved)")

    print()
    print("Done. Platform admin login still works:")
    print("  email: admin@kreedanation.com")
    print("  password: admin123")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
