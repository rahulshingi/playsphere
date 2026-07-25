"""Event Lifecycle Automation (Feb 2026).

Runs a lightweight daily scheduler that:

  Rule A · Upcoming    — today < start_date                → status=upcoming
  Rule B · Ongoing     — start_date ≤ today ≤ end_date     → status=ongoing
  Rule C · Cancelled   — today > end_date, fixtures exist,
                         no matches started                → status=cancelled
                         reason="No matches were played."
  Rule D · Completed   — today > end_date AND ≥1 match started
                         AND status != completed           → status=completed

Also drives reminder emails to the organiser based on lifecycle position:
  Case 1: Event created, no teams              — every 1 day
  Case 2: Teams added, fixtures missing        — every 1 day
  Case 3: Fixtures exist, start_date == +1     — one-shot
  Case 4: start_date == today, no match yet    — one-shot
  Case 5: Ongoing + no score in 8h             — one-shot per 8h window
  Case 6: All fixture matches completed, event
          still not completed                  — one-shot

The scheduler is intentionally minimal — reuses the existing email helper
and touches events only when needed. It DOES NOT scan the whole DB: query
window is (start_date ≤ today+2 OR end_date ≤ today OR status != completed).

Two new event fields (added on-demand only when a reminder fires):
  • last_reminder_sent      — {stage: iso_datetime}   audit trail per case
  • auto_status_updated_at  — iso when the scheduler flipped the status

Everything else reuses existing collections (events, teams, fixtures, matches).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("event_lifecycle")


# ─────────────────────────── Helpers ───────────────────────────

def _today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hours_since(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


async def _event_progress(db: Any, event_id: str) -> dict[str, Any]:
    """Cheap signals — all indexed lookups + counts."""
    team_count = await db.teams.count_documents({"event_id": event_id})
    fixture_count = await db.fixtures.count_documents({"event_id": event_id})
    started_count = await db.fixtures.count_documents(
        {"event_id": event_id, "status": {"$in": ["live", "completed", "in_progress"]}}
    )
    completed_count = await db.fixtures.count_documents(
        {"event_id": event_id, "status": "completed"}
    )
    last_scoring: Optional[dict] = await db.fixtures.find_one(
        {"event_id": event_id, "status": {"$in": ["live", "completed"]}},
        {"_id": 0, "updated_at": 1, "completed_at": 1},
        sort=[("updated_at", -1)],
    )
    last_activity = None
    if last_scoring:
        last_activity = last_scoring.get("updated_at") or last_scoring.get("completed_at")
    return {
        "team_count": team_count,
        "fixture_count": fixture_count,
        "started_count": started_count,
        "completed_count": completed_count,
        "last_activity": last_activity,
    }


# ─────────────────────────── Status rules ───────────────────────────

def _derive_status(start_date: Optional[str], end_date: Optional[str],
                   progress: dict, current_status: str) -> tuple[str, Optional[str]]:
    """Return (new_status, reason). new_status may equal current_status (noop)."""
    today = _today_iso()

    if not start_date:
        return current_status, None

    # Rule A · Upcoming
    if today < start_date:
        return "upcoming", None

    # Between start & end
    if end_date and start_date <= today <= end_date:
        return "ongoing", None
    if not end_date and today >= start_date:
        return "ongoing", None

    # Past end_date
    if end_date and today > end_date:
        # Rule C · Cancelled — fixtures exist, none started
        if progress["fixture_count"] > 0 and progress["started_count"] == 0:
            return "cancelled", "No matches were played."
        # Rule D · Completed — at least one match started, not completed yet
        if progress["started_count"] > 0 and current_status != "completed":
            return "completed", None

    return current_status, None


# ─────────────────────────── Reminder policy ───────────────────────────

REMINDER_SUBJECTS = {
    "no_teams":         ("Complete your teams to organize your tournament",
                         "You created a tournament on Kreeda Nation but haven't added any teams yet. "
                         "Add teams to move forward and start generating fixtures."),
    "no_fixtures":      ("Generate fixtures to continue your tournament",
                         "Your teams are set — the next step is to generate fixtures so participants "
                         "and followers can see the schedule."),
    "starts_tomorrow":  ("Tournament starts tomorrow",
                         "Your tournament starts tomorrow. Please ensure scoring starts on time so "
                         "followers can view live scores."),
    "start_today":      ("Tournament has started",
                         "Your tournament is scheduled for today but no match has started. "
                         "Kick off scoring for your first match so participants and followers can "
                         "see live scores."),
    "no_activity_8h":   ("Continue Tournament",
                         "Your tournament has no recent scoring activity for the last 8 hours. "
                         "Continue updating live scores so followers can stay engaged."),
    "publish_results":  ("Complete Tournament",
                         "All fixture matches are finished. Please publish tournament results by "
                         "marking your event as completed."),
}


def _should_remind(stage: str, last_reminder: dict, cooldown_hours: float) -> bool:
    """One-shot stages set cooldown = a very large number."""
    ts = last_reminder.get(stage)
    hrs = _hours_since(ts)
    if hrs is None:
        return True
    return hrs >= cooldown_hours


async def _pick_reminder(db: Any, event: dict, progress: dict) -> Optional[str]:
    """Return the stage key to remind on, or None."""
    today = _today_iso()
    last_rem: dict = event.get("last_reminder_sent") or {}
    start = event.get("start_date")
    end = event.get("end_date")

    # Case 1: created, no teams → daily
    if progress["team_count"] == 0:
        if _should_remind("no_teams", last_rem, 23):
            return "no_teams"
        return None

    # Case 2: teams present, fixtures missing → daily
    if progress["fixture_count"] == 0:
        if _should_remind("no_fixtures", last_rem, 23):
            return "no_fixtures"
        return None

    # Case 3: start_date is tomorrow → one-shot
    if start:
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        if start == tomorrow and _should_remind("starts_tomorrow", last_rem, 24 * 365):
            return "starts_tomorrow"

    # Case 4: start_date is today and no match started → one-shot
    if start == today and progress["started_count"] == 0 and _should_remind("start_today", last_rem, 24 * 365):
        return "start_today"

    # Case 5: event is ongoing, no scoring activity for 8h → per-8h cadence
    if start and end and start <= today <= end and progress["started_count"] > 0:
        last_activity_h = _hours_since(progress.get("last_activity"))
        if last_activity_h is not None and last_activity_h >= 8:
            if _should_remind("no_activity_8h", last_rem, 8):
                return "no_activity_8h"

    # Case 6: all matches completed but event not marked completed → one-shot
    if progress["fixture_count"] > 0 and progress["completed_count"] == progress["fixture_count"] \
            and event.get("status") != "completed":
        if _should_remind("publish_results", last_rem, 24 * 365):
            return "publish_results"

    return None


# ─────────────────────────── Main tick ───────────────────────────

async def run_tick(db: Any, send_email: Callable[..., Awaitable[bool] | bool]) -> dict[str, int]:
    """One full pass. Returns counters for observability."""
    today = _today_iso()
    # Only look at events that are potentially in-flight — cheap query
    two_days_ahead = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
    query = {
        "$or": [
            {"start_date": {"$lte": two_days_ahead}, "status": {"$ne": "completed"}},
            {"end_date": {"$lte": today}, "status": {"$ne": "completed"}},
            {"status": {"$ne": "completed"}, "start_date": {"$ne": None}},
        ],
        # Skip informal player-hosted local matches — they don't need lifecycle nagging
        "is_local_match": {"$ne": True},
    }
    projection = {
        "_id": 0, "id": 1, "name": 1, "sport": 1, "status": 1, "start_date": 1,
        "end_date": 1, "contact_email": 1, "created_by": 1, "last_reminder_sent": 1,
        "auto_status_updated_at": 1,
    }

    stats = {"scanned": 0, "status_changed": 0, "reminders_sent": 0}
    async for ev in db.events.find(query, projection):
        stats["scanned"] += 1
        try:
            progress = await _event_progress(db, ev["id"])
            new_status, reason = _derive_status(ev.get("start_date"), ev.get("end_date"),
                                                progress, ev.get("status") or "upcoming")

            if new_status != (ev.get("status") or "upcoming"):
                upd: dict[str, Any] = {
                    "status": new_status,
                    "auto_status_updated_at": _now_iso(),
                }
                if reason:
                    upd["auto_status_reason"] = reason
                await db.events.update_one({"id": ev["id"]}, {"$set": upd})
                stats["status_changed"] += 1
                logger.info("event %s: status %s → %s%s",
                            ev["id"], ev.get("status"), new_status,
                            f" ({reason})" if reason else "")
                # Self-heal: sweep any stale live fixtures on this event so
                # the /home 'Happening Now' section doesn't show ghosts.
                # A fixture stuck at status="live" while its parent event is
                # completed/cancelled is a scorer-forgot-to-close artefact.
                if new_status in ("completed", "cancelled"):
                    heal_status = "completed" if new_status == "completed" else "cancelled"
                    heal = await db.fixtures.update_many(
                        {"event_id": ev["id"], "status": "live"},
                        {"$set": {"status": heal_status, "auto_healed_at": _now_iso()}},
                    )
                    if heal.modified_count:
                        logger.info("event %s: healed %d stale-live fixtures → %s",
                                    ev["id"], heal.modified_count, heal_status)
                ev["status"] = new_status  # so reminder logic sees fresh state

            # Reminder logic runs after status is fresh so 'publish_results'
            # only triggers when we didn't already mark it completed above.
            stage = await _pick_reminder(db, ev, progress)
            if stage:
                await _send_reminder(db, ev, stage, send_email)
                stats["reminders_sent"] += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("event_lifecycle tick error for %s: %s", ev.get("id"), exc)

    if stats["status_changed"] or stats["reminders_sent"]:
        logger.info("event_lifecycle tick complete | %s", stats)

    # Piggyback: run the review-escalator on the same daily cadence so pending
    # reviews never stall on a slow vendor. Failures are logged but don't halt.
    try:
        from routes import review_escalator  # local import to keep circular deps clean
        await review_escalator.run_review_escalation(db, send_email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("review escalator failed: %s", exc)

    return stats


async def _send_reminder(db: Any, event: dict, stage: str,
                         send_email: Callable[..., Awaitable[bool] | bool]) -> None:
    to = event.get("contact_email")
    if not to:
        # Fall back to organiser (created_by) email
        u: Optional[dict] = await db.users.find_one({"id": event.get("created_by")}, {"_id": 0, "email": 1})
        to = u.get("email") if u else None
    if not to:
        return

    subject, body = REMINDER_SUBJECTS[stage]
    subject = f"{subject} · {event.get('name', 'Your event')}"

    html = (
        f"<p>Hi,</p>"
        f"<p>{body}</p>"
        f"<p><a href='https://kreedanation.com/events/{event['id']}' "
        f"style='display:inline-block;padding:10px 18px;background:#84CC16;color:#000;"
        f"text-decoration:none;font-weight:bold;border-radius:4px;'>Open event dashboard</a></p>"
        f"<p style='color:#6b7280;font-size:12px;margin-top:24px;'>— Kreeda Nation</p>"
    )
    try:
        result = send_email(to=to, subject=subject, html=html)
        if asyncio.iscoroutine(result):
            await result
        # Persist reminder timestamp for cooldown
        await db.events.update_one(
            {"id": event["id"]},
            {"$set": {f"last_reminder_sent.{stage}": _now_iso()}},
        )
        logger.info("event %s: reminder=%s sent to %s", event["id"], stage, to)
    except Exception as exc:  # noqa: BLE001
        logger.warning("event %s: reminder send failed: %s", event["id"], exc)


# ─────────────────────────── Scheduler wiring ───────────────────────────

def start_event_lifecycle_scheduler(
    db: Any,
    send_email: Callable[..., Awaitable[bool] | bool],
    interval_seconds: int = 24 * 3600,
) -> asyncio.Task:
    """One background task. Default cadence: daily."""
    async def _loop() -> None:
        await asyncio.sleep(45)  # stagger from other schedulers
        while True:
            try:
                await run_tick(db, send_email)
            except Exception as exc:  # noqa: BLE001
                logger.warning("event lifecycle scheduler loop error: %s", exc)
            await asyncio.sleep(interval_seconds)

    return asyncio.create_task(_loop())


# ─────────────────────────── Admin trigger endpoint ───────────────────────────

def register(api: Any, db: Any, send_email: Callable[..., Awaitable[bool] | bool], deps: Any) -> None:
    require_platform_admin = deps.require_platform_admin
    from fastapi import Depends

    @api.post("/admin/events/lifecycle/tick")
    async def manual_tick(_: dict = Depends(require_platform_admin)) -> dict[str, Any]:
        """Admin trigger for the lifecycle sweep — useful for manual runs + CI."""
        return await run_tick(db, send_email)
