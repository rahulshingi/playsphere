import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus, ShieldCheck } from "lucide-react";
import { PERMISSION_LABELS, togglePerm } from "@/components/admin/adminTeamShared";

export default function InviteAdminForm({ value, setValue, allPerms, onCreate }) {
  return (
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
          <Input data-testid="team-new-email" type="email" value={value.email}
            onChange={(e) => setValue({ ...value, email: e.target.value })}
            placeholder="ops@kreedanation.com" className="mt-1 bg-black/40 border-white/10 text-white" />
        </div>
        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">Name</Label>
          <Input data-testid="team-new-name" value={value.name}
            onChange={(e) => setValue({ ...value, name: e.target.value })}
            placeholder="Ops Manager" className="mt-1 bg-black/40 border-white/10 text-white" />
        </div>
        <div>
          <Label className="text-xs font-mono uppercase text-neutral-500">Temporary password</Label>
          <Input data-testid="team-new-password" value={value.password}
            onChange={(e) => setValue({ ...value, password: e.target.value })}
            placeholder="Min 6 characters" className="mt-1 bg-black/40 border-white/10 text-white" />
        </div>
      </div>
      <div>
        <Label className="text-xs font-mono uppercase text-neutral-500">Permissions</Label>
        <div className="grid sm:grid-cols-2 gap-2 mt-2">
          {allPerms.map((p) => (
            <label key={p} className="flex items-start gap-2 text-sm text-neutral-200 cursor-pointer">
              <input type="checkbox" checked={value.permissions.includes(p)}
                onChange={() => setValue({ ...value, permissions: togglePerm(value.permissions, p) })}
                data-testid={`team-new-perm-${p}`} className="mt-1 accent-[#84CC16]" />
              <span>{PERMISSION_LABELS[p] || p}</span>
            </label>
          ))}
        </div>
      </div>
      <Button data-testid="team-create-admin" onClick={onCreate}
        className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
        <Plus className="w-4 h-4 mr-1" /> Create admin
      </Button>
    </div>
  );
}
