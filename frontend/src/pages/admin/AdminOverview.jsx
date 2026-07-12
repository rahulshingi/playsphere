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
import { Filter, Group, Download, Plus } from "lucide-react";
import { fmtPrice } from "@/lib/currency";

/**
 * Admin Overview — iter 46 (Feb 28, 2026).
 *
 * Light-themed workspace scoped via `.dashboard-light` (see index.css). Only
 * this route + its future 5 role siblings adopt the light palette; the rest
 * of the app (Home, Events, Hire, Profile) remains dark on Kreeda lime.
 *
 * Data sources — all EXISTING endpoints, no schema change:
 *   /api/admin/bookings-analytics?range=week  → KPI + status distribution
 *   /api/events                               → events by status (upcoming/live/completed/cancelled)
 *   /api/vendors                              → vendor + user growth
 *   /api/vendor-bookings                      → recent booking rows for the table
 */
export default function AdminOverview() {
  const { user, ready } = useAuth();
  const nav = useNavigate();
  const [analytics, setAnalytics] = useState(null);
  const [events, setEvents] = useState([]);
  const [vendors, setVendors] = useState([]);
  const [players, setPlayers] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [tab, setTab] = useState("overview");
  const [view, setView] = useState("table");

  useEffect(() => {
    if (!ready) return;
    if (!user || !["platform_admin", "admin"].includes(user.role)) {
      nav("/login?next=/platform-admin/overview");
      return;
    }
    Promise.allSettled([
      api.get("/admin/bookings-analytics?range=week"),
      api.get("/events?scope=all"),
      api.get("/vendors"),
      api.get("/players/profiles?limit=200"),
      api.get("/vendor-bookings"),
    ]).then(([a, e, v, p, b]) => {
      if (a.status === "fulfilled") setAnalytics(a.value.data);
      if (e.status === "fulfilled") setEvents(e.value.data || []);
      if (v.status === "fulfilled") setVendors(v.value.data || []);
      if (p.status === "fulfilled") setPlayers(p.value.data || []);
      if (b.status === "fulfilled") setBookings(b.value.data || []);
    });
  }, [ready, user, nav]);

  // ---- KPI donut data ------------------------------------------------------
  const bookingsKpi = useMemo(() => {
    const t = analytics?.totals || {};
    return [
      { name: "Platform", value: t.online_bookings || 0, color: "#06B6D4" },
      { name: "Offline", value: t.offline_bookings || 0, color: "#F59E0B" },
    ];
  }, [analytics]);

  const revenueKpi = useMemo(() => {
    const t = analytics?.totals || {};
    return [
      { name: "Platform ₹", value: Math.round(t.online_revenue || 0), color: "#84CC16" },
      { name: "Commission", value: Math.round(t.commission_earned || 0), color: "#EC4899" },
      { name: "Offline ₹", value: Math.round(t.offline_revenue || 0), color: "#F59E0B" },
    ];
  }, [analytics]);

  const eventsKpi = useMemo(() => {
    const buckets = { upcoming: 0, ongoing: 0, completed: 0, cancelled: 0 };
    events.forEach((e) => {
      const s = e.status || "upcoming";
      if (buckets[s] !== undefined) buckets[s] += 1;
      else buckets.upcoming += 1;
    });
    return [
      { name: "Upcoming", value: buckets.upcoming, color: "#06B6D4" },
      { name: "Ongoing", value: buckets.ongoing, color: "#84CC16" },
      { name: "Completed", value: buckets.completed, color: "#EC4899" },
      { name: "Cancelled", value: buckets.cancelled, color: "#94A3B8" },
    ];
  }, [events]);

  const ecosystemKpi = useMemo(() => [
    { name: "Players", value: players.length, color: "#84CC16" },
    { name: "Vendors", value: vendors.length, color: "#06B6D4" },
    { name: "Events", value: events.length, color: "#EC4899" },
    { name: "HR & Org", value: (analytics?.totals?.hr_count || 0) + (analytics?.totals?.org_count || 0), color: "#F59E0B" },
  ], [players, vendors, events, analytics]);

  // ---- Bookings table rows -------------------------------------------------
  const tableRows = useMemo(() => {
    return (bookings || []).slice(0, 25).map((b) => ({
      id: b.id,
      title: b.listing_title || "Booking",
      created_by: b.hr_email || b.company_name || "—",
      created_date: b.created_at ? b.created_at.slice(0, 10) : "—",
      amount: b.total || b.price || 0,
      currency: b.currency || "INR",
      assigned: b.vendor_business_name || "Vendor",
      status: b.status || "pending",
      priority: b.total > 5000 ? "urgent" : b.total > 2000 ? "high" : "normal",
      next_date: b.requested_date || "—",
    }));
  }, [bookings]);

  const columns = [
    { key: "title", label: "Name", render: (r) => <span className="font-medium text-white">{r.title}</span> },
    { key: "created_by", label: "Created by", render: (r) => (
      <div className="flex items-center gap-2">
        <Avatar name={r.created_by} size={22} />
        <span className="truncate max-w-[140px]">{r.created_by}</span>
      </div>
    )},
    { key: "created_date", label: "Created date" },
    { key: "amount", label: "Amount", align: "right", render: (r) => fmtPrice(r.amount, r.currency) },
    { key: "assigned", label: "Assigned to", render: (r) => (
      <div className="flex items-center gap-2">
        <Avatar name={r.assigned} size={22} />
        <span className="truncate max-w-[140px]">{r.assigned}</span>
      </div>
    )},
    { key: "status", label: "Stage", render: (r) => <StatusPill status={r.status} /> },
    { key: "priority", label: "Priority", render: (r) => <PriorityFlag level={r.priority} /> },
    { key: "next_date", label: "Next date" },
  ];

  const headerRight = (
    <Button
      data-testid="admin-create-btn"
      onClick={() => nav("/platform-admin?tab=events")}
      className="bg-[#06B6D4] hover:bg-[#0891B2] text-white rounded-full h-9 px-4 gap-1.5"
    >
      <Plus className="w-4 h-4" /> Add event
    </Button>
  );

  return (
    <DashboardShell activePath="home" title="Admin Dashboard" headerRight={headerRight}>
      {/* Page title + tabs */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Overview</h1>
          <p className="text-sm text-neutral-500 mt-1">Last 7 days · updated live</p>
        </div>
        <DashboardTabs
          tabs={[{ key: "overview", label: "Overview" }, { key: "table", label: "Table" }]}
          active={tab}
          onChange={setTab}
        />
      </div>

      {/* KPI donut cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mb-8" data-testid="admin-kpi-grid">
        <KpiDonutCard testid="kpi-bookings" title="Bookings" data={bookingsKpi} onClick={() => nav("/platform-admin?tab=bookings")} />
        <KpiDonutCard testid="kpi-revenue" title="Revenue" data={revenueKpi} totalLabel="Total ₹" onClick={() => nav("/platform-admin?tab=bookings")} />
        <KpiDonutCard testid="kpi-events" title="Events" data={eventsKpi} onClick={() => nav("/platform-admin?tab=events")} />
        <KpiDonutCard testid="kpi-ecosystem" title="Ecosystem" data={ecosystemKpi} onClick={() => nav("/platform-admin?tab=users")} />
      </div>

      {/* Table toolbar */}
      <div className="flex items-center justify-between mb-3">
        <ViewToggle view={view} onChange={setView} />
        <div className="flex items-center gap-1">
          <button data-testid="admin-toolbar-import" className="text-xs text-neutral-400 px-3 py-1.5 hover:bg-white/5 rounded-md inline-flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5" /> Import
          </button>
          <button data-testid="admin-toolbar-group" className="text-xs text-neutral-400 px-3 py-1.5 hover:bg-white/5 rounded-md inline-flex items-center gap-1.5">
            <Group className="w-3.5 h-3.5" /> Group
          </button>
          <button data-testid="admin-toolbar-filter" className="text-xs text-neutral-400 px-3 py-1.5 hover:bg-white/5 rounded-md inline-flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5" /> Filters
          </button>
        </div>
      </div>

      {view === "table" ? (
        <SortableTable
          columns={columns}
          data={tableRows}
          testid="admin-bookings-table"
          bulkActions={[
            {
              key: "check-in",
              label: "Mark arrived",
              className: "bg-[#84CC16]/15 text-[#84CC16] hover:bg-[#84CC16]/25",
              onClick: async (rows) => {
                let ok = 0;
                for (const r of rows) {
                  try { await api.post(`/vendor-bookings/${r.id}/check-in`); ok += 1; } catch (e) { /* noop */ }
                }
                toast.success(`${ok}/${rows.length} marked arrived`);
                const b = await api.get("/vendor-bookings").catch(() => ({ data: [] }));
                setBookings(b.data || []);
              },
            },
            {
              key: "no-show",
              label: "Mark no-show",
              className: "bg-[#FF3B30]/15 text-[#FF3B30] hover:bg-[#FF3B30]/25",
              onClick: async (rows) => {
                if (!window.confirm(`Mark ${rows.length} booking(s) as no-show?`)) return;
                let ok = 0;
                for (const r of rows) {
                  try { await api.post(`/vendor-bookings/${r.id}/no-show`); ok += 1; } catch (e) { /* noop */ }
                }
                toast.success(`${ok}/${rows.length} marked no-show`);
                const b = await api.get("/vendor-bookings").catch(() => ({ data: [] }));
                setBookings(b.data || []);
              },
            },
            {
              key: "export",
              label: "Export CSV",
              onClick: async (rows) => {
                const header = ["id", "title", "created_by", "amount", "status", "next_date"].join(",");
                const body = rows.map((r) => [r.id, r.title, r.created_by, r.amount, r.status, r.next_date].map((v) => `"${String(v || "").replace(/"/g, '""')}"`).join(",")).join("\n");
                const blob = new Blob([`${header}\n${body}`], { type: "text/csv" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a"); a.href = url; a.download = `bookings-${new Date().toISOString().slice(0,10)}.csv`; a.click();
                URL.revokeObjectURL(url);
                toast.success(`Exported ${rows.length} rows`);
              },
            },
          ]}
        />
      ) : (
        <BoardView rows={tableRows} />
      )}

      <div className="mt-6 flex items-center justify-between text-xs text-neutral-500">
        <span>Showing {tableRows.length} of {bookings.length} bookings</span>
        <Link to="/platform-admin?tab=bookings" data-testid="admin-see-all" className="text-[#06B6D4] hover:underline">
          → Full analytics
        </Link>
      </div>
    </DashboardShell>
  );
}

/** Kanban-style Board view — one column per status bucket. */
function BoardView({ rows }) {
  const columns = ["pending", "confirmed", "completed", "expired", "cancelled"];
  const grouped = columns.reduce((acc, key) => {
    acc[key] = rows.filter((r) => (r.status || "").toLowerCase() === key);
    return acc;
  }, {});
  return (
    <div data-testid="admin-board-view" className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
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
                <div className="text-xs text-neutral-500 mt-1">{r.assigned}</div>
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
