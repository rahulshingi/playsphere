import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Share2, Trophy } from "lucide-react";
import { toast } from "sonner";
import { renderScore } from "@/lib/sports";
import { shareOrDownloadBracket } from "@/lib/shareBracketImage";

/**
 * Visual tournament bracket for knockout / double-elimination events.
 *
 * For SINGLE-elim events, renders one round per column with connector lines.
 * For DOUBLE-elim events, splits into Winners Bracket + Losers Bracket + Grand Final
 * with distinct accent colours per section.
 *
 * A "Share bracket" button generates a 1080×1350 PNG via canvas (see
 * `lib/shareBracketImage.js`) — reuses the same share-card pipeline as
 * individual match cards.
 */
export default function BracketView({ event, fixtures, teamMap }) {
  const [sharing, setSharing] = useState(false);
  const isDoubleElim = event?.format === "double_elimination";

  const { wb, lb, gf, singleRounds } = useMemo(() => {
    if (isDoubleElim) {
      return {
        wb: fixtures.filter((f) => (f.bracket_position || "").startsWith("WB-")),
        lb: fixtures.filter((f) => (f.bracket_position || "").startsWith("LB-")),
        gf: fixtures.filter((f) => (f.bracket_position || "").startsWith("GF-")),
        singleRounds: null,
      };
    }
    const rounds = {};
    fixtures.forEach((f) => {
      if (!rounds[f.round]) rounds[f.round] = [];
      rounds[f.round].push(f);
    });
    Object.values(rounds).forEach((list) => list.sort((a, b) => a.match_number - b.match_number));
    return { wb: null, lb: null, gf: null, singleRounds: rounds };
  }, [fixtures, isDoubleElim]);

  const handleShare = async () => {
    setSharing(true);
    try {
      const { shared } = await shareOrDownloadBracket({ event, fixtures, teamMap });
      toast.success(shared ? "Bracket shared" : "Bracket downloaded");
    } catch (err) {
      toast.error("Failed to generate bracket image");
    } finally {
      setSharing(false);
    }
  };

  if (fixtures.length === 0) {
    return <div data-testid="bracket-empty" className="text-neutral-500 text-center py-20">Generate fixtures to view the bracket.</div>;
  }

  return (
    <div data-testid="bracket-view" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ Bracket</div>
          <div className="font-display text-2xl tracking-wide mt-1">
            {isDoubleElim ? "Double elimination" : "Knockout bracket"}
          </div>
        </div>
        <Button
          data-testid="share-bracket-btn"
          onClick={handleShare}
          disabled={sharing}
          className="bg-[#F59E0B] hover:bg-[#D97706] text-black font-semibold rounded-sm"
        >
          <Share2 className="w-4 h-4 mr-2" />
          {sharing ? "Preparing…" : "Share bracket"}
        </Button>
      </div>

      {isDoubleElim ? (
        <>
          <BracketSection label="Winners Bracket" fixtures={wb} teamMap={teamMap} event={event} accent="#84CC16" testid="bracket-wb" />
          <BracketSection label="Losers Bracket" fixtures={lb} teamMap={teamMap} event={event} accent="#EC4899" testid="bracket-lb" />
          {gf && gf.length > 0 && (
            <BracketSection label="Grand Final" fixtures={gf} teamMap={teamMap} event={event} accent="#F59E0B" testid="bracket-gf" isFinal />
          )}
        </>
      ) : (
        <div className="overflow-x-auto pb-4">
          <div className="flex gap-6 min-w-full">
            {Object.entries(singleRounds || {}).map(([rnd, list]) => (
              <div key={rnd} data-testid={`bracket-round-${rnd}`} className="min-w-[240px] flex-1">
                <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500 mb-3">/ Round {rnd}</div>
                <div className="space-y-3">
                  {list.map((f) => (
                    <BracketMatchCard key={f.id} fixture={f} teamMap={teamMap} event={event} accent="#06B6D4" />
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function BracketSection({ label, fixtures, teamMap, event, accent, testid, isFinal }) {
  const rounds = useMemo(() => {
    const g = {};
    (fixtures || []).forEach((f) => {
      if (!g[f.round]) g[f.round] = [];
      g[f.round].push(f);
    });
    Object.values(g).forEach((list) => list.sort((a, b) => a.match_number - b.match_number));
    return g;
  }, [fixtures]);

  if (!fixtures || fixtures.length === 0) return null;

  return (
    <div data-testid={testid} className="border border-white/10 rounded-sm bg-[#0f0f0f] p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="w-1 h-5 rounded-sm" style={{ background: accent }} />
        <div className="font-mono text-xs uppercase tracking-widest" style={{ color: accent }}>{label}</div>
      </div>
      <div className="overflow-x-auto pb-2">
        <div className="flex gap-5 min-w-full">
          {Object.entries(rounds).map(([rnd, list]) => (
            <div key={rnd} className={`${isFinal ? "min-w-[280px]" : "min-w-[220px]"} flex-1`}>
              <div className="font-mono text-[9px] uppercase tracking-widest text-neutral-600 mb-2">R{rnd}</div>
              <div className="space-y-3">
                {list.map((f) => (
                  <BracketMatchCard key={f.id} fixture={f} teamMap={teamMap} event={event} accent={accent} isFinal={isFinal} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function BracketMatchCard({ fixture, teamMap, event, accent, isFinal }) {
  const a = teamMap[fixture.team_a_id];
  const b = teamMap[fixture.team_b_id];
  const isLive = fixture.status === "live";
  const isCompleted = fixture.status === "completed";
  return (
    <Link
      to={`/live/${fixture.id}`}
      data-testid={`bracket-card-${fixture.id}`}
      className={`block rounded-sm border p-3 transition-colors hover:bg-white/5 ${isFinal ? "bg-[#F59E0B]/5" : "bg-black/30"} ${isLive ? "border-[#FF3B30]/40" : "border-white/10"}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="font-mono text-[9px] uppercase tracking-widest text-neutral-500">
          M{fixture.match_number}{fixture.bracket_position ? ` · ${fixture.bracket_position}` : ""}
        </span>
        {isLive && <span className="font-mono text-[9px] uppercase text-[#FF3B30]">● LIVE</span>}
        {isCompleted && <span className="font-mono text-[9px] uppercase text-neutral-500">DONE</span>}
      </div>
      <TeamLine team={a} score={renderScore(event.sport, fixture.score?.team_a)} winner={fixture.winner_id === a?.id} accent={accent} />
      <div className="text-[9px] font-mono text-neutral-700 text-center my-0.5">vs</div>
      <TeamLine team={b} score={renderScore(event.sport, fixture.score?.team_b)} winner={fixture.winner_id === b?.id} accent={accent} />
    </Link>
  );
}

function TeamLine({ team, score, winner, accent }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="w-1 h-4 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className={`text-xs truncate ${winner ? "text-white font-semibold" : "text-neutral-400"}`}>
          {team?.name || "TBD"}
        </span>
        {winner && <Trophy className="w-3 h-3" style={{ color: accent }} />}
      </div>
      <span className={`font-mono text-xs ${winner ? "" : "text-neutral-500"}`} style={winner ? { color: accent } : undefined}>{score}</span>
    </div>
  );
}
