import { Link } from "react-router-dom";
import { useState } from "react";
import { resolveImageUrl } from "@/lib/imageUrl";
import { Award, TrendingUp, Trophy, Share2 } from "lucide-react";
import { shareMatchImage } from "@/lib/shareMatchImage";
import { toast } from "sonner";

/** Per-match score card. Rendered inside a "LOCAL MATCH SCORES" or generic
 *  "MATCH SCORES" section on PlayerProfile / public PlayerDirectory pages. */
export default function MatchScoreCard({ match, playerName = "" }) {
  const [sharing, setSharing] = useState(false);

  const onShare = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    setSharing(true);
    try {
      const result = await shareMatchImage(match, { playerName });
      if (result.ok) {
        toast.success(result.mode === "native" ? "Ready to share" : "Match card downloaded");
      } else {
        toast.error("Couldn't create share image");
      }
    } catch (err) {
      toast.error(err.message || "Share failed");
    } finally {
      setSharing(false);
    }
  };
  const resultAccent = {
    won: { color: "#84CC16", bg: "bg-[#84CC16]/10", border: "border-[#84CC16]/30", label: "WON" },
    lost: { color: "#FF3B30", bg: "bg-[#FF3B30]/10", border: "border-[#FF3B30]/30", label: "LOST" },
    draw: { color: "#9CA3AF", bg: "bg-neutral-500/10", border: "border-neutral-500/30", label: "TIE" },
    live: { color: "#F59E0B", bg: "bg-[#F59E0B]/10", border: "border-[#F59E0B]/30", label: "LIVE" },
  }[match.result] || { color: "#9CA3AF", bg: "bg-white/5", border: "border-white/10", label: "—" };
  const AWARD_LABELS = {
    mom: "PLAYER OF THE MATCH",
    best_batter: "BEST BATTER",
    best_bowler: "BEST BOWLER",
    top_scorer: "TOP SCORER",
  };
  return (
    <Link
      to={`/events/${match.event_id}`}
      data-testid={`match-score-card-${match.fixture_id}`}
      className="block border border-white/10 rounded-sm bg-black/40 hover:border-[#84CC16]/40 transition p-3"
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 flex-wrap min-w-0">
          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-white/5 text-neutral-400 tracking-widest">{match.sport}</span>
          {match.is_local_match && (
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#84CC16]/10 text-[#84CC16] border border-[#84CC16]/30 tracking-widest">LOCAL</span>
          )}
          {match.match_number != null && (
            <span className="text-[9px] font-mono uppercase text-neutral-500 tracking-widest">M#{match.match_number}</span>
          )}
        </div>
        <span
          className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm border tracking-widest ${resultAccent.bg} ${resultAccent.border}`}
          style={{ color: resultAccent.color }}
        >
          {resultAccent.label}
        </span>
      </div>
      <div className="text-white text-sm truncate mb-2">{match.event_name}</div>
      <div className="grid grid-cols-2 gap-2">
        <TeamScoreRow team={match.my_team} highlight />
        <TeamScoreRow team={match.opp_team} />
      </div>
      {match.my_awards?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {match.my_awards.map((k) => (
            <span key={k} className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30 tracking-widest flex items-center gap-1">
              <Award className="w-2.5 h-2.5" /> {AWARD_LABELS[k] || k.replace(/_/g, " ").toUpperCase()}
            </span>
          ))}
        </div>
      )}
      {match.hero_image_url && (
        <div className="mt-2 aspect-[16/9] rounded-sm overflow-hidden border border-white/10">
          <img src={resolveImageUrl(match.hero_image_url)} alt="" className="w-full h-full object-cover opacity-80 hover:opacity-100 transition" />
        </div>
      )}
      <div className="mt-2 flex items-center justify-between gap-2">
        <div className="text-[10px] font-mono text-[#06B6D4] uppercase tracking-widest flex items-center gap-1">
          <TrendingUp className="w-3 h-3" /> View match →
        </div>
        <button
          type="button"
          onClick={onShare}
          disabled={sharing}
          data-testid={`match-share-btn-${match.fixture_id}`}
          className="text-[10px] font-mono uppercase tracking-widest text-[#84CC16] hover:text-white flex items-center gap-1 border border-[#84CC16]/30 hover:border-[#84CC16] px-2 py-1 rounded-sm bg-[#84CC16]/5 disabled:opacity-60"
        >
          <Share2 className="w-3 h-3" /> {sharing ? "Building…" : "Share"}
        </button>
      </div>
    </Link>
  );
}

function TeamScoreRow({ team, highlight }) {
  return (
    <div className={`p-2 rounded-sm border ${highlight ? "border-[#84CC16]/30 bg-[#84CC16]/5" : "border-white/10 bg-black/30"}`}>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 flex items-center gap-1 truncate">
        {team.is_winner && <Trophy className="w-2.5 h-2.5 text-[#F59E0B]" />}
        {team.name}
      </div>
      <div className={`text-lg font-display tracking-wider mt-0.5 ${team.is_winner ? "text-[#84CC16]" : "text-white"}`}>{team.score_display}</div>
    </div>
  );
}
