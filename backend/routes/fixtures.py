"""Fixture generation (round-robin & knockout), live score updates, public scorecard, WebSocket.

Wired via `register(api, app, db, ws_manager, deps)` from server.py. The websocket is registered
on `app` directly (not on the `/api` APIRouter) so the path remains `/api/ws`.
"""
import uuid
import random
from datetime import datetime, timezone
from typing import List, Optional
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

    def _compute_totals(score: dict) -> tuple[float, float]:
        """Return (team_a_total, team_b_total) from the score dict. Handles the
        common shapes we support: `{team_a:{total},team_b:{total}}` and the
        newer `{sides:{a:{total},b:{total}}}` shape."""
        try:
            a = (score.get("team_a") or (score.get("sides") or {}).get("a") or score.get("a") or {}) or {}
            b = (score.get("team_b") or (score.get("sides") or {}).get("b") or score.get("b") or {}) or {}
            fa = float(a.get("total") or a.get("score") or a.get("runs") or a.get("goals") or a.get("points") or 0)
            fb = float(b.get("total") or b.get("score") or b.get("runs") or b.get("goals") or b.get("points") or 0)
            return fa, fb
        except Exception:
            return 0.0, 0.0

    def _compute_winner_id(fixture: dict, score: dict) -> Optional[str]:
        """Higher-total wins. On ties → None (draw)."""
        fa, fb = _compute_totals(score or {})
        if fa == fb:
            return None
        return fixture.get("team_a_id") if fa > fb else fixture.get("team_b_id")

    def _compute_awards(sport: str, score: dict, fixture: Optional[dict] = None) -> dict:
        """Best-effort auto-awards from the final score dict.

        Rules (Feb 24, 2026 update):
        * **Cricket** — Best Batter = highest individual runs across both innings.
          Best Bowler = most wickets; tie-breaker = best economy (runs conceded ÷ overs).
          Player of the Match = top run-scorer from the **winning** team; falls back to
          the best bowler if they took 3+ wickets.
        * **Other sports** — Top Scorer picked from the **winning** team only.
          Falls back to the overall top scorer if the winning team has no scorer list.
        """
        awards: dict = {}
        try:
            fa, fb = _compute_totals(score or {})
            winner_side = "a" if fa > fb else ("b" if fb > fa else None)
            a_side = score.get("team_a") or (score.get("sides") or {}).get("a") or score.get("a") or {}
            b_side = score.get("team_b") or (score.get("sides") or {}).get("b") or score.get("b") or {}
            winning_side = a_side if winner_side == "a" else (b_side if winner_side == "b" else {})

            if sport == "cricket":
                batters, bowlers = [], []
                for s in (a_side, b_side):
                    batters += (s.get("batters") or [])
                    bowlers += (s.get("bowlers") or [])
                if batters:
                    top_bat = max(batters, key=lambda p: (p.get("runs") or 0))
                    if (top_bat.get("runs") or 0) > 0:
                        awards["best_batter"] = {
                            "player_id": top_bat.get("player_id") or top_bat.get("id"),
                            "name": top_bat.get("name") or "",
                            "runs": top_bat.get("runs"),
                        }
                if bowlers:
                    # Sort by wickets desc, then economy asc (lower = better).
                    def _bowler_key(p):
                        wickets = p.get("wickets") or 0
                        overs = float(p.get("overs") or 0) or 1
                        runs = p.get("runs_conceded") or p.get("runs") or 0
                        economy = float(runs) / overs
                        return (-wickets, economy)
                    top_bowl = min(bowlers, key=_bowler_key)
                    if (top_bowl.get("wickets") or 0) > 0:
                        awards["best_bowler"] = {
                            "player_id": top_bowl.get("player_id") or top_bowl.get("id"),
                            "name": top_bowl.get("name") or "",
                            "wickets": top_bowl.get("wickets"),
                        }
                # MoM: winner's top run-scorer first; fall back to best bowler with 3+ wickets.
                winning_batters = winning_side.get("batters") or []
                if winning_batters:
                    top_win_bat = max(winning_batters, key=lambda p: (p.get("runs") or 0))
                    if (top_win_bat.get("runs") or 0) > 0:
                        awards["mom"] = {
                            "player_id": top_win_bat.get("player_id") or top_win_bat.get("id"),
                            "name": top_win_bat.get("name") or "",
                            "runs": top_win_bat.get("runs"),
                        }
                if not awards.get("mom") and awards.get("best_bowler") and (awards["best_bowler"].get("wickets") or 0) >= 3:
                    awards["mom"] = awards["best_bowler"]
                if not awards.get("mom") and awards.get("best_batter"):
                    awards["mom"] = awards["best_batter"]
            else:
                # Prefer the winning team's top scorer; fall back to overall.
                winners_scorers = winning_side.get("scorers") or []
                pool = winners_scorers or ((a_side.get("scorers") or []) + (b_side.get("scorers") or []))
                if pool:
                    top = max(pool, key=lambda p: (p.get("points") or p.get("goals") or p.get("score") or 0))
                    metric = top.get("points") or top.get("goals") or top.get("score") or 0
                    if metric:
                        awards["top_scorer"] = {
                            "player_id": top.get("player_id") or top.get("id"),
                            "name": top.get("name") or "",
                            "score": metric,
                        }
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
        # A completed match is locked. Only the event creator or platform admin
        # can reopen it (via POST /fixtures/{id}/reopen) — the scorer can't
        # accidentally clobber the final score.
        if existing.get("status") == "completed":
            raise HTTPException(
                409,
                "This match is marked completed. Ask the event organiser to "
                "reopen it before editing the score.",
            )
        upd = {"score": body.score}
        if body.status:
            upd["status"] = body.status
        if body.winner_id:
            upd["winner_id"] = body.winner_id
        # On transition → completed: auto-fill winner + awards if not passed.
        if body.status == "completed":
            if not body.winner_id and not existing.get("winner_id"):
                auto_winner = _compute_winner_id(existing, body.score or {})
                if auto_winner:
                    upd["winner_id"] = auto_winner
            if not existing.get("awards"):
                awards = _compute_awards(ev.get("sport"), body.score or {}, existing)
                if awards:
                    upd["awards"] = awards
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        if (upd.get("winner_id") or body.winner_id) and doc.get("bracket_position"):
            await propagate_knockout_winner(doc)
            doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
        return Fixture(**doc)

    @api.patch("/fixtures/{fixture_id}/media")
    async def set_fixture_media(fixture_id: str, body: dict, user: dict = Depends(get_current_user)):
        """Set hero image + manual award overrides for a match.

        Only usable while the fixture is NOT completed — once completed, awards
        are locked and the organiser must reopen the fixture first. Event
        creator OR platform admin only.
        """
        fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not fx:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(fx["event_id"])
        if ev.get("created_by") != user.get("id") and user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the event creator can set the hero image")
        if fx.get("status") == "completed" and "awards" in body:
            raise HTTPException(
                409,
                "Awards are locked on completed matches. Reopen the match "
                "to edit awards — the hero image is still editable anytime.",
            )
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

    @api.post("/fixtures/{fixture_id}/reopen", response_model=Fixture)
    async def reopen_fixture(fixture_id: str, user: dict = Depends(get_current_user)):
        """Escape hatch: creator/admin can unlock a completed match to fix the
        score, winner, or awards. Sets status back to `live` (score preserved
        so the scorer picks up where they left off). Clears winner_id +
        auto-computed awards so they're recomputed on the next completion."""
        fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not fx:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(fx["event_id"])
        if ev.get("created_by") != user.get("id") and user.get("role") not in ("platform_admin", "admin"):
            raise HTTPException(403, "Only the event organiser can reopen a match")
        if fx.get("status") != "completed":
            raise HTTPException(400, "Match is not marked completed")
        await db.fixtures.update_one(
            {"id": fixture_id},
            {"$set": {"status": "live"}, "$unset": {"winner_id": "", "awards": ""}},
        )
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
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
