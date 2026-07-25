import { useEffect, useState } from "react";
import api from "@/lib/api";
import { UserCheck, Clock, Users } from "lucide-react";

/**
 * Vendor's live check-in snapshot for today:
 *   - checked_in_count / expected_count
 *   - not_yet_arrived
 *   - avg_delay_minutes (positive = late arrivals, negative = early)
 *
 * Auto-refreshes every 60 seconds so a vendor with the dashboard open sees
 * arrivals stream in without a manual reload.
 */
export default function VendorCheckinAnalytics() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = () => api.get("/vendor/checkin-analytics/today")
      .then((r) => { if (alive) setData(r.data); })
      .catch(() => { /* silent — widget is passive */ });
    load();
    const iv = setInterval(load, 60000);
    return () => { alive = false; clearInterval(iv); };
  }, []);

  if (!data) return null;

  const { checked_in_count, expected_count, not_yet_arrived, avg_delay_minutes } = data;
  const delayLabel = avg_delay_minutes == null
    ? "—"
    : `${avg_delay_minutes > 0 ? "+" : ""}${avg_delay_minutes} min`;
  const delayHint = avg_delay_minutes == null ? ""
    : avg_delay_minutes > 5 ? "late" : avg_delay_minutes < -5 ? "early" : "on time";

  return (
    <div data-testid="vendor-checkin-analytics"
         className="grid grid-cols-3 gap-3 border border-white/10 rounded-sm bg-[#141414] p-4">
      <Metric icon={UserCheck} label="Checked in today"
              value={`${checked_in_count}/${expected_count}`}
              accent="#84CC16"
              testid="analytics-checked-in" />
      <Metric icon={Users} label="Not yet arrived"
              value={not_yet_arrived}
              accent="#FACC15"
              testid="analytics-pending" />
      <Metric icon={Clock} label="Avg arrival delay"
              value={delayLabel}
              hint={delayHint}
              accent="#06B6D4"
              testid="analytics-delay" />
    </div>
  );
}

function Metric({ icon: Icon, label, value, accent, hint, testid }) {
  return (
    <div data-testid={testid} className="flex flex-col gap-1 min-w-0">
      <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 flex items-center gap-1.5">
        <Icon className="w-3 h-3 shrink-0" style={{ color: accent }} />
        <span className="truncate">{label}</span>
      </div>
      <div className="font-display text-2xl tracking-wide" style={{ color: accent }}>{value}</div>
      {hint && <div className="text-[10px] font-mono uppercase text-neutral-500">{hint}</div>}
    </div>
  );
}
