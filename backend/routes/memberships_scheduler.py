"""Background tasks for memberships — renewal reminders.

A simple asyncio loop scans active purchases that expire within the next 7 days
and have NOT yet received their renewal email (`renewal_reminder_sent_at`). One
email per purchase per cycle is enough — we set the timestamp after a successful
send to make the loop idempotent on restart.

Exposed via `start_membership_scheduler(db, interval_seconds=3600)` — call this
once from `@app.on_event("startup")` in server.py. The loop sleeps quietly even
when SendGrid isn't configured.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("kreeda.memberships.scheduler")

_SUBJECT = "Your Kreeda Nation membership expires in 7 days"

_BODY_TEMPLATE = (
    "Hi {name},\n\n"
    "Your {plan_title} membership is set to expire on {expires_at} — that's about a week away.\n\n"
    "Renew with the same vendor at the venue desk (online renewal coming once Razorpay is enabled). "
    "Open https://kreedanation.com/my-memberships to see your usage so far and decide whether to renew the same plan, upgrade, or step down.\n\n"
    "Thanks for being part of Kreeda Nation!\n— The Kreeda Nation team"
)


async def _check_and_send(db, send_email):
    """Single pass — finds active purchases expiring in the next 7 days and emails the buyer."""
    now = datetime.now(timezone.utc)
    cutoff_lo = now.isoformat()  # must not be expired yet
    cutoff_hi = (now + timedelta(days=7)).isoformat()
    cursor = db.membership_purchases.find({
        "status": "active",
        "expires_at": {"$gte": cutoff_lo, "$lte": cutoff_hi},
        "renewal_reminder_sent_at": None,
        "buyer_email": {"$ne": ""},
    }, {"_id": 0})
    sent = 0
    async for doc in cursor:
        email = doc.get("buyer_email")
        if not email:
            continue
        body = _BODY_TEMPLATE.format(
            name=doc.get("buyer_name") or "there",
            plan_title=doc.get("plan_title") or "membership",
            expires_at=(doc.get("expires_at") or "")[:10],
        )
        try:
            res = send_email(email, _SUBJECT, body, kind="membership_renewal_reminder")
            if (res or {}).get("ok"):
                await db.membership_purchases.update_one(
                    {"id": doc["id"]},
                    {"$set": {"renewal_reminder_sent_at": now.isoformat()}},
                )
                sent += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("renewal reminder email failed for %s: %s", email, e)
    if sent:
        logger.info("renewal reminders sent | count=%s", sent)
    return sent


def start_membership_scheduler(db, send_email, interval_seconds: int = 6 * 3600):
    """Spawn a background task that runs `_check_and_send` every interval.

    Default cadence is every 6 hours which means each pending reminder is queued
    within 6 hours of becoming eligible. The job is intentionally simple — for a
    higher-scale workload swap this for APScheduler/Celery later.
    """
    async def _loop():
        # Small staggered start so we don't slam the DB the moment the app boots
        await asyncio.sleep(30)
        while True:
            try:
                await _check_and_send(db, send_email)
            except Exception as e:  # noqa: BLE001
                logger.warning("membership scheduler loop error: %s", e)
            await asyncio.sleep(interval_seconds)

    return asyncio.create_task(_loop())
