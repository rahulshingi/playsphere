/**
 * Big scoreboard panel for the cricket live scorer. Pure presentational —
 * receives the current innings + match meta and renders runs/overs/target/extras.
 */
export default function CricketScoreboard({ inn, score, battingTeam, bowlingTeam, overs, extrasTotal }) {
  return (
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
          <div className="text-xs font-mono text-neutral-500 mt-1">Extras: {extrasTotal}</div>
        </div>
      </div>
    </div>
  );
}
