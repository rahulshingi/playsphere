import { useEffect, useMemo, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { CheckCircle2, XCircle, Filter, Calendar as CalendarIcon, Clock, Users } from "lucide-react";
import { fmtPrice } from "@/lib/currency";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

/**
 * Unified booking table for the vendor dashboard (Task 44 · Feb 2026).
 *
 * Merges two data sources:
 *   • `/vendor-bookings`         — PLATFORM (Kreeda Nation online) bookings
 *   • `/vendor/private-bookings` — OFFLINE (vendor's own walk-ins)
 *
 * Adds:
 *   • Range filter: Today / This week / This month / All
 *   • Status filter: All / Active / Completed / Expired / Cancelled
 *   • Source chip on each row (PLATFORM / OFFLINE)
 *   • Vendor actions: Mark arrived (→ completed) + No-show (→ expired)
 *   • Auto-expired rows land here automatically via backend lazy-sweep.
 */
const RANGE_OPTIONS = [
  { key: "today", label: "Today" },
  { key: "week", label: "Last 7 days" },
  { key: "month", label: "Last 30 days" },
  { key: "all", label: "All" },
];
const STATUS_OPTIONS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "confirmed", label: "Confirmed" },
  { key: "active", label: "Active" },
  { key: "completed", label: "Completed" },
  { key: "expired", label: "Expired · No-show" },
  { key: "cancelled", label: "Cancelled" },
];

function classifyStatus(row) {
  const s = row.status || "";
  if (s === "vendor_accepted" || s === "confirmed") return "confirmed";
  if (s === "pending") return "pending";
  if (s === "active") return "active";
  if (s === "completed" || s === "fulfilled") return "completed";
  if (s === "expired" || s === "no_show") return "expired";
  if (s === "cancelled" || s === "declined" || s === "rejected" || s === "vendor_declined") return "cancelled";
  return s;
}

function statusChipClass(bucket) {
  switch (bucket) {
    case "completed": return "text-[#84CC16] border-[#84CC16]/40";
    case "confirmed": return "text-[#06B6D4] border-[#06B6D4]/40";
    case "active": return "text-[#06B6D4] border-[#06B6D4]/40";
    case "pending": return "text-amber-400 border-amber-500/40";
    case "expired": return "text-[#FF3B30] border-[#FF3B30]/40";
    case "cancelled": return "text-neutral-500 border-white/10";
    default: return "text-neutral-400 border-white/10";
  }
}

function inRange(dateStr, key) {
  if (!dateStr) return false;
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return false;
  const now = new Date();
  if (key === "today") {
    return d.toDateString() === now.toDateString();
  }
  // "Last 7 days" — strictly past-7-day window ending today (inclusive of both).
  if (key === "week") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 6);
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    return d >= start && d < end;
  }
  // "Last 30 days" — strictly past-30-day window ending today (inclusive).
  if (key === "month") {
    const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 29);
    const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
    return d >= start && d < end;
  }
  return true;
}

export default function UnifiedBookingsTable() {
  const [online, setOnline] = useState([]);
  const [offline, setOffline] = useState([]);
  const [range, setRange] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [busy, setBusy] = useState(null);
  // No-show confirmation dialog — row-scoped
  const [noShowTarget, setNoShowTarget] = useState(null);

  const load = () => {
    api.get("/vendor-bookings").then((r) => setOnline(r.data)).catch(() => {});
    api.get("/vendor/private-bookings").then((r) => setOffline(r.data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const rows = useMemo(() => {
    const onlineRows = (online || []).map((b) => ({
      id: b.id,
      source: "platform",
      customer: b.company_name || b.hr_email || "—",
      listing_title: b.listing_title,
      date: b.requested_date,
      time: `${b.start_time}–${b.end_time}`,
      amount: b.total ?? b.price,
      currency: b.currency,
      status: b.status,
      bucket: classifyStatus(b),
      raw: b,
    }));
    const offlineRows = (offline || []).map((b) => ({
      id: b.id,
      source: "offline",
      customer: b.client_name,
      listing_title: b.listing_id,  // no title for offline
      date: b.requested_date,
      time: `${b.start_time}–${b.end_time}`,
      amount: b.amount,
      currency: b.currency,
      status: b.status,
      bucket: classifyStatus(b),
      raw: b,
    }));
    return [...onlineRows, ...offlineRows]
      .filter((r) => range === "all" ? true : inRange(r.date, range))
      .filter((r) => statusFilter === "all" ? true : r.bucket === statusFilter)
      .sort((a, b) => (b.date || "").localeCompare(a.date || "") || (b.time || "").localeCompare(a.time || ""));
  }, [online, offline, range, statusFilter]);

  const stats = useMemo(() => {
    const total = rows.length;
    const completed = rows.filter((r) => r.bucket === "completed").length;
    const expired = rows.filter((r) => r.bucket === "expired").length;
    const active = rows.filter((r) => ["pending", "confirmed", "active"].includes(r.bucket)).length;
    return { total, completed, expired, active };
  }, [rows]);

  const markArrived = async (row) => {
    setBusy(row.id);
    try {
      const url = row.source === "platform"
        ? `/vendor-bookings/${row.id}/check-in`
        : `/vendor/private-bookings/${row.id}/check-in`;
      await api.post(url);
      toast.success("Customer arrival marked");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setBusy(null);
    }
  };

  const markNoShow = async (row) => {
    setBusy(row.id);
    try {
      const url = row.source === "platform"
        ? `/vendor-bookings/${row.id}/no-show`
        : `/vendor/private-bookings/${row.id}/no-show`;
      await api.post(url);
      toast.success("Marked as no-show");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setBusy(null);
      setNoShowTarget(null);
    }
  };

  return (
    <div data-testid="unified-bookings-table" className="border border-white/10 rounded-sm bg-[#0f0f0f]">
      {/* Header — filters + stats */}
      <div className="p-4 border-b border-white/10 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-neutral-500">
            <Filter className="w-3 h-3" /> When
          </div>
          <div className="flex gap-1">
            {RANGE_OPTIONS.map((o) => (
              <button
                key={o.key}
                data-testid={`ub-range-${o.key}`}
                onClick={() => setRange(o.key)}
                className={`px-2.5 py-1 text-[10px] font-mono uppercase rounded-sm border ${range === o.key ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-neutral-500 ml-2">
            <CalendarIcon className="w-3 h-3" /> Status
          </div>
          <div className="flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((o) => (
              <button
                key={o.key}
                data-testid={`ub-status-${o.key}`}
                onClick={() => setStatusFilter(o.key)}
                className={`px-2.5 py-1 text-[10px] font-mono uppercase rounded-sm border ${statusFilter === o.key ? "bg-[#06B6D4] border-[#06B6D4] text-black" : "border-white/10 text-neutral-400 hover:bg-white/5"}`}
              >
                {o.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-3 text-[10px] font-mono uppercase tracking-widest">
          <span className="text-neutral-400" data-testid="ub-total"><span className="text-white text-sm">{stats.total}</span> total</span>
          <span className="text-[#06B6D4]"><span className="text-white text-sm">{stats.active}</span> active</span>
          <span className="text-[#84CC16]"><span className="text-white text-sm">{stats.completed}</span> done</span>
          <span className="text-[#FF3B30]"><span className="text-white text-sm">{stats.expired}</span> no-show</span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#141414] font-mono text-[10px] uppercase tracking-widest text-neutral-500">
            <tr>
              <th className="text-left px-4 py-3">Source</th>
              <th className="text-left px-3 py-3">Customer</th>
              <th className="text-left px-3 py-3">Date · Time</th>
              <th className="text-right px-3 py-3">Amount</th>
              <th className="text-left px-3 py-3">Status</th>
              <th className="text-right px-3 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const canMarkArrived = ["pending", "confirmed", "active"].includes(r.bucket);
              return (
                <tr key={`${r.source}-${r.id}`} data-testid={`ub-row-${r.id}`} className="border-t border-white/5 hover:bg-white/[0.02]">
                  <td className="px-4 py-3">
                    <span className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm border ${r.source === "platform" ? "text-[#84CC16] border-[#84CC16]/40" : "text-[#FACC15] border-[#FACC15]/40"}`}>
                      {r.source === "platform" ? "PLATFORM" : "OFFLINE"}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-neutral-200">{r.customer}</td>
                  <td className="px-3 py-3 font-mono text-neutral-400">
                    <div>{r.date}</div>
                    <div className="text-[10px] text-neutral-500 flex items-center gap-1"><Clock className="w-2.5 h-2.5" />{r.time}</div>
                  </td>
                  <td className="px-3 py-3 text-right font-mono">{fmtPrice(r.amount, r.currency)}</td>
                  <td className="px-3 py-3">
                    <span className={`text-[10px] font-mono uppercase border rounded-sm px-2 py-0.5 ${statusChipClass(r.bucket)}`}>
                      {r.bucket}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">
                    {canMarkArrived && (
                      <div className="flex gap-1 justify-end">
                        <Button
                          size="sm"
                          data-testid={`ub-arrived-${r.id}`}
                          disabled={busy === r.id}
                          onClick={() => markArrived(r)}
                          className="bg-[#84CC16] hover:bg-[#65A30D] text-black h-7 rounded-sm text-[10px] px-2"
                        >
                          <CheckCircle2 className="w-3 h-3 mr-1" /> Arrived
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          data-testid={`ub-noshow-${r.id}`}
                          disabled={busy === r.id}
                          onClick={() => setNoShowTarget(r)}
                          className="border-[#FF3B30]/40 bg-transparent text-[#FF3B30] hover:bg-[#FF3B30]/10 h-7 rounded-sm text-[10px] px-2"
                        >
                          <XCircle className="w-3 h-3 mr-1" /> No-show
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-10 text-neutral-500 text-xs">
                  <Users className="w-4 h-4 mx-auto mb-2 opacity-40" />
                  No bookings match the current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* No-show confirmation dialog (P2 UX polish — replaces window.confirm) */}
      <AlertDialog open={!!noShowTarget} onOpenChange={(v) => !v && setNoShowTarget(null)}>
        <AlertDialogContent data-testid="ub-noshow-dialog" className="bg-[#0c0c0c] border-white/10 text-white">
          <AlertDialogHeader>
            <AlertDialogTitle>Mark customer as no-show?</AlertDialogTitle>
            <AlertDialogDescription className="text-neutral-400">
              The slot will be marked <span className="text-[#FF3B30] font-semibold">expired</span>.
              This is reversible only by the platform admin.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="ub-noshow-cancel" className="bg-transparent border-white/10 text-neutral-400 hover:bg-white/5">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="ub-noshow-confirm"
              onClick={() => noShowTarget && markNoShow(noShowTarget)}
              className="bg-[#FF3B30] hover:bg-[#d72f24] text-white"
            >
              Yes, mark no-show
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
