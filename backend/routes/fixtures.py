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
    """deps must expose: Fixture, ScoreUpdate, require_admin, default_score, propagate_knockout_winner."""
    Fixture = deps.Fixture
    ScoreUpdate = deps.ScoreUpdate
    require_admin = deps.require_admin
    default_score = deps.default_score
    propagate_knockout_winner = deps.propagate_knockout_winner

    @api.post("/events/{event_id}/generate-fixtures")
    async def generate_fixtures_endpoint(event_id: str, _: dict = Depends(require_admin)):
        ev = await db.events.find_one({"id": event_id}, {"_id": 0})
        if not ev:
            raise HTTPException(404, "Event not found")
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

    @api.patch("/fixtures/{fixture_id}", response_model=Fixture)
    async def update_fixture_score(fixture_id: str, body: ScoreUpdate, _: dict = Depends(require_admin)):
        upd = {"score": body.score}
        if body.status:
            upd["status"] = body.status
        if body.winner_id:
            upd["winner_id"] = body.winner_id
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        if body.winner_id and doc.get("bracket_position"):
            await propagate_knockout_winner(doc)
            doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
        return Fixture(**doc)

    @api.post("/fixtures/{fixture_id}/init-score")
    async def init_score(fixture_id: str, _: dict = Depends(require_admin)):
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        ev = await db.events.find_one({"id": doc["event_id"]}, {"_id": 0})
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
