"""Fixture generation (round-robin & knockout), live score updates, public scorecard, WebSocket.

Wired via `register(api, app, db, ws_manager, deps)` from server.py. The websocket is registered
on `app` directly (not on the `/api` APIRouter) so the path remains `/api/ws`.
"""
import uuid
import random
from datetime import datetime, timezone
from typing import List
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect


def generate_round_robin(team_ids: List[str], event_id: str) -> List[dict]:
    teams = list(team_ids)
    if len(teams) % 2 == 1:
        teams.append(None)
    n = len(teams)
    fixtures = []
    half = n // 2
    arr = teams[:]
    match_num = 1
    for r in range(n - 1):
        for i in range(half):
            a, b = arr[i], arr[n - 1 - i]
            if a is not None and b is not None:
                fixtures.append({
                    "id": str(uuid.uuid4()),
                    "event_id": event_id,
                    "round": r + 1,
                    "match_number": match_num,
                    "team_a_id": a,
                    "team_b_id": b,
                    "scheduled_at": None,
                    "venue": "",
                    "status": "scheduled",
                    "score": {},
                    "winner_id": None,
                    "bracket_position": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                match_num += 1
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return fixtures


def generate_knockout(team_ids: List[str], event_id: str) -> List[dict]:
    teams = list(team_ids)
    random.shuffle(teams)
    n = 1
    while n < len(teams):
        n *= 2
    while len(teams) < n:
        teams.append(None)
    fixtures = []
    match_num = 1
    current_round_winners_slots = []
    for i in range(0, n, 2):
        a, b = teams[i], teams[i + 1]
        f_id = str(uuid.uuid4())
        fixtures.append({
            "id": f_id,
            "event_id": event_id,
            "round": 1,
            "match_number": match_num,
            "team_a_id": a,
            "team_b_id": b,
            "scheduled_at": None,
            "venue": "",
            "status": "scheduled",
            "score": {},
            "winner_id": None,
            "bracket_position": f"R1-M{match_num}",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        current_round_winners_slots.append(f_id)
        match_num += 1
    rnd = 2
    prev = current_round_winners_slots
    while len(prev) > 1:
        new_slots = []
        for i in range(0, len(prev), 2):
            f_id = str(uuid.uuid4())
            fixtures.append({
                "id": f_id,
                "event_id": event_id,
                "round": rnd,
                "match_number": match_num,
                "team_a_id": None,
                "team_b_id": None,
                "scheduled_at": None,
                "venue": "",
                "status": "scheduled",
                "score": {},
                "winner_id": None,
                "bracket_position": f"R{rnd}-M{match_num}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            new_slots.append(f_id)
            match_num += 1
        prev = new_slots
        rnd += 1
    return fixtures


def register(api, app, db, ws_manager, deps):
    """deps must expose: Fixture, ScoreUpdate, require_admin, get_current_user,
    can_manage_event, can_score_fixture, fixtures_locked, get_event_or_404,
    default_score, propagate_knockout_winner."""
    Fixture = deps.Fixture
    ScoreUpdate = deps.ScoreUpdate
    get_current_user = deps.get_current_user
    can_manage_event = deps.can_manage_event
    can_score_fixture = deps.can_score_fixture
    fixtures_locked = deps.fixtures_locked
    get_event_or_404 = deps.get_event_or_404
    default_score = deps.default_score
    propagate_knockout_winner = deps.propagate_knockout_winner

    @api.post("/events/{event_id}/generate-fixtures")
    async def generate_fixtures_endpoint(event_id: str, user: dict = Depends(get_current_user)):
        ev = await get_event_or_404(event_id)
        if not await can_manage_event(user, ev):
            raise HTTPException(403, "Only the event organiser can generate fixtures")
        if await fixtures_locked(event_id):
            raise HTTPException(
                400,
                "Fixtures are locked: the tournament has already started. "
                "Regenerating would invalidate live or completed match scores.",
            )
        teams = await db.teams.find({"event_id": event_id}, {"_id": 0, "id": 1}).to_list(500)
        team_ids = [t["id"] for t in teams]
        if len(team_ids) < 2:
            raise HTTPException(400, "Need at least 2 teams to generate fixtures")
        await db.fixtures.delete_many({"event_id": event_id})
        if ev["format"] == "knockout":
            fixtures = generate_knockout(team_ids, event_id)
        else:
            fixtures = generate_round_robin(team_ids, event_id)
        if fixtures:
            await db.fixtures.insert_many(fixtures)
        return {"ok": True, "count": len(fixtures)}

    @api.get("/events/{event_id}/fixtures", response_model=List[Fixture])
    async def list_fixtures(event_id: str):
        docs = await db.fixtures.find({"event_id": event_id}, {"_id": 0}).sort([("round", 1), ("match_number", 1)]).to_list(1000)
        return [Fixture(**d) for d in docs]

    @api.get("/fixtures/{fixture_id}", response_model=Fixture)
    async def get_fixture(fixture_id: str):
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        return Fixture(**doc)

    @api.get("/public/fixtures/{fixture_id}")
    async def public_live_scorecard(fixture_id: str):
        """No-auth, shareable live scoreboard payload."""
        fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not fx:
            raise HTTPException(404, "Fixture not found")
        event = await db.events.find_one({"id": fx["event_id"]}, {"_id": 0}) or {}
        team_ids = [tid for tid in (fx.get("team_a_id"), fx.get("team_b_id")) if tid]
        teams = {}
        if team_ids:
            async for t in db.teams.find({"id": {"$in": team_ids}}, {"_id": 0}):
                teams[t["id"]] = {
                    "id": t["id"],
                    "name": t.get("name"),
                    "short_name": t.get("short_name"),
                    "color": t.get("color"),
                    "logo_url": t.get("logo_url"),
                }
        pub_event = {
            "id": event.get("id"),
            "name": event.get("name"),
            "sport": event.get("sport"),
            "format": event.get("format"),
            "location": event.get("location"),
            "company_id": event.get("company_id"),
        }
        return {"fixture": fx, "event": pub_event, "teams": teams}

    def _compute_awards(sport: str, score: dict) -> dict:
        """Best-effort auto-awards from the final score dict. Works cross-sport
        by scanning both sides for the highest-contributing player. Cricket has
        richer awards (best batter + best bowler) when batter/bowler stats are
        available in the score payload."""
        awards: dict = {}
        try:
            sides = score.get("sides") or {}
            a_side = sides.get("a") or score.get("a") or {}
            b_side = sides.get("b") or score.get("b") or {}
            if sport == "cricket":
                # Aggregate batters + bowlers from both innings.
                batters, bowlers = [], []
                for s in (a_side, b_side):
                    batters += (s.get("batters") or [])
                    bowlers += (s.get("bowlers") or [])
                if batters:
                    top_bat = max(batters, key=lambda p: (p.get("runs") or 0))
                    if top_bat.get("runs"):
                        awards["best_batter"] = {"player_id": top_bat.get("player_id") or top_bat.get("id"), "name": top_bat.get("name"), "runs": top_bat.get("runs")}
                if bowlers:
                    top_bowl = max(bowlers, key=lambda p: (p.get("wickets") or 0))
                    if top_bowl.get("wickets") is not None:
                        awards["best_bowler"] = {"player_id": top_bowl.get("player_id") or top_bowl.get("id"), "name": top_bowl.get("name"), "wickets": top_bowl.get("wickets")}
                # MoM = best batter unless a bowler took 3+ wickets.
                if awards.get("best_bowler") and (awards["best_bowler"].get("wickets") or 0) >= 3:
                    awards["mom"] = awards["best_bowler"]
                elif awards.get("best_batter"):
                    awards["mom"] = awards["best_batter"]
            else:
                # Generic: highest-scoring individual across both sides.
                players = (a_side.get("scorers") or []) + (b_side.get("scorers") or [])
                if players:
                    top = max(players, key=lambda p: (p.get("points") or p.get("goals") or p.get("score") or 0))
                    metric = top.get("points") or top.get("goals") or top.get("score") or 0
                    if metric:
                        awards["top_scorer"] = {"player_id": top.get("player_id") or top.get("id"), "name": top.get("name"), "score": metric}
                        awards["mom"] = awards["top_scorer"]
        except Exception:
            pass
        return awards

    @api.patch("/fixtures/{fixture_id}", response_model=Fixture)
    async def update_fixture_score(fixture_id: str, body: ScoreUpdate, user: dict = Depends(get_current_user)):
        existing = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not existing:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(existing["event_id"])
        if not await can_score_fixture(user, existing, ev):
            raise HTTPException(403, "You are not allowed to score this match")
        upd = {"score": body.score}
        if body.status:
            upd["status"] = body.status
        if body.winner_id:
            upd["winner_id"] = body.winner_id
        # Auto-compute awards when the match transitions to `completed` (and no
        # manual overrides have already been set).
        if body.status == "completed" and not existing.get("awards"):
            awards = _compute_awards(ev.get("sport"), body.score or {})
            if awards:
                upd["awards"] = awards
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        if body.winner_id and doc.get("bracket_position"):
            await propagate_knockout_winner(doc)
            doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
        return Fixture(**doc)

    @api.patch("/fixtures/{fixture_id}/media")
    async def set_fixture_media(fixture_id: str, body: dict, user: dict = Depends(get_current_user)):
        """Set hero image + manual award overrides for a match."""
        fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not fx:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(fx["event_id"])
        # Event creator OR platform admin (scorer scores, doesn't edit media).
        if ev.get("created_by") != user.get("id") and user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the event creator can set the hero image")
        upd = {}
        if "hero_image_url" in body:
            upd["hero_image_url"] = (body.get("hero_image_url") or "").strip()
        if "awards" in body and isinstance(body["awards"], dict):
            upd["awards"] = body["awards"]
        if not upd:
            raise HTTPException(400, "hero_image_url or awards required")
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        return Fixture(**doc)

    @api.post("/fixtures/{fixture_id}/init-score")
    async def init_score(fixture_id: str, user: dict = Depends(get_current_user)):
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(doc["event_id"])
        if not await can_score_fixture(user, doc, ev):
            raise HTTPException(403, "You are not allowed to score this match")
        score = default_score(ev["sport"])
        await db.fixtures.update_one({"id": fixture_id}, {"$set": {"score": score, "status": "live"}})
        updated = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": updated})
        return {"ok": True, "score": score}

    # ---------- WebSocket ----------
    @app.websocket("/api/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws_manager.connect(ws)
        try:
            await ws.send_json({"type": "hello", "ts": datetime.now(timezone.utc).isoformat()})
            while True:
                msg = await ws.receive_text()
                if msg == "ping":
                    await ws.send_json({"type": "pong"})
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)
        except Exception:
            ws_manager.disconnect(ws)
