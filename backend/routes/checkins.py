"""QR-based check-in flows (Feb 2026).

Two-way scan:
  • Player scans venue QR → sees THEIR active/open bookings at that vendor's
    listings for today and self-checks in.
  • Vendor scans player QR → sees THAT player's active/open bookings across the
    vendor's listings for today (platform + offline matched via phone/email).

Both flows finish by calling `POST /api/vendor-bookings/{id}/check-in` (platform
booking) or `POST /api/private-bookings/{id}/check-in` (vendor offline booking).
Idempotent — once a booking is checked in we return 409 with the timestamp so
the UI can render "Already checked in at HH:MM".
"""
import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import Depends, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("kreeda.routes.checkins")


# ---------- Response shapes ----------
class ScanBooking(BaseModel):
    id: str
    source: str  # "platform" | "offline"
    listing_id: str
    listing_title: Optional[str] = ""
    vendor_id: str
    vendor_name: Optional[str] = ""
    requested_date: str
    start_time: str
    end_time: Optional[str] = ""
    hours: int = 1
    sport: Optional[str] = ""
    status: str
    checked_in_at: Optional[str] = None
    within_window: bool = False  # True if now is within ±2h of start_time
    player_name: Optional[str] = ""


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _within_window(booking_date: str, start_time: str, minutes: int = 120) -> bool:
    """True if 'now' is within ±`minutes` of the booking's scheduled start."""
    try:
        start = datetime.strptime(f"{booking_date} {start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except Exception:
        return False
    delta = abs((datetime.now(timezone.utc) - start).total_seconds()) / 60.0
    return delta <= minutes


# Platform booking is "open" if it is confirmed / accepted AND not yet checked-in
# AND not cancelled/completed/no_show/expired.
_OPEN_PLATFORM_STATUSES = {"confirmed", "vendor_accepted", "approved", "pending"}
_OPEN_OFFLINE_STATUSES = {"active"}


def register(api, db, deps):
    get_current_user = deps.get_current_user
    ensure_vendor_owner = deps.ensure_vendor_owner  # async fn from business.py
    send_email = getattr(deps, "send_email", None) or (lambda *a, **k: {"ok": False})

    # ---------------------------------------------------------------
    # PLAYER-SIDE: scan venue QR → list my active bookings at that vendor
    # ---------------------------------------------------------------
    @api.get("/checkin/venue/{listing_id}/my-bookings", response_model=List[ScanBooking])
    async def player_scan_venue(listing_id: str, user: dict = Depends(get_current_user)):
        if user.get("role") not in ("player", "company_admin", "organiser", "platform_admin", "admin"):
            raise HTTPException(403, "Only players can self-check-in")
        listing = await db.vendor_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(404, "Listing not found")
        vendor_id = listing["vendor_id"]
        today = _today_iso()

        rows = await db.vendor_bookings.find(
            {
                "vendor_id": vendor_id,
                "created_by": user["id"],
                "requested_date": today,
                "status": {"$in": list(_OPEN_PLATFORM_STATUSES) + ["checked_in"]},
            },
            {"_id": 0},
        ).sort("start_time", 1).to_list(50)

        vendor = await db.vendors.find_one({"id": vendor_id}, {"_id": 0, "business_name": 1})
        vendor_name = (vendor or {}).get("business_name") or ""

        return [
            ScanBooking(
                id=b["id"],
                source="platform",
                listing_id=b.get("listing_id") or "",
                listing_title=b.get("listing_title") or "",
                vendor_id=vendor_id,
                vendor_name=vendor_name,
                requested_date=b.get("requested_date") or today,
                start_time=b.get("start_time") or "",
                end_time=b.get("end_time") or "",
                hours=int(b.get("hours") or 1),
                sport=b.get("sport") or "",
                status=b.get("status") or "confirmed",
                checked_in_at=b.get("checked_in_at"),
                within_window=_within_window(b.get("requested_date") or today, b.get("start_time") or "00:00"),
            )
            for b in rows
        ]

    # ---------------------------------------------------------------
    # VENDOR-SIDE: scan player QR → list that player's active bookings at MY vendor
    # ---------------------------------------------------------------
    @api.get("/checkin/player/{player_id}/bookings", response_model=List[ScanBooking])
    async def vendor_scan_player(player_id: str, user: dict = Depends(get_current_user)):
        vendor = await ensure_vendor_owner(db, user)
        profile = await db.player_profiles.find_one({"id": player_id}, {"_id": 0})
        if not profile:
            raise HTTPException(404, "Player not found")

        vendor_id = vendor["id"]
        today = _today_iso()
        out: List[ScanBooking] = []

        # 1) Platform bookings (created by that player's user_id, at this vendor, today)
        platform_rows = await db.vendor_bookings.find(
            {
                "vendor_id": vendor_id,
                "created_by": profile.get("user_id"),
                "requested_date": today,
                "status": {"$in": list(_OPEN_PLATFORM_STATUSES) + ["checked_in"]},
            },
            {"_id": 0},
        ).sort("start_time", 1).to_list(50)
        for b in platform_rows:
            out.append(ScanBooking(
                id=b["id"], source="platform",
                listing_id=b.get("listing_id") or "",
                listing_title=b.get("listing_title") or "",
                vendor_id=vendor_id, vendor_name=vendor.get("business_name") or "",
                requested_date=b.get("requested_date") or today,
                start_time=b.get("start_time") or "",
                end_time=b.get("end_time") or "",
                hours=int(b.get("hours") or 1),
                sport=b.get("sport") or "",
                status=b.get("status") or "confirmed",
                checked_in_at=b.get("checked_in_at"),
                within_window=_within_window(b.get("requested_date") or today, b.get("start_time") or "00:00"),
                player_name=profile.get("name") or "",
            ))

        # 2) Offline private_bookings — match via VendorCustomer.phone / .email
        mobile = (profile.get("mobile") or "").strip()
        email = (profile.get("email") or "").strip().lower()
        cust_filter: Dict[str, Any] = {"vendor_id": vendor_id, "$or": []}
        if mobile:
            # phones can be stored with or without country code — match either exact or endswith
            digits = "".join(ch for ch in mobile if ch.isdigit())[-10:]
            if digits:
                cust_filter["$or"].append({"phone": {"$regex": f"{digits}$"}})
        if email:
            cust_filter["$or"].append({"email": email})
        offline_rows: List[dict] = []
        if cust_filter["$or"]:
            customers = await db.vendor_customers.find(cust_filter, {"_id": 0, "id": 1, "name": 1}).to_list(20)
            cust_ids = [c["id"] for c in customers]
            if cust_ids:
                offline_rows = await db.private_bookings.find(
                    {
                        "vendor_id": vendor_id,
                        "customer_id": {"$in": cust_ids},
                        "requested_date": today,
                        "status": {"$in": list(_OPEN_OFFLINE_STATUSES) + ["checked_in"]},
                    },
                    {"_id": 0},
                ).sort("start_time", 1).to_list(50)
        for b in offline_rows:
            listing = await db.vendor_listings.find_one({"id": b.get("listing_id")}, {"_id": 0, "title": 1})
            out.append(ScanBooking(
                id=b["id"], source="offline",
                listing_id=b.get("listing_id") or "",
                listing_title=(listing or {}).get("title") or "",
                vendor_id=vendor_id, vendor_name=vendor.get("business_name") or "",
                requested_date=b.get("requested_date") or today,
                start_time=b.get("start_time") or "",
                end_time=b.get("end_time") or "",
                hours=int(b.get("hours") or 1),
                sport=b.get("sport") or "",
                status=b.get("status") or "active",
                checked_in_at=b.get("checked_in_at"),
                within_window=_within_window(b.get("requested_date") or today, b.get("start_time") or "00:00"),
                player_name=b.get("client_name") or profile.get("name") or "",
            ))
        return out

    # ---------------------------------------------------------------
    # CHECK-IN endpoints (called by player-self OR vendor)
    # ---------------------------------------------------------------
    @api.post("/checkin/vendor-booking/{booking_id}")
    async def check_in_vendor_booking(booking_id: str, user: dict = Depends(get_current_user)):
        doc = await db.vendor_bookings.find_one({"id": booking_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Booking not found")

        # Authorisation: booking creator (player self) OR vendor owner
        actor_role = "player"
        if doc.get("created_by") != user["id"]:
            # Must be the vendor owner
            try:
                vendor = await ensure_vendor_owner(db, user)
            except HTTPException:
                raise HTTPException(403, "Not your booking")
            if vendor["id"] != doc.get("vendor_id"):
                raise HTTPException(403, "Not your booking")
            actor_role = "vendor"

        # Idempotent: already checked in?
        if doc.get("checked_in_at"):
            raise HTTPException(409, {
                "code": "already_checked_in",
                "checked_in_at": doc["checked_in_at"],
                "checked_in_by_role": doc.get("checked_in_by_role"),
            })

        # Reject checking-in a booking that's not today
        if doc.get("requested_date") != _today_iso():
            raise HTTPException(400, "Booking is not scheduled for today")

        # Reject terminal statuses
        if doc.get("status") in ("cancelled", "rejected", "completed", "no_show", "expired"):
            raise HTTPException(400, f"Cannot check in — booking is {doc.get('status')}")

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.vendor_bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "checked_in_at": now_iso,
                "checked_in_by": user["id"],
                "checked_in_by_role": actor_role,
                "arrived_at": doc.get("arrived_at") or now_iso,
                "status": "checked_in",
            }},
        )
        logger.info("checkin OK | booking=%s by=%s(%s)", booking_id, user.get("email"), actor_role)

        # Notify vendor whenever a PLAYER self-checks-in (vendor-initiated
        # check-ins don't need a "someone just arrived" alert since the vendor
        # is already at the counter). Best-effort — never blocks the request.
        if actor_role == "player":
            try:
                vendor_doc = await db.vendors.find_one({"id": doc.get("vendor_id")}, {"_id": 0, "user_id": 1, "business_name": 1})
                vendor_user = await db.users.find_one({"id": (vendor_doc or {}).get("user_id")}, {"_id": 0, "email": 1, "name": 1}) if vendor_doc else None
                if vendor_user and vendor_user.get("email"):
                    player_name = user.get("name") or user.get("email") or "A player"
                    listing_title = doc.get("listing_title") or "your venue"
                    slot = f"{doc.get('start_time','?')}–{doc.get('end_time','?')}"
                    body = (
                        f"Hi {vendor_user.get('name') or 'there'},\n\n"
                        f"{player_name} has just checked in at {listing_title}.\n\n"
                        f"Slot: {slot} ({doc.get('requested_date')})\n"
                        f"Sport: {doc.get('sport') or '—'}\n"
                        f"Booking ID: {booking_id}\n\n"
                        f"— Kreeda Nation"
                    )
                    send_email(
                        vendor_user["email"],
                        f"Arrival: {player_name} checked in at {listing_title}",
                        body,
                        kind="checkin_arrival",
                    )
            except Exception as e:  # pragma: no cover — email best-effort
                logger.warning("checkin arrival email failed | booking=%s err=%s", booking_id, e)

        return {"ok": True, "checked_in_at": now_iso, "checked_in_by_role": actor_role, "status": "checked_in"}

    @api.post("/checkin/private-booking/{booking_id}")
    async def check_in_private_booking(booking_id: str, user: dict = Depends(get_current_user)):
        vendor = await ensure_vendor_owner(db, user)
        doc = await db.private_bookings.find_one({"id": booking_id, "vendor_id": vendor["id"]}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Booking not found")

        if doc.get("checked_in_at"):
            raise HTTPException(409, {
                "code": "already_checked_in",
                "checked_in_at": doc["checked_in_at"],
                "checked_in_by_role": doc.get("checked_in_by_role") or "vendor",
            })

        if doc.get("requested_date") != _today_iso():
            raise HTTPException(400, "Booking is not scheduled for today")

        if doc.get("status") in ("cancelled", "completed", "expired"):
            raise HTTPException(400, f"Cannot check in — booking is {doc.get('status')}")

        now_iso = datetime.now(timezone.utc).isoformat()
        await db.private_bookings.update_one(
            {"id": booking_id},
            {"$set": {
                "checked_in_at": now_iso,
                "checked_in_by": user["id"],
                "checked_in_by_role": "vendor",
                "arrived_at": doc.get("arrived_at") or now_iso,
                "status": "checked_in",
            }},
        )
        logger.info("checkin OK (private) | booking=%s vendor=%s", booking_id, vendor["id"])
        return {"ok": True, "checked_in_at": now_iso, "checked_in_by_role": "vendor", "status": "checked_in"}

    # ---------------------------------------------------------------
    # ANALYTICS — vendor's today snapshot: check-in count + avg delay
    # ---------------------------------------------------------------
    @api.get("/vendor/checkin-analytics/today")
    async def checkin_analytics_today(user: dict = Depends(get_current_user)):
        """Compact snapshot for the vendor dashboard:
          - checked_in_count: bookings checked-in today (platform + offline)
          - expected_count: bookings scheduled for today (platform + offline, non-cancelled)
          - avg_delay_minutes: (actual checked_in_at − scheduled start) averaged across today's check-ins.
            Positive = late arrival, negative = early.
        """
        vendor = await ensure_vendor_owner(db, user)
        today = _today_iso()

        # Load all today's bookings (both surfaces)
        platform = await db.vendor_bookings.find(
            {"vendor_id": vendor["id"], "requested_date": today,
             "status": {"$nin": ["cancelled", "rejected", "expired"]}},
            {"_id": 0, "id": 1, "start_time": 1, "checked_in_at": 1, "requested_date": 1, "status": 1},
        ).to_list(500)
        offline = await db.private_bookings.find(
            {"vendor_id": vendor["id"], "requested_date": today,
             "status": {"$nin": ["cancelled", "expired"]}},
            {"_id": 0, "id": 1, "start_time": 1, "checked_in_at": 1, "requested_date": 1, "status": 1},
        ).to_list(500)
        rows = platform + offline

        expected = len(rows)
        deltas: List[float] = []
        checked_in = 0
        for r in rows:
            if not r.get("checked_in_at"):
                continue
            checked_in += 1
            try:
                start = datetime.strptime(f"{r['requested_date']} {r['start_time']}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                actual = datetime.fromisoformat(r["checked_in_at"].replace("Z", "+00:00"))
                deltas.append((actual - start).total_seconds() / 60.0)
            except Exception:
                continue

        avg_delay = round(sum(deltas) / len(deltas), 1) if deltas else None
        return {
            "date": today,
            "checked_in_count": checked_in,
            "expected_count": expected,
            "not_yet_arrived": max(expected - checked_in, 0),
            "avg_delay_minutes": avg_delay,
        }
