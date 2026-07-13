"""Seed / reset the Demovendorname vendor (rmshingi@gmail.com) with sample
listings + bookings so the user can visualise the new Vendor Overview.

Idempotent — safe to re-run. Password is reset to `vendor123`.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running from anywhere.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from passlib.context import CryptContext  # noqa: E402

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

VENDOR_EMAIL = "rmshingi@gmail.com"
VENDOR_PASSWORD = "vendor123"
VENDOR_NAME = "Demovendorname"
BUSINESS_NAME = "Demo vendor"


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1) Reset user (create-or-update)
    existing_user = await db.users.find_one({"email": VENDOR_EMAIL})
    if existing_user:
        user_id = existing_user["id"]
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "password_hash": pwd.hash(VENDOR_PASSWORD),
                "name": VENDOR_NAME,
                "role": "vendor",
                "email_verified": True,
                "disabled": False,
            }},
        )
        print(f"[user] updated {VENDOR_EMAIL} (id={user_id})")
    else:
        user_id = str(uuid.uuid4())
        await db.users.insert_one({
            "id": user_id,
            "email": VENDOR_EMAIL,
            "name": VENDOR_NAME,
            "role": "vendor",
            "mobile": "+919000000099",
            "password_hash": pwd.hash(VENDOR_PASSWORD),
            "email_verified": True,
            "created_at": now_iso,
        })
        print(f"[user] created {VENDOR_EMAIL} (id={user_id})")

    # 2) Vendor profile — approved + offline mode ON so the Offline tab unlocks
    existing_vendor = await db.vendors.find_one({"user_id": user_id})
    vendor_doc = {
        "user_id": user_id,
        "business_name": BUSINESS_NAME,
        "vendor_type": "court",
        "vendor_types": ["court", "ground", "coach"],
        "contact_name": VENDOR_NAME,
        "mobile": "+919000000099",
        "email": VENDOR_EMAIL,
        "city": "Bengaluru",
        "approved": True,
        "offline_mode": True,
        "commission_percent": 10.0,
        "commission_min_flat": 100.0,
        "invoice_business_name": BUSINESS_NAME,
        "invoice_address": "12 MG Road, Bengaluru 560001",
        "invoice_phone": "+919000000099",
        "invoice_email": VENDOR_EMAIL,
        "invoice_tax_percent": 18.0,
    }
    if existing_vendor:
        vendor_id = existing_vendor["id"]
        await db.vendors.update_one({"id": vendor_id}, {"$set": vendor_doc})
        print(f"[vendor] updated business={BUSINESS_NAME} (id={vendor_id})")
    else:
        vendor_id = str(uuid.uuid4())
        vendor_doc["id"] = vendor_id
        vendor_doc["created_at"] = now_iso
        await db.vendors.insert_one(vendor_doc)
        print(f"[vendor] created business={BUSINESS_NAME} (id={vendor_id})")

    # 3) Listings — 3 varied. Idempotent by title.
    listings_seed = [
        {
            "title": "Demo Turf — Whitefield",
            "description": "5-a-side artificial turf with floodlights.",
            "vendor_type": "ground",
            "sports": ["football", "cricket"],
            "price": 1200.0,
            "price_unit": "per hour",
            "capacity": 12,
            "facilities": ["Floodlights", "Changing room", "Parking"],
            "images": ["https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800"],
        },
        {
            "title": "Demo Badminton Court — Indiranagar",
            "description": "Wooden-floor indoor badminton court.",
            "vendor_type": "court",
            "sports": ["badminton"],
            "price": 400.0,
            "price_unit": "per hour",
            "capacity": 4,
            "facilities": ["AC", "Water", "Racquet rental"],
            "images": ["https://images.unsplash.com/photo-1626224583764-f87db24ac4ea?w=800"],
        },
        {
            "title": "Coach Arjun — Cricket batting",
            "description": "Ex-Ranji batter offering 1-on-1 cricket coaching.",
            "vendor_type": "coach",
            "sports": ["cricket"],
            "price": 800.0,
            "price_unit": "per session",
            "capacity": 1,
            "facilities": ["Video analysis", "Equipment provided"],
            "images": ["https://images.unsplash.com/photo-1531415074968-036ba1b575da?w=800"],
        },
    ]

    listing_ids: dict[str, str] = {}
    for base in listings_seed:
        found = await db.vendor_listings.find_one({"vendor_id": vendor_id, "title": base["title"]})
        if found:
            await db.vendor_listings.update_one(
                {"id": found["id"]},
                {"$set": {**base, "approved": True, "active": True}},
            )
            listing_ids[base["title"]] = found["id"]
        else:
            lid = str(uuid.uuid4())
            await db.vendor_listings.insert_one({
                "id": lid,
                "vendor_id": vendor_id,
                "city": "Bengaluru",
                "currency": "INR",
                "approved": True,
                "active": True,
                "created_at": now_iso,
                **base,
            })
            listing_ids[base["title"]] = lid
    print(f"[listings] {len(listing_ids)} listings synced")

    # 4) Sample platform bookings — mixed statuses across last 10 days.
    turf_id = listing_ids["Demo Turf — Whitefield"]
    badm_id = listing_ids["Demo Badminton Court — Indiranagar"]

    def day_offset(n: int) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=n)).date().isoformat()

    booking_seed = [
        # (listing, date_offset, start, end, hours, status, customer_email, total)
        (turf_id, "Demo Turf — Whitefield", -2, "18:00", "19:00", 1, "completed", "hr@acme.com", 1200),
        (turf_id, "Demo Turf — Whitefield", -1, "19:00", "20:00", 1, "completed", "hr@brico.com", 1200),
        (badm_id, "Demo Badminton Court — Indiranagar", 0, "07:00", "08:00", 1, "confirmed", "riya@testplayer.io", 400),
        (badm_id, "Demo Badminton Court — Indiranagar", 1, "08:00", "09:00", 1, "pending", "arya@testplayer.io", 400),
        (turf_id, "Demo Turf — Whitefield", 2, "17:00", "18:00", 1, "confirmed", "hr@acme.com", 1200),
        (turf_id, "Demo Turf — Whitefield", -3, "20:00", "21:00", 1, "expired", "hr@lost.com", 1200),
        (badm_id, "Demo Badminton Court — Indiranagar", 3, "18:00", "19:00", 1, "pending", "kabir@testplayer.io", 400),
    ]

    # Wipe existing sample rows first so re-runs don't stack duplicates
    await db.vendor_bookings.delete_many({"vendor_id": vendor_id})
    for (lid, ltitle, offset, start, end, hours, status, buyer, total) in booking_seed:
        commission_amt = round(max(total * 0.10, 100), 2)
        await db.vendor_bookings.insert_one({
            "id": str(uuid.uuid4()),
            "listing_id": lid,
            "listing_title": ltitle,
            "vendor_id": vendor_id,
            "vendor_type": "ground" if "Turf" in ltitle else "court",
            "company_id": "demo-company",
            "company_name": buyer.split("@")[1].split(".")[0].title() + " Corp",
            "requested_date": day_offset(offset),
            "start_time": start,
            "end_time": end,
            "hours": hours,
            "sport": "football" if "Turf" in ltitle else "badminton",
            "city": "Bengaluru",
            "price": total,
            "currency": "INR",
            "total": total,
            "notes": "Seeded demo booking",
            "status": status,
            "created_by": "demo-buyer",
            "hr_email": buyer,
            "commission_percent": 10.0,
            "commission_amount": commission_amt,
            "commission_min_flat": 100.0,
            "checked_in_at": (datetime.now(timezone.utc) - timedelta(days=abs(offset))).isoformat() if status == "completed" else None,
            "created_at": (datetime.now(timezone.utc) + timedelta(days=offset - 1)).isoformat(),
            "notifications": [],
            "previous_slots": [],
            "offline_source": False,
        })
    print(f"[platform bookings] {len(booking_seed)} rows seeded")

    # 5) Offline private bookings — 3 rows (walk-in cash bookings)
    await db.private_bookings.delete_many({"vendor_id": vendor_id})
    private_seed = [
        (turf_id, -1, "10:00", "11:00", "fulfilled", "Ravi Kumar", 1000),
        (badm_id, 0, "17:00", "18:00", "approved", "Sneha S.", 400),
        (badm_id, 2, "19:00", "20:00", "pending", "Aakash R.", 400),
    ]
    for (lid, offset, start, end, status, client_name, amount) in private_seed:
        await db.private_bookings.insert_one({
            "id": str(uuid.uuid4()),
            "vendor_id": vendor_id,
            "listing_id": lid,
            "listing_title": "Demo Turf — Whitefield" if lid == turf_id else "Demo Badminton Court — Indiranagar",
            "client_name": client_name,
            "client_mobile": "+91900000{0:04d}".format(hash(client_name) % 9999),
            "requested_date": day_offset(offset),
            "start_time": start,
            "end_time": end,
            "hours": 1,
            "amount": amount,
            "currency": "INR",
            "status": status,
            "is_platform_booking": False,
            "created_at": (datetime.now(timezone.utc) + timedelta(days=offset - 1)).isoformat(),
        })
    print(f"[offline bookings] {len(private_seed)} rows seeded")

    print("\n=== DEMO VENDOR READY ===")
    print(f"  URL   : /login")
    print(f"  Email : {VENDOR_EMAIL}")
    print(f"  Pass  : {VENDOR_PASSWORD}")
    print(f"  Land  : /vendor/overview")


if __name__ == "__main__":
    asyncio.run(main())
