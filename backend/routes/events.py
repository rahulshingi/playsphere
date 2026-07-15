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
    get_current_user = deps.get_current_user
    require_admin = deps.require_admin
    require_company_admin = deps.require_company_admin
    _can_manage_event = deps.can_manage_event
    # Sport metadata defaults — passed in via deps so we don't reach across
    # modules for a private symbol.
    _SPORT_DEFAULTS = getattr(deps, "SPORT_DEFAULTS", None) or {}

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
        if scope == "hosted" and user and user.get("id"):
            # "Events I host" — used by player local-match dashboard.
            q = {"created_by": user["id"]}

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

        # ---- Local-match visibility filter ----
        # Player-hosted local matches with `listed_publicly=False` are hidden
        # from the general /events list. Creator + admins still see them via
        # direct fetch and (for the creator) via list.
        if role not in ("platform_admin", "admin"):
            uid = (user or {}).get("id")
            hide_hidden = {
                "$or": [
                    {"listed_publicly": {"$ne": False}},
                    {"is_local_match": {"$ne": True}},
                ]
            }
            if uid:
                hide_hidden = {
                    "$or": [
                        {"listed_publicly": {"$ne": False}},
                        {"is_local_match": {"$ne": True}},
                        {"created_by": uid},
                    ]
                }
            q = {"$and": [q, hide_hidden]} if q else hide_hidden

        docs = await db.events.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        # NOTE: on-read auto-complete removed (iter41). Status transitions are
        # now driven by routes.event_lifecycle.run_tick which runs daily and
        # correctly handles the cancelled vs completed distinction. Reading a
        # stale event never mutates it — the next tick will sort it out.
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
        # Status transitions are handled by routes.event_lifecycle.run_tick
        # (see list_events comment). Reads are pure.
        return Event(**doc)

    @api.post("/events", response_model=Event)
    async def create_event(body: EventCreate, user: dict = Depends(get_current_user)):
        # Allow platform_admin, admin, company_admin, organiser AND player. When
        # a player creates it, flag it as a "local match" so public marketplace
        # surfaces keep organiser/HR events curated.
        role = user.get("role")
        if role not in ("player", "company_admin", "organiser", "platform_admin", "admin"):
            raise HTTPException(403, "Not allowed to create events")
        payload = body.model_dump()
        # ---- Require start_date + end_date at create-time (edits stay flexible) ----
        # Keeps the model itself Optional so PATCH /events/{id} can accept partials.
        start = (payload.get("start_date") or "").strip()
        end = (payload.get("end_date") or "").strip()
        if not start:
            raise HTTPException(400, "start_date is required")
        if not end:
            raise HTTPException(400, "end_date is required")
        if end < start:
            raise HTTPException(400, "end_date cannot be earlier than start_date")
        payload["start_date"] = start
        payload["end_date"] = end
        # ---- Sport enrichment --------------------------------------------
        # Look up the sport doc to auto-populate `scoring_pattern` +
        # `player_format`. Falls back to `_SPORT_DEFAULTS` for well-known
        # slugs so events keep working even when db.sports is empty.
        sport_slug = (payload.get("sport") or "").strip().lower()
        payload["sport"] = sport_slug
        sport_doc = await db.sports.find_one({"value": sport_slug, "active": True}, {"_id": 0})
        defaults = _SPORT_DEFAULTS.get(sport_slug, {"scoring_pattern": "generic", "player_format": "team"})
        sport_scoring = (sport_doc or {}).get("scoring_pattern") or defaults["scoring_pattern"]
        sport_pf = (sport_doc or {}).get("player_format") or defaults["player_format"]
        # Explicit user pick wins (e.g. "doubles" for badminton), else inherit from sport.
        if not payload.get("scoring_pattern"):
            payload["scoring_pattern"] = sport_scoring
        if not payload.get("player_format"):
            # For "both" sports, require the creator to pick singles/doubles.
            if sport_pf == "both":
                raise HTTPException(400, f"{sport_slug} supports both singles and doubles — pick one via `player_format`")
            payload["player_format"] = sport_pf
        elif sport_pf == "both" and payload["player_format"] not in ("singles", "doubles"):
            raise HTTPException(400, "player_format must be 'singles' or 'doubles' for racket sports")

        if user.get("role") in ("company_admin", "organiser"):
            payload["company_id"] = user.get("company_id")
        payload["created_by"] = user.get("id")
        # Player-created → tag as local match; auto-approve (no HQ review) so
        # they can start using it immediately.
        if role == "player":
            payload["is_local_match"] = True
            payload["approval_status"] = "approved"
            payload["approved_at"] = datetime.now(timezone.utc).isoformat()
        elif user.get("role") == "organiser":
            payload["approval_status"] = "pending_organiser_ack"
        else:
            payload["approval_status"] = "approved"
            payload["approved_at"] = datetime.now(timezone.utc).isoformat()
        ev = Event(**payload)
        await db.events.insert_one(ev.model_dump())
        return ev

    # -------- Event photo gallery --------
    @api.post("/events/{event_id}/photos")
    async def add_event_photo(event_id: str, body: dict, user: dict = Depends(get_current_user)):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        # Creator OR platform admin can upload.
        if ev.get("created_by") != user.get("id") and user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the event creator can add photos")
        url = (body.get("url") or "").strip()
        if not url:
            raise HTTPException(400, "url required")
        photos = list(ev.get("photos") or [])
        # Cap at 7 — keeps the gallery visually tight (single 3-2-2 grid row on
        # mobile) and prevents runaway storage costs on popular local matches.
        if url in photos:
            return {"ok": True, "photos": photos}
        if len(photos) >= 7:
            raise HTTPException(
                400,
                "Photo limit reached — you can have up to 7 photos in the gallery. "
                "Remove one before adding another.",
            )
        photos.append(url)
        await db.events.update_one({"id": event_id}, {"$set": {"photos": photos}})
        return {"ok": True, "photos": photos}

    @api.delete("/events/{event_id}/photos")
    async def remove_event_photo(event_id: str, url: str, user: dict = Depends(get_current_user)):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        if ev.get("created_by") != user.get("id") and user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Not allowed")
        photos = [p for p in (ev.get("photos") or []) if p != url]
        await db.events.update_one({"id": event_id}, {"$set": {"photos": photos}})
        return {"ok": True, "photos": photos}

    # -------- Tournaments a player HOSTED (created themselves) --------
    @api.get("/players/{player_id}/hosted-tournaments")
    async def player_hosted_tournaments(player_id: str, user: Optional[dict] = Depends(get_current_user_optional)):
        # Resolve player_id -> user_id (creator column stores user id, not profile id).
        prof = await db.player_profiles.find_one({"id": player_id}, {"_id": 0, "user_id": 1})
        if not prof:
            return []
        uid = prof.get("user_id")
        if not uid:
            return []
        # Hide unlisted events from strangers.
        is_owner = user and user.get("id") == uid
        is_admin = user and user.get("role") in ("platform_admin", "admin")
        q = {"created_by": uid}
        if not (is_owner or is_admin):
            q = {"$and": [q, {"$or": [{"listed_publicly": {"$ne": False}}, {"is_local_match": {"$ne": True}}]}]}
        events = await db.events.find(q, {
            "_id": 0, "id": 1, "name": 1, "sport": 1, "start_date": 1, "end_date": 1,
            "banner_url": 1, "is_local_match": 1, "listed_publicly": 1,
            "approval_status": 1, "status": 1, "venue": 1,
        }).sort("created_at", -1).to_list(500)
        return events

    # -------- Tournaments a player participated in --------
    @api.get("/players/{player_id}/tournaments")
    async def player_tournaments(player_id: str):
        # A player's participation is derived from team rosters. Match against
        # all shapes we've stored historically: legacy `player_ids` / `players[].*`
        # and the current `members: [player_id]` array.
        rosters = await db.teams.find(
            {"$or": [
                {"members": player_id},
                {"player_ids": player_id},
                {"players.id": player_id},
                {"players.user_id": player_id},
                {"players.player_id": player_id},
            ]},
            {"_id": 0, "id": 1, "name": 1, "event_id": 1, "sport": 1}
        ).to_list(500)
        event_ids = list({t["event_id"] for t in rosters if t.get("event_id")})
        if not event_ids:
            return []
        events = await db.events.find(
            {"id": {"$in": event_ids}},
            {"_id": 0, "id": 1, "name": 1, "sport": 1, "start_date": 1, "end_date": 1, "banner_url": 1,
             "is_local_match": 1, "created_by": 1, "approval_status": 1}
        ).to_list(500)
        # Contribution stats — pull awards from db.fixtures (NOT db.matches — earlier
        # copy-paste bug meant this always returned zeros).
        fixtures = await db.fixtures.find(
            {"event_id": {"$in": event_ids}, "status": "completed"},
            {"_id": 0, "event_id": 1, "awards": 1}
        ).to_list(2000)
        by_event: dict = {eid: {"matches": 0, "mom": 0, "best_batter": 0, "best_bowler": 0, "top_scorer": 0} for eid in event_ids}
        for m in fixtures:
            awards = m.get("awards") or {}
            eid = m["event_id"]
            if eid in by_event:
                by_event[eid]["matches"] += 1
            for key in ("mom", "best_batter", "best_bowler", "top_scorer"):
                who = awards.get(key)
                pid = who.get("player_id") if isinstance(who, dict) else who
                if pid == player_id:
                    by_event.setdefault(eid, {"matches": 0, "mom": 0, "best_batter": 0, "best_bowler": 0, "top_scorer": 0})[key] += 1
        out = []
        for ev in events:
            stats = by_event.get(ev["id"], {})
            out.append({**ev, "contribution": stats})
        out.sort(key=lambda e: (e.get("start_date") or "", e.get("name") or ""), reverse=True)
        return out

    # -------- Fixture-level match history (per-match cards) --------
    @api.get("/players/{player_id}/match-history")
    async def player_match_history(player_id: str):
        """Every fixture the player was rostered on, with a score card payload
        the frontend can render directly. Only returns fixtures with status in
        {live, completed} — a scheduled fixture has no score yet.

        Shape (one item per fixture):
        ```
        {
          fixture_id, event_id, event_name, sport, is_local_match, banner_url,
          match_number, status, played_at,
          my_team: {id, name, score_display, is_winner},
          opp_team: {id, name, score_display},
          result: 'won'|'lost'|'draw',
          my_awards: ['mom', 'best_batter', ...],  # awards this player won
          hero_image_url
        }
        ```
        """
        # 1. Every team this player was rostered on.
        rosters = await db.teams.find(
            {"$or": [
                {"members": player_id},
                {"player_ids": player_id},
                {"players.id": player_id},
                {"players.user_id": player_id},
                {"players.player_id": player_id},
            ]},
            {"_id": 0, "id": 1, "name": 1, "event_id": 1}
        ).to_list(500)
        if not rosters:
            return []
        team_ids = {t["id"] for t in rosters}
        team_by_id = {t["id"]: t for t in rosters}
        event_ids = list({t["event_id"] for t in rosters if t.get("event_id")})

        # 2. Fixtures involving any of those teams, with a score to show.
        fixtures = await db.fixtures.find(
            {
                "event_id": {"$in": event_ids},
                "status": {"$in": ["live", "completed"]},
                "$or": [{"team_a_id": {"$in": list(team_ids)}}, {"team_b_id": {"$in": list(team_ids)}}],
            },
            {"_id": 0},
        ).sort("match_number", -1).to_list(2000)
        if not fixtures:
            return []

        # 3. Event + opponent team metadata in bulk.
        events = await db.events.find(
            {"id": {"$in": list({f["event_id"] for f in fixtures})}},
            {"_id": 0, "id": 1, "name": 1, "sport": 1, "banner_url": 1, "is_local_match": 1}
        ).to_list(500)
        ev_by_id = {e["id"]: e for e in events}
        opp_ids = list({f["team_b_id"] if f["team_a_id"] in team_ids else f["team_a_id"] for f in fixtures})
        opp_teams = await db.teams.find({"id": {"$in": opp_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        opp_by_id = {t["id"]: t for t in opp_teams}

        # Fetch full team docs so we can (a) render captain/first-member as MoM
        # for individual-sport matches without per-player stats, and (b) list
        # opponent teams. We need `members` for backfill, so re-query without
        # the projection restriction on my_team as well.
        all_team_ids = list(set(team_ids) | set(opp_ids))
        full_teams = await db.teams.find(
            {"id": {"$in": all_team_ids}},
            {"_id": 0, "id": 1, "name": 1, "members": 1, "captain_player_id": 1}
        ).to_list(500)
        full_by_id = {t["id"]: t for t in full_teams}
        # Refresh opp_by_id + team_by_id so downstream loops read consistent
        # full docs (fall back to the projection docs if a team was deleted).
        for tid, doc in full_by_id.items():
            if tid in opp_by_id:
                opp_by_id[tid] = doc

        def _display(score_side: dict, sport: str) -> str:
            """Render a compact score string. Handles all score shapes we've
            shipped: cricket `total/wkts (overs)`, other-team-sport totals, and
            racket-sport `sets: [a, b, c]` arrays."""
            if not isinstance(score_side, dict):
                return "—"
            if sport == "cricket":
                total = score_side.get("total") if score_side.get("total") is not None else score_side.get("runs")
                if total is None:
                    total = 0
                wkts = score_side.get("wickets")
                overs = score_side.get("overs")
                out = f"{total}"
                if wkts is not None:
                    out += f"/{wkts}"
                if overs:
                    out += f" ({overs})"
                return out
            for k in ("total", "goals", "points", "score"):
                if score_side.get(k) is not None:
                    return str(score_side.get(k) or 0)
            # Racket / set-based sports (badminton, tennis, table tennis, squash).
            sets_arr = score_side.get("sets")
            if isinstance(sets_arr, list) and sets_arr:
                # Show the sets list joined by ·, e.g. "1 · 0 · 3".
                return " · ".join(str(int(x) if x is not None else 0) for x in sets_arr)
            return "—"

        def _my_awards_for_fixture(f: dict, winning_team_id: str) -> list:
            """Which award keys did THIS player win on this fixture?

            Reads stored `awards` first (populated by _compute_awards on match
            completion). If stored awards are empty AND the player is on the
            winning team of an individual/racket sport, we synthesise 'mom' +
            'top_scorer' — a badminton singles winner has no `scorers` list
            to compute from, so this fallback ensures they still get credit.
            """
            awards = f.get("awards") or {}
            keys_won = []
            for key in ("mom", "best_batter", "best_bowler", "top_scorer"):
                who = awards.get(key)
                pid = who.get("player_id") if isinstance(who, dict) else who
                if pid == player_id:
                    keys_won.append(key)
            if keys_won or not winning_team_id:
                return keys_won
            # Fallback path: awards empty. Give the win credit to the winning
            # team's captain (or, if there's no captain, first roster member).
            wteam = full_by_id.get(winning_team_id)
            if not wteam:
                return keys_won
            captain = wteam.get("captain_player_id")
            members = wteam.get("members") or []
            representative = captain if captain in members or captain else (members[0] if members else None)
            if representative == player_id:
                # Racket/individual sports: crown MoM + top_scorer.
                # Team sports: only 'mom' — a single field goal wouldn't
                # crown a "top scorer" without stats.
                sport = (ev_by_id.get(f.get("event_id")) or {}).get("sport") or ""
                if sport in ("badminton", "tennis", "table_tennis", "squash",
                              "chess", "quiz", "hackathon"):
                    return ["mom", "top_scorer"]
                return ["mom"]
            return keys_won

        out = []
        for f in fixtures:
            ev = ev_by_id.get(f["event_id"])
            if not ev:
                continue
            my_side_key = "team_a" if f["team_a_id"] in team_ids else "team_b"
            my_team_id = f["team_a_id"] if my_side_key == "team_a" else f["team_b_id"]
            opp_team_id = f["team_b_id"] if my_side_key == "team_a" else f["team_a_id"]
            my_team = full_by_id.get(my_team_id) or team_by_id.get(my_team_id) or {"name": "My team"}
            opp_team = opp_by_id.get(opp_team_id) or {"name": "Opponent"}
            score = f.get("score") or {}
            my_score = _display(score.get(my_side_key) or {}, ev.get("sport") or "")
            opp_score = _display(score.get("team_b" if my_side_key == "team_a" else "team_a") or {}, ev.get("sport") or "")
            winner_id = f.get("winner_id")
            if not winner_id:
                result = "live" if f["status"] == "live" else "draw"
            elif winner_id == my_team_id:
                result = "won"
            else:
                result = "lost"
            my_awards = _my_awards_for_fixture(f, winner_id or "")
            out.append({
                "fixture_id": f["id"],
                "event_id": ev["id"],
                "event_name": ev.get("name") or "",
                "sport": ev.get("sport") or "",
                "is_local_match": bool(ev.get("is_local_match")),
                "banner_url": ev.get("banner_url") or "",
                "match_number": f.get("match_number"),
                "status": f["status"],
                "my_team": {"id": my_team_id, "name": my_team.get("name") or "My team", "score_display": my_score, "is_winner": winner_id == my_team_id},
                "opp_team": {"id": opp_team_id, "name": opp_team.get("name") or "Opponent", "score_display": opp_score},
                "result": result,
                "my_awards": my_awards,
                "hero_image_url": f.get("hero_image_url") or "",
            })
        return out

    # ---------- Approval workflow ----------
    @api.post("/events/{event_id}/acknowledge-instructions", response_model=Event)
    async def acknowledge_instructions(event_id: str, body: Optional[dict] = None, user: dict = Depends(require_admin)):
        """Organiser acknowledges the platform's instructions and submits the event
        for admin approval. Allowed when the event is `pending_organiser_ack`
        (initial flow) OR `rejected` (resubmit after editing).

        Body may include `{payment_method: "online"|"offline"}` to record how the
        organiser is paying the (admin-configured) event fee. `online` is stubbed
        as instantly paid until Razorpay lands; `offline` marks the invoice
        pending and the platform admin later marks it paid. When the fee is 0,
        payment_method is ignored and the event submits for free.
        """
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        if ev.get("approval_status") not in ("pending_organiser_ack", "rejected"):
            raise HTTPException(400, "Event is not pending acknowledgement")
        if ev.get("created_by") and ev.get("created_by") != user.get("id"):
            if user.get("role") not in ("platform_admin", "admin"):
                raise HTTPException(403, "Only the event creator can acknowledge")

        # Load fee from site settings and record a payment record on the event.
        settings = await db.settings.find_one({"id": "site"}, {"_id": 0}) or {}
        fee = float(settings.get("organiser_event_fee") or 0)
        currency = settings.get("organiser_event_fee_currency") or "INR"
        payment_method = (body or {}).get("payment_method")
        now_iso = datetime.now(timezone.utc).isoformat()
        payment: dict = {"fee": fee, "currency": currency, "status": "not_required"}
        if fee > 0:
            if payment_method == "online":
                # Stubbed: Razorpay integration lands later. For now we accept the
                # organiser's declaration + capture the fact it should have been
                # collected online. Admin sees this in the dashboard.
                payment.update({"status": "paid_online", "method": "online", "paid_at": now_iso, "provider": "razorpay_stub"})
            elif payment_method == "offline":
                payment.update({"status": "pending_offline", "method": "offline"})
            else:
                raise HTTPException(400, f"Event fee of {fee} {currency} required — pick payment_method online or offline")
        await db.events.update_one({"id": event_id}, {"$set": {
            "approval_status": "pending_admin_approval",
            "submitted_at": now_iso,
            "rejection_reason": "",
            "payment": payment,
        }})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        return Event(**doc)

    @api.post("/events/{event_id}/mark-paid", response_model=Event)
    async def mark_event_paid(event_id: str, user: dict = Depends(require_admin)):
        """Platform admin marks an offline event-fee payment as received."""
        if user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the platform admin can confirm payment")
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
        payment = ev.get("payment") or {}
        if payment.get("status") not in ("pending_offline",):
            raise HTTPException(400, "Nothing to mark paid on this event")
        payment.update({"status": "paid_offline", "paid_at": datetime.now(timezone.utc).isoformat(), "confirmed_by": user.get("id")})
        await db.events.update_one({"id": event_id}, {"$set": {"payment": payment}})
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
    async def update_event(event_id: str, body: dict, user: dict = Depends(get_current_user)):
        body.pop("id", None)
        existing = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Event not found")
        # Creator OR anyone who can manage the event (platform admin,
        # company_admin/organiser of the owning company) may edit.
        if not await _can_manage_event(user, existing):
            raise HTTPException(403, "Not your event")
        # Protect sensitive lifecycle fields from being overwritten via PATCH.
        for protected in ("created_by", "company_id", "approval_status",
                          "approved_by", "approved_at", "created_at", "payment"):
            body.pop(protected, None)
        # Once an event exists, start/end are ALWAYS present — reject explicit
        # blanks so editors can't accidentally clear them. Order check runs
        # against whichever value isn't in the patch.
        if "start_date" in body:
            new_start = (body.get("start_date") or "").strip()
            if not new_start:
                raise HTTPException(400, "start_date cannot be empty")
            body["start_date"] = new_start
        if "end_date" in body:
            new_end = (body.get("end_date") or "").strip()
            if not new_end:
                raise HTTPException(400, "end_date cannot be empty")
            body["end_date"] = new_end
        effective_start = body.get("start_date", existing.get("start_date"))
        effective_end = body.get("end_date", existing.get("end_date"))
        if effective_start and effective_end and effective_end < effective_start:
            raise HTTPException(400, "end_date cannot be earlier than start_date")
        await db.events.update_one({"id": event_id}, {"$set": body})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        return Event(**doc)

    @api.delete("/events/{event_id}")
    async def delete_event(event_id: str, user: dict = Depends(get_current_user)):
        existing = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not existing:
            return {"ok": True}
        if not await _can_manage_event(user, existing):
            raise HTTPException(403, "Not your event")
        await db.events.delete_one({"id": event_id})
        await db.teams.update_many({"event_id": event_id}, {"$set": {"event_id": None}})
        await db.fixtures.delete_many({"event_id": event_id})
        return {"ok": True}

    @api.post("/events/{event_id}/cancel", response_model=Event)
    async def cancel_event(event_id: str, body: dict = None, user: dict = Depends(get_current_user)):
        """Soft-cancel an event: mark status=cancelled without deleting data.

        Preserves fixtures, teams, photos, awards — useful for record-keeping
        and future audit. Creator + platform admin + company admins of the
        owning company can call this. Optional body `{reason}` is stored on
        the event as `cancellation_reason`.
        """
        existing = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Event not found")
        if not await _can_manage_event(user, existing):
            raise HTTPException(403, "Not your event")
        if existing.get("status") == "cancelled":
            raise HTTPException(400, "Event already cancelled")
        upd = {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": user.get("id"),
        }
        reason = (body or {}).get("reason") or ""
        if reason:
            upd["cancellation_reason"] = reason.strip()[:500]
        await db.events.update_one({"id": event_id}, {"$set": upd})
        doc = await db.events.find_one({"id": event_id}, {"_id": 0})
        return Event(**doc)

    # ---------- Teams ----------
    @api.get("/teams", response_model=List[Team])
    async def list_teams(event_id: Optional[str] = None, user: Optional[dict] = Depends(get_current_user_optional)):
        """Teams are scoped to the caller:
        * anonymous users may only read the roster for a specific `event_id`;
        * platform_admin sees all teams;
        * company_admin/organiser sees teams on events they can manage + teams they created;
        * players see only teams they captain or belong to.
        * When `event_id` is passed and it's not one they own, the public roster
          of that event is still returned (needed for public event pages).
        """
        if not user:
            if not event_id:
                raise HTTPException(401, "Login required to list teams")
            docs = await db.teams.find({"event_id": event_id}, {"_id": 0}).sort("created_at", -1).to_list(500)
            return [Team(**d) for d in docs]
        role = user.get("role")
        if role in ("platform_admin", "admin"):
            q = {"event_id": event_id} if event_id else {}
        else:
            cid = user.get("company_id")
            # Events the user can manage
            owned_or = []
            if cid:
                owned_or.append({"company_id": cid})
                owned_or.append({"companies": cid})
            owned_event_ids = []
            if owned_or:
                events = await db.events.find({"$or": owned_or}, {"_id": 0, "id": 1}).to_list(1000)
                owned_event_ids = [e["id"] for e in events]
            or_clauses = [{"created_by": user["id"]}]
            if role == "player":
                # Include teams the player is captain of or a member of.
                pl = await db.players.find_one({"user_id": user["id"]}, {"_id": 0, "id": 1})
                if pl:
                    or_clauses.append({"captain_player_id": pl["id"]})
                    or_clauses.append({"members": pl["id"]})
            if owned_event_ids:
                or_clauses.append({"event_id": {"$in": owned_event_ids}})
            if event_id and event_id not in owned_event_ids:
                # Public read of a specific event's roster is always allowed.
                q = {"event_id": event_id}
            else:
                q = {"$or": or_clauses}
                if event_id:
                    q = {"$and": [q, {"event_id": event_id}]}
        docs = await db.teams.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
        return [Team(**d) for d in docs]

    @api.get("/teams/{team_id}", response_model=Team)
    async def get_team(team_id: str):
        doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Team not found")
        return Team(**doc)

    @api.post("/teams", response_model=Team)
    async def create_team(body: TeamCreate, user: dict = Depends(require_admin)):
        t = Team(**body.model_dump(), created_by=user["id"])
        await db.teams.insert_one(t.model_dump())
        return t

    async def _require_own_team(team_id: str, user: dict) -> dict:
        doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Team not found")
        if user.get("role") in ("platform_admin", "admin"):
            return doc
        if doc.get("created_by") == user["id"]:
            return doc
        if doc.get("event_id"):
            ev = await db.events.find_one({"id": doc["event_id"]}, {"_id": 0})
            if ev and await _can_manage_event(user, ev):
                return doc
        raise HTTPException(403, "You can only manage teams you created")

    @api.patch("/teams/{team_id}", response_model=Team)
    async def update_team(team_id: str, body: dict, user: dict = Depends(require_admin)):
        await _require_own_team(team_id, user)
        body.pop("id", None); body.pop("created_by", None)
        await db.teams.update_one({"id": team_id}, {"$set": body})
        doc = await db.teams.find_one({"id": team_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Team not found")
        return Team(**doc)

    @api.delete("/teams/{team_id}")
    async def delete_team(team_id: str, user: dict = Depends(require_admin)):
        await _require_own_team(team_id, user)
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
