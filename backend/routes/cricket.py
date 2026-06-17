"""
Cricket scoring routes — CricHeroes-style toss/XI/ball-by-ball flow.

This module is wired via `register(api, db, ws_manager, require_admin, propagate_knockout_winner)`
called from server.py during startup. All cricket endpoints attach to the same `api` router so
existing `/api/fixtures/{id}/cricket/*` URLs are preserved.
"""
from typing import Optional
from fastapi import Depends, HTTPException


DISMISSAL_TYPES = {"bowled", "caught", "lbw", "runout", "stumped", "hitwicket", "retired"}
EXTRA_TYPES = {"wd", "nb", "b", "lb"}


def cricket_initial_state(overs_limit: int = 20) -> dict:
    return {
        "sport": "cricket",
        "match_state": "toss",
        "overs_limit": overs_limit,
        "toss": None,
        "playing_xi": {"team_a": [], "team_b": []},
        "current_innings": 0,
        "innings": [],
        "team_a": {"runs": 0, "wickets": 0, "overs": 0.0},
        "team_b": {"runs": 0, "wickets": 0, "overs": 0.0},
    }


def _empty_innings(batting_team_id: str, bowling_team_id: str) -> dict:
    return {
        "batting_team_id": batting_team_id,
        "bowling_team_id": bowling_team_id,
        "runs": 0,
        "wickets": 0,
        "legal_balls": 0,
        "extras": {"wd": 0, "nb": 0, "b": 0, "lb": 0},
        "batsmen": [],
        "bowlers": [],
        "striker_id": None,
        "non_striker_id": None,
        "current_bowler_id": None,
        "balls_log": [],
        "completed": False,
        "target": None,
    }


def _overs_str(legal_balls: int) -> float:
    return float(f"{legal_balls // 6}.{legal_balls % 6}")


def _sync_summary_fields(score: dict, fixture_team_a_id: str, fixture_team_b_id: str):
    summary = {fixture_team_a_id: {"runs": 0, "wickets": 0, "overs": 0.0},
               fixture_team_b_id: {"runs": 0, "wickets": 0, "overs": 0.0}}
    for inn in score.get("innings", []):
        t = inn["batting_team_id"]
        if t in summary:
            summary[t] = {
                "runs": inn["runs"],
                "wickets": inn["wickets"],
                "overs": _overs_str(inn["legal_balls"]),
            }
    score["team_a"] = summary[fixture_team_a_id]
    score["team_b"] = summary[fixture_team_b_id]


def _get_innings(score: dict) -> dict:
    idx = score.get("current_innings", 0)
    if idx >= len(score.get("innings", [])):
        raise HTTPException(400, "No active innings")
    return score["innings"][idx]


def _find_batsman(inn: dict, player_id: str) -> Optional[dict]:
    for b in inn["batsmen"]:
        if b["player_id"] == player_id:
            return b
    return None


def _find_bowler(inn: dict, player_id: str) -> Optional[dict]:
    for b in inn["bowlers"]:
        if b["player_id"] == player_id:
            return b
    return None


def _add_batsman(inn: dict, player_id: str, name: str) -> dict:
    rec = {"player_id": player_id, "name": name, "runs": 0, "balls": 0,
           "fours": 0, "sixes": 0, "out": False, "dismissal": None}
    inn["batsmen"].append(rec)
    return rec


def _add_bowler(inn: dict, player_id: str, name: str) -> dict:
    rec = {"player_id": player_id, "name": name, "balls": 0, "runs": 0,
           "wickets": 0, "maidens": 0}
    inn["bowlers"].append(rec)
    return rec


def register(api, db, ws_manager, require_admin, propagate_knockout_winner):
    """Attach all cricket endpoints to the provided router."""

    async def _get_fixture_or_404(fixture_id: str) -> dict:
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Fixture not found")
        return doc

    async def _save_score(fixture_id: str, score: dict, event_id: str):
        await db.fixtures.update_one({"id": fixture_id}, {"$set": {"score": score}})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": event_id, "fixture": doc})
        return doc

    @api.post("/fixtures/{fixture_id}/cricket/setup")
    async def cricket_setup(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        raw = body.get("overs_limit")
        if raw is None:
            raw = 20
        try:
            overs_limit = int(raw)
        except (TypeError, ValueError):
            raise HTTPException(400, "overs_limit must be an integer")
        if overs_limit < 1 or overs_limit > 90:
            raise HTTPException(400, "overs_limit must be between 1 and 90")
        fixture = await _get_fixture_or_404(fixture_id)
        ev = await db.events.find_one({"id": fixture["event_id"]}, {"_id": 0})
        if not ev or ev.get("sport") != "cricket":
            raise HTTPException(400, "Fixture is not a cricket match")
        if not fixture.get("team_a_id") or not fixture.get("team_b_id"):
            raise HTTPException(400, "Both teams must be assigned before setup")
        score = cricket_initial_state(overs_limit)
        score["_team_a_id"] = fixture["team_a_id"]
        score["_team_b_id"] = fixture["team_b_id"]
        await db.fixtures.update_one(
            {"id": fixture_id},
            {"$set": {"score": score, "status": "live"}},
        )
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/toss")
    async def cricket_toss(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        winner_team_id = body.get("winner_team_id")
        decision = body.get("decision")
        if decision not in ("bat", "bowl"):
            raise HTTPException(400, "decision must be bat or bowl")
        fixture = await _get_fixture_or_404(fixture_id)
        if winner_team_id not in (fixture.get("team_a_id"), fixture.get("team_b_id")):
            raise HTTPException(400, "winner_team_id must be one of the playing teams")
        score = fixture.get("score") or {}
        if not score or score.get("sport") != "cricket":
            raise HTTPException(400, "Run /cricket/setup first to initialize cricket state")
        if score.get("match_state") not in ("toss", None, ""):
            raise HTTPException(400, "Toss can only be set during the toss phase")
        score["toss"] = {"winner_team_id": winner_team_id, "decision": decision}
        score["match_state"] = "playing_xi"
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/playing-xi")
    async def cricket_playing_xi(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if not score or score.get("sport") != "cricket":
            raise HTTPException(400, "Call /cricket/setup first")
        if score.get("match_state") not in ("playing_xi", "toss"):
            raise HTTPException(400, "Playing XI can only be set before play begins")
        for side in ("team_a", "team_b"):
            if side in body and isinstance(body[side], list):
                score["playing_xi"][side] = [{
                    "player_id": p.get("player_id"),
                    "name": p.get("name") or "Player",
                    "captain": bool(p.get("captain")),
                    "wk": bool(p.get("wk")),
                } for p in body[side] if p.get("player_id")]
        a, b = score["playing_xi"]["team_a"], score["playing_xi"]["team_b"]
        if a and b:
            score["match_state"] = "ready"
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/start-innings")
    async def cricket_start_innings(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        state = score.get("match_state")
        if state not in ("ready", "playing_xi", "innings_break"):
            raise HTTPException(400, f"Cannot start innings from state '{state}'")
        if not score.get("toss"):
            raise HTTPException(400, "Toss must be completed first")
        striker_id = body.get("striker_id")
        non_striker_id = body.get("non_striker_id")
        bowler_id = body.get("bowler_id")
        if not (striker_id and non_striker_id and bowler_id):
            raise HTTPException(400, "striker_id, non_striker_id and bowler_id are required")
        if striker_id == non_striker_id:
            raise HTTPException(400, "Striker and non-striker must differ")

        a_id, b_id = fixture["team_a_id"], fixture["team_b_id"]
        if not score.get("innings"):
            toss_winner = score["toss"]["winner_team_id"]
            toss_decision = score["toss"]["decision"]
            batting = toss_winner if toss_decision == "bat" else (b_id if toss_winner == a_id else a_id)
            bowling = b_id if batting == a_id else a_id
        else:
            prev = score["innings"][-1]
            batting = prev["bowling_team_id"]
            bowling = prev["batting_team_id"]

        inn = _empty_innings(batting, bowling)
        if score.get("innings"):
            inn["target"] = score["innings"][-1]["runs"] + 1

        xi_batting = score["playing_xi"]["team_a"] if batting == a_id else score["playing_xi"]["team_b"]
        xi_bowling = score["playing_xi"]["team_b"] if batting == a_id else score["playing_xi"]["team_a"]
        batting_name_map = {p["player_id"]: p["name"] for p in xi_batting}
        bowling_name_map = {p["player_id"]: p["name"] for p in xi_bowling}

        if striker_id not in batting_name_map or non_striker_id not in batting_name_map:
            raise HTTPException(400, "Striker/non-striker must be in batting XI")
        if bowler_id not in bowling_name_map:
            raise HTTPException(400, "Bowler must be in bowling XI")

        _add_batsman(inn, striker_id, batting_name_map[striker_id])
        _add_batsman(inn, non_striker_id, batting_name_map[non_striker_id])
        _add_bowler(inn, bowler_id, bowling_name_map[bowler_id])
        inn["striker_id"] = striker_id
        inn["non_striker_id"] = non_striker_id
        inn["current_bowler_id"] = bowler_id

        score.setdefault("innings", []).append(inn)
        score["current_innings"] = len(score["innings"]) - 1
        score["match_state"] = "in_play"
        _sync_summary_fields(score, a_id, b_id)
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/ball")
    async def cricket_ball(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        if score.get("match_state") != "in_play":
            raise HTTPException(400, "No active innings")

        inn = _get_innings(score)
        if inn.get("completed"):
            raise HTTPException(400, "Innings is already completed")

        striker_id = inn["striker_id"]
        bowler_id = inn["current_bowler_id"]
        striker = _find_batsman(inn, striker_id)
        bowler = _find_bowler(inn, bowler_id)
        if not striker or not bowler:
            raise HTTPException(400, "Striker / bowler not set")

        runs = max(0, int(body.get("runs") or 0))
        extra = body.get("extra")
        if extra and extra not in EXTRA_TYPES:
            raise HTTPException(400, f"extra must be one of {sorted(EXTRA_TYPES)}")
        wicket = body.get("wicket")
        commentary = (body.get("commentary") or "").strip()

        legal = True
        bat_runs = 0
        team_runs = 0
        bowler_runs = 0
        extras_inc = {"wd": 0, "nb": 0, "b": 0, "lb": 0}
        swap_strike = False

        if extra == "wd":
            legal = False
            team_runs = 1 + runs
            bowler_runs = 1 + runs
            extras_inc["wd"] = 1 + runs
        elif extra == "nb":
            legal = False
            team_runs = 1 + runs
            bowler_runs = 1 + runs
            bat_runs = runs
            extras_inc["nb"] = 1
            if runs % 2 == 1:
                swap_strike = True
        elif extra == "b":
            legal = True
            team_runs = runs
            extras_inc["b"] = runs
            if runs % 2 == 1:
                swap_strike = True
        elif extra == "lb":
            legal = True
            team_runs = runs
            extras_inc["lb"] = runs
            if runs % 2 == 1:
                swap_strike = True
        else:
            legal = True
            team_runs = runs
            bat_runs = runs
            bowler_runs = runs
            if runs % 2 == 1:
                swap_strike = True

        if legal and extra not in ("b", "lb"):
            striker["balls"] += 1
        striker["runs"] += bat_runs
        if bat_runs == 4:
            striker["fours"] += 1
        elif bat_runs == 6:
            striker["sixes"] += 1

        if legal:
            bowler["balls"] += 1
        bowler["runs"] += bowler_runs

        inn["runs"] += team_runs
        for k, v in extras_inc.items():
            inn["extras"][k] = inn["extras"].get(k, 0) + v
        if legal:
            inn["legal_balls"] += 1

        out_player = None
        if wicket and wicket.get("type") in DISMISSAL_TYPES:
            wtype = wicket["type"]
            out_pid = wicket.get("batsman_id") or striker_id
            out_player = _find_batsman(inn, out_pid)
            if out_player and not out_player["out"]:
                out_player["out"] = True
                out_player["dismissal"] = {
                    "type": wtype,
                    "bowler_id": bowler_id if wtype in ("bowled", "caught", "lbw", "stumped", "hitwicket") else None,
                    "fielder_id": wicket.get("fielder_id"),
                }
                inn["wickets"] += 1
                if wtype != "runout":
                    bowler["wickets"] += 1
                if inn["striker_id"] == out_pid:
                    inn["striker_id"] = None
                elif inn["non_striker_id"] == out_pid:
                    inn["non_striker_id"] = None
                score["match_state"] = "wicket"

        over_num = (inn["legal_balls"] - 1) // 6 if legal else inn["legal_balls"] // 6
        ball_in_over = ((inn["legal_balls"] - 1) % 6) + 1 if legal else 0
        inn["balls_log"].append({
            "over": over_num,
            "ball": ball_in_over,
            "runs": bat_runs,
            "team_runs": team_runs,
            "extra": extra,
            "wicket": wicket if wicket else None,
            "striker_id": striker_id,
            "bowler_id": bowler_id,
            "commentary": commentary,
        })

        end_of_over = legal and inn["legal_balls"] % 6 == 0
        if end_of_over:
            over_balls = [b for b in inn["balls_log"] if b["over"] == over_num][-6:]
            bowler_runs_over = sum(
                b["team_runs"] if b["extra"] in ("wd", "nb") else b["runs"]
                for b in over_balls if b["bowler_id"] == bowler_id
            )
            if bowler_runs_over == 0:
                bowler["maidens"] += 1
            swap_strike = not swap_strike
            inn["current_bowler_id"] = None

        if swap_strike and inn["striker_id"] and inn["non_striker_id"]:
            inn["striker_id"], inn["non_striker_id"] = inn["non_striker_id"], inn["striker_id"]

        overs_limit = score.get("overs_limit", 20)
        target = inn.get("target")
        all_out = inn["wickets"] >= 10
        overs_done = inn["legal_balls"] >= overs_limit * 6
        chase_done = target and inn["runs"] >= target
        if all_out or overs_done or chase_done:
            inn["completed"] = True
            if score["current_innings"] == 0:
                score["match_state"] = "innings_break"
            else:
                score["match_state"] = "completed"
        elif score.get("match_state") not in ("wicket",):
            score["match_state"] = "in_play"

        _sync_summary_fields(score, fixture["team_a_id"], fixture["team_b_id"])
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"], "match_state": score["match_state"]}

    @api.post("/fixtures/{fixture_id}/cricket/new-batsman")
    async def cricket_new_batsman(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        player_id = body.get("player_id")
        if not player_id:
            raise HTTPException(400, "player_id required")
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        if score.get("match_state") not in ("wicket", "in_play"):
            raise HTTPException(400, "No active innings")
        inn = _get_innings(score)
        if player_id in (inn["striker_id"], inn["non_striker_id"]):
            raise HTTPException(400, "Player is already on the crease")
        existing = _find_batsman(inn, player_id)
        if existing and existing["out"]:
            raise HTTPException(400, "Player is already out")
        a_id = fixture["team_a_id"]
        xi = score["playing_xi"]["team_a"] if inn["batting_team_id"] == a_id else score["playing_xi"]["team_b"]
        name_map = {p["player_id"]: p["name"] for p in xi}
        if player_id not in name_map:
            raise HTTPException(400, "Player must be in batting XI")
        if not existing:
            _add_batsman(inn, player_id, name_map[player_id])
        if not inn["striker_id"]:
            inn["striker_id"] = player_id
        else:
            inn["non_striker_id"] = player_id
        score["match_state"] = "in_play"
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/new-bowler")
    async def cricket_new_bowler(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        player_id = body.get("player_id")
        if not player_id:
            raise HTTPException(400, "player_id required")
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        if score.get("match_state") != "in_play":
            raise HTTPException(400, "No active innings")
        inn = _get_innings(score)
        a_id = fixture["team_a_id"]
        xi = score["playing_xi"]["team_b"] if inn["batting_team_id"] == a_id else score["playing_xi"]["team_a"]
        name_map = {p["player_id"]: p["name"] for p in xi}
        if player_id not in name_map:
            raise HTTPException(400, "Bowler must be in bowling XI")
        if not _find_bowler(inn, player_id):
            _add_bowler(inn, player_id, name_map[player_id])
        inn["current_bowler_id"] = player_id
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/end-innings")
    async def cricket_end_innings(fixture_id: str, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        inn = _get_innings(score)
        inn["completed"] = True
        if score["current_innings"] == 0:
            score["match_state"] = "innings_break"
        else:
            score["match_state"] = "completed"
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}

    @api.post("/fixtures/{fixture_id}/cricket/end-match")
    async def cricket_end_match(fixture_id: str, body: dict, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        winner_id = (body.get("winner_team_id") or "").strip() or None
        if winner_id and winner_id not in (fixture.get("team_a_id"), fixture.get("team_b_id")):
            raise HTTPException(400, "winner_team_id must be one of the playing teams or empty for tie")
        score["match_state"] = "completed"
        upd = {"score": score, "status": "completed"}
        if winner_id:
            upd["winner_id"] = winner_id
        await db.fixtures.update_one({"id": fixture_id}, {"$set": upd})
        doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        if winner_id and doc.get("bracket_position"):
            await propagate_knockout_winner(doc)
            doc = await db.fixtures.find_one({"id": fixture_id}, {"_id": 0})
        await ws_manager.broadcast({"type": "fixture_update", "event_id": doc["event_id"], "fixture": doc})
        return {"ok": True, "fixture": doc}

    @api.post("/fixtures/{fixture_id}/cricket/undo")
    async def cricket_undo(fixture_id: str, _: dict = Depends(require_admin)):
        fixture = await _get_fixture_or_404(fixture_id)
        score = fixture.get("score") or {}
        if score.get("sport") != "cricket":
            raise HTTPException(400, "Not a cricket fixture")
        inn = _get_innings(score)
        if not inn["balls_log"]:
            raise HTTPException(400, "Nothing to undo")
        inn["balls_log"].pop()
        inn["runs"] = 0
        inn["wickets"] = 0
        inn["legal_balls"] = 0
        inn["extras"] = {"wd": 0, "nb": 0, "b": 0, "lb": 0}
        for b in inn["batsmen"]:
            b["runs"] = 0
            b["balls"] = 0
            b["fours"] = 0
            b["sixes"] = 0
            b["out"] = False
            b["dismissal"] = None
        for bw in inn["bowlers"]:
            bw["balls"] = 0
            bw["runs"] = 0
            bw["wickets"] = 0
            bw["maidens"] = 0
        for b in inn["balls_log"]:
            striker = _find_batsman(inn, b["striker_id"])
            bowler = _find_bowler(inn, b["bowler_id"])
            extra = b.get("extra")
            runs = b.get("runs", 0)
            team_runs = b.get("team_runs", 0)
            if extra == "wd":
                inn["extras"]["wd"] += team_runs
                if bowler:
                    bowler["runs"] += team_runs
            elif extra == "nb":
                inn["extras"]["nb"] += 1
                if striker:
                    striker["runs"] += runs
                    if runs == 4:
                        striker["fours"] += 1
                    if runs == 6:
                        striker["sixes"] += 1
                if bowler:
                    bowler["runs"] += team_runs
            elif extra == "b":
                inn["extras"]["b"] += team_runs
                if striker:
                    striker["balls"] += 1
                if bowler:
                    bowler["balls"] += 1
                inn["legal_balls"] += 1
            elif extra == "lb":
                inn["extras"]["lb"] += team_runs
                if striker:
                    striker["balls"] += 1
                if bowler:
                    bowler["balls"] += 1
                inn["legal_balls"] += 1
            else:
                if striker:
                    striker["balls"] += 1
                    striker["runs"] += runs
                    if runs == 4:
                        striker["fours"] += 1
                    if runs == 6:
                        striker["sixes"] += 1
                if bowler:
                    bowler["balls"] += 1
                    bowler["runs"] += runs
                inn["legal_balls"] += 1
            inn["runs"] += team_runs
            w = b.get("wicket")
            if w and w.get("type") in DISMISSAL_TYPES:
                inn["wickets"] += 1
                wb = _find_batsman(inn, w.get("batsman_id") or b["striker_id"])
                if wb:
                    wb["out"] = True
                    wb["dismissal"] = {"type": w["type"]}
                if w["type"] != "runout" and bowler:
                    bowler["wickets"] += 1
        inn["completed"] = False
        score["match_state"] = "in_play"
        _sync_summary_fields(score, fixture["team_a_id"], fixture["team_b_id"])
        doc = await _save_score(fixture_id, score, fixture["event_id"])
        return {"ok": True, "score": doc["score"]}
