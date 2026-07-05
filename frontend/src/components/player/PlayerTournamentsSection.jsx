import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Trophy, Calendar, Award, MapPin, Plus } from "lucide-react";
import { resolveImageUrl } from "@/lib/imageUrl";
import MatchScoreCard from "@/components/player/MatchScoreCard";

/**
 * Player tournaments dashboard — renders three sections in order:
 *
 *   1. MY LOCAL MATCHES         — events they hosted (creator)
 *   2. LOCAL MATCH SCORES       — per-match score cards for local tournaments
 *                                 they played in (auto-added, iter35)
 *   3. TOURNAMENTS PLAYED       — non-local corporate/organiser tournaments
 *                                 they participated in (aggregated card view)
 *
 * profileId: PlayerProfile.id
 * isOwner: enables the "Host a local match" CTA + shows hidden hosted events.
 */
export default function PlayerTournamentsSection({ profileId, isOwner }) {
  const [hosted, setHosted] = useState([]);
  const [played, setPlayed] = useState([]);
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!profileId) return;
    let cancelled = false;
    Promise.all([
      api.get(`/players/${profileId}/hosted-tournaments`).catch(() => ({ data: [] })),
      api.get(`/players/${profileId}/tournaments`).catch(() => ({ data: [] })),
      api.get(`/players/${profileId}/match-history`).catch(() => ({ data: [] })),
    ]).then(([h, p, m]) => {
      if (cancelled) return;
      setHosted(h.data || []);
      setPlayed(p.data || []);
      setMatches(m.data || []);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [profileId]);

  if (loading) return null;
  const localMatches = matches.filter((m) => m.is_local_match);
  const nonLocalPlayed = played.filter((e) => !e.is_local_match);

  if (!isOwner && hosted.length === 0 && localMatches.length === 0 && nonLocalPlayed.length === 0) return null;

  return (
    <div className="space-y-8 mt-10" data-testid="player-tournaments-section">
      {/* HOSTED */}
      <section className="border border-white/10 rounded-sm bg-[#141414] p-5">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Local matches hosted</div>
            <div className="font-display tracking-wider text-2xl mt-1">MY LOCAL MATCHES ({hosted.length})</div>
          </div>
          {isOwner && (
            <Link to="/admin">
              <Button data-testid="player-host-cta" size="sm" className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
                <Plus className="w-4 h-4 mr-1" /> Host a local match
              </Button>
            </Link>
          )}
        </div>
        {hosted.length === 0 ? (
          <p className="text-sm text-neutral-500" data-testid="player-hosted-empty">
            {isOwner ? "You haven't hosted a local match yet. Tap the button above to run your first neighborhood tournament." : "No local matches hosted yet."}
          </p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {hosted.map((e) => (
              <TournamentCard key={e.id} event={e} hosted />
            ))}
          </div>
        )}
      </section>

      {/* LOCAL MATCH SCORES — per-match cards for local tournaments played */}
      {localMatches.length > 0 && (
        <section className="border border-white/10 rounded-sm bg-[#141414] p-5" data-testid="local-match-scores-section">
          <div className="mb-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ Local match scores</div>
            <div className="font-display tracking-wider text-2xl mt-1">LOCAL MATCH SCORES ({localMatches.length})</div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {localMatches.map((m) => (
              <MatchScoreCard key={m.fixture_id} match={m} />
            ))}
          </div>
        </section>
      )}

      {/* NON-LOCAL TOURNAMENTS PLAYED */}
      {nonLocalPlayed.length > 0 && (
        <section className="border border-white/10 rounded-sm bg-[#141414] p-5">
          <div className="mb-4">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#06B6D4]">/ Tournaments played</div>
            <div className="font-display tracking-wider text-2xl mt-1">TOURNAMENTS PLAYED ({nonLocalPlayed.length})</div>
          </div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {nonLocalPlayed.map((e) => (
              <TournamentCard key={e.id} event={e} contribution={e.contribution} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function TournamentCard({ event, hosted, contribution }) {
  return (
    <Link
      to={`/events/${event.id}`}
      data-testid={`tournament-card-${event.id}`}
      className="block border border-white/10 rounded-sm bg-black/40 hover:border-[#84CC16]/40 transition overflow-hidden"
    >
      <div className="aspect-[16/9] bg-[#0a0a0a] overflow-hidden">
        {event.banner_url ? (
          <img src={resolveImageUrl(event.banner_url)} alt={event.name} className="w-full h-full object-cover opacity-80 hover:opacity-100 transition" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-neutral-700">
            <Trophy className="w-10 h-10" />
          </div>
        )}
      </div>
      <div className="p-3 space-y-1.5">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-white/5 text-neutral-400 tracking-widest">{event.sport}</span>
          {event.is_local_match && (
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#84CC16]/10 text-[#84CC16] border border-[#84CC16]/30 tracking-widest">LOCAL</span>
          )}
          {hosted && event.listed_publicly === false && (
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-neutral-500/10 text-neutral-400 border border-neutral-500/30 tracking-widest">HIDDEN</span>
          )}
        </div>
        <div className="font-semibold text-sm truncate text-white">{event.name}</div>
        <div className="text-[10px] font-mono text-neutral-500 flex items-center gap-3 flex-wrap">
          {event.start_date && (
            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" /> {event.start_date}</span>
          )}
          {event.venue && (
            <span className="flex items-center gap-1 truncate"><MapPin className="w-3 h-3" /> {event.venue}</span>
          )}
        </div>
        {contribution && (contribution.matches > 0 || contribution.mom > 0) && (
          <div className="flex gap-2 flex-wrap pt-1">
            <ContribChip label="Matches" value={contribution.matches} />
            {contribution.mom > 0 && <ContribChip label="MOM" value={contribution.mom} accent />}
            {contribution.best_batter > 0 && <ContribChip label="Best batter" value={contribution.best_batter} />}
            {contribution.best_bowler > 0 && <ContribChip label="Best bowler" value={contribution.best_bowler} />}
            {contribution.top_scorer > 0 && <ContribChip label="Top scorer" value={contribution.top_scorer} />}
          </div>
        )}
      </div>
    </Link>
  );
}

function ContribChip({ label, value, accent }) {
  return (
    <span
      className={`text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm tracking-widest ${
        accent ? "bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/30" : "bg-white/5 text-neutral-300 border border-white/10"
      }`}
    >
      {accent && <Award className="w-2.5 h-2.5 inline mr-0.5" />}
      {label} · {value}
    </span>
  );
}
