import { useMemo, useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { toast } from "sonner";
import { MapPin, Users2, Trophy, Plus, Trash2 } from "lucide-react";

const OFFICIAL_ROLES = ["umpire", "referee", "scorer", "line_judge", "video_referee", "match_supervisor"];

const TOSS_DECISIONS_BY_SPORT = {
  cricket: [
    { value: "bat", label: "Bat first" },
    { value: "field", label: "Field first" },
  ],
  badminton: [
    { value: "serve", label: "Serve first" },
    { value: "receive", label: "Receive" },
    { value: "choose_side", label: "Choose side" },
  ],
  pickleball: [
    { value: "serve", label: "Serve first" },
    { value: "receive", label: "Receive" },
    { value: "choose_side", label: "Choose side" },
  ],
  tennis: [
    { value: "serve", label: "Serve first" },
    { value: "receive", label: "Receive" },
    { value: "choose_side", label: "Choose side" },
  ],
  tabletennis: [
    { value: "serve", label: "Serve first" },
    { value: "receive", label: "Receive" },
  ],
  volleyball: [
    { value: "serve", label: "Serve first" },
    { value: "receive", label: "Receive" },
  ],
  default: [
    { value: "bat", label: "Bat / attack first" },
    { value: "field", label: "Field / defend first" },
    { value: "serve", label: "Serve first" },
    { value: "choose_side", label: "Choose side" },
  ],
};

function decisionsFor(sport) {
  return TOSS_DECISIONS_BY_SPORT[sport] || TOSS_DECISIONS_BY_SPORT.default;
}

/**
 * Owner-only dialog for setting a fixture's Phase 3 metadata:
 *   • venue (free text — overrides event.venue for this match)
 *   • court / table / lane number
 *   • scheduled_at (ISO local datetime)
 *   • officials (list of {role, name})
 *   • toss (winner_team_id + decision + optional note)
 *
 * PATCH /api/fixtures/{id}/meta — event creator / platform admin only.
 * Backend accepts partial payloads; unspecified fields are left untouched.
 */
export default function FixtureMetaEditor({ fixture, event, teamA, teamB, open, onClose, onSaved }) {
  const [venue, setVenue] = useState(fixture.venue || "");
  const [courtNumber, setCourtNumber] = useState(fixture.court_number || "");
  const [scheduledAt, setScheduledAt] = useState(() => {
    const s = fixture.scheduled_at;
    if (!s) return "";
    try {
      const d = new Date(s);
      const pad = (n) => String(n).padStart(2, "0");
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    } catch {
      return "";
    }
  });
  const [officials, setOfficials] = useState(() =>
    Array.isArray(fixture.officials) ? fixture.officials.map((o) => ({ role: o.role || "umpire", name: o.name || "" })) : []
  );
  const [toss, setToss] = useState(() => ({
    winner_team_id: fixture.toss?.winner_team_id || "",
    decision: fixture.toss?.decision || "",
    note: fixture.toss?.note || "",
  }));
  const [busy, setBusy] = useState(false);

  const decisions = useMemo(() => decisionsFor(event?.sport), [event?.sport]);

  const addOfficial = () => setOfficials([...officials, { role: "umpire", name: "" }]);
  const removeOfficial = (idx) => setOfficials(officials.filter((_, i) => i !== idx));
  const updateOfficial = (idx, patch) => setOfficials(officials.map((o, i) => (i === idx ? { ...o, ...patch } : o)));

  const save = async () => {
    setBusy(true);
    try {
      const payload = {
        venue: venue.trim(),
        court_number: courtNumber.trim(),
        officials: officials.filter((o) => (o.name || "").trim()).map((o) => ({ role: o.role, name: o.name.trim() })),
      };
      if (scheduledAt) {
        // Send as ISO string; backend stores as-is
        const d = new Date(scheduledAt);
        payload.scheduled_at = isNaN(d.getTime()) ? scheduledAt : d.toISOString();
      } else {
        payload.scheduled_at = "";
      }
      // Only include toss if user has picked at least the winner
      if (toss.winner_team_id) {
        payload.toss = {
          winner_team_id: toss.winner_team_id,
          decision: toss.decision || null,
          note: toss.note || null,
        };
      } else if (fixture.toss) {
        // Explicitly clear existing toss when user removed the pick
        payload.toss = null;
      }
      await api.patch(`/fixtures/${fixture.id}/meta`, payload);
      toast.success("Match details saved");
      onSaved?.();
      onClose?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-[#0c0c0c] border-white/10 text-white max-w-lg" data-testid="fixture-meta-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <MapPin className="w-4 h-4 text-[#06B6D4]" /> Match details
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 max-h-[70vh] overflow-y-auto pr-1">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Venue</Label>
              <Input data-testid="fm-venue" value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="e.g. Main ground" className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Court / Table / Lane</Label>
              <Input data-testid="fm-court" value={courtNumber} onChange={(e) => setCourtNumber(e.target.value)} placeholder="e.g. Court 1 · Table 3" className="mt-1 bg-black/40 border-white/10 text-white" />
            </div>
          </div>
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Scheduled at</Label>
            <Input data-testid="fm-scheduled" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} className="mt-1 bg-black/40 border-white/10 text-white" />
          </div>

          {/* Toss / initial-choice */}
          <div className="border border-white/10 rounded-sm p-3 space-y-2">
            <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-neutral-500">
              <Trophy className="w-3 h-3 text-[#F59E0B]" /> Toss / initial choice
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Select value={toss.winner_team_id || "__none__"} onValueChange={(v) => setToss({ ...toss, winner_team_id: v === "__none__" ? "" : v })}>
                <SelectTrigger data-testid="fm-toss-winner" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Toss winner" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  <SelectItem value="__none__">— None —</SelectItem>
                  {teamA && <SelectItem value={teamA.id}>{teamA.name}</SelectItem>}
                  {teamB && <SelectItem value={teamB.id}>{teamB.name}</SelectItem>}
                </SelectContent>
              </Select>
              <Select value={toss.decision || "__none__"} onValueChange={(v) => setToss({ ...toss, decision: v === "__none__" ? "" : v })}>
                <SelectTrigger data-testid="fm-toss-decision" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Decision" /></SelectTrigger>
                <SelectContent className="bg-[#141414] text-white border-white/10">
                  <SelectItem value="__none__">— None —</SelectItem>
                  {decisions.map((d) => <SelectItem key={d.value} value={d.value}>{d.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Input data-testid="fm-toss-note" value={toss.note} onChange={(e) => setToss({ ...toss, note: e.target.value })} placeholder="Note (optional)" className="bg-black/40 border-white/10 text-white" />
          </div>

          {/* Officials */}
          <div className="border border-white/10 rounded-sm p-3 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-widest text-neutral-500">
                <Users2 className="w-3 h-3 text-[#84CC16]" /> Officials
              </div>
              <Button data-testid="fm-add-official" size="sm" variant="outline" onClick={addOfficial} className="rounded-sm border-white/10 text-white h-7 px-2">
                <Plus className="w-3 h-3 mr-1" /> Add
              </Button>
            </div>
            {officials.length === 0 && <div className="text-[10px] text-neutral-600">No officials added.</div>}
            {officials.map((o, i) => (
              <div key={`official-${i}`} className="grid grid-cols-[130px_1fr_28px] gap-2 items-center">
                <Select value={o.role} onValueChange={(v) => updateOfficial(i, { role: v })}>
                  <SelectTrigger data-testid={`fm-official-role-${i}`} className="bg-black/40 border-white/10 text-white h-9"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#141414] text-white border-white/10">
                    {OFFICIAL_ROLES.map((r) => <SelectItem key={r} value={r}>{r.replace(/_/g, " ")}</SelectItem>)}
                  </SelectContent>
                </Select>
                <Input data-testid={`fm-official-name-${i}`} value={o.name} onChange={(e) => updateOfficial(i, { name: e.target.value })} placeholder="Name" className="bg-black/40 border-white/10 text-white h-9" />
                <button data-testid={`fm-official-del-${i}`} onClick={() => removeOfficial(i)} className="text-[#FF3B30] hover:text-white p-1"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="fm-save" disabled={busy} onClick={save} className="bg-[#06B6D4] hover:bg-[#0891B2] text-black font-semibold rounded-sm">
            {busy ? "Saving…" : "Save details"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Compact strip shown on the fixture card summarising venue/court/officials/toss. */
export function FixtureMetaStrip({ fixture, teamMap }) {
  const bits = [];
  if (fixture.court_number) bits.push({ k: "court", v: fixture.court_number });
  if (fixture.toss?.winner_team_id) {
    const t = teamMap?.[fixture.toss.winner_team_id];
    const decision = fixture.toss.decision ? ` · ${fixture.toss.decision.replace(/_/g, " ")}` : "";
    if (t) bits.push({ k: "toss", v: `${t.name}${decision}` });
  }
  if (Array.isArray(fixture.officials) && fixture.officials.length > 0) {
    const primary = fixture.officials[0];
    bits.push({ k: "official", v: `${primary.name}${fixture.officials.length > 1 ? ` +${fixture.officials.length - 1}` : ""}` });
  }
  if (bits.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[10px] font-mono text-neutral-500" data-testid={`fixture-meta-${fixture.id}`}>
      {bits.map((b) => (
        <span key={b.k}>
          <span className="text-neutral-600 uppercase tracking-widest">{b.k}</span> · <span className="text-neutral-300">{b.v}</span>
        </span>
      ))}
    </div>
  );
}
