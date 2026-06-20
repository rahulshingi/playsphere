import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Trash2 } from "lucide-react";
import { PERMISSION_LABELS, togglePerm } from "@/components/admin/adminTeamShared";

function renderPermissionsSummary(admin) {
  if (admin.is_super_admin) return "All permissions (full control)";
  if (admin.permissions.length === 0) return <span className="text-amber-400">No permissions assigned</span>;
  return admin.permissions.map((p) => PERMISSION_LABELS[p] || p).join(" · ");
}

export default function AdminRow({ admin, editing, setEditing, allPerms, onSave, onRemove }) {
  const isEditing = editing && editing.id === admin.id;
  return (
    <div data-testid={`team-admin-${admin.id}`} className="border border-white/10 rounded-sm p-4 bg-black/30">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-semibold">
            {admin.name}
            {admin.is_super_admin && <span className="ml-2 text-[10px] font-mono uppercase text-[#FF3B30] border border-[#FF3B30]/40 rounded-sm px-2 py-0.5">SUPER ADMIN</span>}
          </div>
          <div className="text-xs font-mono text-neutral-500">{admin.email}</div>
          {!isEditing && <div className="text-xs text-neutral-400 mt-2">{renderPermissionsSummary(admin)}</div>}
        </div>
        {!admin.is_super_admin && !isEditing && (
          <div className="flex gap-1 shrink-0">
            <Button size="sm" variant="ghost" data-testid={`team-edit-${admin.id}`}
              onClick={() => setEditing({ id: admin.id, name: admin.name, permissions: [...admin.permissions] })}
              className="text-[#84CC16]">Edit</Button>
            <Button size="sm" variant="ghost" data-testid={`team-delete-${admin.id}`}
              onClick={() => onRemove(admin)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
          </div>
        )}
      </div>

      {isEditing && (
        <div className="mt-4 space-y-3">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Name</Label>
            <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              className="mt-1 bg-black/40 border-white/10 text-white"
              data-testid={`team-edit-name-${admin.id}`} />
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Permissions</Label>
            <div className="grid sm:grid-cols-2 gap-2 mt-2">
              {allPerms.map((p) => (
                <label key={p} className="flex items-start gap-2 text-sm text-neutral-200 cursor-pointer">
                  <input type="checkbox" checked={editing.permissions.includes(p)}
                    onChange={() => setEditing({ ...editing, permissions: togglePerm(editing.permissions, p) })}
                    data-testid={`team-edit-perm-${admin.id}-${p}`}
                    className="mt-1 accent-[#84CC16]" />
                  <span>{PERMISSION_LABELS[p] || p}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <Button size="sm" data-testid={`team-save-${admin.id}`} onClick={() => onSave(editing)}
              className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(null)} className="text-neutral-400">Cancel</Button>
          </div>
        </div>
      )}
    </div>
  );
}
