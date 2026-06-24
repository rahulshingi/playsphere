import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Search, ExternalLink, ShieldOff, ShieldCheck } from "lucide-react";

/**
 * Platform Admin → Users tab.
 * - Lists every signed-up user across the platform.
 * - Role filter chips (All / Player / Vendor / Organiser / HR / Sponsor / Scorer).
 * - Free-text search across name + email + business / brand name.
 * - Click a row to deep-link into the role-appropriate detail page:
 *     player  → /players/{player_profile_id}
 *     vendor  → /platform-admin/vendors/{vendor_id}
 *     org/HR  → /platform-admin/companies/{company_id}
 *     sponsor → /sponsors/{user_id}  (admin viewer)
 *     scorer  → /platform-admin/scorers/{user_id}
 * - Enable / Disable account is preserved from the prior Accounts tab.
 */
const ROLE_OPTIONS = [
  { key: "all",         label: "All",        accent: "#84CC16" },
  { key: "player",      label: "Players",    accent: "#84CC16" },
  { key: "vendor",      label: "Vendors",    accent: "#EC4899" },
  { key: "organiser",   label: "Organisers", accent: "#06B6D4" },
  { key: "company_admin", label: "Company HR", accent: "#FACC15" },
  { key: "sponsor",     label: "Sponsors",   accent: "#FACC15" },
  { key: "scorer",      label: "Scorers",    accent: "#06B6D4" },
];

export default function UsersTab() {
  const [users, setUsers] = useState([]);
  const [role, setRole] = useState("all");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    try {
      const path = role === "all" ? "/admin/users" : `/admin/users?role=${role}`;
      const { data } = await api.get(path);
      setUsers(data || []);
    } catch {
      setUsers([]); toast.error("Failed to load users");
    } finally { setBusy(false); }
  };
  useEffect(() => { load(); }, [role]);

  const filtered = useMemo(() => {
    if (!q.trim()) return users;
    const needle = q.trim().toLowerCase();
    return users.filter((u) =>
      [u.name, u.email, u.vendor_business_name, u.sponsor_brand_name, u.company_name]
        .filter(Boolean).some((v) => String(v).toLowerCase().includes(needle))
    );
  }, [users, q]);

  const counts = useMemo(() => {
    const out = { all: users.length };
    for (const u of users) out[u.role] = (out[u.role] || 0) + 1;
    return out;
  }, [users]);

  const toggleDisabled = async (u) => {
    if (!window.confirm(`${u.disabled ? "Re-enable" : "Disable"} ${u.email}?`)) return;
    try {
      await api.patch(`/admin/users/${u.id}/disabled`, { disabled: !u.disabled });
      toast.success(u.disabled ? "Account re-enabled" : "Account disabled");
      load();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-5">
      <div className="border border-white/10 rounded-sm bg-[#141414]/60 p-3 text-xs text-neutral-400" data-testid="users-tab-note">
        <b className="text-neutral-200">Note:</b> this tab lists every signed-up
        <span className="text-[#06B6D4]"> user</span> (one row per person). The
        <span className="text-[#84CC16]"> Companies</span> /
        <span className="text-[#06B6D4]"> Organisers</span> tabs above list the
        <span className="text-neutral-200"> organisations themselves</span> — so a
        single company with multiple HR users will appear once in <i>Companies</i>
        but multiple times here under <i>Company HR</i>.
      </div>

      {/* Search + filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <div className="flex-1 min-w-[240px] relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
          <Input data-testid="users-search" placeholder="Search name, email, business, brand…"
            value={q} onChange={(e) => setQ(e.target.value)}
            className="pl-9 bg-black/40 border-white/10 text-white" />
        </div>
        <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">
          {filtered.length} of {users.length}
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {ROLE_OPTIONS.map((opt) => {
          const active = role === opt.key;
          return (
            <button key={opt.key} type="button" data-testid={`users-filter-${opt.key}`}
              onClick={() => setRole(opt.key)}
              className={`text-[11px] font-mono uppercase px-2.5 py-1 rounded-sm border transition-colors ${
                active
                  ? "text-black border-transparent"
                  : "bg-black/40 text-neutral-300 border-white/10 hover:border-white/30"
              }`}
              style={active ? { backgroundColor: opt.accent } : {}}>
              {opt.label} {opt.key === role && counts[opt.key] !== undefined ? `(${counts[opt.key]})` : ""}
            </button>
          );
        })}
      </div>

      {/* Table */}
      {busy && <div className="text-neutral-500 text-center py-12">Loading…</div>}
      {!busy && filtered.length === 0 && (
        <div data-testid="users-empty" className="text-neutral-500 text-center py-16 border border-dashed border-white/10 rounded-sm">
          No users match the current filter.
        </div>
      )}

      <div className="space-y-2">
        {filtered.map((u) => (
          <UserRow key={u.id} user={u} onToggleDisabled={() => toggleDisabled(u)} />
        ))}
      </div>
    </div>
  );
}

/** Map a user record to the most useful click-through. Uses platform-admin routes
 *  so the back link returns to the admin instead of bouncing to dashboard. */
function deepLinkFor(u) {
  if (u.role === "player" && u.player_profile_id) {
    return { href: `/platform-admin/players/${u.player_profile_id}`, label: "View profile" };
  }
  if (u.role === "vendor" && u.vendor_id) {
    return { href: `/platform-admin/vendors/${u.vendor_id}`, label: "View vendor" };
  }
  if ((u.role === "organiser" || u.role === "company_admin") && u.company_id) {
    return { href: `/platform-admin/companies/${u.company_id}`, label: "View company" };
  }
  // No dedicated admin detail pages for sponsors / scorers yet — surface their
  // public marketplace presence or scorer console as the best available context.
  if (u.role === "sponsor") {
    return { href: `/sponsorships`, label: "View marketplace" };
  }
  if (u.role === "scorer") {
    return { href: `/scorer/dashboard`, label: "Open console" };
  }
  return null;
}

function UserRow({ user, onToggleDisabled }) {
  const link = deepLinkFor(user);
  const roleColors = {
    player: "#84CC16", vendor: "#EC4899", organiser: "#06B6D4",
    company_admin: "#FACC15", sponsor: "#FACC15", scorer: "#06B6D4",
  };
  const accent = roleColors[user.role] || "#84CC16";
  const subtitle = [
    user.role === "vendor" && user.vendor_business_name,
    user.role === "sponsor" && user.sponsor_brand_name,
    (user.role === "organiser" || user.role === "company_admin") && user.company_name,
    user.role === "player" && (user.player_city || (user.player_sports || []).join(", ")),
    user.role === "scorer" && `${user.scorer_assignments || 0} event(s) · ${user.scorer_fixtures || 0} fixture(s)`,
  ].filter(Boolean).join(" · ");

  return (
    <div data-testid={`user-row-${user.id}`}
      className={`border rounded-sm p-4 bg-[#141414] flex items-center justify-between gap-3 transition-colors ${
        user.disabled ? "border-[#FF3B30]/30 opacity-60" : "border-white/10 hover:border-white/30"
      }`}>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold truncate">{user.name || user.email}</span>
          <span data-testid={`user-role-pill-${user.id}`}
            className="text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm border"
            style={{ color: accent, borderColor: `${accent}44` }}>
            {user.role.replace("_", " ")}
          </span>
          {user.role === "vendor" && !user.vendor_approved && (
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-amber-500/15 text-amber-400 border border-amber-500/40">Pending</span>
          )}
          {user.disabled && (
            <span className="text-[9px] font-mono uppercase px-1.5 py-0.5 rounded-sm bg-[#FF3B30]/15 text-[#FF3B30] border border-[#FF3B30]/40">Disabled</span>
          )}
        </div>
        <div className="text-xs font-mono text-neutral-500 mt-1 truncate">{user.email}</div>
        {subtitle && <div className="text-xs text-neutral-300 mt-1 truncate">{subtitle}</div>}
      </div>
      <div className="flex items-center gap-1 shrink-0">
        {link && (
          <Link to={link.href} data-testid={`user-link-${user.id}`}>
            <Button size="sm" variant="ghost" className="text-[#84CC16] text-xs">
              {link.label} <ExternalLink className="w-3 h-3 ml-1" />
            </Button>
          </Link>
        )}
        <Button size="sm" variant="ghost" data-testid={`user-toggle-disabled-${user.id}`}
          onClick={onToggleDisabled}
          className={user.disabled ? "text-[#84CC16]" : "text-[#FF3B30]"}
          title={user.disabled ? "Re-enable account" : "Disable account"}>
          {user.disabled ? <ShieldCheck className="w-4 h-4" /> : <ShieldOff className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
