import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "@/lib/api";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";

const COLORS = ["#84CC16", "#FF3B30", "#10B981", "#F59E0B", "#A855F7", "#EC4899", "#06B6D4", "#FFFFFF"];

export default function RegisterTeam() {
  const nav = useNavigate();
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState({ name: "", department: "", captain: "", color: "#84CC16", event_id: "", logo_url: "" });
  const [players, setPlayers] = useState([{ name: "", role: "", jersey: "" }]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.get("/events").then((r) => setEvents(r.data)); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name) return toast.error("Team name is required");
    setBusy(true);
    try {
      const { data: team } = await api.post("/teams", { ...form, event_id: form.event_id || null });
      for (const p of players.filter((x) => x.name.trim())) {
        await api.post("/players", {
          name: p.name,
          team_id: team.id,
          role: p.role || "",
          jersey_number: p.jersey ? Number(p.jersey) : null,
        });
      }
      toast.success("Team registered");
      nav(`/teams/${team.id}`);
    } catch (e) {
      toast.error("Failed to register team");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="bg-[#0a0a0a] min-h-screen text-white">
      <Nav />
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-24">
        <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-[#84CC16]">/ New squad</div>
        <h1 className="font-display text-6xl tracking-wide mt-3">REGISTER YOUR TEAM</h1>
        <p className="text-neutral-400 mt-3">Add your team, pick an event, and lock in your roster.</p>

        <form onSubmit={submit} className="mt-10 space-y-5">
          <div className="grid md:grid-cols-2 gap-4">
            <Field label="Team name" required>
              <Input data-testid="rt-team-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-[#141414] border-white/10 text-white" />
            </Field>
            <Field label="Department">
              <Input data-testid="rt-department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} className="bg-[#141414] border-white/10 text-white" />
            </Field>
            <Field label="Captain">
              <Input data-testid="rt-captain" value={form.captain} onChange={(e) => setForm({ ...form, captain: e.target.value })} className="bg-[#141414] border-white/10 text-white" />
            </Field>
            <Field label="Event">
              <Select value={form.event_id} onValueChange={(v) => setForm({ ...form, event_id: v })}>
                <SelectTrigger data-testid="rt-event-select" className="bg-[#141414] border-white/10 text-white"><SelectValue placeholder="Select event (optional)" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  {events.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </Field>
          </div>

          <Field label="Team color">
            <div className="flex gap-2">
              {COLORS.map((c) => (
                <button key={c} type="button" data-testid={`rt-color-${c}`} onClick={() => setForm({ ...form, color: c })}
                  className={`w-9 h-9 rounded-sm border-2 ${form.color === c ? "border-white" : "border-transparent"}`}
                  style={{ background: c }} />
              ))}
            </div>
          </Field>

          <div>
            <div className="flex items-center justify-between mb-3">
              <Label className="text-xs font-mono uppercase text-neutral-500">Roster (optional)</Label>
              <Button type="button" size="sm" variant="ghost" data-testid="rt-add-player" onClick={() => setPlayers([...players, { name: "", role: "", jersey: "" }])} className="text-[#84CC16]">+ Add player</Button>
            </div>
            <div className="space-y-2">
              {players.map((p, i) => (
                <div key={i} className="grid grid-cols-12 gap-2">
                  <Input data-testid={`rt-player-name-${i}`} placeholder="Name" value={p.name} onChange={(e) => updatePlayer(i, "name", e.target.value)} className="col-span-6 bg-[#141414] border-white/10 text-white" />
                  <Input data-testid={`rt-player-role-${i}`} placeholder="Role" value={p.role} onChange={(e) => updatePlayer(i, "role", e.target.value)} className="col-span-4 bg-[#141414] border-white/10 text-white" />
                  <Input data-testid={`rt-player-jersey-${i}`} placeholder="#" value={p.jersey} onChange={(e) => updatePlayer(i, "jersey", e.target.value)} className="col-span-2 bg-[#141414] border-white/10 text-white" />
                </div>
              ))}
            </div>
          </div>

          <Button type="submit" disabled={busy} data-testid="rt-submit" className="w-full bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold h-12 rounded-sm">
            {busy ? "Registering..." : "Register team"}
          </Button>
        </form>
      </div>
      <Footer />
    </div>
  );

  function updatePlayer(i, field, value) {
    const next = [...players];
    next[i] = { ...next[i], [field]: value };
    setPlayers(next);
  }
}

function Field({ label, required, children }) {
  return (
    <div>
      <Label className="text-xs font-mono uppercase text-neutral-500">{label}{required && " *"}</Label>
      <div className="mt-2">{children}</div>
    </div>
  );
}
