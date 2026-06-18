import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trash2, Plus, Copy, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const PERMISSION_LABELS = {
  manage_events: "Manage events (create / delete tournaments)",
  manage_vendors: "Approve & revoke vendors",
  manage_listings: "Approve listings (grounds, coaches, etc.)",
  manage_bookings: "Confirm / reject ground bookings",
  manage_reviews: "Moderate reviews queue",
  manage_settings: "Edit site settings & About page",
  manage_companies: "Manage companies",
};

const blankInvite = { email: "", name: "", password: "", permissions: [] };

export default function AdminTeam() {
  const [admins, setAdmins] = useState([]);
  const [allPerms, setAllPerms] = useState([]);
  const [newAdmin, setNewAdmin] = useState(blankInvite);
  const [invite, setInvite] = useState(null); // last-created admin credentials to share
  const [editing, setEditing] = useState(null); // {id, permissions, name}

  const load = async () => {
    try {
      const [staff, me] = await Promise.all([
        api.get("/admin/staff"),
        api.get("/admin/permissions/me"),
      ]);
      setAdmins(staff.data);
      setAllPerms(me.data.all_permissions || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load team");
    }
  };
  useEffect(() => { load(); }, []);

  const togglePerm = (list, p) =>
    list.includes(p) ? list.filter((x) => x !== p) : [...list, p];

  const create = async () => {
    if (!newAdmin.email.trim() || !newAdmin.name.trim() || !newAdmin.password.trim()) {
      return toast.error("Email, name and password are required");
    }
    if (newAdmin.password.length < 6) return toast.error("Password must be at least 6 characters");
    try {
      const { data } = await api.post("/admin/staff", {
        email: newAdmin.email.trim().toLowerCase(),
        name: newAdmin.name.trim(),
        password: newAdmin.password,
        permissions: newAdmin.permissions,
      });
      toast.success("Admin invited");
      setInvite(data.invite);
      setNewAdmin(blankInvite);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const savePerms = async (a) => {
    try {
      await api.patch(`/admin/staff/${a.id}`, {
        name: a.name,
        permissions: a.permissions,
      });
      toast.success("Permissions updated");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const remove = async (a) => {
    if (!window.confirm(`Remove ${a.email}? They will lose admin access immediately.`)) return;
    try {
      await api.delete(`/admin/staff/${a.id}`);
      toast.success("Admin removed");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const copyInvite = () => {
    if (!invite) return;
    const text = `Welcome to Kreeda Nation HQ.\n\nLogin: ${window.location.origin}${invite.login_url}\nEmail: ${invite.email}\nTemporary password: ${invite.temp_password}\n\nPlease change your password after first sign-in.`;
    navigator.clipboard?.writeText(text);
    toast.success("Copied invite to clipboard");
  };

  return (
    <div className="space-y-6">
      {/* Invite form */}
      <div className="border border-white/10 rounded-sm bg-[#141414] p-6 space-y-3">
        <div className="font-display tracking-wider text-2xl flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-[#84CC16]" /> INVITE A STAFF ADMIN
        </div>
        <p className="text-xs text-neutral-500 font-mono">
          Create additional admins with scoped permissions. Only the <span className="text-[#FF3B30]">super admin</span> can add or delete admins, services and users — staff admins handle the day-to-day operations you assign below.
        </p>
        <div className="grid md:grid-cols-3 gap-3">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Email</Label>
            <Input
              data-testid="team-new-email"
              type="email"
              value={newAdmin.email}
              onChange={(e) => setNewAdmin({ ...newAdmin, email: e.target.value })}
              placeholder="ops@kreedanation.com"
              className="mt-1 bg-black/40 border-white/10 text-white"
            />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Name</Label>
            <Input
              data-testid="team-new-name"
              value={newAdmin.name}
              onChange={(e) => setNewAdmin({ ...newAdmin, name: e.target.value })}
              placeholder="Ops Manager"
              className="mt-1 bg-black/40 border-white/10 text-white"
            />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Temporary password</Label>
            <Input
              data-testid="team-new-password"
              value={newAdmin.password}
              onChange={(e) => setNewAdmin({ ...newAdmin, password: e.target.value })}
              placeholder="Min 6 characters"
              className="mt-1 bg-black/40 border-white/10 text-white"
            />
          </div>
        </div>
        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">Permissions</Label>
          <div className="grid sm:grid-cols-2 gap-2 mt-2">
            {allPerms.map((p) => (
              <label key={p} className="flex items-start gap-2 text-sm text-neutral-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={newAdmin.permissions.includes(p)}
                  onChange={() => setNewAdmin({ ...newAdmin, permissions: togglePerm(newAdmin.permissions, p) })}
                  data-testid={`team-new-perm-${p}`}
                  className="mt-1 accent-[#84CC16]"
                />
                <span>{PERMISSION_LABELS[p] || p}</span>
              </label>
            ))}
          </div>
        </div>
        <Button
          data-testid="team-create-admin"
          onClick={create}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm"
        >
          <Plus className="w-4 h-4 mr-1" /> Create admin
        </Button>
      </div>

      {/* Invite credentials (one-time display) */}
      {invite && (
        <div data-testid="team-invite-banner" className="border border-[#84CC16]/40 rounded-sm bg-[#84CC16]/10 p-5">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[#84CC16]">/ Invite created</div>
              <div className="text-sm text-neutral-100 mt-2">
                <div><strong>Email:</strong> {invite.email}</div>
                <div><strong>Password:</strong> <code className="bg-black/40 px-2 py-0.5 rounded-sm">{invite.temp_password}</code></div>
                <div><strong>Sign in:</strong> {window.location.origin}{invite.login_url}</div>
              </div>
              <p className="text-xs text-neutral-300 mt-2">{invite.note}</p>
            </div>
            <div className="flex flex-col gap-2 shrink-0">
              <Button size="sm" variant="ghost" onClick={copyInvite} data-testid="team-invite-copy" className="text-[#84CC16]">
                <Copy className="w-4 h-4 mr-1" /> Copy
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setInvite(null)} className="text-neutral-400">Dismiss</Button>
            </div>
          </div>
        </div>
      )}

      {/* Existing admins */}
      <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
        <div className="font-display tracking-wider text-2xl">CURRENT ADMINS ({admins.length})</div>
        <div className="space-y-2 mt-4">
          {admins.map((a) => {
            const isEditing = editing && editing.id === a.id;
            return (
              <div key={a.id} data-testid={`team-admin-${a.id}`} className="border border-white/10 rounded-sm p-4 bg-black/30">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-semibold">
                      {a.name}
                      {a.is_super_admin && <span className="ml-2 text-[10px] font-mono uppercase text-[#FF3B30] border border-[#FF3B30]/40 rounded-sm px-2 py-0.5">SUPER ADMIN</span>}
                    </div>
                    <div className="text-xs font-mono text-neutral-500">{a.email}</div>
                    {!isEditing && (
                      <div className="text-xs text-neutral-400 mt-2">
                        {a.is_super_admin
                          ? "All permissions (full control)"
                          : (a.permissions.length === 0
                              ? <span className="text-amber-400">No permissions assigned</span>
                              : a.permissions.map((p) => PERMISSION_LABELS[p] || p).join(" · "))}
                      </div>
                    )}
                  </div>
                  {!a.is_super_admin && !isEditing && (
                    <div className="flex gap-1 shrink-0">
                      <Button size="sm" variant="ghost" data-testid={`team-edit-${a.id}`} onClick={() => setEditing({ id: a.id, name: a.name, permissions: [...a.permissions] })} className="text-[#84CC16]">Edit</Button>
                      <Button size="sm" variant="ghost" data-testid={`team-delete-${a.id}`} onClick={() => remove(a)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
                    </div>
                  )}
                </div>

                {isEditing && (
                  <div className="mt-4 space-y-3">
                    <div>
                      <Label className="text-xs font-mono uppercase text-neutral-500">Name</Label>
                      <Input
                        value={editing.name}
                        onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                        className="mt-1 bg-black/40 border-white/10 text-white"
                        data-testid={`team-edit-name-${a.id}`}
                      />
                    </div>
                    <div>
                      <Label className="text-xs font-mono uppercase text-neutral-500">Permissions</Label>
                      <div className="grid sm:grid-cols-2 gap-2 mt-2">
                        {allPerms.map((p) => (
                          <label key={p} className="flex items-start gap-2 text-sm text-neutral-200 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={editing.permissions.includes(p)}
                              onChange={() => setEditing({ ...editing, permissions: togglePerm(editing.permissions, p) })}
                              data-testid={`team-edit-perm-${a.id}-${p}`}
                              className="mt-1 accent-[#84CC16]"
                            />
                            <span>{PERMISSION_LABELS[p] || p}</span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" data-testid={`team-save-${a.id}`} onClick={() => savePerms(editing)} className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save</Button>
                      <Button size="sm" variant="ghost" onClick={() => setEditing(null)} className="text-neutral-400">Cancel</Button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
