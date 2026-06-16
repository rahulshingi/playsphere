import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

export default function SportsManager() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ value: "", label: "" });

  const load = () => api.get("/sports?include_inactive=true").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!(form.value && form.label)) return toast.error("Both fields required");
    try {
      await api.post("/sports", form);
      toast.success("Sport added");
      setForm({ value: "", label: "" });
      load();
    } catch (e2) { toast.error(e2.response?.data?.detail || "Failed"); }
  };
  const toggle = async (s) => {
    await api.patch(`/sports/${s.id}`, { active: !s.active });
    load();
  };
  const remove = async (s) => {
    if (!window.confirm(`Delete sport ${s.label}? Existing events keep their sport string.`)) return;
    await api.delete(`/sports/${s.id}`);
    load();
  };

  return (
    <div data-testid="sports-manager" className="space-y-4">
      <form onSubmit={create} className="border border-white/10 rounded-sm bg-[#141414] p-5 grid md:grid-cols-3 gap-2">
        <div className="md:col-span-3 font-display tracking-wider text-xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> ADD SPORT</div>
        <Input data-testid="sport-value" placeholder="value (slug, e.g. tennis)" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <Input data-testid="sport-label" placeholder="label (display, e.g. Tennis)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <Button data-testid="sport-add" type="submit" className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add</Button>
      </form>
      <div className="space-y-2">
        {items.map((s) => (
          <div key={s.id} data-testid={`sport-row-${s.value}`} className="border border-white/10 rounded-sm bg-[#141414] p-3 flex items-center justify-between">
            <div>
              <span className="font-semibold">{s.label}</span>
              <span className="ml-2 font-mono text-[10px] uppercase text-neutral-500">{s.value}</span>
              {!s.active && <span className="ml-2 text-[10px] font-mono uppercase text-[#F59E0B]">INACTIVE</span>}
            </div>
            <div className="flex gap-2">
              <Button data-testid={`sport-toggle-${s.value}`} size="sm" variant="outline" onClick={() => toggle(s)} className="rounded-sm border-white/10 text-white">{s.active ? "Disable" : "Enable"}</Button>
              <Button data-testid={`sport-del-${s.value}`} size="sm" variant="ghost" onClick={() => remove(s)} className="text-[#FF3B30]"><Trash2 className="w-4 h-4" /></Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
