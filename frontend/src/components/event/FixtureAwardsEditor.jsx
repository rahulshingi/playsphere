import { useState } from "react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import ImageUpload from "@/components/ImageUpload";
import { toast } from "sonner";
import { Award, Image as ImageIcon, Lock, RotateCcw } from "lucide-react";
import { resolveImageUrl } from "@/lib/imageUrl";

const AWARD_FIELDS_BY_SPORT = {
  cricket: [
    { key: "mom", label: "Player of the match" },
    { key: "best_batter", label: "Best batter" },
    { key: "best_bowler", label: "Best bowler" },
  ],
  football: [
    { key: "mom", label: "Player of the match" },
    { key: "top_scorer", label: "Top scorer" },
  ],
  basketball: [
    { key: "mom", label: "Player of the match" },
    { key: "top_scorer", label: "Top scorer" },
  ],
  default: [{ key: "mom", label: "Player of the match" }, { key: "top_scorer", label: "Top scorer" }],
};

function fieldsFor(sport) {
  return AWARD_FIELDS_BY_SPORT[sport] || AWARD_FIELDS_BY_SPORT.default;
}

/** Compact banner shown on the fixture card: hero image (if any) + up to 3 awards.
 *  Rendered only when the match is completed and at least one award or hero image exists. */
export function FixtureAwardsBanner({ fixture }) {
  if (fixture.status !== "completed") return null;
  const awards = fixture.awards || {};
  const hero = fixture.hero_image_url;
  const entries = Object.entries(awards).filter(([, v]) => v && (typeof v === "string" || v.name));
  if (!hero && entries.length === 0) return null;
  return (
    <div className="mt-3 border-t border-white/10 pt-3 space-y-2" data-testid={`fixture-awards-${fixture.id}`}>
      {hero && (
        <div className="rounded-sm overflow-hidden border border-white/10 aspect-[16/9] bg-black/40">
          <img src={resolveImageUrl(hero)} alt="Match hero" className="w-full h-full object-cover" />
        </div>
      )}
      {entries.length > 0 && (
        <div className="grid grid-cols-2 gap-2">
          {entries.slice(0, 4).map(([k, v]) => (
            <div key={k} className="text-[10px] font-mono uppercase text-neutral-400">
              <div className="text-[9px] tracking-widest text-[#F59E0B]">{k.replace(/_/g, " ")}</div>
              <div className="text-white text-xs mt-0.5 truncate">{typeof v === "string" ? v : (v.name || "—")}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Owner-only dialog for a fixture's hero image + awards.
 *
 * • While the match is IN PROGRESS: creator/admin can edit hero + awards freely.
 * • Once the match is COMPLETED: awards are locked (backend rejects PATCH when
 *   `status=completed`). The hero image is still editable — you may want to
 *   swap in a better photo later. To edit awards, the creator/admin must click
 *   `Reopen match`, which flips the match back to `live` and clears winner +
 *   awards so the scorer can restart the "mark completed" flow.
 */
export default function FixtureAwardsEditor({ fixture, sport, open, onClose, onSaved }) {
  const isLocked = fixture.status === "completed";
  const [heroDraft, setHeroDraft] = useState(fixture.hero_image_url || "");
  const [awardsDraft, setAwardsDraft] = useState(() => {
    const src = fixture.awards || {};
    const out = {};
    fieldsFor(sport).forEach((f) => {
      const v = src[f.key];
      out[f.key] = typeof v === "string" ? v : (v?.name || "");
    });
    return out;
  });
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      const payload = { hero_image_url: heroDraft || "" };
      // Awards can only be sent while the match isn't locked. The backend
      // returns 409 otherwise — we omit the field client-side too so a locked
      // save can still update the hero image alone.
      if (!isLocked) {
        const cleaned = {};
        Object.entries(awardsDraft).forEach(([k, v]) => {
          const s = (v || "").trim();
          if (s) cleaned[k] = { name: s };
        });
        payload.awards = cleaned;
      }
      // NOTE: this hits /fixtures/{id}/media (NOT /fixtures/{id} — that route
      // is for the scorer and expects a full score body). Sending awards to
      // the score route was the "blank page after save" bug shipped in iter31.
      await api.patch(`/fixtures/${fixture.id}/media`, payload);
      toast.success("Match highlights saved");
      onSaved?.();
      onClose?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  const reopen = async () => {
    if (!window.confirm("Reopen this match? Winner + awards will be cleared and the scorer can edit the score again.")) return;
    setBusy(true);
    try {
      await api.post(`/fixtures/${fixture.id}/reopen`);
      toast.success("Match reopened — you can now edit the score");
      onSaved?.();
      onClose?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to reopen");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose?.()}>
      <DialogContent className="bg-[#0c0c0c] border-white/10 text-white max-w-lg" data-testid="fixture-awards-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Award className="w-4 h-4 text-[#F59E0B]" /> Match highlights
            {isLocked && (
              <span
                data-testid="awards-locked-chip"
                className="ml-2 text-[9px] font-mono uppercase tracking-widest px-1.5 py-0.5 rounded-sm bg-neutral-500/10 text-neutral-400 border border-neutral-500/30 flex items-center gap-1"
              >
                <Lock className="w-3 h-3" /> Locked
              </span>
            )}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {isLocked && (
            <div className="rounded-sm border border-neutral-500/30 bg-neutral-500/5 p-3 text-xs text-neutral-400 leading-relaxed" data-testid="awards-locked-note">
              This match is marked <b>completed</b>. Winner and awards were auto-computed and are now locked to preserve match records. You can still swap the hero image below. To edit awards or the score, click <b>Reopen match</b> — winner + awards will be cleared and the scorer can rescore the match.
            </div>
          )}
          <div>
            <Label className="text-[10px] font-mono uppercase tracking-widest text-neutral-500 flex items-center gap-1"><ImageIcon className="w-3 h-3" /> Hero image</Label>
            <div className="mt-1.5">
              <ImageUpload value={heroDraft} onChange={setHeroDraft} testid="hero-image" placeholder="Paste image URL or click Upload →" />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-[10px] font-mono uppercase tracking-widest text-neutral-500">Awards {isLocked && <span className="text-neutral-600 normal-case">· read-only</span>}</div>
            {fieldsFor(sport).map((f) => (
              <div key={f.key} className="grid grid-cols-[140px_1fr] gap-3 items-center">
                <Label className="text-xs text-neutral-400">{f.label}</Label>
                <Input
                  data-testid={`award-${f.key}`}
                  value={awardsDraft[f.key] || ""}
                  onChange={(e) => setAwardsDraft({ ...awardsDraft, [f.key]: e.target.value })}
                  placeholder={isLocked ? "—" : "Player name"}
                  readOnly={isLocked}
                  disabled={isLocked}
                  className="bg-black/40 border-white/10 text-white disabled:opacity-60"
                />
              </div>
            ))}
          </div>
        </div>
        <DialogFooter className="flex-wrap gap-2">
          {isLocked && (
            <Button
              variant="outline"
              onClick={reopen}
              disabled={busy}
              data-testid="fixture-reopen-btn"
              className="border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/10 rounded-sm"
            >
              <RotateCcw className="w-4 h-4 mr-1" /> Reopen match
            </Button>
          )}
          <div className="flex-1" />
          <Button variant="ghost" onClick={onClose} className="text-neutral-400">Cancel</Button>
          <Button data-testid="fixture-awards-save" disabled={busy} onClick={save} className="bg-[#F59E0B] hover:bg-[#D97706] text-black font-semibold rounded-sm">
            {busy ? "Saving…" : (isLocked ? "Save hero image" : "Save highlights")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
