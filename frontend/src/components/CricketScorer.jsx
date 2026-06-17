import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { devError } from "@/lib/devLog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Crown, Award, Undo2, ChevronRight, X } from "lucide-react";

/**
 * CricHeroes-style cricket scorer.
 * Drives the fixture.score state machine: toss -> playing_xi -> ready -> in_play -> innings_break -> in_play -> completed
 */
export default function CricketScorer({ fixture, event, teamMap, onClose, onSaved }) {
  const [score, setScore] = useState(fixture.score || {});
  const [busy, setBusy] = useState(false);
  const [rosters, setRosters] = useState({ team_a: [], team_b: [] });

  const teamA = teamMap[fixture.team_a_id];
  const teamB = teamMap[fixture.team_b_id];

  // Load team rosters once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [ra, rb] = await Promise.all([
          api.get(`/events/${event.id}/teams/${fixture.team_a_id}/members`),
          api.get(`/events/${event.id}/teams/${fixture.team_b_id}/members`),
        ]);
        if (!cancelled) setRosters({ team_a: ra.data, team_b: rb.data });
      } catch (err) {
        devError("[CricketScorer] roster load failed:", err);
      }
    })();
    return () => { cancelled = true; };
  }, [event.id, fixture.team_a_id, fixture.team_b_id]);

  const callApi = async (path, body) => {
    setBusy(true);
    try {
      const r = await api.post(`/fixtures/${fixture.id}/cricket/${path}`, body || {});
      setScore(r.data.score || r.data.fixture?.score || {});
      onSaved && onSaved();
      return r.data;
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || "Failed";
      toast.error(msg);
      throw err;
    } finally {
      setBusy(false);
    }
  };

  const matchState = score?.match_state;
  const needsSetup = !score?.sport || score.sport !== "cricket";

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="cricket-scorer-modal" className="bg-[#0c0c0c] border border-white/10 max-w-4xl text-white max-h-[92vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl tracking-wider flex items-center gap-3">
            CRICKET SCORING
            <span className="text-xs font-mono uppercase text-neutral-500">/ Match #{fixture.match_number}</span>
          </DialogTitle>
          <DialogDescription className="sr-only">CricHeroes-style cricket scoring controls for this fixture.</DialogDescription>
          <div className="flex items-center gap-2 text-xs font-mono uppercase text-neutral-400">
            <TeamChip team={teamA} />
            <span className="text-neutral-600">vs</span>
            <TeamChip team={teamB} />
            <span className="ml-auto text-[#84CC16]">{matchState ? `STATE: ${matchState.toUpperCase()}` : "NOT STARTED"}</span>
          </div>
        </DialogHeader>

        {needsSetup && (
          <SetupPanel busy={busy} onSetup={(overs) => callApi("setup", { overs_limit: overs })} />
        )}

        {matchState === "toss" && (
          <TossPanel teamA={teamA} teamB={teamB} busy={busy}
            onSubmit={(winner_team_id, decision) => callApi("toss", { winner_team_id, decision })} />
        )}

        {matchState === "playing_xi" && (
          <XIPanel rosters={rosters} teamA={teamA} teamB={teamB} busy={busy}
            existing={score.playing_xi}
            onSubmit={(team_a, team_b) => callApi("playing-xi", { team_a, team_b })} />
        )}

        {matchState === "ready" && (
          <ReadyPanel score={score} fixture={fixture} teamA={teamA} teamB={teamB} busy={busy}
            onStart={(payload) => callApi("start-innings", payload)} />
        )}

        {(matchState === "in_play" || matchState === "wicket") && (
          <LivePanel score={score} fixture={fixture} teamMap={teamMap} busy={busy} callApi={callApi} />
        )}

        {matchState === "innings_break" && (
          <InningsBreakPanel score={score} fixture={fixture} teamA={teamA} teamB={teamB} busy={busy}
            onStart={(payload) => callApi("start-innings", payload)} />
        )}

        {matchState === "completed" && (
          <CompletedPanel score={score} fixture={fixture} teamA={teamA} teamB={teamB} busy={busy}
            onDeclare={(winner_team_id) => callApi("end-match", { winner_team_id })}
            onClose={onClose} />
        )}

        <div className="mt-4 flex justify-end">
          <Button variant="ghost" data-testid="cricket-close-btn" onClick={onClose} className="text-neutral-400">
            <X className="w-4 h-4 mr-2" /> Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function TeamChip({ team }) {
  if (!team) return <span>—</span>;
  return (
    <span className="flex items-center gap-2">
      <span className="w-2 h-2 rounded-full" style={{ background: team.color || "#666" }} />
      <span>{team.short_name || team.name}</span>
    </span>
  );
}

/* ---------------- Setup ---------------- */
function SetupPanel({ busy, onSetup }) {
  const [overs, setOvers] = useState(20);
  return (
    <div className="mt-6 border border-white/10 rounded-sm p-6 bg-[#141414]">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Step 1 — Initialize Match</div>
      <Label className="text-xs font-mono uppercase text-neutral-500 mt-4 block">Overs per innings</Label>
      <div className="flex gap-2 mt-2">
        {[5, 10, 15, 20, 50].map((n) => (
          <button key={n} data-testid={`cricket-overs-${n}`} onClick={() => setOvers(n)}
            className={`px-4 py-2 text-sm font-mono rounded-sm border ${overs === n ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400"}`}>
            {n}
          </button>
        ))}
        <Input type="number" value={overs} onChange={(e) => setOvers(Math.max(1, Number(e.target.value) || 1))}
          className="w-20 bg-black/40 border-white/10 text-white text-center" />
      </div>
      <Button data-testid="cricket-setup-btn" disabled={busy} onClick={() => onSetup(overs)}
        className="mt-6 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
        Initialize match ({overs} overs)
      </Button>
    </div>
  );
}

/* ---------------- Toss ---------------- */
function TossPanel({ teamA, teamB, busy, onSubmit }) {
  const [winner, setWinner] = useState(null);
  const [decision, setDecision] = useState(null);
  return (
    <div className="mt-6 border border-white/10 rounded-sm p-6 bg-[#141414]">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Step 2 — Toss</div>
      <Label className="text-xs font-mono uppercase text-neutral-500 mt-4 block">Toss winner</Label>
      <div className="flex gap-2 mt-2">
        {[teamA, teamB].map((t) => (
          <button key={t?.id || "x"} data-testid={`toss-winner-${t?.id}`} onClick={() => setWinner(t?.id)}
            className={`flex-1 px-4 py-3 text-sm font-semibold rounded-sm border ${winner === t?.id ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400 hover:border-white/30"}`}>
            <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: t?.color || "#666" }} />
            {t?.name || "Team"}
          </button>
        ))}
      </div>
      <Label className="text-xs font-mono uppercase text-neutral-500 mt-5 block">Decision</Label>
      <div className="flex gap-2 mt-2">
        {[{ v: "bat", l: "Choose to BAT" }, { v: "bowl", l: "Choose to BOWL" }].map((d) => (
          <button key={d.v} data-testid={`toss-decision-${d.v}`} onClick={() => setDecision(d.v)}
            className={`flex-1 px-4 py-3 text-sm font-semibold rounded-sm border ${decision === d.v ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400 hover:border-white/30"}`}>
            {d.l}
          </button>
        ))}
      </div>
      <Button data-testid="toss-submit" disabled={busy || !winner || !decision} onClick={() => onSubmit(winner, decision)}
        className="mt-6 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
        Confirm toss <ChevronRight className="w-4 h-4 ml-2" />
      </Button>
    </div>
  );
}

/* ---------------- Playing XI ---------------- */
function XIPanel({ rosters, teamA, teamB, busy, existing, onSubmit }) {
  const [selA, setSelA] = useState(new Set((existing?.team_a || []).map((p) => p.player_id)));
  const [selB, setSelB] = useState(new Set((existing?.team_b || []).map((p) => p.player_id)));
  const [captainA, setCaptainA] = useState((existing?.team_a || []).find((p) => p.captain)?.player_id || null);
  const [captainB, setCaptainB] = useState((existing?.team_b || []).find((p) => p.captain)?.player_id || null);
  const [wkA, setWkA] = useState((existing?.team_a || []).find((p) => p.wk)?.player_id || null);
  const [wkB, setWkB] = useState((existing?.team_b || []).find((p) => p.wk)?.player_id || null);

  const toggle = (set, setFn, id) => {
    const n = new Set(set);
    if (n.has(id)) n.delete(id);
    else if (n.size < 11) n.add(id);
    setFn(n);
  };

  const submit = () => {
    if (selA.size < 2 || selB.size < 2) { toast.error("Pick at least 2 players per side"); return; }
    const buildList = (set, roster, captain, wk) => Array.from(set).map((pid) => {
      const p = roster.find((r) => r.id === pid);
      return { player_id: pid, name: p?.name || "Player", captain: pid === captain, wk: pid === wk };
    });
    onSubmit(
      buildList(selA, rosters.team_a, captainA, wkA),
      buildList(selB, rosters.team_b, captainB, wkB),
    );
  };

  return (
    <div className="mt-6 grid md:grid-cols-2 gap-4">
      <XISide title={teamA?.name || "Team A"} color={teamA?.color} roster={rosters.team_a}
        selected={selA} onToggle={(id) => toggle(selA, setSelA, id)}
        captain={captainA} setCaptain={setCaptainA} wk={wkA} setWk={setWkA} testidPrefix="xi-a" />
      <XISide title={teamB?.name || "Team B"} color={teamB?.color} roster={rosters.team_b}
        selected={selB} onToggle={(id) => toggle(selB, setSelB, id)}
        captain={captainB} setCaptain={setCaptainB} wk={wkB} setWk={setWkB} testidPrefix="xi-b" />
      <div className="md:col-span-2">
        <Button data-testid="xi-submit" disabled={busy} onClick={submit}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm w-full md:w-auto">
          Save Playing XI ({selA.size} / {selB.size}) <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function XISide({ title, color, roster, selected, onToggle, captain, setCaptain, wk, setWk, testidPrefix }) {
  return (
    <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 font-semibold">
          <span className="w-2 h-2 rounded-full" style={{ background: color || "#666" }} />
          {title}
        </div>
        <span className="font-mono text-xs text-neutral-500">{selected.size}/11</span>
      </div>
      <div className="space-y-1.5 mt-3 max-h-72 overflow-y-auto pr-1">
        {roster.length === 0 && <div className="text-xs text-neutral-500">No team members yet. Add players to the team first.</div>}
        {roster.map((p) => {
          const checked = selected.has(p.id);
          return (
            <div key={p.id} data-testid={`${testidPrefix}-row-${p.id}`}
              className={`flex items-center justify-between px-3 py-2 rounded-sm border text-sm ${checked ? "border-[#84CC16]/50 bg-[#84CC16]/5" : "border-white/10"}`}>
              <button data-testid={`${testidPrefix}-toggle-${p.id}`} onClick={() => onToggle(p.id)}
                className="flex items-center gap-2 flex-1 text-left">
                <span className={`w-4 h-4 inline-block border rounded-sm ${checked ? "bg-[#84CC16] border-[#84CC16]" : "border-white/30"}`} />
                <span className="text-white">{p.name}</span>
              </button>
              {checked && (
                <div className="flex gap-1">
                  <button onClick={() => setCaptain(captain === p.id ? null : p.id)} data-testid={`${testidPrefix}-cap-${p.id}`}
                    title="Captain"
                    className={`p-1 rounded-sm border ${captain === p.id ? "bg-[#FF3B30] border-[#FF3B30]" : "border-white/10 text-neutral-400"}`}>
                    <Crown className="w-3 h-3" />
                  </button>
                  <button onClick={() => setWk(wk === p.id ? null : p.id)} data-testid={`${testidPrefix}-wk-${p.id}`}
                    title="Wicket Keeper"
                    className={`p-1 rounded-sm border ${wk === p.id ? "bg-[#06B6D4] border-[#06B6D4]" : "border-white/10 text-neutral-400"}`}>
                    <Award className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- Ready (pick striker/non-striker/bowler) ---------------- */
function ReadyPanel({ score, fixture, teamA, teamB, busy, onStart }) {
  // Determine batting team from toss
  const battingTeamId = useMemo(() => {
    const toss = score.toss;
    if (!toss) return null;
    if (toss.decision === "bat") return toss.winner_team_id;
    return toss.winner_team_id === fixture.team_a_id ? fixture.team_b_id : fixture.team_a_id;
  }, [score.toss, fixture.team_a_id, fixture.team_b_id]);

  const battingXI = battingTeamId === fixture.team_a_id ? score.playing_xi?.team_a : score.playing_xi?.team_b;
  const bowlingXI = battingTeamId === fixture.team_a_id ? score.playing_xi?.team_b : score.playing_xi?.team_a;
  const battingTeam = battingTeamId === fixture.team_a_id ? teamA : teamB;
  const bowlingTeam = battingTeamId === fixture.team_a_id ? teamB : teamA;

  const [striker, setStriker] = useState(null);
  const [nonStriker, setNonStriker] = useState(null);
  const [bowler, setBowler] = useState(null);

  return (
    <div className="mt-6 grid md:grid-cols-2 gap-4">
      <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
        <div className="font-mono text-[10px] uppercase text-neutral-500">/ Batting · {battingTeam?.name}</div>
        <PickPlayer label="Striker" players={battingXI} value={striker} onChange={setStriker} testid="pick-striker" excludeId={nonStriker} />
        <PickPlayer label="Non-striker" players={battingXI} value={nonStriker} onChange={setNonStriker} testid="pick-non-striker" excludeId={striker} />
      </div>
      <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
        <div className="font-mono text-[10px] uppercase text-neutral-500">/ Bowling · {bowlingTeam?.name}</div>
        <PickPlayer label="Opening bowler" players={bowlingXI} value={bowler} onChange={setBowler} testid="pick-bowler" />
      </div>
      <div className="md:col-span-2">
        <Button data-testid="start-innings-btn" disabled={busy || !striker || !nonStriker || !bowler}
          onClick={() => onStart({ striker_id: striker, non_striker_id: nonStriker, bowler_id: bowler })}
          className="bg-[#FF3B30] hover:bg-[#d62f24] text-white font-semibold rounded-sm w-full md:w-auto">
          Start Innings <ChevronRight className="w-4 h-4 ml-2" />
        </Button>
      </div>
    </div>
  );
}

function PickPlayer({ label, players, value, onChange, testid, excludeId }) {
  const filtered = useMemo(
    () => (players || []).filter((p) => p.player_id !== excludeId),
    [players, excludeId]
  );
  return (
    <div className="mt-3">
      <Label className="text-[10px] font-mono uppercase text-neutral-500">{label}</Label>
      <Select value={value || ""} onValueChange={onChange}>
        <SelectTrigger data-testid={testid} className="mt-1 bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select player" /></SelectTrigger>
        <SelectContent className="bg-[#141414] text-white border-white/10">
          {filtered.map((p) => (
            <SelectItem key={p.player_id} value={p.player_id} data-testid={`${testid}-opt-${p.player_id}`}>
              {p.name}{p.captain ? " (C)" : ""}{p.wk ? " (WK)" : ""}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/* ---------------- Live ball-by-ball scoring ---------------- */
function LivePanel({ score, fixture, teamMap, busy, callApi }) {
  const inn = score.innings?.[score.current_innings] || {};
  const battingTeam = teamMap[inn.batting_team_id];
  const bowlingTeam = teamMap[inn.bowling_team_id];
  const overs = `${Math.floor((inn.legal_balls || 0) / 6)}.${(inn.legal_balls || 0) % 6}`;

  const striker = (inn.batsmen || []).find((b) => b.player_id === inn.striker_id);
  const nonStriker = (inn.batsmen || []).find((b) => b.player_id === inn.non_striker_id);
  const bowler = (inn.bowlers || []).find((b) => b.player_id === inn.current_bowler_id);

  const xi = battingTeam?.id === fixture.team_a_id ? score.playing_xi?.team_a : score.playing_xi?.team_b;
  const bowlingXI = battingTeam?.id === fixture.team_a_id ? score.playing_xi?.team_b : score.playing_xi?.team_a;
  const availableBatsmen = (xi || []).filter((p) => {
    const rec = (inn.batsmen || []).find((b) => b.player_id === p.player_id);
    return !rec || !rec.out;
  }).filter((p) => p.player_id !== inn.striker_id && p.player_id !== inn.non_striker_id);

  const [newBatter, setNewBatter] = useState("");
  const [newBowler, setNewBowler] = useState("");
  const [wicketType, setWicketType] = useState("");

  const sendBall = (runs, extra = null, wicket = null) => {
    callApi("ball", { runs, extra, wicket });
    setWicketType("");
  };

  const inWicket = score.match_state === "wicket";
  const overBreak = inn.legal_balls % 6 === 0 && inn.legal_balls > 0 && !inn.current_bowler_id;
  const freeHit = !!inn.free_hit_pending;

  // Partnership: scan balls_log backwards to find the most recent wicket; sum runs+balls since.
  const partnership = useMemo(() => {
    const log = inn.balls_log || [];
    let lastWicketIdx = -1;
    for (let i = log.length - 1; i >= 0; i -= 1) {
      const w = log[i].wicket;
      if (w && w.type && !w.ignored_free_hit) {
        lastWicketIdx = i;
        break;
      }
    }
    let runs = 0;
    let balls = 0;
    for (let i = lastWicketIdx + 1; i < log.length; i += 1) {
      const b = log[i];
      runs += b.team_runs || 0;
      // Count legal deliveries (not wd/nb) as balls faced together
      if (b.extra !== "wd" && b.extra !== "nb") balls += 1;
    }
    return { runs, balls };
  }, [inn.balls_log]);

  return (
    <div className="mt-6 space-y-4">
      {/* Big scoreboard */}
      <div className="bg-gradient-to-r from-[#0a0a0a] via-[#1a1a1a] to-[#0a0a0a] border border-white/10 rounded-sm p-6">
        <div className="grid grid-cols-3 gap-4 items-center">
          <div>
            <div className="font-mono text-[10px] uppercase text-neutral-500">{battingTeam?.name}</div>
            <div className="font-display text-5xl text-white mt-1">{inn.runs ?? 0}<span className="text-2xl text-neutral-500">/{inn.wickets ?? 0}</span></div>
            <div className="text-xs font-mono text-neutral-500 mt-1">{overs} / {score.overs_limit} ov · RR {((inn.runs || 0) / ((inn.legal_balls || 1) / 6)).toFixed(2)}</div>
          </div>
          <div className="text-center">
            {inn.target && (
              <>
                <div className="text-[10px] font-mono uppercase text-neutral-500">Target</div>
                <div className="font-display text-3xl text-[#FF3B30]">{inn.target}</div>
                <div className="text-xs text-neutral-400 mt-1">Need {Math.max(0, inn.target - inn.runs)} in {Math.max(0, score.overs_limit * 6 - inn.legal_balls)} balls</div>
              </>
            )}
          </div>
          <div className="text-right">
            <div className="font-mono text-[10px] uppercase text-neutral-500">Bowling</div>
            <div className="text-base font-semibold">{bowlingTeam?.name}</div>
            <div className="text-xs font-mono text-neutral-500 mt-1">Extras: {Object.values(inn.extras || {}).reduce((a, b) => a + b, 0)}</div>
          </div>
        </div>
      </div>

      {/* Striker / Non-striker / Bowler */}
      <div className="grid grid-cols-3 gap-3">
        <BatterCard label="Striker *" b={striker} highlight />
        <BatterCard label="Non-striker" b={nonStriker} />
        <BowlerCard b={bowler} />
      </div>

      {/* Partnership widget */}
      {striker && nonStriker && (
        <div data-testid="partnership-widget" className="flex items-center justify-between border border-white/10 rounded-sm px-4 py-2 bg-[#141414] text-xs font-mono uppercase">
          <span className="text-neutral-500">Partnership</span>
          <span className="text-white">
            <span className="text-[#84CC16]">{partnership.runs}</span> runs · {partnership.balls} balls · RR{" "}
            <span className="text-neutral-300">
              {partnership.balls > 0 ? ((partnership.runs / partnership.balls) * 6).toFixed(2) : "0.00"}
            </span>
          </span>
        </div>
      )}

      {/* Free-hit banner */}
      {freeHit && !inWicket && (
        <div data-testid="free-hit-banner" className="border border-[#A855F7]/50 bg-[#A855F7]/15 rounded-sm px-4 py-2 flex items-center justify-between">
          <span className="font-mono text-[11px] uppercase tracking-widest text-[#A855F7]">/ FREE HIT — batsman can only be runout</span>
          <span className="text-[10px] font-mono text-neutral-400">resets after next legal ball</span>
        </div>
      )}

      {/* Wicket prompt */}
      {inWicket && (
        <div className="border border-[#FF3B30]/40 bg-[#FF3B30]/10 rounded-sm p-4">
          <div className="font-mono text-[10px] uppercase text-[#FF3B30]">/ WICKET — pick the new batsman</div>
          <div className="flex gap-2 mt-3">
            <Select value={newBatter} onValueChange={setNewBatter}>
              <SelectTrigger data-testid="new-batsman-select" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select incoming batsman" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {availableBatsmen.map((p) => (
                  <SelectItem key={p.player_id} value={p.player_id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button data-testid="new-batsman-submit" disabled={!newBatter || busy} onClick={() => { callApi("new-batsman", { player_id: newBatter }); setNewBatter(""); }}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Send in</Button>
          </div>
        </div>
      )}

      {/* End of over prompt */}
      {overBreak && !inWicket && (
        <div className="border border-[#84CC16]/40 bg-[#84CC16]/10 rounded-sm p-4">
          <div className="font-mono text-[10px] uppercase text-[#84CC16]">/ END OF OVER — pick the next bowler</div>
          <div className="flex gap-2 mt-3">
            <Select value={newBowler} onValueChange={setNewBowler}>
              <SelectTrigger data-testid="new-bowler-select" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select bowler" /></SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {(bowlingXI || []).filter((p) => p.player_id !== inn.current_bowler_id).map((p) => (
                  <SelectItem key={p.player_id} value={p.player_id}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button data-testid="new-bowler-submit" disabled={!newBowler || busy} onClick={() => { callApi("new-bowler", { player_id: newBowler }); setNewBowler(""); }}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Confirm</Button>
          </div>
        </div>
      )}

      {/* Ball entry */}
      {!inWicket && !overBreak && (
        <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Record a ball</div>
          <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 mt-3">
            {[0, 1, 2, 3, 4, 6].map((r) => (
              <RunButton key={r} runs={r} testid={`ball-runs-${r}`} disabled={busy}
                onClick={() => sendBall(r)} />
            ))}
            <RunButton runs="WD" testid="ball-wd" disabled={busy} accent onClick={() => sendBall(0, "wd")} />
            <RunButton runs="NB" testid="ball-nb" disabled={busy} accent onClick={() => sendBall(0, "nb")} />
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
            <RunButton runs="1 BYE" testid="ball-b1" disabled={busy} onClick={() => sendBall(1, "b")} />
            <RunButton runs="1 LB" testid="ball-lb1" disabled={busy} onClick={() => sendBall(1, "lb")} />
            <RunButton runs="4 BYE" testid="ball-b4" disabled={busy} onClick={() => sendBall(4, "b")} />
            <Button data-testid="ball-undo" disabled={busy} variant="outline" onClick={() => callApi("undo")}
              className="border-white/10 bg-transparent text-neutral-300 hover:bg-white/5">
              <Undo2 className="w-4 h-4 mr-1" /> Undo last
            </Button>
          </div>

          {/* Wicket panel */}
          <div className="mt-4 border-t border-white/10 pt-3">
            <div className="font-mono text-[10px] uppercase text-neutral-500 flex items-center gap-2">
              / Wicket
              {freeHit && <span className="text-[#A855F7]">— free-hit: only runout dismisses</span>}
            </div>
            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-2">
              {["bowled", "caught", "lbw", "runout", "stumped", "hitwicket"].map((wt) => {
                const disabled = busy || (freeHit && wt !== "runout");
                return (
                  <button key={wt} data-testid={`ball-wicket-${wt}`} disabled={disabled}
                    onClick={() => sendBall(0, null, { type: wt })}
                    className={`px-3 py-2 text-xs font-mono uppercase rounded-sm border ${
                      disabled
                        ? "border-white/10 text-neutral-600 cursor-not-allowed"
                        : "border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/10"
                    }`}>
                    {wt}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Cards */}
      <div className="grid md:grid-cols-2 gap-3">
        <BattingCard innings={inn} />
        <BowlingCard innings={inn} />
      </div>

      {/* End innings manually */}
      <div className="flex justify-end">
        <Button data-testid="end-innings-btn" variant="outline" disabled={busy}
          onClick={() => { if (window.confirm("End innings now?")) callApi("end-innings"); }}
          className="border-white/10 bg-transparent text-neutral-300 hover:bg-white/5">
          End innings
        </Button>
      </div>
    </div>
  );
}

function RunButton({ runs, onClick, disabled, accent, testid }) {
  const isExtra = typeof runs === "string";
  return (
    <button data-testid={testid} disabled={disabled} onClick={onClick}
      className={`px-3 py-3 text-base font-display tracking-wider rounded-sm border transition ${
        accent ? "bg-[#FF3B30]/10 border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/20"
               : runs === 4 ? "bg-[#06B6D4]/10 border-[#06B6D4]/40 text-[#06B6D4] hover:bg-[#06B6D4]/20"
               : runs === 6 ? "bg-[#A855F7]/10 border-[#A855F7]/40 text-[#A855F7] hover:bg-[#A855F7]/20"
               : "border-white/10 text-white hover:bg-white/5"
      }`}>
      {isExtra ? runs : (runs === 0 ? "·" : runs)}
    </button>
  );
}

function BatterCard({ label, b, highlight }) {
  if (!b) return <div className="border border-white/10 rounded-sm p-3 bg-[#141414] text-xs text-neutral-500">{label}: —</div>;
  const sr = b.balls > 0 ? ((b.runs / b.balls) * 100).toFixed(1) : "0.0";
  return (
    <div className={`border rounded-sm p-3 ${highlight ? "border-[#84CC16]/40 bg-[#84CC16]/5" : "border-white/10 bg-[#141414]"}`}>
      <div className="font-mono text-[10px] uppercase text-neutral-500">{label}</div>
      <div className="text-sm font-semibold mt-1">{b.name}</div>
      <div className="font-mono text-xs text-neutral-400 mt-1">{b.runs}({b.balls}) · 4s {b.fours} · 6s {b.sixes} · SR {sr}</div>
    </div>
  );
}

function BowlerCard({ b }) {
  if (!b) return <div className="border border-white/10 rounded-sm p-3 bg-[#141414] text-xs text-neutral-500">Bowler: —</div>;
  const overs = `${Math.floor(b.balls / 6)}.${b.balls % 6}`;
  const econ = b.balls > 0 ? ((b.runs / b.balls) * 6).toFixed(2) : "0.00";
  return (
    <div className="border border-[#06B6D4]/40 bg-[#06B6D4]/5 rounded-sm p-3">
      <div className="font-mono text-[10px] uppercase text-neutral-500">Bowler</div>
      <div className="text-sm font-semibold mt-1">{b.name}</div>
      <div className="font-mono text-xs text-neutral-400 mt-1">{overs} ov · {b.runs} runs · {b.wickets} wkt · Econ {econ}</div>
    </div>
  );
}

function BattingCard({ innings }) {
  return (
    <div className="border border-white/10 rounded-sm p-3 bg-[#141414]">
      <div className="font-mono text-[10px] uppercase text-neutral-500 mb-2">/ Batting</div>
      <table className="w-full text-xs">
        <thead className="text-neutral-500 font-mono">
          <tr><th className="text-left">Batsman</th><th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th></tr>
        </thead>
        <tbody>
          {(innings.batsmen || []).map((b) => {
            const sr = b.balls > 0 ? ((b.runs / b.balls) * 100).toFixed(1) : "-";
            return (
              <tr key={b.player_id} className="border-t border-white/5">
                <td className="py-1.5">
                  {b.name}
                  {b.out && <span className="ml-1 text-[#FF3B30] text-[10px] uppercase">({b.dismissal?.type || "out"})</span>}
                </td>
                <td className="text-center font-mono">{b.runs}</td>
                <td className="text-center font-mono">{b.balls}</td>
                <td className="text-center font-mono">{b.fours}</td>
                <td className="text-center font-mono">{b.sixes}</td>
                <td className="text-center font-mono">{sr}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="text-[10px] font-mono text-neutral-500 mt-2">
        Extras: wd {innings.extras?.wd || 0} · nb {innings.extras?.nb || 0} · b {innings.extras?.b || 0} · lb {innings.extras?.lb || 0}
      </div>
    </div>
  );
}

function BowlingCard({ innings }) {
  return (
    <div className="border border-white/10 rounded-sm p-3 bg-[#141414]">
      <div className="font-mono text-[10px] uppercase text-neutral-500 mb-2">/ Bowling</div>
      <table className="w-full text-xs">
        <thead className="text-neutral-500 font-mono">
          <tr><th className="text-left">Bowler</th><th>O</th><th>M</th><th>R</th><th>W</th><th>Econ</th></tr>
        </thead>
        <tbody>
          {(innings.bowlers || []).map((b) => {
            const ov = `${Math.floor(b.balls / 6)}.${b.balls % 6}`;
            const econ = b.balls > 0 ? ((b.runs / b.balls) * 6).toFixed(2) : "-";
            return (
              <tr key={b.player_id} className="border-t border-white/5">
                <td className="py-1.5">{b.name}</td>
                <td className="text-center font-mono">{ov}</td>
                <td className="text-center font-mono">{b.maidens}</td>
                <td className="text-center font-mono">{b.runs}</td>
                <td className="text-center font-mono">{b.wickets}</td>
                <td className="text-center font-mono">{econ}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ---------------- Innings break ---------------- */
function InningsBreakPanel({ score, fixture, teamA, teamB, busy, onStart }) {
  const inn1 = score.innings?.[0] || {};
  const battingTeam = inn1.batting_team_id === fixture.team_a_id ? teamA : teamB;
  const nextBattingId = inn1.bowling_team_id;
  const nextBattingXI = nextBattingId === fixture.team_a_id ? score.playing_xi?.team_a : score.playing_xi?.team_b;
  const nextBowlingXI = nextBattingId === fixture.team_a_id ? score.playing_xi?.team_b : score.playing_xi?.team_a;

  const [striker, setStriker] = useState(null);
  const [nonStriker, setNonStriker] = useState(null);
  const [bowler, setBowler] = useState(null);

  const overs = `${Math.floor((inn1.legal_balls || 0) / 6)}.${(inn1.legal_balls || 0) % 6}`;
  return (
    <div className="mt-6 space-y-4">
      <div className="border border-[#84CC16]/40 bg-[#84CC16]/5 rounded-sm p-6">
        <div className="font-mono text-[10px] uppercase text-[#84CC16]">/ Innings Break</div>
        <div className="mt-2 text-2xl font-display">
          {battingTeam?.name} scored <span className="text-[#84CC16]">{inn1.runs}/{inn1.wickets}</span> in {overs} overs.
        </div>
        <div className="text-sm text-neutral-300 mt-2">Target for {(nextBattingId === fixture.team_a_id ? teamA : teamB)?.name}: <strong className="text-[#FF3B30]">{inn1.runs + 1}</strong> runs.</div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Chasing — opening pair</div>
          <PickPlayer label="Striker" players={nextBattingXI} value={striker} onChange={setStriker} testid="i2-striker" excludeId={nonStriker} />
          <PickPlayer label="Non-striker" players={nextBattingXI} value={nonStriker} onChange={setNonStriker} testid="i2-non-striker" excludeId={striker} />
        </div>
        <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Opening bowler</div>
          <PickPlayer label="Bowler" players={nextBowlingXI} value={bowler} onChange={setBowler} testid="i2-bowler" />
        </div>
      </div>

      <Button data-testid="start-i2-btn" disabled={busy || !striker || !nonStriker || !bowler}
        onClick={() => onStart({ striker_id: striker, non_striker_id: nonStriker, bowler_id: bowler })}
        className="bg-[#FF3B30] hover:bg-[#d62f24] text-white font-semibold rounded-sm w-full md:w-auto">
        Start Innings 2 <ChevronRight className="w-4 h-4 ml-2" />
      </Button>
    </div>
  );
}

/* ---------------- Completed ---------------- */
function CompletedPanel({ score, fixture, teamA, teamB, busy, onDeclare, onClose }) {
  const inn1 = score.innings?.[0];
  const inn2 = score.innings?.[1];

  const teamRuns = (team_id) => {
    const inn = score.innings?.find((i) => i.batting_team_id === team_id);
    return inn ? `${inn.runs}/${inn.wickets} (${Math.floor(inn.legal_balls / 6)}.${inn.legal_balls % 6})` : "—";
  };

  // Suggested winner
  const aRuns = score.innings?.find((i) => i.batting_team_id === fixture.team_a_id)?.runs ?? 0;
  const bRuns = score.innings?.find((i) => i.batting_team_id === fixture.team_b_id)?.runs ?? 0;
  const suggested = aRuns > bRuns ? fixture.team_a_id : bRuns > aRuns ? fixture.team_b_id : null;
  const [winner, setWinner] = useState(fixture.winner_id || suggested);

  return (
    <div className="mt-6 space-y-4">
      <div className="border border-[#84CC16]/40 bg-[#84CC16]/5 rounded-sm p-6 text-center">
        <div className="font-mono text-[10px] uppercase text-[#84CC16]">/ Match Result</div>
        <div className="grid grid-cols-2 mt-4 gap-6">
          <ResultBox team={teamA} score={teamRuns(fixture.team_a_id)} winner={winner === fixture.team_a_id} />
          <ResultBox team={teamB} score={teamRuns(fixture.team_b_id)} winner={winner === fixture.team_b_id} />
        </div>
      </div>

      {inn1 && <BattingCard innings={inn1} />}
      {inn2 && <BattingCard innings={inn2} />}

      <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
        <div className="font-mono text-[10px] uppercase text-neutral-500">/ Declare winner</div>
        <div className="flex gap-2 mt-3">
          {[teamA, teamB].map((t) => (
            <button key={t?.id} data-testid={`declare-${t?.id}`} onClick={() => setWinner(t?.id)}
              className={`flex-1 px-3 py-2 text-sm rounded-sm border ${winner === t?.id ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400"}`}>
              {t?.name}
            </button>
          ))}
          <button data-testid="declare-tie" onClick={() => setWinner("")} className={`px-3 py-2 text-sm rounded-sm border ${winner === "" ? "bg-neutral-700 border-neutral-700" : "border-white/10 text-neutral-400"}`}>
            Tie
          </button>
        </div>
        <Button data-testid="declare-submit" disabled={busy} onClick={() => onDeclare(winner)}
          className="mt-4 bg-[#FF3B30] hover:bg-[#d62f24] rounded-sm text-white font-semibold">
          Finalize match
        </Button>
      </div>
    </div>
  );
}

function ResultBox({ team, score, winner }) {
  return (
    <div className={`border rounded-sm p-4 ${winner ? "border-[#84CC16] bg-[#84CC16]/10" : "border-white/10"}`}>
      <div className="flex items-center justify-center gap-2 font-display text-2xl">
        <span className="w-3 h-3 rounded-full" style={{ background: team?.color || "#666" }} />
        {team?.name || "—"}
      </div>
      <div className="font-mono text-3xl mt-3">{score}</div>
      {winner && <div className="mt-2 text-[#84CC16] text-xs uppercase font-mono">WINNER</div>}
    </div>
  );
}
