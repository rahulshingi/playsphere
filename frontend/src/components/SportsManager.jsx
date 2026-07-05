import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";

const SPORT_TEMPLATES = [
  { value: "kabaddi",   label: "Kabaddi",    scoring_pattern: "generic",    player_format: "team" },
  { value: "khokho",    label: "Kho-Kho",    scoring_pattern: "generic",    player_format: "team" },
  { value: "futsal",    label: "Futsal",     scoring_pattern: "football",   player_format: "team" },
  { value: "padel",     label: "Padel",      scoring_pattern: "racket",     player_format: "both" },
  { value: "squash",    label: "Squash",     scoring_pattern: "racket",     player_format: "both" },
  { value: "throwball", label: "Throwball",  scoring_pattern: "racket",     player_format: "team" },
  { value: "dodgeball", label: "Dodgeball",  scoring_pattern: "generic",    player_format: "team" },
  { value: "esports",   label: "Esports",    scoring_pattern: "generic",    player_format: "team" },
  { value: "carrom",    label: "Carrom",     scoring_pattern: "chess",      player_format: "individual" },
  { value: "snooker",   label: "Snooker",    scoring_pattern: "generic",    player_format: "individual" },
];

export default function SportsManager() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ value: "", label: "", scoring_pattern: "generic", player_format: "team" });
  const applyTemplate = (v) => {
    const tpl = SPORT_TEMPLATES.find((t) => t.value === v);
    if (tpl) setForm({ ...tpl });
  };

  const load = () => api.get("/sports?include_inactive=true").then((r) => setItems(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!(form.value && form.label)) return toast.error("Both fields required");
    try {
      await api.post("/sports", form);
      toast.success("Sport added");
      setForm({ value: "", label: "", scoring_pattern: "generic", player_format: "team" });
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
      <form onSubmit={create} className="border border-white/10 rounded-sm bg-[#141414] p-5 grid md:grid-cols-4 gap-2">
        <div className="md:col-span-4 font-display tracking-wider text-xl flex items-center gap-2"><Plus className="w-4 h-4 text-[#84CC16]" /> ADD SPORT</div>
        <div className="md:col-span-4">
          <div className="text-[10px] font-mono uppercase text-neutral-500 mb-1">/ Prefill from a sport template (optional)</div>
          <Select value="" onValueChange={applyTemplate}>
            <SelectTrigger data-testid="sport-template" className="bg-black/40 border-[#84CC16]/40 text-[#84CC16]"><SelectValue placeholder="Pick a template (Kabaddi, Padel, Futsal, Esports…)" /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              {SPORT_TEMPLATES.map((t) => (
                <SelectItem key={t.value} value={t.value}>{t.label} — {t.scoring_pattern} · {t.player_format}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Input data-testid="sport-value" placeholder="value (slug, e.g. pickleball)" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value.toLowerCase().replace(/\s+/g, "") })} className="bg-black/40 border-white/10 text-white" />
        <Input data-testid="sport-label" placeholder="label (display, e.g. Pickleball)" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} className="bg-black/40 border-white/10 text-white" />
        <Select value={form.scoring_pattern} onValueChange={(v) => setForm({ ...form, scoring_pattern: v })}>
          <SelectTrigger data-testid="sport-scoring" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="scoring pattern" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="cricket">Cricket (runs/wickets/overs)</SelectItem>
            <SelectItem value="football">Football (goals)</SelectItem>
            <SelectItem value="basketball">Basketball (points)</SelectItem>
            <SelectItem value="racket">Racket / set-based (badminton, tennis, pickleball, tabletennis, volleyball)</SelectItem>
            <SelectItem value="chess">Chess (points)</SelectItem>
            <SelectItem value="quiz">Quiz (points)</SelectItem>
            <SelectItem value="hackathon">Hackathon (score)</SelectItem>
            <SelectItem value="generic">Generic score</SelectItem>
          </SelectContent>
        </Select>
        <Select value={form.player_format} onValueChange={(v) => setForm({ ...form, player_format: v })}>
          <SelectTrigger data-testid="sport-playerformat" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="player format" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            <SelectItem value="team">Team (11-a-side, 5-a-side…)</SelectItem>
            <SelectItem value="individual">Individual (1 person per side)</SelectItem>
            <SelectItem value="both">Both singles &amp; doubles (racket)</SelectItem>
          </SelectContent>
        </Select>
        <Button data-testid="sport-add" type="submit" className="md:col-span-4 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Add sport</Button>
        <p className="md:col-span-4 text-[10px] font-mono text-neutral-500">
          Well-known slugs (cricket, football, badminton, tennis, pickleball…) get sensible defaults automatically — you can still override them.
        </p>
      </form>
      <div className="space-y-2">
        {items.map((s) => (
          <div key={s.id} data-testid={`sport-row-${s.value}`} className="border border-white/10 rounded-sm bg-[#141414] p-3 flex items-center justify-between">
            <div>
              <span className="font-semibold">{s.label}</span>
              <span className="ml-2 font-mono text-[10px] uppercase text-neutral-500">{s.value}</span>
              {s.scoring_pattern && <span className="ml-2 font-mono text-[10px] uppercase text-[#06B6D4]">· {s.scoring_pattern}</span>}
              {s.player_format && <span className="ml-2 font-mono text-[10px] uppercase text-[#EC4899]">· {s.player_format}</span>}
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
