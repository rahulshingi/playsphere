import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  DashboardShell, KpiDonutCard, StatusPill, PriorityFlag, Avatar,
  SortableTable, ViewToggle, DashboardTabs,
} from "@/components/dashboard/DashboardKit";
import { Filter, Group, Download, Plus, Store } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

/**
 * Vendor Overview (iter 47) — Pepper-style dark shell tailored to vendor needs.
 *
 * KPI donuts:
 *   • Today's utilisation   — slots taken vs still open today
 *   • Bookings mix          — Platform vs Offline (last 7 days)
 *   • Booking status        — pending / confirmed / completed / expired
 *   • Revenue split         — platform receivable, offline collected, commission owed
 *
 * Table: unified bookings (platform + offline) with bulk actions:
 *   • Mark arrived (bulk)   → POST /vendor-bookings/{id}/check-in or /vendor/private-bookings/{id}/check-in
 *   • Mark no-show (bulk)   → POST corresponding /no-show
 *   • Export CSV
 *
 * Board view: 5-column Kanban by status.
 */
export default function VendorOverview() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [online, setOnline] = useState([]);
  const [offline, setOffline] = useState([]);
  const [listings, setListings] = useState([]);
  const [tab, setTab] = useState("overview");
  const [view, setView] = useState("table");
  const [range, setRange] = useState("week");

  const load = () => {
    api.get("/vendor-bookings").then((r) => setOnline(r.data || [])).catch(() => {});
    api.get("/vendor/private-bookings").then((r) => setOffline(r.data || [])).catch(() => {});
    api.get("/vendors/me/listings").then((r) => setListings(r.data || [])).catch(() => {});
  };
  useEffect(() => {
    if (!ready) return;
    if (!user || user.role !== "vendor") { nav("/login?next=/vendor/overview"); return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, user]);

  // ---- Consolidated rows (platform + offline) ----
  const rows = useMemo(() => {
    const mapRow = (b, source) => ({
      id: b.id,
      title: b.listing_title || (source === "platform" ? "Booking" : "Offline slot"),
      customer: b.company_name || b.hr_email || b.client_name || "—",
      date: b.requested_date || "—",
      time: `${b.start_time}–${b.end_time}`,
      amount: b.total ?? b.amount ?? b.price ?? 0,
      currency: b.currency || "INR",
      source,
      status: (b.status || "pending").toLowerCase(),
      priority: (b.total ?? b.amount ?? 0) > 5000 ? "urgent" : (b.total ?? b.amount ?? 0) > 2000 ? "high" : "normal",
      raw: b,
    });
    const inRangeFn = (dateStr) => {
      if (range === "all" || !dateStr) return true;
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return false;
      const now = new Date();
      if (range === "today") return d.toDateString() === now.toDateString();
      const days = range === "week" ? 7 : 30;
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - (days - 1));
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
      return d >= start && d < end;
    };
    const all = [...online.map((b) => mapRow(b, "platform")), ...offline.map((b) => mapRow(b, "offline"))];
    return all.filter((r) => inRangeFn(r.date)).sort((a, b) => (b.date || "").localeCompare(a.date || ""));
  }, [online, offline, range]);

  // ---- KPI donut data ----
  const utilKpi = useMemo(() => {
    const today = new Date().toISOString().slice(0, 10);
    const todayRows = rows.filter((r) => r.date === today);
    const active = todayRows.filter((r) => ["pending", "confirmed", "active"].includes(r.status)).length;
    const done = todayRows.filter((r) => r.status === "completed").length;
    const lost = todayRows.filter((r) => r.status === "expired").length;
    return [
      { name: "Confirmed", value: active, color: "#06B6D4" },
      { name: "Completed", value: done, color: "#84CC16" },
      { name: "No-show", value: lost, color: "#EF4444" },
    ];
  }, [rows]);

  const mixKpi = useMemo(() => [
    { name: "Platform", value: rows.filter((r) => r.source === "platform").length, color: "#84CC16" },
    { name: "Offline", value: rows.filter((r) => r.source === "offline").length, color: "#F59E0B" },
  ], [rows]);

  const statusKpi = useMemo(() => {
    const b = { pending: 0, confirmed: 0, completed: 0, expired: 0 };
    rows.forEach((r) => {
      if (b[r.status] !== undefined) b[r.status] += 1;
      else if (r.status === "vendor_accepted" || r.status === "active") b.confirmed += 1;
      else if (r.status === "no_show") b.expired += 1;
    });
    return [
      { name: "Pending", value: b.pending, color: "#F59E0B" },
      { name: "Confirmed", value: b.confirmed, color: "#06B6D4" },
      { name: "Completed", value: b.completed, color: "#84CC16" },
      { name: "Expired", value: b.expired, color: "#94A3B8" },
    ];
  }, [rows]);

  const revenueKpi = useMemo(() => {
    let platform = 0, offlineRev = 0, commission = 0;
    online.forEach((b) => { platform += Number(b.total || b.price || 0); commission += Number(b.commission_amount || 0); });
    offline.forEach((b) => { offlineRev += Number(b.amount || 0); });
    return [
      { name: "Platform ₹", value: Math.round(platform), color: "#84CC16" },
      { name: "Offline ₹", value: Math.round(offlineRev), color: "#F59E0B" },
      { name: "Commission owed", value: Math.round(commission), color: "#EC4899" },
    ];
  }, [online, offline]);

  // ---- Table columns ----
  const columns = [
    { key: "title", label: "Booking", render: (r) => (
      <div className="flex items-center gap-2">
        <span className={`text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm border ${r.source === "platform" ? "text-[#84CC16] border-[#84CC16]/40" : "text-[#F59E0B] border-[#F59E0B]/40"}`}>
          {r.source === "platform" ? "PLAT" : "OFF"}
        </span>
        <span className="font-medium text-white truncate max-w-[220px]">{r.title}</span>
      </div>
    )},
    { key: "customer", label: "Customer", render: (r) => (
      <div className="flex items-center gap-2">
        <Avatar name={r.customer} size={22} />
        <span className="truncate max-w-[160px]">{r.customer}</span>
      </div>
    )},
    { key: "date", label: "Date", render: (r) => (
      <div><div>{r.date}</div><div className="text-[10px] text-neutral-500">{r.time}</div></div>
    )},
    { key: "amount", label: "Amount", align: "right", render: (r) => fmtPrice(r.amount, r.currency) },
    { key: "status", label: "Status", render: (r) => <StatusPill status={r.status} /> },
    { key: "priority", label: "Priority", render: (r) => <PriorityFlag level={r.priority} /> },
  ];

  const doBulk = async (rowsSel, endpointFn, verb) => {
    let ok = 0;
    for (const r of rowsSel) {
      try { await api.post(endpointFn(r)); ok += 1; } catch (e) { /* noop */ }
    }
    toast.success(`${ok}/${rowsSel.length} ${verb}`);
    load();
  };

  const bulkActions = [
    {
      key: "check-in",
      label: "Mark arrived",
      className: "bg-[#84CC16]/15 text-[#84CC16] hover:bg-[#84CC16]/25",
      onClick: (sel) => doBulk(sel, (r) => r.source === "platform" ? `/vendor-bookings/${r.id}/check-in` : `/vendor/private-bookings/${r.id}/check-in`, "marked arrived"),
    },
    {
      key: "no-show",
      label: "Mark no-show",
      className: "bg-[#FF3B30]/15 text-[#FF3B30] hover:bg-[#FF3B30]/25",
      onClick: async (sel) => {
        if (!window.confirm(`Mark ${sel.length} booking(s) as no-show?`)) return;
        await doBulk(sel, (r) => r.source === "platform" ? `/vendor-bookings/${r.id}/no-show` : `/vendor/private-bookings/${r.id}/no-show`, "marked no-show");
      },
    },
    {
      key: "export",
      label: "Export CSV",
      onClick: async (sel) => {
        const header = ["id","title","customer","date","time","amount","status","source"].join(",");
        const body = sel.map((r) => [r.id,r.title,r.customer,r.date,r.time,r.amount,r.status,r.source].map((v) => `"${String(v||"").replace(/"/g,'""')}"`).join(",")).join("\n");
        const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a"); a.href = url; a.download = `vendor-bookings-${new Date().toISOString().slice(0,10)}.csv`; a.click();
        URL.revokeObjectURL(url);
        toast.success(`Exported ${sel.length} rows`);
      },
    },
  ];

  const headerRight = (
    <Button data-testid="vendor-add-offline" onClick={() => nav("/vendor/dashboard?tab=offline")} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-full h-9 px-4 gap-1.5">
      <Plus className="w-4 h-4" /> Add offline booking
    </Button>
  );

  return (
    <DashboardShell activePath="home" title="Vendor Dashboard" headerRight={headerRight}>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Overview</h1>
          <p className="text-sm text-neutral-500 mt-1">{listings.length} listings · updated live</p>
        </div>
        <div className="flex items-center gap-2">
          <DashboardTabs
            tabs={[{ key: "today", label: "Today" }, { key: "week", label: "Last 7d" }, { key: "month", label: "Last 30d" }, { key: "all", label: "All" }]}
            active={range}
            onChange={setRange}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8" data-testid="vendor-kpi-grid">
        <KpiDonutCard testid="kpi-utilisation" title="Today" data={utilKpi} totalLabel="Slots" onClick={() => setRange("today")} />
        <KpiDonutCard testid="kpi-mix" title="Booking mix" data={mixKpi} onClick={() => nav("/vendor/dashboard")} />
        <KpiDonutCard testid="kpi-status" title="By status" data={statusKpi} onClick={() => setView("board")} />
        <KpiDonutCard testid="kpi-revenue" title="Revenue" data={revenueKpi} totalLabel="Total ₹" onClick={() => nav("/vendor/dashboard")} />
      </div>

      <div className="flex items-center justify-between mb-3">
        <ViewToggle view={view} onChange={setView} />
        <div className="flex items-center gap-1">
          <button data-testid="vendor-toolbar-listings" onClick={() => nav("/vendor/dashboard")} className="text-xs text-neutral-400 px-3 py-1.5 hover:bg-white/5 rounded-md inline-flex items-center gap-1.5">
            <Store className="w-3.5 h-3.5" /> Listings
          </button>
          <button data-testid="vendor-toolbar-filter" className="text-xs text-neutral-400 px-3 py-1.5 hover:bg-white/5 rounded-md inline-flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" /> Filters
          </button>
        </div>
      </div>

      {view === "table" ? (
        <SortableTable columns={columns} data={rows} testid="vendor-bookings-table" bulkActions={bulkActions} />
      ) : (
        <BoardView rows={rows} />
      )}

      <div className="mt-6 flex items-center justify-between text-xs text-neutral-500">
        <span>{rows.length} bookings in view</span>
        <Link to="/vendor/dashboard" data-testid="vendor-back-classic" className="text-[#06B6D4] hover:underline">
          → Classic vendor dashboard
        </Link>
      </div>
    </DashboardShell>
  );
}

function BoardView({ rows }) {
  const columns = ["pending", "confirmed", "completed", "expired", "cancelled"];
  const grouped = columns.reduce((acc, key) => {
    acc[key] = rows.filter((r) => r.status === key || (key === "confirmed" && (r.status === "vendor_accepted" || r.status === "active")) || (key === "expired" && r.status === "no_show"));
    return acc;
  }, {});
  return (
    <div data-testid="vendor-board-view" className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {columns.map((key) => (
        <div key={key} className="bg-[#141414] rounded-xl border border-white/10 p-3">
          <div className="flex items-center justify-between mb-3">
            <StatusPill status={key} />
            <span className="text-xs text-neutral-500">{grouped[key].length}</span>
          </div>
          <div className="space-y-2 min-h-[80px]">
            {grouped[key].map((r) => (
              <div key={r.id} className="border border-white/10 bg-black/30 rounded-lg p-3 hover:border-white/20 transition-colors">
                <div className="text-sm font-medium text-white truncate">{r.title}</div>
                <div className="text-xs text-neutral-500 mt-1">{r.customer}</div>
                <div className="text-xs font-mono text-neutral-300 mt-2 flex items-center justify-between">
                  <span>{fmtPrice(r.amount, r.currency)}</span>
                  <PriorityFlag level={r.priority} />
                </div>
              </div>
            ))}
            {grouped[key].length === 0 && <div className="text-xs text-neutral-600 text-center py-6">Empty</div>}
          </div>
        </div>
      ))}
    </div>
  );
}
