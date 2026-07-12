import { Link } from "react-router-dom";
import { useMemo, useState } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer } from "recharts";
import {
  Home, Calendar, Store, Users, Award, Settings, Search, Plus, Bell,
  ChevronUp, ChevronDown, Flag,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/context/AuthContext";

/**
 * Kreeda Nation Dashboard Kit — DARK Pepper-style workspace (iter 46).
 *
 * The user validated the layout (Pepper reference) but reverted the theme
 * from light to Kreeda's signature dark. All surfaces use the platform's
 * existing dark palette so no CSS-variable override is needed. The
 * `.dashboard-light` marker class is preserved for scoping affordance but
 * carries no light overrides in `index.css`.
 */
export function DashboardShell({ children, activePath, title, headerRight, hideTopBar = false }) {
  return (
    <div className="dashboard-light flex h-screen overflow-hidden bg-[#0a0a0a]" data-testid="dashboard-shell">
      <LeftIconNav activePath={activePath} />
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        {!hideTopBar && <TopBar title={title} headerRight={headerRight} />}
        <div className="flex-1 overflow-auto p-8 text-white" data-testid="dashboard-content">
          {children}
        </div>
      </div>
    </div>
  );
}

const NAV_ITEMS = [
  { key: "home", href: "/platform-admin", icon: Home, label: "Home" },
  { key: "bookings", href: "/platform-admin?tab=bookings", icon: Calendar, label: "Bookings" },
  { key: "events", href: "/platform-admin?tab=events", icon: Award, label: "Events" },
  { key: "vendors", href: "/platform-admin?tab=vendors", icon: Store, label: "Vendors" },
  { key: "users", href: "/platform-admin?tab=users", icon: Users, label: "Users" },
  { key: "settings", href: "/platform-admin?tab=settings", icon: Settings, label: "Settings" },
];

function LeftIconNav({ activePath }) {
  return (
    <nav
      data-testid="left-icon-nav"
      className="w-[80px] flex-shrink-0 flex flex-col items-center py-6 gap-2 bg-black border-r border-white/10 z-20"
    >
      <Link to="/" className="mb-4" data-testid="nav-brand-home">
        <div className="w-10 h-10 rounded-full bg-[#84CC16] flex items-center justify-center font-black text-black text-sm shadow-lg shadow-[#84CC16]/20">KN</div>
      </Link>
      {NAV_ITEMS.map((it) => {
        const Icon = it.icon;
        const active = activePath === it.key;
        return (
          <Link
            key={it.key}
            to={it.href}
            data-testid={`nav-${it.key}`}
            title={it.label}
            className={`w-11 h-11 flex items-center justify-center rounded-lg transition-colors ${
              active ? "bg-[#84CC16] text-black" : "text-neutral-500 hover:bg-white/5 hover:text-white"
            }`}
          >
            <Icon className="w-5 h-5" />
          </Link>
        );
      })}
    </nav>
  );
}

function TopBar({ title, headerRight }) {
  const { user } = useAuth();
  const initials = (user?.name || user?.email || "K").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <header
      data-testid="top-bar"
      className="h-16 flex items-center justify-between px-8 bg-[#0f0f0f] border-b border-white/10 z-10 shrink-0"
    >
      <div className="text-lg font-semibold text-white tracking-tight">{title || "Dashboard"}</div>
      <div className="flex-1 max-w-xl mx-8">
        <div className="relative">
          <Search className="w-4 h-4 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <Input
            data-testid="top-bar-search"
            placeholder="Search bookings, events, vendors…"
            className="pl-9 h-9 rounded-full bg-[#141414] border-white/10 text-sm text-white placeholder:text-neutral-500 focus-visible:ring-1 focus-visible:ring-[#06B6D4] focus-visible:bg-black/40"
          />
        </div>
      </div>
      <div className="flex items-center gap-2">
        {headerRight}
        <button data-testid="top-bar-add" className="w-9 h-9 rounded-full border border-white/10 flex items-center justify-center text-neutral-400 hover:bg-white/5 hover:text-white">
          <Plus className="w-4 h-4" />
        </button>
        <button data-testid="top-bar-bell" className="w-9 h-9 rounded-full border border-white/10 flex items-center justify-center text-neutral-400 hover:bg-white/5 hover:text-white relative">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-[#EC4899]" />
        </button>
        <div data-testid="top-bar-avatar" className="w-9 h-9 rounded-full bg-[#F59E0B] flex items-center justify-center font-semibold text-black text-xs">
          {initials}
        </div>
      </div>
    </header>
  );
}

export function KpiDonutCard({ title, data, totalLabel = "Total", testid }) {
  const total = useMemo(() => data.reduce((s, d) => s + (Number(d.value) || 0), 0), [data]);
  const chartData = data.length ? data : [{ name: "empty", value: 1, color: "#1F2937" }];
  return (
    <div data-testid={testid || "kpi-donut-card"} className="bg-[#141414] rounded-xl border border-white/10 p-5 flex flex-col gap-3 hover:border-white/20 transition-colors">
      <div className="text-xs font-semibold text-neutral-400 uppercase tracking-widest">{title}</div>
      <div className="flex items-center gap-5">
        <div className="relative w-[100px] h-[100px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                innerRadius={32}
                outerRadius={48}
                paddingAngle={2}
                stroke="none"
              >
                {chartData.map((d, i) => (
                  <Cell key={`c${i}`} fill={d.color || "#4B5563"} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
            <div className="text-[10px] text-neutral-500">{totalLabel}</div>
            <div className="text-2xl font-bold text-white leading-none">{total}</div>
          </div>
        </div>
        <div className="flex-1 grid grid-cols-2 gap-x-3 gap-y-1.5 min-w-0">
          {data.map((d) => (
            <div key={d.name} className="flex items-baseline gap-2 min-w-0">
              <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: d.color }} />
              <div className="min-w-0 flex-1">
                <div className="text-[11px] text-neutral-400 truncate">{d.name}</div>
                <div className="text-sm font-semibold text-white -mt-0.5">{d.value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function StatusPill({ status }) {
  const map = {
    upcoming:  { bg: "bg-[#06B6D4]/15", txt: "text-[#06B6D4]", label: "Upcoming" },
    live:      { bg: "bg-[#84CC16]/15", txt: "text-[#84CC16]", label: "Live" },
    ongoing:   { bg: "bg-[#84CC16]/15", txt: "text-[#84CC16]", label: "Ongoing" },
    completed: { bg: "bg-[#EC4899]/15", txt: "text-[#EC4899]", label: "Completed" },
    pending:   { bg: "bg-[#F59E0B]/15", txt: "text-[#F59E0B]", label: "Pending" },
    confirmed: { bg: "bg-[#06B6D4]/15", txt: "text-[#06B6D4]", label: "Confirmed" },
    expired:   { bg: "bg-white/5",       txt: "text-neutral-400", label: "Expired" },
    cancelled: { bg: "bg-white/5",       txt: "text-neutral-400", label: "Cancelled" },
    approved:  { bg: "bg-[#84CC16]/15", txt: "text-[#84CC16]", label: "Approved" },
    active:    { bg: "bg-[#84CC16]/15", txt: "text-[#84CC16]", label: "Active" },
  };
  const v = map[(status || "").toLowerCase()] || { bg: "bg-white/5", txt: "text-neutral-400", label: status || "—" };
  return (
    <span data-testid={`status-pill-${status}`} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-medium ${v.bg} ${v.txt}`}>
      {v.label}
    </span>
  );
}

export function PriorityFlag({ level }) {
  const map = {
    urgent: "text-[#EF4444] fill-[#EF4444]",
    high:   "text-[#F59E0B] fill-[#F59E0B]",
    normal: "text-[#06B6D4] fill-[#06B6D4]",
    low:    "text-neutral-500 fill-neutral-600",
  };
  const cls = map[level] || "text-neutral-600 fill-neutral-700";
  return <Flag data-testid={`priority-flag-${level}`} className={`w-4 h-4 ${cls}`} />;
}

export function Avatar({ name, size = 24, color }) {
  const initials = (name || "?").split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  const bg = color || pickColorFromString(name || "");
  return (
    <div
      className="rounded-full flex items-center justify-center font-semibold text-white shrink-0"
      style={{ width: size, height: size, background: bg, fontSize: size <= 24 ? 10 : 12 }}
      title={name}
    >
      {initials}
    </div>
  );
}

function pickColorFromString(s) {
  const PALETTE = ["#06B6D4", "#84CC16", "#EC4899", "#F59E0B", "#8B5CF6", "#EF4444", "#10B981"];
  let hash = 0;
  for (let i = 0; i < s.length; i += 1) hash = (hash * 31 + s.charCodeAt(i)) & 0xff;
  return PALETTE[hash % PALETTE.length];
}

export function SortableTable({ columns, data, defaultSort, testid }) {
  const [sortKey, setSortKey] = useState(defaultSort?.key || columns[0]?.key);
  const [sortDir, setSortDir] = useState(defaultSort?.dir || "asc");
  const [selected, setSelected] = useState(new Set());

  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sortKey);
    if (!col) return data;
    const accessor = col.sortAccessor || ((r) => r[col.key]);
    return [...data].sort((a, b) => {
      const av = accessor(a);
      const bv = accessor(b);
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return sortDir === "asc" ? av - bv : bv - av;
      return sortDir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av));
    });
  }, [columns, data, sortKey, sortDir]);

  const toggleSort = (key) => {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };

  const toggleRow = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };
  const toggleAll = () => {
    if (selected.size === sorted.length) setSelected(new Set());
    else setSelected(new Set(sorted.map((r) => r.id)));
  };

  return (
    <div data-testid={testid || "sortable-table"} className="bg-[#141414] rounded-xl border border-white/10 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-[#0f0f0f] border-b border-white/10">
            <tr>
              <th className="w-10 px-4 py-3">
                <input
                  type="checkbox"
                  data-testid="st-select-all"
                  checked={selected.size > 0 && selected.size === sorted.length}
                  onChange={toggleAll}
                  className="rounded border-white/20 bg-black/40"
                />
              </th>
              {columns.map((c) => (
                <th
                  key={c.key}
                  onClick={() => toggleSort(c.key)}
                  data-testid={`st-header-${c.key}`}
                  className={`px-3 py-3 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider cursor-pointer select-none ${c.align === "right" ? "text-right" : "text-left"}`}
                >
                  <span className="inline-flex items-center gap-1">
                    {c.label}
                    {sortKey === c.key ? (
                      sortDir === "asc" ? <ChevronUp className="w-3 h-3 text-neutral-500" /> : <ChevronDown className="w-3 h-3 text-neutral-500" />
                    ) : <ChevronUp className="w-3 h-3 text-neutral-700" />}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row) => (
              <tr key={row.id} data-testid={`st-row-${row.id}`} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                <td className="px-4 py-3">
                  <input
                    type="checkbox"
                    data-testid={`st-check-${row.id}`}
                    checked={selected.has(row.id)}
                    onChange={() => toggleRow(row.id)}
                    className="rounded border-white/20 bg-black/40"
                  />
                </td>
                {columns.map((c) => (
                  <td
                    key={c.key}
                    className={`px-3 py-3 text-sm text-neutral-200 ${c.align === "right" ? "text-right font-mono" : ""}`}
                  >
                    {c.render ? c.render(row) : row[c.key]}
                  </td>
                ))}
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={columns.length + 1} className="text-center py-12 text-neutral-500 text-sm">
                  No records match.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ViewToggle({ view, onChange }) {
  return (
    <div data-testid="view-toggle" className="inline-flex items-center bg-[#141414] border border-white/10 rounded-lg p-0.5 text-xs">
      {["table", "board"].map((v) => (
        <button
          key={v}
          data-testid={`view-toggle-${v}`}
          onClick={() => onChange(v)}
          className={`px-3 py-1.5 rounded-md font-medium capitalize transition-colors ${
            view === v ? "bg-[#06B6D4]/15 text-[#06B6D4]" : "text-neutral-400 hover:text-white"
          }`}
        >
          {v}
        </button>
      ))}
    </div>
  );
}

export function DashboardTabs({ tabs, active, onChange }) {
  return (
    <div data-testid="dashboard-tabs" className="inline-flex items-center gap-2 flex-wrap">
      {tabs.map((t) => (
        <button
          key={t.key}
          data-testid={`dashboard-tab-${t.key}`}
          onClick={() => onChange(t.key)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
            active === t.key
              ? "bg-[#06B6D4] text-black"
              : "bg-[#141414] text-neutral-400 border border-white/10 hover:bg-white/5 hover:text-white"
          }`}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
