import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import ImageUpload from "@/components/ImageUpload";
import { Trash2 } from "lucide-react";

export default function PeopleEditor({ label, testid, people, onChange }) {
  const add = () => onChange([...people, { name: "", role: "", image_url: "", bio: "", linkedin_url: "", twitter_url: "" }]);
  const upd = (i, patch) => { const next = [...people]; next[i] = { ...next[i], ...patch }; onChange(next); };
  const del = (i) => onChange(people.filter((_, idx) => idx !== i));
  return (
    <div className="border border-white/10 rounded-sm p-3 mt-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">/ {label} ({people.length})</div>
        <Button size="sm" variant="ghost" onClick={add} className="text-[#84CC16]" data-testid={`${testid}-add`}>+ Add</Button>
      </div>
      <div className="space-y-2 mt-2">
        {people.map((p, i) => (
          <div key={`person-${p.name || "new"}-${i}`} className="grid grid-cols-12 gap-2 items-center">
            <Input data-testid={`${testid}-${i}-name`} placeholder="Name" value={p.name} onChange={(e) => upd(i, { name: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
            <Input data-testid={`${testid}-${i}-role`} placeholder="Role" value={p.role} onChange={(e) => upd(i, { role: e.target.value })} className="col-span-3 bg-black/40 border-white/10 text-white" />
            <div className="col-span-4"><ImageUpload value={p.image_url} onChange={(v) => upd(i, { image_url: v })} testid={`${testid}-${i}-image`} placeholder="Image — paste URL or upload" /></div>
            <Input placeholder="LinkedIn" value={p.linkedin_url || ""} onChange={(e) => upd(i, { linkedin_url: e.target.value })} className="col-span-1 bg-black/40 border-white/10 text-white" />
            <Button size="sm" variant="ghost" onClick={() => del(i)} className="col-span-1 text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
            <Textarea data-testid={`${testid}-${i}-bio`} rows={1} placeholder="Bio" value={p.bio || ""} onChange={(e) => upd(i, { bio: e.target.value })} className="col-span-12 bg-black/40 border-white/10 text-white" />
          </div>
        ))}
      </div>
    </div>
  );
}
