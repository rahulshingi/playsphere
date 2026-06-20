import { useEffect, useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import InviteAdminForm from "@/components/admin/InviteAdminForm";
import InviteCredentialsBanner from "@/components/admin/InviteCredentialsBanner";
import AdminRow from "@/components/admin/AdminRow";

const BLANK_INVITE = { email: "", name: "", password: "", permissions: [] };

export default function AdminTeam() {
  const [admins, setAdmins] = useState([]);
  const [allPerms, setAllPerms] = useState([]);
  const [newAdmin, setNewAdmin] = useState(BLANK_INVITE);
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
      setNewAdmin(BLANK_INVITE);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed");
    }
  };

  const savePerms = async (a) => {
    try {
      await api.patch(`/admin/staff/${a.id}`, { name: a.name, permissions: a.permissions });
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

  return (
    <div className="space-y-6">
      <InviteAdminForm value={newAdmin} setValue={setNewAdmin} allPerms={allPerms} onCreate={create} />

      {invite && <InviteCredentialsBanner invite={invite} onDismiss={() => setInvite(null)} />}

      <div className="border border-white/10 rounded-sm bg-[#141414] p-6">
        <div className="font-display tracking-wider text-2xl">CURRENT ADMINS ({admins.length})</div>
        <div className="space-y-2 mt-4">
          {admins.map((a) => (
            <AdminRow
              key={a.id}
              admin={a}
              editing={editing}
              setEditing={setEditing}
              allPerms={allPerms}
              onSave={savePerms}
              onRemove={remove}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
