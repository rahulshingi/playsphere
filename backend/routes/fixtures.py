"""Fixture generation (round-robin & knockout), live score updates, public scorecard, WebSocket.

Wired via `register(api, app, db, ws_manager, deps)` from server.py. The websocket is registered
on `app` directly (not on the `/api` APIRouter) so the path remains `/api/ws`.
"""
import uuid
import math
import random
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect, Query


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


def _new_fixture(event_id: str, rnd: int, match_num: int, team_a_id, team_b_id,
                 bracket_position: Optional[str] = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "event_id": event_id,
        "round": rnd,
        "match_number": match_num,
        "team_a_id": team_a_id,
        "team_b_id": team_b_id,
        "scheduled_at": None,
        "venue": "",
        "status": "scheduled",
        "score": {},
        "winner_id": None,
        "bracket_position": bracket_position,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def generate_swiss(team_ids: List[str], event_id: str, rounds: int = 0) -> List[dict]:
    """Swiss-system fixture generation.

    Only round 1 is materialised with concrete pairings — seeded top-half vs
    bottom-half. Later rounds are created as empty placeholders and are paired
    dynamically after each round completes via
    `POST /events/{event_id}/swiss/pair-next-round`.

    Default rounds = ceil(log2(N)) — the standard Swiss recommendation. Caller
    can override via the query param on `/generate-fixtures?rounds=...`.
    """
    teams = list(team_ids)
    if len(teams) < 2:
        return []
    if rounds <= 0:
        rounds = max(1, math.ceil(math.log2(len(teams))))
    # Round 1: top-half vs bottom-half based on the incoming order (which the
    # caller can pre-seed). If odd, the last team gets a bye (team_b_id=None).
    n = len(teams)
    half = n // 2
    top = teams[:half]
    bot = teams[half:half * 2]
    bye = teams[-1] if n % 2 == 1 else None
    fixtures: List[dict] = []
    match_num = 1
    for a, b in zip(top, bot):
        fixtures.append(_new_fixture(event_id, 1, match_num, a, b, f"SW-R1-M{match_num}"))
        match_num += 1
    if bye is not None:
        # Bye: team_a plays "null" — auto-win awarded when standings run.
        fixtures.append(_new_fixture(event_id, 1, match_num, bye, None, f"SW-R1-M{match_num}"))
        match_num += 1
    # Placeholder empty fixtures for later rounds — filled by /swiss/pair-next-round.
    per_round_slots = math.ceil(n / 2)
    for rnd in range(2, rounds + 1):
        for _ in range(per_round_slots):
            fixtures.append(_new_fixture(event_id, rnd, match_num, None, None, f"SW-R{rnd}-M{match_num}"))
            match_num += 1
    return fixtures


def generate_double_elimination(team_ids: List[str], event_id: str) -> List[dict]:
    """Double-elimination bracket generator.

    Produces: Winners Bracket (WB) — a standard single-elim tree; Losers
    Bracket (LB) — every WB loser drops into the LB; Grand Final (GF) — LB
    winner vs WB winner (single match — reset match omitted for simplicity).

    Bracket positions:
      WB-R{n}-M{n} — winners bracket
      LB-R{n}-M{n} — losers bracket
      GF-M1        — grand final
    """
    teams = list(team_ids)
    random.shuffle(teams)
    if len(teams) < 2:
        return []
    # Pad to next power of 2
    n = 1
    while n < len(teams):
        n *= 2
    while len(teams) < n:
        teams.append(None)

    fixtures: List[dict] = []
    match_num = 1
    # ---- Winners Bracket ----
    # Round 1 with concrete pairings
    wb_current = []
    for i in range(0, n, 2):
        f = _new_fixture(event_id, 1, match_num, teams[i], teams[i + 1], f"WB-R1-M{match_num}")
        fixtures.append(f)
        wb_current.append(f["id"])
        match_num += 1
    wb_rounds = int(math.log2(n))
    for rnd in range(2, wb_rounds + 1):
        new_current = []
        for _ in range(len(wb_current) // 2):
            f = _new_fixture(event_id, rnd, match_num, None, None, f"WB-R{rnd}-M{match_num}")
            fixtures.append(f)
            new_current.append(f["id"])
            match_num += 1
        wb_current = new_current
    # ---- Losers Bracket ----
    # Number of LB rounds = 2 * wb_rounds - 1. Each pair of consecutive rounds
    # halves the LB size; alternating rounds absorb new drops from the WB.
    lb_rounds = 2 * wb_rounds - 1
    lb_matches = n // 4  # first LB round pairs the losers of WB-R1
    lb_round_num = 1
    while lb_matches >= 1 and lb_round_num <= lb_rounds:
        for _ in range(lb_matches):
            f = _new_fixture(event_id, wb_rounds + lb_round_num, match_num, None, None,
                             f"LB-R{lb_round_num}-M{match_num}")
            fixtures.append(f)
            match_num += 1
        lb_round_num += 1
        # Alternate: consolidation round (same size), then halving.
        if lb_round_num % 2 == 0:
            # Consolidation round keeps the same match count (WB loser joins in).
            pass
        else:
            lb_matches = max(1, lb_matches // 2) if lb_matches > 1 else 0
        if lb_matches == 0:
            break
    # ---- Grand Final ----
    fixtures.append(_new_fixture(event_id, wb_rounds + lb_rounds + 1, match_num, None, None, "GF-M1"))
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
    async def generate_fixtures_endpoint(
        event_id: str,
        user: dict = Depends(get_current_user),
        rounds: int = Query(0, ge=0, le=32),
    ):
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
        fmt = ev["format"]
        if fmt == "knockout":
            fixtures = generate_knockout(team_ids, event_id)
        elif fmt == "swiss":
            fixtures = generate_swiss(team_ids, event_id, rounds=rounds or 0)
        elif fmt == "double_elimination":
            fixtures = generate_double_elimination(team_ids, event_id)
        else:
            fixtures = generate_round_robin(team_ids, event_id)
        if fixtures:
            await db.fixtures.insert_many(fixtures)
        return {"ok": True, "count": len(fixtures), "format": fmt}

    @api.post("/events/{event_id}/swiss/pair-next-round")
    async def swiss_pair_next_round(event_id: str, user: dict = Depends(get_current_user)):
        """Pair the next unpaired Swiss round based on current standings.

        Standings = wins (2 pts each) + draws (1 pt) + byes (2 pts). Teams are
        ranked by points desc, then id (stable). Pair adjacent ranked teams
        while avoiding repeat opponents when possible. Empty slots in the next
        pending round are filled in-place.
        """
        ev = await get_event_or_404(event_id)
        if not await can_manage_event(user, ev):
            raise HTTPException(403, "Only the event organiser can pair rounds")
        if ev.get("format") != "swiss":
            raise HTTPException(400, "Event is not a Swiss-format tournament")
        all_fx = await db.fixtures.find({"event_id": event_id}, {"_id": 0}).sort(
            [("round", 1), ("match_number", 1)]
        ).to_list(2000)
        if not all_fx:
            raise HTTPException(400, "No fixtures generated yet")
        # Find the earliest round that still has empty slots (team_a/team_b None).
        target_round = None
        for f in all_fx:
            if f["team_a_id"] is None and f["team_b_id"] is None:
                target_round = f["round"]
                break
        if target_round is None:
            return {"ok": True, "paired": 0, "message": "All rounds already paired"}
        # Ensure previous rounds are completed
        prev_incomplete = [
            f for f in all_fx if f["round"] < target_round and f.get("status") != "completed"
            and (f["team_a_id"] is not None or f["team_b_id"] is not None)
        ]
        if prev_incomplete:
            raise HTTPException(400, f"Complete round {target_round - 1} before pairing round {target_round}")
        # Compute standings from completed fixtures
        team_ids: List[str] = []
        for f in all_fx:
            for tid in (f.get("team_a_id"), f.get("team_b_id")):
                if tid and tid not in team_ids:
                    team_ids.append(tid)
        points = {tid: 0 for tid in team_ids}
        opponents: dict = {tid: set() for tid in team_ids}
        for f in all_fx:
            if f.get("round") >= target_round:
                continue
            a, b = f.get("team_a_id"), f.get("team_b_id")
            if a and b is None:
                points[a] = points.get(a, 0) + 2  # bye
            elif f.get("status") == "completed":
                w = f.get("winner_id")
                if w in (a, b):
                    points[w] = points.get(w, 0) + 2
                else:  # draw
                    if a:
                        points[a] = points.get(a, 0) + 1
                    if b:
                        points[b] = points.get(b, 0) + 1
                if a and b:
                    opponents[a].add(b)
                    opponents[b].add(a)
        # Rank teams
        ranked = sorted(team_ids, key=lambda t: (-points[t], t))
        # Pair adjacent ranked teams, avoiding rematches greedily.
        pairs: List[tuple] = []
        used: set = set()
        for i, t in enumerate(ranked):
            if t in used:
                continue
            paired = False
            for j in range(i + 1, len(ranked)):
                candidate = ranked[j]
                if candidate in used:
                    continue
                if candidate in opponents[t]:
                    continue
                pairs.append((t, candidate))
                used.add(t)
                used.add(candidate)
                paired = True
                break
            if not paired and t not in used:
                # forced rematch or bye
                for j in range(i + 1, len(ranked)):
                    candidate = ranked[j]
                    if candidate not in used:
                        pairs.append((t, candidate))
                        used.add(t)
                        used.add(candidate)
                        paired = True
                        break
                if not paired:
                    pairs.append((t, None))  # bye
                    used.add(t)
        # Persist pairings into the empty slots of target_round
        empty_slots = [f for f in all_fx if f["round"] == target_round and f["team_a_id"] is None]
        for slot, pair in zip(empty_slots, pairs):
            a, b = pair
            await db.fixtures.update_one({"id": slot["id"]}, {"$set": {"team_a_id": a, "team_b_id": b}})
        return {"ok": True, "paired": len(pairs), "round": target_round}


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
        common shapes we support: `{team_a:{total},team_b:{total}}`, the newer
        `{sides:{a:{total},b:{total}}}` shape, AND racket-sport `sets` arrays."""
        try:
            a = (score.get("team_a") or (score.get("sides") or {}).get("a") or score.get("a") or {}) or {}
            b = (score.get("team_b") or (score.get("sides") or {}).get("b") or score.get("b") or {}) or {}

            def _score_of(side: dict) -> float:
                for k in ("total", "score", "runs", "goals", "points", "frames_won"):
                    v = side.get(k)
                    if v is not None:
                        return float(v)
                sets_arr = side.get("sets")
                if isinstance(sets_arr, list) and sets_arr:
                    # Racket sports: total sets won by this side is the "score".
                    # We can only tell that by comparing head-to-head — done below.
                    return float(sum(x or 0 for x in sets_arr))
                return 0.0

            # For racket sets, a fairer "total" is the number of sets won
            # (comparing set-by-set) rather than the sum of set points.
            a_sets = a.get("sets") if isinstance(a.get("sets"), list) else None
            b_sets = b.get("sets") if isinstance(b.get("sets"), list) else None
            if a_sets is not None and b_sets is not None:
                a_sets_won = sum(1 for i in range(min(len(a_sets), len(b_sets))) if (a_sets[i] or 0) > (b_sets[i] or 0))
                b_sets_won = sum(1 for i in range(min(len(a_sets), len(b_sets))) if (b_sets[i] or 0) > (a_sets[i] or 0))
                # Tie-break: fall through to raw point sum if the set counts are tied.
                if a_sets_won != b_sets_won:
                    return float(a_sets_won), float(b_sets_won)
            return _score_of(a), _score_of(b)
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
                # Fallback: no per-player stats (e.g. badminton `{sets: [...]}`)
                # → credit the winning team's captain / first-member as MoM.
                winner_id = upd.get("winner_id") or body.winner_id or existing.get("winner_id")
                if not awards and winner_id:
                    wteam = await db.teams.find_one({"id": winner_id}, {"_id": 0, "captain_player_id": 1, "members": 1})
                    if wteam:
                        rep = wteam.get("captain_player_id")
                        members = wteam.get("members") or []
                        if not rep and members:
                            rep = members[0]
                        if rep:
                            prof = await db.player_profiles.find_one({"id": rep}, {"_id": 0, "name": 1})
                            representative = {"player_id": rep, "name": (prof or {}).get("name") or ""}
                            awards = {"mom": representative}
                            # For individual sports also crown top_scorer with the same rep.
                            if (ev.get("sport") or "") in ("badminton", "tennis", "table_tennis", "squash", "chess", "quiz", "hackathon"):
                                awards["top_scorer"] = representative
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

    # ---------- Phase 3: Match metadata (venue, court, officials, toss) ----------
    _FIXTURE_META_ALLOWED = {"venue", "court_number", "scheduled_at"}

    def _sanitize_officials(raw) -> list:
        if not isinstance(raw, list):
            return []
        out = []
        for entry in raw[:12]:  # hard cap
            if not isinstance(entry, dict):
                continue
            role = (entry.get("role") or "").strip()
            name = (entry.get("name") or "").strip()
            if not name:
                continue
            out.append({"role": role or "official", "name": name})
        return out

    def _sanitize_toss(raw, team_a_id, team_b_id) -> Optional[dict]:
        if not isinstance(raw, dict):
            return None
        winner = raw.get("winner_team_id")
        if winner and winner not in (team_a_id, team_b_id):
            raise HTTPException(400, "toss.winner_team_id must be team_a or team_b")
        decision = (raw.get("decision") or "").strip().lower()
        allowed_decisions = {"", "bat", "field", "bowl", "serve", "receive", "choose_side"}
        if decision and decision not in allowed_decisions:
            raise HTTPException(400, f"Invalid toss decision. Allowed: {sorted(allowed_decisions - {''})}")
        note = (raw.get("note") or "").strip()
        return {"winner_team_id": winner or None, "decision": decision or None, "note": note or None}

    @api.patch("/fixtures/{fixture_id}/meta", response_model=Fixture)
    async def set_fixture_meta(fixture_id: str, body: dict, user: dict = Depends(get_current_user)):
        """Set venue / court / scheduled_at / officials / toss on a fixture.

        Auth: event creator, platform admin, or company_admin scoped to the
        event's company. Editable at any status (including completed) so
        organisers can retroactively correct match-day metadata.
        """
        fx = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not fx:
            raise HTTPException(404, "Fixture not found")
        ev = await get_event_or_404(fx["event_id"])
        if not await can_manage_event(user, ev):
            raise HTTPException(403, "Only the event organiser can edit match metadata")
        body = body or {}
        upd: dict = {}
        for k in _FIXTURE_META_ALLOWED:
            if k in body:
                v = body[k]
                upd[k] = (v.strip() if isinstance(v, str) else v) or ""
        if "officials" in body:
            upd["officials"] = _sanitize_officials(body["officials"])
        if "toss" in body:
            upd["toss"] = _sanitize_toss(body["toss"], fx.get("team_a_id"), fx.get("team_b_id"))
        if not upd:
            raise HTTPException(400, "No valid fields provided")
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
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
