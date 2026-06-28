import { useEffect, useState } from "react";
import api from "@/lib/api";

/**
 * UtilizationBars — fetches /memberships/purchase/{id}/utilization and renders
 * two side-by-side progress bars: sessions used vs allowed, days elapsed vs total.
 * Used on /my-memberships (buyer view) and inside VendorPurchaseRequests (vendor view).
 */
export default function UtilizationBars({ purchaseId, compact = false }) {
  const [u, setU] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.get(`/memberships/purchase/${purchaseId}/utilization`)
      .then((r) => { if (!cancelled) setU(r.data); })
      .catch(() => { if (!cancelled) setU(null); });
    return () => { cancelled = true; };
  }, [purchaseId]);

  if (!u) return null;

  return (
    <div data-testid={`util-${purchaseId}`} className={`grid grid-cols-2 gap-3 ${compact ? "mt-2" : "mt-3"}`}>
      <Bar
        testid={`util-sessions-${purchaseId}`}
        label="Sessions"
        used={u.sessions_used}
        total={u.sessions_allowed}
        percent={u.sessions_percent}
        color="#06B6D4"
        compact={compact}
        suffixFallback="Unlimited"
      />
      <Bar
        testid={`util-days-${purchaseId}`}
        label="Days"
        used={u.days_elapsed}
        total={u.days_total}
        percent={u.days_percent}
        color="#EC4899"
        compact={compact}
        rightHint={u.days_remaining != null ? `${u.days_remaining}d left` : null}
      />
    </div>
  );
}

function Bar({ testid, label, used, total, percent, color, compact, suffixFallback, rightHint }) {
  const showPct = percent != null;
  const right = total == null
    ? (suffixFallback || "—")
    : `${used}/${total}`;
  const pct = Math.max(0, Math.min(100, Number(percent || 0)));
  return (
    <div data-testid={testid} className="border border-white/10 rounded-sm bg-black/30 p-2">
      <div className={`flex items-center justify-between font-mono uppercase text-neutral-500 ${compact ? "text-[9px]" : "text-[10px]"}`}>
        <span>{label}</span>
        <span className="text-neutral-300 normal-case">{right}{rightHint && <span className="ml-1 text-neutral-500 lowercase">· {rightHint}</span>}</span>
      </div>
      <div className="mt-1 h-1.5 rounded-sm bg-white/10 overflow-hidden">
        <div
          data-testid={`${testid}-fill`}
          className="h-full rounded-sm transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      {showPct && (
        <div className={`mt-0.5 font-mono text-neutral-500 ${compact ? "text-[9px]" : "text-[10px]"}`}>{pct}%</div>
      )}
    </div>
  );
}
