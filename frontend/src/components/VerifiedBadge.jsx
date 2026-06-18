import { BadgeCheck, Star } from "lucide-react";

/**
 * Compact "Verified" badge + star average for a listing.
 * Pass `listing` (must include rating_average + rating_count + verified)
 * or pass the trio explicitly via `average`, `count`, `verified`.
 */
export default function VerifiedBadge({ listing, average, count, verified, size = "sm" }) {
  const avg = listing?.rating_average ?? average ?? 0;
  const c = listing?.rating_count ?? count ?? 0;
  const v = listing?.verified ?? verified ?? false;

  if (c === 0 && !v) return null;

  const isLg = size === "lg";
  return (
    <span data-testid="verified-badge" className="inline-flex items-center gap-2">
      {v && (
        <span
          className={`inline-flex items-center gap-1 rounded-sm border border-[#84CC16]/40 bg-[#84CC16]/10 text-[#84CC16] font-mono uppercase ${isLg ? "text-[11px] px-2 py-0.5" : "text-[10px] px-1.5 py-0.5"}`}
          title="Verified vendor — 5+ reviews, avg ≥ 4.0"
        >
          <BadgeCheck className={isLg ? "w-3.5 h-3.5" : "w-3 h-3"} />
          Verified
        </span>
      )}
      {c > 0 && (
        <span className={`inline-flex items-center gap-1 text-neutral-300 font-mono ${isLg ? "text-xs" : "text-[10px]"}`}>
          <Star className={`fill-[#FACC15] text-[#FACC15] ${isLg ? "w-3.5 h-3.5" : "w-3 h-3"}`} />
          {avg.toFixed(1)} <span className="text-neutral-500">· {c}</span>
        </span>
      )}
    </span>
  );
}
