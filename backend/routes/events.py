"""Events + Teams + legacy team-roster Players endpoints.

Wired via `register(api, db, deps)` from server.py.
deps must provide: Event, EventCreate, Team, TeamCreate, Player, PlayerCreate,
get_current_user_optional, require_admin, require_company_admin.
"""
from typing import List, Optional
from datetime import datetime, timezone
import os
import logging
from fastapi import Depends, HTTPException

logger = logging.getLogger("kreeda.routes.events")


def _public_app_url() -> str:
    return os.environ.get("PUBLIC_APP_URL", "https://kreedanation.com").rstrip("/")


def _approval_email_html(event_name: str, status: str, reason: str = "") -> str:
    """Render the approval / rejection email body. Kept inline to keep the route file
    self-contained — Kreeda's brand pulse is consistent across the few templates we
    send, no Jinja required."""
    base_url = _public_app_url()
    if status == "approved":
        headline = "EVENT APPROVED"
        accent = "#84CC16"
        body_html = (
            f"<p>Your event <b style='color:#84CC16;'>{event_name}</b> has been approved by the Kreeda Nation team and is now live on the public events page.</p>"
            "<p>You can start adding teams, generating fixtures, inviting scorers and going live.</p>"
        )
        cta_label = "OPEN EVENT"
    else:  # rejected
        headline = "EVENT REJECTED"
        accent = "#FF3B30"
        safe_reason = reason or "No specific reason provided."
        body_html = (
            f"<p>Your event <b style='color:#FF3B30;'>{event_name}</b> was not approved by the Kreeda Nation team.</p>"
            "<p style='font-size:13px;color:#a3a3a3;'>Reason from the platform admin:</p>"
            f"<div style='background:#0a0a0a;border:1px solid #ffffff14;border-radius:4px;padding:14px;margin:8px 0 18px;font-family:ui-monospace,monospace;font-size:13px;color:#e5e5e5;'>{safe_reason}</div>"
            "<p>Edit the event details based on the feedback and resubmit when ready.</p>"
        )
        cta_label = "REVIEW & RESUBMIT"
    return f"""
    <div style='font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0a0a0a;color:#e5e5e5;padding:32px 20px;'>
      <div style='max-width:560px;margin:auto;background:#141414;border:1px solid #ffffff14;border-radius:6px;padding:32px;'>
        <div style='font-size:11px;letter-spacing:.3em;color:{accent};text-transform:uppercase;font-family:ui-monospace,monospace;'>/ Approval update</div>
        <h1 style='font-size:28px;letter-spacing:.05em;margin:12px 0 24px;color:#fff;'>{headline}</h1>
        {body_html}
        <p style='text-align:center;margin:28px 0;'>
          <a href='{base_url}/events' style='display:inline-block;background:{accent};color:#000;font-weight:700;padding:12px 28px;border-radius:4px;text-decoration:none;letter-spacing:.05em;'>{cta_label}</a>
        </p>
        <hr style='border:none;border-top:1px solid #ffffff14;margin:28px 0;'/>
        <p style='font-size:11px;color:#737373;font-family:ui-monospace,monospace;text-transform:uppercase;letter-spacing:.2em;'>Kreeda Nation · Where teams compete, connect &amp; grow</p>
      </div>
    </div>
    """


async def _notify_organiser_decision(db, event: dict, status: str, reason: str = ""):
    """Best-effort email the event's creator. Failures are swallowed (logged)."""
    if not event.get("created_by"):
        return
    user = await db.users.find_one({"id": event["created_by"]}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return
    try:
        from email_service import send_email  # type: ignore
        subject = (
            f"[Kreeda Nation] Your event '{event.get('name')}' has been approved"
            if status == "approved"
            else f"[Kreeda Nation] Your event '{event.get('name')}' was not approved"
        )
        send_email(
            to=user["email"],
            subject=subject,
            html=_approval_email_html(event.get("name", ""), status, reason),
        )
    except Exception:
        logger.exception("Failed to dispatch organiser approval email")


def register(api, db, deps):
    Event = deps.Event
    EventCreate = deps.EventCreate
    Team = deps.Team
    TeamCreate = deps.TeamCreate
    Player = deps.Player
    PlayerCreate = deps.PlayerCreate
    get_current_user_optional = deps.get_current_user_optional
    require_admin = deps.require_admin
    require_company_admin = deps.require_company_admin

    # ---------- Events ----------
    @api.get("/events", response_model=List[Event])
    async def list_events(
        company_id: Optional[str] = None,
        scope: Optional[str] = None,
        user: Optional[dict] = Depends(get_current_user_optional),
    ):
        q: dict = {}
        if company_id:
            q["company_id"] = company_id
        if scope == "mine" and user and user.get("role") in ("company_admin", "organiser"):
            cid = user.get("company_id")
            if cid:
                q = {"$or": [{"company_id": cid}, {"companies": cid}]}

        # ---- Approval-status visibility filter ----
        # Public + non-organiser-non-admin viewers only see approved events.
        # Organisers/HRs see their own pending/rejected events alongside approved ones.
        # Platform admins see everything (including the approvals inbox).
        role = (user or {}).get("role")
        if role not in ("platform_admin", "admin"):
            allowed_filter: dict
            uid = (user or {}).get("id")
            cid = (user or {}).get("company_id")
            if role in ("organiser", "company_admin") and (uid or cid):
                # Approved events for everyone, plus my own pending/rejected events.
                allowed_filter = {
                    "$or": [
                        {"approval_status": {"$in": ["approved", None]}},
                        {"created_by": uid} if uid else {"company_id": cid},
                    ]
                }
            else:
                allowed_filter = {"approval_status": {"$in": ["approved", None]}}
            # Merge with existing q.
            if q:
                q = {"$and": [q, allowed_filter]}
            else:
                q = allowed_filter

        docs = await db.events.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [Event(**d) for d in docs]

    @api.get("/my/teams", response_model=List[Team])
    async def my_teams(user: dict = Depends(require_company_admin)):
        cid = user.get("company_id")
        if not cid:
            return []
        docs = await db.teams.find({"company_id": cid}, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [Team(**d) for d in docs]

    @api.get("/venues/suggest")
    async def venues_suggest(
        city: Optional[str] = None,
        q: Optional[str] = None,
        sport: Optional[str] = None,
        user: Optional[dict] = Depends(get_current_user_optional),
    ):
        """Venue picker for event creation.
        - Returns approved + active venue listings only (ground or court).
        - `sport` (cricket / football / badminton / …) filters to listings that include
          that sport in their `sports` array — so a cricket event won't suggest
          badminton courts.
        - `q` is a free-text contains match against either title OR city — that's how
          a user in Pune can search "kharadi" or "balewadi" and find venues whose city
          field is "Kharadi" / "Pune" even if they only typed an area name.
        - `city` is an explicit city contains filter, kept for the old dropdown.
        - Results are ordered so venues in the caller's company's stored city come first,
          giving an "things near you" feel without needing geo-coordinates.
        """
        flt: dict = {"approved": True, "active": True, "vendor_type": {"$in": ["ground", "court"]}}
        if sport:
            flt["sports"] = sport
        if city:
            flt["city"] = {"$regex": city, "$options": "i"}
        if q:
            flt["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"city": {"$regex": q, "$options": "i"}},
            ]
        docs = await db.vendor_listings.find(
            flt, {"_id": 0, "title": 1, "city": 1, "price": 1, "currency": 1, "id": 1, "sports": 1}
        ).limit(60).to_list(60)

        # If we know the caller's company city, surface those venues first.
        nearby_city = None
        if user and user.get("company_id"):
            company = await db.companies.find_one(
                {"id": user["company_id"]}, {"_id": 0, "city": 1}
            )
            nearby_city = (company or {}).get("city") or None
        if nearby_city:
            nc = nearby_city.lower()
            docs.sort(key=lambda d: 0 if (d.get("city") or "").lower() == nc else 1)
        return docs

    @api.get("/events/pending-approval", response_model=List[Event])
    async def list_pending_approval(user: dict = Depends(require_admin)):
        """Platform-admin inbox: events submitted by organisers awaiting approval.
        Defined BEFORE /events/{event_id} so the literal path wins over the path-param."""
        if user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the platform admin can view the approval queue")
        docs = await db.events.find(
            {"approval_status": "pending_admin_approval"}, {"_id": 0}
        ).sort("submitted_at", -1).to_list(500)
        return [Event(**d) for d in docs]

    @api.get("/events/{event_id}", response_model=Event)
    async def get_event(event_id: str):
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Event not found")
        return Event(**doc)

    @api.post("/events", response_model=Event)
    async def create_event(body: EventCreate, user: dict = Depends(require_admin)):
        payload = body.model_dump()
        if user.get("role") in ("company_admin", "organiser"):
            payload["company_id"] = user.get("company_id")
        payload["created_by"] = user.get("id")
        # Organiser-created events must go through the acknowledgement +
        # platform-admin approval workflow. HRs/admins skip it.
        if user.get("role") == "organiser":
            payload["approval_status"] = "pending_organiser_ack"
        else:
            payload["approval_status"] = "approved"
            payload["approved_at"] = datetime.now(timezone.utc).isoformat()
        ev = Event(**payload)
        await db.events.insert_one(ev.model_dump())
        return ev

    # ---------- Approval workflow ----------
    @api.post("/events/{event_id}/acknowledge-instructions", response_model=Event)
    async def acknowledge_instructions(event_id: str, user: dict = Depends(require_admin)):
        """Organiser acknowledges the platform's instructions and submits the event
        for admin approval. Allowed when the event is `pending_organiser_ack`
        (initial flow) OR `rejected` (resubmit after editing)."""
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        if ev.get("approval_status") not in ("pending_organiser_ack", "rejected"):
            raise HTTPException(400, "Event is not pending acknowledgement")
        if ev.get("created_by") and ev.get("created_by") != user.get("id"):
            if user.get("role") not in ("platform_admin", "admin"):
                raise HTTPException(403, "Only the event creator can acknowledge")
        await db.events.update_one({"id": event_id}, {"$set": {
            "approval_status": "pending_admin_approval",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "rejection_reason": "",
        }})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        return Event(**doc)

    @api.post("/events/{event_id}/approve", response_model=Event)
    async def approve_event(event_id: str, user: dict = Depends(require_admin)):
        if user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the platform admin can approve events")
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        await db.events.update_one({"id": event_id}, {"$set": {
            "approval_status": "approved",
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": user.get("id"),
            "rejection_reason": "",
        }})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        await _notify_organiser_decision(db, doc, "approved")
        return Event(**doc)

    @api.post("/events/{event_id}/reject", response_model=Event)
    async def reject_event(event_id: str, body: dict, user: dict = Depends(require_admin)):
        if user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the platform admin can reject events")
        reason = (body or {}).get("reason", "").strip()
        if not reason:
            raise HTTPException(400, "Rejection reason is required")
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        await db.events.update_one({"id": event_id}, {"$set": {
            "approval_status": "rejected",
            "rejection_reason": reason,
            "approved_by": user.get("id"),
        }})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        await _notify_organiser_decision(db, doc, "rejected", reason)
        return Event(**doc)

    @api.patch("/events/{event_id}", response_model=Event)
    async def update_event(event_id: str, body: dict, user: dict = Depends(require_admin)):
        body.pop("id", None)
        existing = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Event not found")
        if user.get("role") in ("company_admin", "organiser") and existing.get("company_id") != user.get("company_id"):
            raise HTTPException(403, "Not your event")
        await db.events.update_one({"id": event_id}, {"$set": body})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        return Event(**doc)

    @api.delete("/events/{event_id}")
    async def delete_event(event_id: str, user: dict = Depends(require_admin)):
        existing = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not existing:
            return {"ok": True}
        if user.get("role") in ("company_admin", "organiser") and existing.get("company_id") != user.get("company_id"):
            raise HTTPException(403, "Not your event")
        await db.events.delete_one({"id": event_id})
        await db.teams.update_many({"event_id": event_id}, {"$set": {"event_id": None}})
        await db.fixtures.delete_many({"event_id": event_id})
        return {"ok": True}

    # ---------- Teams ----------
    @api.get("/teams", response_model=List[Team])
    async def list_teams(event_id: Optional[str] = None):
        q = {"event_id": event_id} if event_id else {}
        docs = await db.teams.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [Team(**d) for d in docs]

    @api.get("/teams/{team_id}", response_model=Team)
    async def get_team(team_id: str):
        doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Team not found")
        return Team(**doc)

    @api.post("/teams", response_model=Team)
    async def create_team(body: TeamCreate):
        t = Team(**body.model_dump())
        await db.teams.insert_one(t.model_dump())
        return t

    @api.patch("/teams/{team_id}", response_model=Team)
    async def update_team(team_id: str, body: dict, _: dict = Depends(require_admin)):
        body.pop("id", None)
        await db.teams.update_one({"id": team_id}, {"$set": body})
        doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Team not found")
        return Team(**doc)

    @api.delete("/teams/{team_id}")
    async def delete_team(team_id: str, _: dict = Depends(require_admin)):
        await db.teams.delete_one({"id": team_id})
        await db.players.delete_many({"team_id": team_id})
        return {"ok": True}

    # ---------- Team-roster players (legacy, distinct from player accounts) ----------
    @api.get("/team-players", response_model=List[Player])
    async def list_team_players(team_id: Optional[str] = None):
        q = {"team_id": team_id} if team_id else {}
        docs = await db.players.find(q, {"_id": 0}).sort("created_at", -1).to_list(1000)
        return [Player(**d) for d in docs]

    @api.get("/team-players/{player_id}", response_model=Player)
    async def get_team_player(player_id: str):
        doc = await db.players.find_one({"id": player_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Player not found")
        return Player(**doc)

    @api.post("/team-players", response_model=Player)
    async def create_team_player(body: PlayerCreate):
        p = Player(**body.model_dump())
        await db.players.insert_one(p.model_dump())
        return p

    @api.patch("/team-players/{player_id}", response_model=Player)
    async def update_team_player(player_id: str, body: dict, _: dict = Depends(require_admin)):
        body.pop("id", None)
        await db.players.update_one({"id": player_id}, {"$set": body})
        doc = await db.players.find_one({"id": player_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Player not found")
        return Player(**doc)

    @api.delete("/team-players/{player_id}")
    async def delete_team_player(player_id: str, _: dict = Depends(require_admin)):
        await db.players.delete_one({"id": player_id})
        return {"ok": True}
