"""Seed pending offline_subscriptions + venue_leads for BusinessTab UI test."""
import os, sys, uuid, asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

RUN = uuid.uuid4().hex[:8]
VENDOR_EMAIL = f"bt_vendor_{RUN}@turfx.in"
VENDOR_ID = f"vendor_{RUN}"

async def main():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    # Insert synthetic vendor doc so activate can toggle offline_mode
    await db.vendors.insert_one({
        "id": VENDOR_ID,
        "email": VENDOR_EMAIL,
        "business_name": f"TurfX Bengaluru BT {RUN}",
        "city": "Bangalore",
        "vendor_type": "ground",
        "vendor_types": ["ground"],
        "approved": True,
        "offline_mode": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Insert two pending offline subscription requests
    subs = []
    for i in range(2):
        sid = f"sub_bt_{RUN}_{i}"
        subs.append(sid)
        await db.offline_subscriptions.insert_one({
            "id": sid,
            "vendor_id": VENDOR_ID,
            "vendor_email": VENDOR_EMAIL,
            "plan_type": "monthly",
            "amount": 99.0,
            "currency": "INR",
            "payment_method": "offline",
            "status": "pending_payment",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    print("VENDOR_EMAIL=", VENDOR_EMAIL)
    print("VENDOR_ID=", VENDOR_ID)
    print("SUBS=", subs)
    print("RUN=", RUN)

    # Insert venue lead
    lead_id = f"lead_bt_{RUN}"
    await db.venue_leads.insert_one({
        "id": lead_id,
        "venue_name": f"Test Court BLR {RUN}",
        "city": "Bangalore",
        "locality": "Whitefield",
        "street": "12 ITPL Main Rd",
        "state": "Karnataka",
        "pincode": "560066",
        "contact_name": "Owner Ravi",
        "contact_phone": "+919876543210",
        "contact_email": "owner@testcourt.in",
        "submitted_by_email": "admin@kreedanation.com",
        "submitted_by_user_id": "admin",
        "submitted_by_role": "platform_admin",
        "status": "open",
        "admin_notes": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    print("LEAD_ID=", lead_id)

if __name__ == "__main__":
    asyncio.run(main())
