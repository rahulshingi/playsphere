import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { renderScore } from "@/lib/sports";

/**
 * Sport-specific live scorer modal.
 */
export default function LiveScorer({ fixture, event, teamMap, onClose, onSaved }) {
  const [score, setScore] = useState(fixture.score && Object.keys(fixture.score).length ? fixture.score : defaultScore(event.sport));
  const [status, setStatus] = useState(fixture.status === "scheduled" ? "live" : fixture.status);
  const [winnerId, setWinnerId] = useState(fixture.winner_id || "");
  const a = teamMap[fixture.team_a_id];
  const b = teamMap[fixture.team_b_id];

  useEffect(() => {
    if (!fixture.score || !Object.keys(fixture.score).length) {
      api.post(`/fixtures/${fixture.id}/init-score`).then((r) => setScore(r.data.score)).catch(() => {});
    }
  }, [fixture.id]);

  const save = async () => {
    const body = { score, status };
    if (winnerId) body.winner_id = winnerId;
    try {
      await api.patch(`/fixtures/${fixture.id}`, body);
      toast.success("Score updated");
      onSaved && onSaved();
      onClose();
    } catch (e) {
      toast.error("Failed to save");
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent data-testid="live-scorer-modal" className="bg-[#0c0c0c] border border-white/10 max-w-2xl text-white">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl tracking-wider">LIVE SCORING</DialogTitle>
          <p className="font-mono text-[10px] uppercase tracking-widest text-neutral-500">{event.sport} · Match #{fixture.match_number}</p>
        </DialogHeader>

        <div className="grid grid-cols-2 gap-4 mt-2">
          <SideEditor sport={event.sport} side="team_a" team={a} score={score} setScore={setScore} />
          <SideEditor sport={event.sport} side="team_b" team={b} score={score} setScore={setScore} />
        </div>

        <div className="mt-4 grid md:grid-cols-2 gap-3">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Status</Label>
            <div className="flex gap-2 mt-2">
              {["scheduled", "live", "completed"].map((s) => (
                <button
                  key={s}
                  data-testid={`status-${s}`}
                  onClick={() => setStatus(s)}
                  className={`px-3 py-1.5 text-xs font-mono uppercase rounded-sm border ${status === s ? "bg-[#84CC16] border-[#84CC16] text-black" : "border-white/10 text-neutral-400"}`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Winner (on completion)</Label>
            <div className="flex gap-2 mt-2">
              <button data-testid="winner-a" onClick={() => setWinnerId(a?.id)} className={`px-3 py-1.5 text-xs uppercase rounded-sm border ${winnerId === a?.id ? "bg-[#84CC16] border-[#84CC16]" : "border-white/10 text-neutral-400"}`}>{a?.name || "A"}</button>
              <button data-testid="winner-b" onClick={() => setWinnerId(b?.id)} className={`px-3 py-1.5 text-xs uppercase rounded-sm border ${winnerId === b?.id ? "bg-[#84CC16] border-[#84CC16]" : "border-white/10 text-neutral-400"}`}>{b?.name || "B"}</button>
              <button data-testid="winner-clear" onClick={() => setWinnerId("")} className="px-3 py-1.5 text-xs uppercase rounded-sm border border-white/10 text-neutral-400">Clear</button>
            </div>
          </div>
        </div>

        <div className="mt-5 p-4 bg-black/40 border border-white/10 rounded-sm font-mono text-center">
          <span className="text-2xl">{renderScore(event.sport, score.team_a)}</span>
          <span className="mx-4 text-neutral-500">vs</span>
          <span className="text-2xl">{renderScore(event.sport, score.team_b)}</span>
        </div>

        <DialogFooter className="mt-4">
          <Button variant="ghost" onClick={onClose} data-testid="scorer-cancel-btn" className="text-neutral-400">Cancel</Button>
          <Button data-testid="scorer-save-btn" onClick={save} className="bg-[#FF3B30] hover:bg-[#d72f24] rounded-sm">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function defaultScore(sport) {
  switch (sport) {
    case "cricket": return { team_a: { runs: 0, wickets: 0, overs: 0 }, team_b: { runs: 0, wickets: 0, overs: 0 } };
    case "football": return { team_a: { goals: 0 }, team_b: { goals: 0 } };
    case "basketball": return { team_a: { points: 0, q: 1 }, team_b: { points: 0, q: 1 } };
    case "badminton":
    case "tabletennis":
    case "volleyball":
      return { team_a: { sets: [0, 0, 0] }, team_b: { sets: [0, 0, 0] } };
    case "chess":
    case "quiz":
      return { team_a: { points: 0 }, team_b: { points: 0 } };
    case "hackathon":
      return { team_a: { score: 0 }, team_b: { score: 0 } };
    default:
      return { team_a: { score: 0 }, team_b: { score: 0 } };
  }
}

function SideEditor({ sport, side, team, score, setScore }) {
  const s = score[side] || {};
  const update = (patch) => setScore({ ...score, [side]: { ...s, ...patch } });

  return (
    <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
      <div className="flex items-center gap-2 mb-3">
        <span className="w-1.5 h-6 rounded-sm" style={{ background: team?.color || "#333" }} />
        <span className="font-semibold">{team?.name || side}</span>
      </div>

      {sport === "cricket" && (
        <div className="space-y-2">
          <NumberField testid={`${side}-runs`} label="Runs" value={s.runs ?? 0} onChange={(v) => update({ runs: v })} />
          <NumberField testid={`${side}-wickets`} label="Wickets" value={s.wickets ?? 0} onChange={(v) => update({ wickets: v })} max={10} />
          <NumberField testid={`${side}-overs`} label="Overs" value={s.overs ?? 0} step={0.1} onChange={(v) => update({ overs: v })} />
        </div>
      )}

      {sport === "football" && (
        <NumberField testid={`${side}-goals`} label="Goals" value={s.goals ?? 0} onChange={(v) => update({ goals: v })} />
      )}

      {sport === "basketball" && (
        <div className="space-y-2">
          <NumberField testid={`${side}-points`} label="Points" value={s.points ?? 0} onChange={(v) => update({ points: v })} />
          <NumberField testid={`${side}-q`} label="Quarter" value={s.q ?? 1} max={4} onChange={(v) => update({ q: v })} />
        </div>
      )}

      {(sport === "badminton" || sport === "tabletennis" || sport === "volleyball") && (
        <div className="space-y-2">
          {(s.sets || [0, 0, 0]).map((v, i) => (
            <NumberField key={i} testid={`${side}-set-${i + 1}`} label={`Set ${i + 1}`} value={v} onChange={(nv) => {
              const arr = [...(s.sets || [0, 0, 0])];
              arr[i] = nv;
              update({ sets: arr });
            }} />
          ))}
        </div>
      )}

      {(sport === "chess" || sport === "quiz") && (
        <NumberField testid={`${side}-points`} label="Points" value={s.points ?? 0} onChange={(v) => update({ points: v })} />
      )}

      {sport === "hackathon" && (
        <NumberField testid={`${side}-score`} label="Score" value={s.score ?? 0} onChange={(v) => update({ score: v })} />
      )}

      {!["cricket", "football", "basketball", "badminton", "tabletennis", "volleyball", "chess", "quiz", "hackathon"].includes(sport) && (
        <NumberField testid={`${side}-score`} label="Score" value={s.score ?? 0} onChange={(v) => update({ score: v })} />
      )}
    </div>
  );
}

function NumberField({ label, value, onChange, step = 1, max, testid }) {
  return (
    <div>
      <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">{label}</Label>
      <div className="flex items-center gap-1 mt-1">
        <Button type="button" size="sm" variant="outline" data-testid={`${testid}-dec`} className="h-9 w-9 p-0 border-white/10 bg-transparent text-white" onClick={() => onChange(Math.max(0, Number((value - step).toFixed(1))))}>−</Button>
        <Input data-testid={testid} value={value} onChange={(e) => onChange(Number(e.target.value) || 0)} className="h-9 text-center font-mono bg-black/40 border-white/10 text-white" />
        <Button type="button" size="sm" data-testid={`${testid}-inc`} className="h-9 w-9 p-0 bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm" onClick={() => {
          const nv = Number((value + step).toFixed(1));
          if (max !== undefined && nv > max) return;
          onChange(nv);
        }}>+</Button>
      </div>
    </div>
  );
}
