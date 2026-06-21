import { useEffect, useState } from "react";
import api from "@/lib/api";
import { STATS_SCHEMAS, formatStatValue } from "@/lib/sportStatsSchema";
import { TrendingUp, Sparkles } from "lucide-react";

/** Pull-down stats and pick the value to display: manual override wins, else auto. */
function pickValue(field, autoBag, manualBag) {
  if (manualBag && Object.prototype.hasOwnProperty.call(manualBag, field.key)) {
    return manualBag[field.key];
  }
  return autoBag?.[field.key];
}

function StatCell({ field, value }) {
  return (
    <div className="bg-[#0a0a0a] p-3" data-testid={`stat-${field.key}`}>
      <div className="font-mono text-lg text-white">{formatStatValue(value, field)}</div>
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 mt-0.5">{field.label}</div>
    </div>
  );
}

/**
 * Read-only career-stats dashboard. Renders one card per sport that the player is
 * interested in. Cricket shows auto-computed matches/runs/wickets/etc. from completed
 * Kreeda Nation fixtures; other sports show whatever the player entered in their manual
 * lifetime_stats.
 *
 * Pass `interestedSports` so the order matches the player's profile chip picker. If the
 * player removed a sport from their interests, its stats card is hidden (but the data
 * itself is preserved in lifetime_stats so it reappears when they re-add the sport).
 */
export default function SportStatsDashboard({ profileId, interestedSports }) {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    if (!profileId) return;
    api.get(`/players/profiles/${profileId}/stats`).then((r) => setStats(r.data)).catch(() => setStats({}));
  }, [profileId]);

  if (!stats) {
    return <div className="border border-white/10 rounded-sm bg-[#141414] p-6 text-xs font-mono text-neutral-500">Loading career stats…</div>;
  }

  const sports = (interestedSports?.length ? interestedSports : Object.keys(stats));
  if (sports.length === 0) return null;

  return (
    <div className="space-y-3" data-testid="player-stats-dashboard">
      <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16] flex items-center gap-2">
        <TrendingUp className="w-3 h-3" /> Career stats
      </div>
      {sports.map((sport) => {
        const schema = STATS_SCHEMAS[sport];
        if (!schema) return null;
        const bag = stats[sport] || { auto: {}, manual: {} };
        // Combine auto + manual fields. Filter out fields with no value at all (so empty cards don't bloat the UI).
        // Text fields are shown as a separate achievement banner below, so exclude them from the grid here.
        const allFields = [...schema.auto, ...schema.manual].filter((f) => f.type !== "text");
        const rowsWithData = allFields
          .map((f) => ({ f, v: pickValue(f, bag.auto, bag.manual) }))
          .filter(({ v }) => v != null && v !== "" && v !== 0)
          .map(({ f, v }) => [f, v]);
        // Also show fields that have value === 0 from `auto` (matches=0 etc.) only if the player
        // has any auto-tracked data at all.
        const hasAnyAuto = schema.auto.some((f) => (bag.auto?.[f.key] ?? 0) > 0);
        const displayedFields = rowsWithData.length
          ? rowsWithData
          : (hasAnyAuto ? schema.auto.map((f) => [f, bag.auto?.[f.key]]) : []);

        return (
          <div key={sport} data-testid={`stats-card-${sport}`} className="border border-white/10 rounded-sm bg-[#141414] p-4">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: schema.color }} />
                <div className="font-display tracking-wider text-lg">{schema.label.toUpperCase()}</div>
                {hasAnyAuto && (
                  <span className="text-[9px] font-mono uppercase text-[#84CC16] border border-[#84CC16]/40 rounded-sm px-1.5 py-0.5 flex items-center gap-1">
                    <Sparkles className="w-2.5 h-2.5" /> auto-tracked
                  </span>
                )}
              </div>
            </div>
            {displayedFields.length === 0 ? (
              <div className="text-xs font-mono text-neutral-500 mt-3">No stats recorded yet.</div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-px bg-white/10 mt-3 border border-white/10 rounded-sm overflow-hidden">
                {displayedFields.map(([f, v]) => <StatCell key={f.key} field={f} value={v} />)}
              </div>
            )}
            {bag.manual?.notable_achievement && (
              <div className="mt-3 text-xs font-mono text-[#FACC15] border-l-2 border-[#FACC15]/50 pl-2">
                ✦ {bag.manual.notable_achievement}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
