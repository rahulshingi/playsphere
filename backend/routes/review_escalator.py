"""Review moderation SLA escalator (Feb 2026).

Reviews left in `pending_vendor` for more than 48 hours are auto-escalated
to `pending_admin` so they never stall on a slow vendor. Runs as part of
the existing daily lifecycle scheduler in `event_lifecycle.py`.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable

logger = logging.getLogger("review_escalator")

# Escalate anything untouched by the vendor for more than this many hours.
ESCALATE_AFTER_HOURS = 48


async def run_review_escalation(db: Any, send_email: Callable[..., Awaitable[bool] | bool]) -> dict:
    """One tick — flip stale `pending_vendor` reviews to `pending_admin`."""
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=ESCALATE_AFTER_HOURS)).isoformat()

    stale = db.reviews.find(
        {"status": "pending_vendor", "created_at": {"$lte": cutoff}},
        {"_id": 0},
    )
    moved = 0
    async for rv in stale:
        try:
            await db.reviews.update_one(
                {"id": rv["id"]},
                {"$set": {
                    "status": "pending_admin",
                    "auto_escalated_at": now.isoformat(),
                    "auto_escalated_reason": f"Vendor did not act within {ESCALATE_AFTER_HOURS}h",
                }},
            )
            moved += 1
            # Best-effort admin ping
            try:
                admin = await db.users.find_one({"role": "platform_admin"}, {"_id": 0, "email": 1})
                if admin and admin.get("email"):
                    send_email(
                        admin["email"],
                        "Review auto-escalated to your queue",
                        f"A {rv['rating']}/5 review by {rv.get('author_name','?')} "
                        f"has been sitting in the vendor's inbox for over {ESCALATE_AFTER_HOURS}h — moved to admin queue.\n\n"
                        f"Listing: {rv.get('listing_id')}\nBooking: {rv.get('booking_id')}\n\nReview it in the Platform Admin console.",
                        kind="review_auto_escalated",
                    )
            except Exception as e:  # pragma: no cover — email best-effort
                logger.warning("escalation email failed for review %s: %s", rv.get("id"), e)
        except Exception as exc:  # noqa: BLE001
            logger.warning("review escalation failed for %s: %s", rv.get("id"), exc)

    logger.info("review escalator tick | moved=%s cutoff=%s", moved, cutoff)
    return {"moved_to_admin": moved, "cutoff": cutoff}
