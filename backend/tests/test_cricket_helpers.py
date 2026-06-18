"""Unit tests for the pure ball-processing helpers extracted from cricket_ball().

These are pure-function tests — no HTTP, no DB — meant to lock in the scoring math
so future refactors of `cricket_ball()` can rely on them as a safety net.
"""
import pytest
from routes.cricket import (
    _compute_ball_delta,
    _apply_ball_to_players,
    _apply_wicket,
    _is_innings_complete,
    _resolve_innings_teams,
)


# ----- _compute_ball_delta -----
class TestComputeBallDelta:
    def test_legal_dot_ball(self):
        d = _compute_ball_delta(None, 0)
        assert d["legal"] is True
        assert d["bat_runs"] == 0
        assert d["team_runs"] == 0
        assert d["bowler_runs"] == 0
        assert d["swap_strike"] is False

    def test_legal_single(self):
        d = _compute_ball_delta(None, 1)
        assert d["legal"] is True
        assert d["bat_runs"] == 1
        assert d["team_runs"] == 1
        assert d["bowler_runs"] == 1
        assert d["swap_strike"] is True

    def test_legal_boundary(self):
        d = _compute_ball_delta(None, 4)
        assert d["bat_runs"] == 4 and d["team_runs"] == 4 and d["swap_strike"] is False

    def test_wide_zero_runs(self):
        d = _compute_ball_delta("wd", 0)
        assert d["legal"] is False
        assert d["team_runs"] == 1 and d["bowler_runs"] == 1
        assert d["extras_inc"]["wd"] == 1
        assert d["bat_runs"] == 0 and d["swap_strike"] is False

    def test_wide_with_extra_runs(self):
        # Batsmen ran 3 byes on a wide → all 4 (1 wide + 3) credited to wides
        d = _compute_ball_delta("wd", 3)
        assert d["legal"] is False
        assert d["team_runs"] == 4
        assert d["extras_inc"]["wd"] == 4
        assert d["bat_runs"] == 0

    def test_no_ball_with_runs_off_bat(self):
        d = _compute_ball_delta("nb", 4)
        assert d["legal"] is False
        assert d["bat_runs"] == 4
        assert d["team_runs"] == 5  # 1 nb + 4 off bat
        assert d["bowler_runs"] == 5
        assert d["extras_inc"]["nb"] == 1
        assert d["swap_strike"] is False  # 4 = even

    def test_no_ball_single(self):
        d = _compute_ball_delta("nb", 1)
        assert d["legal"] is False and d["swap_strike"] is True

    def test_bye(self):
        d = _compute_ball_delta("b", 2)
        assert d["legal"] is True
        assert d["bat_runs"] == 0
        assert d["team_runs"] == 2
        assert d["bowler_runs"] == 0
        assert d["extras_inc"]["b"] == 2

    def test_legbye(self):
        d = _compute_ball_delta("lb", 1)
        assert d["legal"] is True
        assert d["bat_runs"] == 0
        assert d["extras_inc"]["lb"] == 1
        assert d["swap_strike"] is True


# ----- _apply_ball_to_players -----
def _new_innings():
    return {
        "runs": 0, "wickets": 0, "legal_balls": 0,
        "extras": {"wd": 0, "nb": 0, "b": 0, "lb": 0},
        "balls_log": [],
    }


def _new_player(role="striker"):
    if role == "striker":
        return {"player_id": "p1", "name": "x", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False}
    return {"player_id": "p2", "name": "y", "balls": 0, "runs": 0, "wickets": 0, "maidens": 0}


def test_apply_legal_single_to_players():
    inn, s, b = _new_innings(), _new_player("striker"), _new_player("bowler")
    _apply_ball_to_players(inn, s, b, _compute_ball_delta(None, 1), None)
    assert s["runs"] == 1 and s["balls"] == 1
    assert b["runs"] == 1 and b["balls"] == 1
    assert inn["runs"] == 1 and inn["legal_balls"] == 1


def test_apply_boundary_increments_fours():
    inn, s, b = _new_innings(), _new_player("striker"), _new_player("bowler")
    _apply_ball_to_players(inn, s, b, _compute_ball_delta(None, 4), None)
    assert s["fours"] == 1 and s["sixes"] == 0


def test_apply_six_increments_sixes():
    inn, s, b = _new_innings(), _new_player("striker"), _new_player("bowler")
    _apply_ball_to_players(inn, s, b, _compute_ball_delta(None, 6), None)
    assert s["sixes"] == 1


def test_apply_wide_does_not_count_balls():
    inn, s, b = _new_innings(), _new_player("striker"), _new_player("bowler")
    _apply_ball_to_players(inn, s, b, _compute_ball_delta("wd", 0), "wd")
    assert s["balls"] == 0 and b["balls"] == 0
    assert inn["legal_balls"] == 0
    assert inn["extras"]["wd"] == 1


def test_apply_bye_does_not_credit_striker_balls_faced():
    # Bye is a legal ball but striker didn't face it for the runs
    inn, s, b = _new_innings(), _new_player("striker"), _new_player("bowler")
    _apply_ball_to_players(inn, s, b, _compute_ball_delta("b", 1), "b")
    assert s["balls"] == 0  # striker doesn't get the ball-face on byes
    assert inn["legal_balls"] == 1  # but it counts as a legal delivery
    assert inn["extras"]["b"] == 1


# ----- _is_innings_complete -----
def test_innings_complete_all_out():
    inn = {"wickets": 10, "legal_balls": 0, "runs": 0, "target": None}
    assert _is_innings_complete(inn, overs_limit=20) is True


def test_innings_complete_overs_done():
    inn = {"wickets": 4, "legal_balls": 120, "runs": 150, "target": None}
    assert _is_innings_complete(inn, overs_limit=20) is True


def test_innings_complete_chase_done():
    inn = {"wickets": 4, "legal_balls": 50, "runs": 200, "target": 200}
    assert _is_innings_complete(inn, overs_limit=20) is True


def test_innings_not_complete():
    inn = {"wickets": 4, "legal_balls": 50, "runs": 80, "target": 200}
    assert _is_innings_complete(inn, overs_limit=20) is False


# ----- _apply_wicket -----
def test_wicket_caught_credits_bowler():
    inn = {
        "batsmen": [
            {"player_id": "s", "name": "S", "runs": 5, "balls": 6, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
            {"player_id": "n", "name": "N", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
        ],
        "bowlers": [{"player_id": "b", "name": "B", "balls": 0, "runs": 0, "wickets": 0, "maidens": 0}],
        "wickets": 0, "striker_id": "s", "non_striker_id": "n",
    }
    score = {"match_state": "in_play"}
    out = _apply_wicket(inn, score, "s", "b", {"type": "caught"}, free_hit_active=False)
    assert out["type"] == "caught"
    assert inn["wickets"] == 1
    assert inn["batsmen"][0]["out"] is True
    assert inn["bowlers"][0]["wickets"] == 1
    assert score["match_state"] == "wicket"


def test_wicket_runout_does_not_credit_bowler():
    inn = {
        "batsmen": [
            {"player_id": "s", "name": "S", "runs": 5, "balls": 6, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
            {"player_id": "n", "name": "N", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
        ],
        "bowlers": [{"player_id": "b", "name": "B", "balls": 0, "runs": 0, "wickets": 0, "maidens": 0}],
        "wickets": 0, "striker_id": "s", "non_striker_id": "n",
    }
    score = {"match_state": "in_play"}
    _apply_wicket(inn, score, "s", "b", {"type": "runout"}, free_hit_active=False)
    assert inn["wickets"] == 1
    assert inn["bowlers"][0]["wickets"] == 0  # run-out doesn't credit the bowler


def test_wicket_ignored_on_free_hit_except_runout():
    inn = {
        "batsmen": [
            {"player_id": "s", "name": "S", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
            {"player_id": "n", "name": "N", "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "out": False, "dismissal": None},
        ],
        "bowlers": [{"player_id": "b", "name": "B", "balls": 0, "runs": 0, "wickets": 0, "maidens": 0}],
        "wickets": 0, "striker_id": "s", "non_striker_id": "n",
    }
    score = {"match_state": "in_play"}
    out = _apply_wicket(inn, score, "s", "b", {"type": "bowled"}, free_hit_active=True)
    assert out["ignored_free_hit"] is True
    assert inn["wickets"] == 0
    assert inn["batsmen"][0]["out"] is False


# ----- _resolve_innings_teams -----
def test_resolve_teams_toss_chose_bat_winner_is_a():
    score = {"innings": [], "toss": {"winner_team_id": "A", "decision": "bat"}}
    batting, bowling = _resolve_innings_teams(score, "A", "B")
    assert batting == "A" and bowling == "B"


def test_resolve_teams_toss_chose_bowl_winner_is_a():
    score = {"innings": [], "toss": {"winner_team_id": "A", "decision": "bowl"}}
    batting, bowling = _resolve_innings_teams(score, "A", "B")
    assert batting == "B" and bowling == "A"


def test_resolve_teams_second_innings_swaps():
    score = {
        "innings": [{"batting_team_id": "A", "bowling_team_id": "B"}],
        "toss": {"winner_team_id": "A", "decision": "bat"},
    }
    batting, bowling = _resolve_innings_teams(score, "A", "B")
    assert batting == "B" and bowling == "A"
