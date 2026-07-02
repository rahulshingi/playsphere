"""Seed a vendor with offline_mode=true + one active listing for Phase 5b UI testing.

Idempotent — uses fixed IDs prefixed with 'p5b_' so re-running cleans+recreates.
Prints login credentials on completion.
"""
import asyncio, os, sys, hashlib, secrets
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
import bcrypt

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

VENDOR_EMAIL = "phase5b.vendor@example.com"
VENDOR_PASSWORD = "vendor5b!"
VENDOR_ID = "p5b_vendor_1"
USER_ID = "p5b_user_1"
LISTING_ID = "p5b_listing_1"


async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Cleanup
    await db.users.delete_many({"id": USER_ID})
    await db.vendors.delete_many({"id": VENDOR_ID})
    await db.vendor_listings.delete_many({"id": LISTING_ID})
    await db.vendor_customers.delete_many({"vendor_id": VENDOR_ID})
    await db.vendor_private_bookings.delete_many({"vendor_id": VENDOR_ID})
    await db.vendor_invoices.delete_many({"vendor_id": VENDOR_ID})

    now = datetime.now(timezone.utc).isoformat()
    pw_hash = bcrypt.hashpw(VENDOR_PASSWORD.encode(), bcrypt.gensalt()).decode()

    await db.users.insert_one({
        "id": USER_ID,
        "email": VENDOR_EMAIL,
        "password_hash": pw_hash,
        "name": "Phase5b Vendor",
        "role": "vendor",
        "created_at": now,
    })

    await db.vendors.insert_one({
        "id": VENDOR_ID,
        "user_id": USER_ID,
        "business_name": "Phase5b Turf",
        "contact_name": "Phase5b Vendor",
        "mobile": "9999900000",
        "email": VENDOR_EMAIL,
        "city": "Bangalore",
        "vendor_types": ["ground"],
        "approved": True,
        "offline_mode": True,
        "offline_subscription_expires_at": "2027-12-31",
        "created_at": now,
    })

    await db.vendor_listings.insert_one({
        "id": LISTING_ID,
        "vendor_id": VENDOR_ID,
        "listing_type": "ground",
        "title": "Phase5b Court A",
        "sport": "football",
        "city": "Bangalore",
        "price_per_hour": 800,
        "capacity": 12,
        "status": "active",
        "created_at": now,
        "address": {"line1": "123 Test St", "city": "Bangalore", "state": "KA", "pincode": "560001"},
    })

    print(f"OK — vendor {VENDOR_EMAIL} / {VENDOR_PASSWORD} ready. offline_mode=true.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
