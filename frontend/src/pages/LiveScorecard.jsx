import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Share2, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";
import { devError } from "@/lib/devLog";

const BACKEND = process.env.REACT_APP_BACKEND_URL || "";
const API = BACKEND ? `${BACKEND}/api` : "/api";
const POLL_MS = 5000;

/** Public, auth-less live scorecard for any fixture. Auto-refreshes every 5s. */
export default function LiveScorecard() {
  const { fixture_id } = useParams();
  const [payload, setPayload] = useState(null);
  const [error, setError] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [showFull, setShowFull] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let timer;
    const fetch = async () => {
      try {
        const r = await axios.get(`${API}/public/fixtures/${fixture_id}`);
        if (!cancelled) {
          setPayload(r.data);
          setError(null);
          setUpdatedAt(new Date());
        }
      } catch (err) {
        if (!cancelled) setError(err.response?.data?.detail || "Unable to load scorecard");
      } finally {
        if (!cancelled) timer = setTimeout(fetch, POLL_MS);
      }
    };
    fetch();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [fixture_id]);

  const share = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try { await navigator.share({ title: "Live score", url }); }
      catch (err) { devError("[LiveScorecard] navigator.share failed:", err); }
    } else {
      try { await navigator.clipboard.writeText(url); }
      catch (err) { devError("[LiveScorecard] clipboard.writeText blocked:", err); }
    }
  };

  if (error && !payload) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white grid place-items-center px-6 text-center">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#FF3B30] tracking-widest">/ Error</div>
          <h1 className="font-display text-3xl mt-3">{error}</h1>
          <p className="text-neutral-400 mt-2 text-sm">Verify the fixture link or try again later.</p>
        </div>
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] text-white grid place-items-center">
        <div className="animate-pulse text-neutral-500 font-mono text-sm">Loading live scorecard…</div>
      </div>
    );
  }

  const { fixture, event, teams } = payload;
  const teamA = teams[fixture.team_a_id];
  const teamB = teams[fixture.team_b_id];
  const isCricket = event.sport === "cricket";

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-white pb-24">
      {/* Hero scorecard */}
      <header className="border-b border-white/10 bg-gradient-to-b from-[#141414] to-[#0a0a0a]">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 py-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="font-mono text-[10px] uppercase text-[#84CC16] tracking-widest">/ Live · {event.sport?.toUpperCase()}</div>
              <h1 className="font-display text-2xl sm:text-4xl mt-1 leading-tight">{event.name}</h1>
              <div className="text-xs text-neutral-500 font-mono mt-1">Match #{fixture.match_number || "—"} · {fixture.status?.toUpperCase()}</div>
            </div>
            <div className="flex items-center gap-2">
              <button data-testid="share-btn" onClick={share} className="px-3 py-2 text-xs font-mono uppercase border border-white/10 rounded-sm hover:bg-white/5 flex items-center gap-1">
                <Share2 className="w-3.5 h-3.5" /> Share
              </button>
              <div className="hidden sm:flex items-center gap-1 text-[10px] font-mono text-neutral-500">
                <RefreshCw className="w-3 h-3 animate-spin-slow" />
                <span>{updatedAt ? `updated ${updatedAt.toLocaleTimeString()}` : "—"}</span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 mt-6 items-center gap-3">
            <TeamPanel team={teamA} align="left" />
            <ScoreSummary fixture={fixture} event={event} teamA={teamA} teamB={teamB} />
            <TeamPanel team={teamB} align="right" />
          </div>
        </div>
      </header>

      {/* Sport-specific body */}
      <main className="mx-auto max-w-4xl px-4 sm:px-6 mt-6">
        {isCricket ? (
          <CricketBody fixture={fixture} teams={teams} showFull={showFull} setShowFull={setShowFull} />
        ) : (
          <GenericBody fixture={fixture} teamA={teamA} teamB={teamB} sport={event.sport} />
        )}
      </main>

      <footer className="mt-12 text-center text-[10px] font-mono text-neutral-600 uppercase tracking-widest">
        powered by <span className="text-[#84CC16]">kreeda nation</span>
      </footer>
    </div>
  );
}

function TeamPanel({ team, align }) {
  return (
    <div className={`flex flex-col ${align === "right" ? "items-end text-right" : "items-start text-left"}`}>
      <div className="flex items-center gap-2">
        {team?.logo_url ? (
          <img src={team.logo_url} alt="" className="w-8 h-8 sm:w-10 sm:h-10 rounded-sm object-cover" />
        ) : (
          <span className="w-8 h-8 sm:w-10 sm:h-10 rounded-sm inline-block" style={{ background: team?.color || "#333" }} />
        )}
        <div>
          <div className="font-display text-base sm:text-xl leading-tight">{team?.name || "TBD"}</div>
          <div className="text-[10px] font-mono text-neutral-500">{team?.short_name || ""}</div>
        </div>
      </div>
    </div>
  );
}

function ScoreSummary({ fixture, event, teamA, teamB }) {
  const score = fixture.score || {};
  if (event.sport === "cricket") {
    const a = score.team_a || {};
    const b = score.team_b || {};
    return (
      <div className="text-center">
        <div className="font-display text-2xl sm:text-4xl leading-none">
          <span className="text-white">{a.runs ?? 0}<span className="text-neutral-500 text-base">/{a.wickets ?? 0}</span></span>
          <span className="text-neutral-600 mx-2 text-base">vs</span>
          <span className="text-white">{b.runs ?? 0}<span className="text-neutral-500 text-base">/{b.wickets ?? 0}</span></span>
        </div>
        <div className="text-[10px] font-mono text-neutral-500 mt-1">
          {a.overs ?? 0} ov · {b.overs ?? 0} ov
        </div>
      </div>
    );
  }
  const a = score.team_a || {};
  const b = score.team_b || {};

  // Pick the right headline value per sport.
  // Set-sports (badminton/tabletennis/volleyball) show "sets won", everything else
  // falls back to whatever numeric key the score doc carries (goals/points/score).
  let headlineA = 0, headlineB = 0, subline = null;
  if (["badminton", "tabletennis", "volleyball"].includes(event.sport)) {
    const setsA = a.sets || []; const setsB = b.sets || [];
    headlineA = setsA.filter((s, i) => s > (setsB[i] ?? 0)).length;
    headlineB = setsB.filter((s, i) => s > (setsA[i] ?? 0)).length;
    subline = "Sets won";
  } else {
    headlineA = a.goals ?? a.points ?? a.score ?? 0;
    headlineB = b.goals ?? b.points ?? b.score ?? 0;
    if (event.sport === "basketball" && (a.q || b.q)) subline = `Q${a.q || b.q || 1}`;
  }

  return (
    <div className="text-center">
      <div className="font-display text-3xl sm:text-5xl leading-none">
        <span className="text-white">{headlineA}</span>
        <span className="text-neutral-600 mx-2">·</span>
        <span className="text-white">{headlineB}</span>
      </div>
      {subline && (
        <div className="text-[10px] font-mono uppercase text-[#FACC15] mt-1">{subline}</div>
      )}
      {fixture.status === "completed" && fixture.winner_id && (
        <div className="text-[10px] font-mono uppercase text-[#84CC16] mt-2">
          {fixture.winner_id === teamA?.id ? teamA?.short_name || teamA?.name : teamB?.short_name || teamB?.name} WON
        </div>
      )}
    </div>
  );
}

function CricketBody({ fixture, teams, showFull, setShowFull }) {
  const score = fixture.score || {};
  const innings = score.innings || [];
  const matchState = score.match_state || "—";
  const currentInn = innings[score.current_innings] || null;

  return (
    <div className="space-y-4">
      {/* Match status banner */}
      <div className="border border-white/10 rounded-sm px-4 py-3 bg-[#141414] flex items-center justify-between flex-wrap gap-2">
        <div className="font-mono text-[10px] uppercase text-neutral-500">/ Match state · <span className="text-[#84CC16]">{matchState.toUpperCase()}</span></div>
        {score.toss && (
          <div className="font-mono text-[10px] text-neutral-400">
            Toss: <span className="text-white">{teams[score.toss.winner_team_id]?.short_name || teams[score.toss.winner_team_id]?.name || "—"}</span> chose to {score.toss.decision}
          </div>
        )}
      </div>

      {/* Live ball-by-ball strip */}
      {currentInn && !currentInn.completed && (
        <CurrentInningsPanel innings={currentInn} teams={teams} score={score} />
      )}

      {/* Innings summaries */}
      {innings.length > 0 && (
        <div className="flex items-center justify-between mt-2">
          <h2 className="font-display text-xl">Innings</h2>
          <button
            data-testid="toggle-full"
            onClick={() => setShowFull((v) => !v)}
            className="text-xs font-mono text-neutral-400 hover:text-white flex items-center gap-1"
          >
            {showFull ? "Collapse" : "Full scorecards"}
            {showFull ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
        </div>
      )}

      {showFull && innings.map((inn, idx) => (
        <InningsCard key={`inn-${idx}`} idx={idx} inn={inn} teams={teams} overs_limit={score.overs_limit} />
      ))}

      {/* Final result */}
      {matchState === "completed" && (
        <div className="border border-[#84CC16]/40 bg-[#84CC16]/10 rounded-sm p-5 text-center">
          <div className="font-mono text-[10px] uppercase text-[#84CC16]">/ Match Result</div>
          <div className="font-display text-2xl sm:text-3xl mt-1">
            {fixture.winner_id ? `${teams[fixture.winner_id]?.name || ""} won` : "Tie / no result"}
          </div>
        </div>
      )}
    </div>
  );
}

function CurrentInningsPanel({ innings, teams, score }) {
  const battingTeam = teams[innings.batting_team_id];
  const striker = (innings.batsmen || []).find((b) => b.player_id === innings.striker_id);
  const nonStriker = (innings.batsmen || []).find((b) => b.player_id === innings.non_striker_id);
  const bowler = (innings.bowlers || []).find((b) => b.player_id === innings.current_bowler_id);
  const overs = `${Math.floor((innings.legal_balls || 0) / 6)}.${(innings.legal_balls || 0) % 6}`;
  const lastBalls = (innings.balls_log || []).slice(-6).reverse();
  const requirement = innings.target ? Math.max(0, innings.target - innings.runs) : null;
  const ballsLeft = score.overs_limit ? Math.max(0, score.overs_limit * 6 - innings.legal_balls) : null;

  return (
    <div className="border border-[#06B6D4]/40 bg-[#06B6D4]/5 rounded-sm p-4 sm:p-5">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#06B6D4]">/ Now batting · {battingTeam?.name}</div>
          <div className="font-display text-3xl mt-1">{innings.runs}/{innings.wickets} <span className="text-neutral-500 text-base">({overs} ov)</span></div>
        </div>
        {requirement !== null && (
          <div className="text-right">
            <div className="font-mono text-[10px] uppercase text-[#FF3B30]">/ Target</div>
            <div className="font-display text-xl">{innings.target}</div>
            <div className="text-[10px] font-mono text-neutral-400">Need {requirement} in {ballsLeft} balls</div>
          </div>
        )}
      </div>

      <div className="grid sm:grid-cols-3 gap-2 mt-4">
        <CrumbCard label="Striker *" name={striker?.name} stats={striker ? `${striker.runs}(${striker.balls})` : null} accent="#84CC16" />
        <CrumbCard label="Non-striker" name={nonStriker?.name} stats={nonStriker ? `${nonStriker.runs}(${nonStriker.balls})` : null} />
        <CrumbCard label="Bowler" name={bowler?.name} stats={bowler ? `${bowler.runs}-${bowler.wickets} (${Math.floor(bowler.balls / 6)}.${bowler.balls % 6})` : null} accent="#06B6D4" />
      </div>

      {lastBalls.length > 0 && (
        <div className="mt-4">
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ This over</div>
          <div className="flex gap-2 mt-2 overflow-x-auto pb-1">
            {lastBalls.map((b, i) => (
              <BallChip key={`bb-${i}`} b={b} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CrumbCard({ label, name, stats, accent }) {
  if (!name) return <div className="border border-white/10 rounded-sm p-3 bg-black/30 text-xs text-neutral-500">{label}: —</div>;
  return (
    <div className="border rounded-sm p-3 bg-black/30" style={{ borderColor: accent ? `${accent}66` : "rgba(255,255,255,0.1)" }}>
      <div className="font-mono text-[10px] uppercase text-neutral-500">{label}</div>
      <div className="text-sm font-semibold mt-0.5 truncate">{name}</div>
      {stats && <div className="font-mono text-xs text-neutral-400 mt-0.5">{stats}</div>}
    </div>
  );
}

function BallChip({ b }) {
  let label = b.runs;
  let style = "bg-white/5 text-white";
  if (b.wicket && !b.wicket.ignored_free_hit) { label = "W"; style = "bg-[#FF3B30] text-white"; }
  else if (b.extra === "wd") { label = "wd"; style = "bg-[#A855F7]/30 text-[#A855F7]"; }
  else if (b.extra === "nb") { label = "nb"; style = "bg-[#A855F7]/30 text-[#A855F7]"; }
  else if (b.extra === "b") { label = `b${b.team_runs}`; style = "bg-neutral-700 text-neutral-200"; }
  else if (b.extra === "lb") { label = `lb${b.team_runs}`; style = "bg-neutral-700 text-neutral-200"; }
  else if (b.runs === 4) { style = "bg-[#06B6D4]/30 text-[#06B6D4]"; }
  else if (b.runs === 6) { style = "bg-[#A855F7]/30 text-[#A855F7]"; }
  return (
    <span className={`w-9 h-9 grid place-items-center text-sm font-mono font-semibold rounded-sm ${style}`}>
      {label}
    </span>
  );
}

function InningsCard({ idx, inn, teams, overs_limit }) {
  const battingTeam = teams[inn.batting_team_id];
  const bowlingTeam = teams[inn.bowling_team_id];
  const overs = `${Math.floor((inn.legal_balls || 0) / 6)}.${(inn.legal_balls || 0) % 6}`;
  const extras = inn.extras || {};
  const extrasTotal = Object.values(extras).reduce((a, b) => a + b, 0);
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <div className="font-mono text-[10px] uppercase text-neutral-500">/ Innings {idx + 1} · {battingTeam?.name}</div>
          <div className="font-display text-2xl mt-1">{inn.runs}/{inn.wickets} <span className="text-neutral-500 text-base">({overs} / {overs_limit} ov)</span></div>
        </div>
        <div className="text-right text-xs text-neutral-400">
          <div>vs {bowlingTeam?.name}</div>
          {inn.target && <div className="text-[#FF3B30]">Target: {inn.target}</div>}
        </div>
      </div>

      {/* Batting card */}
      {(inn.batsmen || []).length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs min-w-[480px]">
            <thead className="text-neutral-500 font-mono">
              <tr><th className="text-left py-1">Batsman</th><th>R</th><th>B</th><th>4s</th><th>6s</th><th>SR</th></tr>
            </thead>
            <tbody>
              {inn.batsmen.map((b) => {
                const sr = b.balls > 0 ? ((b.runs / b.balls) * 100).toFixed(1) : "-";
                return (
                  <tr key={b.player_id} className="border-t border-white/5">
                    <td className="py-1.5">
                      {b.name}
                      {b.out && <span className="ml-1 text-[#FF3B30] text-[10px] uppercase">({b.dismissal?.type || "out"})</span>}
                      {b.player_id === inn.striker_id && <span className="ml-1 text-[#84CC16] text-[10px]">*</span>}
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
            Extras: {extrasTotal} (wd {extras.wd || 0}, nb {extras.nb || 0}, b {extras.b || 0}, lb {extras.lb || 0})
          </div>
        </div>
      )}

      {/* Bowling card */}
      {(inn.bowlers || []).length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-xs min-w-[480px]">
            <thead className="text-neutral-500 font-mono">
              <tr><th className="text-left py-1">Bowler</th><th>O</th><th>M</th><th>R</th><th>W</th><th>Econ</th></tr>
            </thead>
            <tbody>
              {inn.bowlers.map((b) => {
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
      )}
    </div>
  );
}

/* ---------------- Generic (non-cricket) scorecard renderer ----------------
 * Replaces the previous JSON dump with a readable, sport-specific layout for
 * football, basketball, badminton/tabletennis/volleyball, chess/quiz, hackathon
 * and any fallback `{score}` shape. */

const SCORE_LABEL = {
  football: "Goals",
  basketball: "Points",
  chess: "Points",
  quiz: "Points",
  hackathon: "Score",
};

function GenericBody({ fixture, teamA, teamB, sport }) {
  const score = fixture.score || {};
  const a = score.team_a || {};
  const b = score.team_b || {};
  const status = fixture.status;
  const isSetSport = sport === "badminton" || sport === "tabletennis" || sport === "volleyball";

  // Badminton / TT / Volleyball — render set-by-set with winner highlighting.
  if (isSetSport) {
    const setsA = a.sets || [];
    const setsB = b.sets || [];
    const maxSets = Math.max(setsA.length, setsB.length);
    const wonA = setsA.filter((s, i) => s > (setsB[i] ?? 0)).length;
    const wonB = setsB.filter((s, i) => s > (setsA[i] ?? 0)).length;
    return (
      <div className="border border-white/10 rounded-sm bg-[#141414] p-5">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-4">/ {sport.toUpperCase()} · Set scoreboard</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] font-mono uppercase text-neutral-500">
                <th className="text-left py-2">Team</th>
                {Array.from({ length: maxSets }).map((_, i) => (
                  // Set scores are positional and the column count never changes
                  // mid-render, so a stable string key prefix is sufficient + clearer.
                  <th key={`set-${i + 1}`} className="text-center py-2 w-14">Set {i + 1}</th>
                ))}
                <th className="text-center py-2 w-14">Sets won</th>
              </tr>
            </thead>
            <tbody>
              <TeamSetRow team={teamA} sets={setsA} other={setsB} wins={wonA} winner={wonA > wonB && status === "completed"} />
              <TeamSetRow team={teamB} sets={setsB} other={setsA} wins={wonB} winner={wonB > wonA && status === "completed"} />
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // Basketball — show score + current quarter / period.
  if (sport === "basketball") {
    const quarter = a.q || b.q || 1;
    return (
      <ScoreSidesBox sport={sport} teamA={teamA} teamB={teamB}
        valueA={a.points ?? 0} valueB={b.points ?? 0}
        label="Points" subline={`Quarter ${quarter}`} status={status} />
    );
  }

  // Football / chess / quiz / hackathon / fallback — single numeric score per side.
  // Picks the right key from the score doc for the given sport. Kept as a small helper
  // instead of a nested ternary so the precedence is explicit and easier to extend.
  const pickValueKey = () => {
    if (sport === "football") return "goals";
    if (sport === "hackathon") return "score";
    if (a.points !== undefined) return "points";
    return "score";
  };
  const valueKey = pickValueKey();
  const label = SCORE_LABEL[sport] || (valueKey.charAt(0).toUpperCase() + valueKey.slice(1));
  return (
    <ScoreSidesBox sport={sport} teamA={teamA} teamB={teamB}
      valueA={a[valueKey] ?? 0} valueB={b[valueKey] ?? 0}
      label={label} status={status} />
  );
}

function TeamSetRow({ team, sets, other, wins, winner }) {
  return (
    <tr className={`border-t border-white/10 ${winner ? "bg-[#84CC16]/5" : ""}`}>
      <td className="py-3 pr-4 flex items-center gap-2">
        <span className="w-1.5 h-5 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className="font-semibold truncate">{team?.name || "—"}</span>
        {winner && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#84CC16] text-black">Winner</span>}
      </td>
      {sets.map((s, i) => {
        const o = other[i] ?? 0;
        return (
          // Composite key ties each cell to its team + set position so React can
          // reconcile correctly when the underlying team flips or sets are added.
          <td key={`${team?.id || team?.name || "team"}-set-${i + 1}`}
              className={`text-center py-3 font-mono ${s > o ? "text-[#84CC16] font-semibold" : "text-neutral-400"}`}>{s}</td>
        );
      })}
      <td className="text-center py-3 font-display text-2xl text-white">{wins}</td>
    </tr>
  );
}

function ScoreSidesBox({ sport, teamA, teamB, valueA, valueB, label, subline, status }) {
  const winnerA = status === "completed" && valueA > valueB;
  const winnerB = status === "completed" && valueB > valueA;
  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
      <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-4">/ {sport.toUpperCase()} · {label}</div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-4 sm:gap-8">
        <ScoreSide team={teamA} value={valueA} winner={winnerA} align="left" />
        <div className="text-center">
          <div className="font-mono text-[10px] uppercase text-neutral-600">vs</div>
          {subline && <div className="text-[10px] font-mono uppercase text-[#FACC15] mt-1">{subline}</div>}
        </div>
        <ScoreSide team={teamB} value={valueB} winner={winnerB} align="right" />
      </div>
    </div>
  );
}

function ScoreSide({ team, value, winner, align }) {
  return (
    <div className={align === "right" ? "text-right" : "text-left"}>
      <div className={`flex items-center gap-2 ${align === "right" ? "justify-end" : ""}`}>
        <span className="w-1.5 h-7 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className="font-semibold truncate">{team?.name || "—"}</span>
        {winner && <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#84CC16] text-black">Winner</span>}
      </div>
      <div className="font-display text-6xl mt-2" style={{ color: winner ? "#84CC16" : "#fff" }}>{value}</div>
    </div>
  );
}
