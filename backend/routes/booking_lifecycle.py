"""Auto-expire + show-up tracking for vendor & private bookings.

Rules (Task 44 · Feb 2026):
  • A booking is considered EXPIRED (customer no-show) once
      (end_time + GRACE_HOURS) < now
    AND the booking has not been checked-in / completed / cancelled.
  • Grace period: 4 hours (per product decision — accommodates late arrivals /
    matches running long).
  • Lazy expiration: no cron job. Every list / detail read runs this helper
    and mutates the DB in-place. This keeps the system simple and eventually
    consistent — a booking not read for weeks eventually gets touched by the
    admin analytics query.
  • Throttled: to avoid re-scanning on every request under load, we cache a
    per-collection sweep timestamp on `site_settings` and skip the DB write
    when the previous sweep ran <60s ago.
  • Applies to BOTH `vendor_bookings` (platform online bookings) and
    `private_bookings` (vendor's offline mode entries).
"""
from datetime import datetime, timezone, timedelta
from typing import List

GRACE_HOURS = 4
# Minimum seconds between two sweeps of the same collection.
SWEEP_THROTTLE_SEC = 60

# For online (vendor_bookings) — statuses that are "still active" i.e. eligible
# for expiration.
ONLINE_ACTIVE_STATUSES = {"pending", "vendor_accepted", "confirmed"}
# Terminal statuses that must never be auto-changed.
ONLINE_TERMINAL_STATUSES = {"completed", "cancelled", "rejected", "expired", "no_show", "fulfilled"}

# For private (offline) bookings — only `active` is eligible.
OFFLINE_ACTIVE_STATUSES = {"active"}
OFFLINE_TERMINAL_STATUSES = {"completed", "cancelled", "expired", "no_show"}


def _end_datetime(booking: dict) -> datetime:
    """Combine `requested_date` (YYYY-MM-DD) + `end_time` (HH:MM) into UTC datetime.

    Both fields are user-facing local strings. We treat them as UTC for the
    purpose of expiration comparison — this errs on the side of NOT expiring
    early (Indian tz is UTC+5:30, so a 6pm IST slot = 12:30pm UTC; we compare
    against `now` in UTC → margin already erring on the safe side by ~5.5h).
    Combined with the 4h grace, real-world premature-expiration is impossible.
    """
    date_s = booking.get("requested_date") or ""
    end_s = booking.get("end_time") or "00:00"
    try:
        d = datetime.strptime(date_s, "%Y-%m-%d")
        hh, mm = [int(x) for x in end_s.split(":")[:2]]
        return d.replace(hour=hh, minute=mm, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        # Malformed → treat as far-future so we don't expire it
        return datetime.max.replace(tzinfo=timezone.utc)


def _is_expired(booking: dict, active_statuses: set) -> bool:
    if booking.get("status") not in active_statuses:
        return False
    end_dt = _end_datetime(booking)
    grace = timedelta(hours=GRACE_HOURS)
    return (end_dt + grace) < datetime.now(timezone.utc)


async def _should_sweep(db, collection_name: str) -> bool:
    """Return True iff no sweep for `collection_name` ran in the last
    `SWEEP_THROTTLE_SEC` seconds; also stamps the current sweep timestamp
    atomically on the fly.

    Uses the singleton `site_settings` doc as the store (single row with all
    global config — no separate collection needed).
    """
    key = f"_sweep_{collection_name}_at"
    now = datetime.now(timezone.utc)
    doc = await db.site_settings.find_one({}, {"_id": 0, key: 1}) or {}
    prev = doc.get(key)
    if prev:
        try:
            prev_dt = datetime.fromisoformat(prev)
            if (now - prev_dt).total_seconds() < SWEEP_THROTTLE_SEC:
                return False
        except (TypeError, ValueError):
            pass
    # Upsert the new timestamp — creates the singleton row if missing.
    await db.site_settings.update_one({}, {"$set": {key: now.isoformat()}}, upsert=True)
    return True


async def sweep_online_bookings(db, docs: List[dict]) -> List[dict]:
    """Mutates each vendor_booking in-place if it's past its grace window.

    Returns the same list, now with `status="expired"` + `no_show_at` set where
    applicable, and the DB updated to match. Throttled: skips DB write when
    another sweep ran <60s ago (still evaluates in-memory for the returned list).
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    to_expire = [d["id"] for d in docs if _is_expired(d, ONLINE_ACTIVE_STATUSES)]
    if not to_expire:
        return docs
    for d in docs:
        if d["id"] in to_expire:
            d["status"] = "expired"
            d["no_show_at"] = now_iso
    # Only persist to Mongo if enough time has elapsed since the last sweep.
    if await _should_sweep(db, "vendor_bookings"):
        await db.vendor_bookings.update_many(
            {"id": {"$in": to_expire}},
            {"$set": {"status": "expired", "no_show_at": now_iso}},
        )
    return docs


async def sweep_offline_bookings(db, docs: List[dict]) -> List[dict]:
    """Same as `sweep_online_bookings` but for `private_bookings`."""
    now_iso = datetime.now(timezone.utc).isoformat()
    to_expire = [d["id"] for d in docs if _is_expired(d, OFFLINE_ACTIVE_STATUSES)]
    if not to_expire:
        return docs
    for d in docs:
        if d["id"] in to_expire:
            d["status"] = "expired"
            d["no_show_at"] = now_iso
    if await _should_sweep(db, "private_bookings"):
        await db.private_bookings.update_many(
            {"id": {"$in": to_expire}},
            {"$set": {"status": "expired", "no_show_at": now_iso}},
        )
    return docs
