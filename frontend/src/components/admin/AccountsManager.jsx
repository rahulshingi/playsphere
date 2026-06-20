import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const ROLE_TABS = [
  { value: "organiser", label: "Organisers" },
  { value: "company_admin", label: "Company admins" },
  { value: "vendor", label: "Vendors" },
  { value: "player", label: "Players" },
];

function RoleBadge({ role, vendorApproved }) {
  if (role === "organiser") return <span className="text-[10px] uppercase font-mono text-[#06B6D4] border border-[#06B6D4]/40 rounded-sm px-1.5 py-0.5">ORGANISER</span>;
  if (role === "company_admin") return <span className="text-[10px] uppercase font-mono text-[#84CC16] border border-[#84CC16]/40 rounded-sm px-1.5 py-0.5">COMPANY</span>;
  if (role === "vendor") return <span className="text-[10px] uppercase font-mono text-[#EC4899] border border-[#EC4899]/40 rounded-sm px-1.5 py-0.5">VENDOR{vendorApproved ? "" : " · PENDING"}</span>;
  if (role === "player") return <span className="text-[10px] uppercase font-mono text-[#FBBF24] border border-[#FBBF24]/40 rounded-sm px-1.5 py-0.5">PLAYER</span>;
  return null;
}

function AccountRow({ user, busy, onToggle }) {
  return (
    <div
      data-testid={`account-row-${user.id}`}
      className={`border rounded-sm p-4 flex items-center justify-between gap-3 ${user.disabled ? "border-amber-500/30 bg-amber-500/5" : "border-white/10 bg-black/30"}`}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="font-semibold truncate">{user.name || user.email}</div>
          {user.disabled && <span className="text-[10px] uppercase font-mono text-amber-400 border border-amber-500/40 rounded-sm px-1.5 py-0.5">DISABLED</span>}
          <RoleBadge role={user.role} vendorApproved={user.vendor_approved} />
        </div>
        <div className="text-xs font-mono text-neutral-500 mt-1 truncate">
          {user.email}
          {user.company_name && <> · {user.company_name}</>}
          {user.vendor_business_name && <> · {user.vendor_business_name} ({user.vendor_type})</>}
        </div>
        {user.disabled && user.disabled_at && (
          <div className="text-[10px] font-mono text-amber-300/80 mt-1">
            disabled {new Date(user.disabled_at).toLocaleString()}{user.disabled_by ? ` by ${user.disabled_by}` : ""}
          </div>
        )}
      </div>
      <Button
        size="sm"
        data-testid={`account-toggle-${user.id}`}
        disabled={busy}
        onClick={() => onToggle(user)}
        className={user.disabled ? "bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm" : "bg-[#FF3B30] hover:bg-[#dc2626] text-white font-semibold rounded-sm"}
      >
        {busy ? "…" : (user.disabled ? "Enable" : "Disable")}
      </Button>
    </div>
  );
}

export default function AccountsManager() {
  const [role, setRole] = useState("organiser");
  const [users, setUsers] = useState([]);
  const [showDisabled, setShowDisabled] = useState(true);
  const [q, setQ] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = (r = role) => api.get(`/admin/users?role=${r}`).then((res) => setUsers(res.data)).catch((e) => toast.error(e.response?.data?.detail || "Failed to load accounts"));
  useEffect(() => { load(role); }, [role]);

  const toggleDisabled = async (u) => {
    const next = !u.disabled;
    const verb = next ? "disable" : "enable";
    if (!window.confirm(`Are you sure you want to ${verb} ${u.email}?${next ? "\nThey will no longer be able to log in." : ""}`)) return;
    try {
      setBusyId(u.id);
      await api.patch(`/admin/users/${u.id}/disabled`, { disabled: next });
      toast.success(next ? "Account disabled" : "Account enabled");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    } finally {
      setBusyId(null);
    }
  };

  const filtered = users.filter((u) => {
    if (!showDisabled && u.disabled) return false;
    if (!q.trim()) return true;
    const hay = `${u.email} ${u.name || ""} ${u.company_name || ""} ${u.vendor_business_name || ""}`.toLowerCase();
    return hay.includes(q.toLowerCase());
  });

  const counts = users.reduce((acc, u) => { acc.total++; if (u.disabled) acc.disabled++; return acc; }, { total: 0, disabled: 0 });

  return (
    <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
      <div className="font-display tracking-wider text-2xl">ACCOUNT SUSPENSION</div>
      <p className="text-xs text-neutral-400 mt-1">
        Disable any organiser, vendor, player, or company admin from logging in. Their data stays intact — they just see a contact-admin message at login until re-enabled.
      </p>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        {ROLE_TABS.map((t) => (
          <Button
            key={t.value}
            data-testid={`accounts-role-${t.value}`}
            size="sm"
            onClick={() => setRole(t.value)}
            className={role === t.value ? "bg-[#FF3B30] hover:bg-[#dc2626] text-white rounded-sm" : "bg-white/5 hover:bg-white/10 text-white rounded-sm"}
          >
            {t.label}
          </Button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <Input data-testid="accounts-search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email, name, company…" className="bg-black/40 border-white/10 text-white text-sm w-64" />
          <label className="text-xs font-mono text-neutral-400 flex items-center gap-2">
            <input type="checkbox" data-testid="accounts-show-disabled" checked={showDisabled} onChange={(e) => setShowDisabled(e.target.checked)} className="accent-[#84CC16]" />
            Show disabled
          </label>
        </div>
      </div>

      <div className="text-[10px] font-mono uppercase text-neutral-500 mt-4">
        / {counts.total} total · {counts.disabled} disabled · showing {filtered.length}
      </div>

      <div className="mt-3 space-y-2">
        {filtered.length === 0 && <div className="text-neutral-500 text-sm text-center py-12 border border-dashed border-white/10 rounded-sm">No matching accounts.</div>}
        {filtered.map((u) => (
          <AccountRow key={u.id} user={u} busy={busyId === u.id} onToggle={toggleDisabled} />
        ))}
      </div>
    </div>
  );
}
