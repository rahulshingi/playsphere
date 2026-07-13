import { useEffect, useState } from "react";
import api from "@/lib/api";
import { fmtPrice } from "@/lib/currency";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { CheckCircle2, XCircle, RotateCcw, ClipboardList, Clock } from "lucide-react";

/**
 * VendorOfflineBookingsList — flat, simple list of every offline
 * (walk-in / private) booking on the Offline-mode tab. This is what
 * the vendor asked for after finding the KPI view too abstract —
 * a plain list showing each row with its status, amount and actions.
 *
 * All actions defer to the same `/vendor/private-bookings/…/…` endpoints
 * used by the UnifiedBookingsTable to keep behaviour consistent.
 */
export default function VendorOfflineBookingsList() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);
  const [statusFilter, setStatusFilter] = useState("all");

  const load = () => {
    setLoading(true);
    api.get("/vendor/private-bookings")
      .then((r) => setRows(r.data || []))
      .catch(() => setRows([]))
      .finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  const doAction = async (id, path, successMsg) => {
    setBusy(id);
    try {
      await api.post(`/vendor/private-bookings/${id}/${path}`);
      toast.success(successMsg);
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    } finally { setBusy(null); }
  };

  const filtered = statusFilter === "all" ? rows : rows.filter((r) => (r.status || "").toLowerCase() === statusFilter);

  const counts = rows.reduce((acc, r) => { acc[r.status] = (acc[r.status] || 0) + 1; return acc; }, {});
  const TABS = [
    { key: "all", label: `All (${rows.length})` },
    { key: "active", label: `Active (${counts.active || 0})` },
    { key: "completed", label: `Completed (${counts.completed || 0})` },
    { key: "expired", label: `Expired (${counts.expired || 0})` },
    { key: "cancelled", label: `Cancelled (${counts.cancelled || 0})` },
  ];

  return (
    <div data-testid="offline-bookings-list" className="mt-6 border border-white/10 rounded-sm bg-[#0f0f0f]">
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <ClipboardList className="w-4 h-4 text-[#FACC15]" />
          <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15]">/ Offline bookings</div>
        </div>
        <div className="flex gap-1 flex-wrap">
          {TABS.map((t) => (
            <button
              key={t.key}
              data-testid={`offline-filter-${t.key}`}
              onClick={() => setStatusFilter(t.key)}
              className={`text-[10px] font-mono uppercase px-2 py-1 rounded-sm border ${statusFilter === t.key ? "bg-[#FACC15] border-[#FACC15] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <div className="p-6 text-center text-neutral-500 text-sm">Loading…</div>}

      {!loading && filtered.length === 0 && (
        <div className="p-8 text-center text-neutral-500 text-sm">
          No {statusFilter === "all" ? "" : statusFilter + " "}offline bookings yet.
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
              <tr>
                <th className="text-left px-3 py-2">Customer</th>
                <th className="text-left px-3 py-2">Date · Slot</th>
                <th className="text-right px-3 py-2">Amount</th>
                <th className="text-right px-3 py-2">OT</th>
                <th className="text-left px-3 py-2">Status</th>
                <th className="text-right px-3 py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id} data-testid={`offline-row-${r.id}`} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="px-3 py-2 text-neutral-200">
                    <div>{r.client_name}</div>
                    <div className="text-[10px] font-mono text-neutral-500">{r.client_phone || r.client_email || "—"}</div>
                  </td>
                  <td className="px-3 py-2 font-mono text-neutral-400">
                    <div>{r.requested_date}</div>
                    <div className="text-[10px] text-neutral-500 flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> {r.start_time}–{r.end_time}</div>
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{fmtPrice(r.amount, r.currency || "INR")}</td>
                  <td className="px-3 py-2 text-right font-mono text-[#FACC15]">
                    {r.overtime_amount > 0 ? (
                      <div>
                        <div>{fmtPrice(r.overtime_amount, r.currency || "INR")}</div>
                        <div className="text-[10px]">{r.overtime_minutes}m</div>
                      </div>
                    ) : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${statusChipClass(r.status)}`}>
                      {r.status}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    <RowActions row={r} busy={busy === r.id} onAction={doAction} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function statusChipClass(s) {
  s = (s || "").toLowerCase();
  if (s === "completed") return "text-[#84CC16] border-[#84CC16]/40 bg-[#84CC16]/10";
  if (s === "active" || s === "confirmed") return "text-[#06B6D4] border-[#06B6D4]/40 bg-[#06B6D4]/10";
  if (s === "expired" || s === "no_show") return "text-[#FF3B30] border-[#FF3B30]/40 bg-[#FF3B30]/10";
  return "text-neutral-400 border-white/10 bg-white/5";
}

function RowActions({ row, busy, onAction }) {
  const s = (row.status || "").toLowerCase();
  if (s === "active" || s === "confirmed") {
    return (
      <div className="flex gap-1 justify-end">
        <Button
          size="sm"
          data-testid={`offline-complete-${row.id}`}
          disabled={busy}
          onClick={() => onAction(row.id, "check-in", "Marked completed")}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black h-7 rounded-sm text-[10px] px-2"
        >
          <CheckCircle2 className="w-3 h-3 mr-1" /> Complete
        </Button>
        <Button
          size="sm"
          variant="outline"
          data-testid={`offline-noshow-${row.id}`}
          disabled={busy}
          onClick={() => onAction(row.id, "no-show", "Marked no-show")}
          className="border-[#FF3B30]/40 bg-transparent text-[#FF3B30] hover:bg-[#FF3B30]/10 h-7 rounded-sm text-[10px] px-2"
        >
          <XCircle className="w-3 h-3 mr-1" /> No-show
        </Button>
      </div>
    );
  }
  if (s === "expired" || s === "cancelled" || s === "no_show") {
    return (
      <Button
        size="sm"
        variant="outline"
        data-testid={`offline-reopen-${row.id}`}
        disabled={busy}
        onClick={() => onAction(row.id, "reopen", "Booking reopened")}
        className="border-[#06B6D4]/40 bg-transparent text-[#06B6D4] hover:bg-[#06B6D4]/10 h-7 rounded-sm text-[10px] px-2"
      >
        <RotateCcw className="w-3 h-3 mr-1" /> Reopen
      </Button>
    );
  }
  return null;
}
