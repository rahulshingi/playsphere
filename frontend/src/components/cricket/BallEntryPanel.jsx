import { Button } from "@/components/ui/button";
import { Undo2 } from "lucide-react";

const WICKET_TYPES = ["bowled", "caught", "lbw", "runout", "stumped", "hitwicket"];

function RunButton({ runs, onClick, disabled, accent, testid }) {
  const isExtra = typeof runs === "string";
  return (
    <button data-testid={testid} disabled={disabled} onClick={onClick}
      className={`px-3 py-3 text-base font-display tracking-wider rounded-sm border transition ${
        accent ? "bg-[#FF3B30]/10 border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/20"
               : runs === 4 ? "bg-[#06B6D4]/10 border-[#06B6D4]/40 text-[#06B6D4] hover:bg-[#06B6D4]/20"
               : runs === 6 ? "bg-[#A855F7]/10 border-[#A855F7]/40 text-[#A855F7] hover:bg-[#A855F7]/20"
               : "border-white/10 text-white hover:bg-white/5"
      }`}>
      {isExtra ? runs : (runs === 0 ? "·" : runs)}
    </button>
  );
}

/**
 * Ball-entry panel: 0/1/2/3/4/6 + WD/NB + byes/leg-byes/undo + wicket-type buttons.
 */
export default function BallEntryPanel({ busy, freeHit, onSendBall, onUndo }) {
  return (
    <div className="border border-white/10 rounded-sm p-4 bg-[#141414]">
      <div className="font-mono text-[10px] uppercase text-neutral-500">/ Record a ball</div>
      <div className="grid grid-cols-4 sm:grid-cols-8 gap-2 mt-3">
        {[0, 1, 2, 3, 4, 6].map((r) => (
          <RunButton key={r} runs={r} testid={`ball-runs-${r}`} disabled={busy} onClick={() => onSendBall(r)} />
        ))}
        <RunButton runs="WD" testid="ball-wd" disabled={busy} accent onClick={() => onSendBall(0, "wd")} />
        <RunButton runs="NB" testid="ball-nb" disabled={busy} accent onClick={() => onSendBall(0, "nb")} />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
        <RunButton runs="1 BYE" testid="ball-b1" disabled={busy} onClick={() => onSendBall(1, "b")} />
        <RunButton runs="1 LB" testid="ball-lb1" disabled={busy} onClick={() => onSendBall(1, "lb")} />
        <RunButton runs="4 BYE" testid="ball-b4" disabled={busy} onClick={() => onSendBall(4, "b")} />
        <Button data-testid="ball-undo" disabled={busy} variant="outline" onClick={onUndo}
          className="border-white/10 bg-transparent text-neutral-300 hover:bg-white/5">
          <Undo2 className="w-4 h-4 mr-1" /> Undo last
        </Button>
      </div>

      <div className="mt-4 border-t border-white/10 pt-3">
        <div className="font-mono text-[10px] uppercase text-neutral-500 flex items-center gap-2">
          / Wicket
          {freeHit && <span className="text-[#A855F7]">— free-hit: only runout dismisses</span>}
        </div>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-2">
          {WICKET_TYPES.map((wt) => {
            const disabled = busy || (freeHit && wt !== "runout");
            return (
              <button key={wt} data-testid={`ball-wicket-${wt}`} disabled={disabled}
                onClick={() => onSendBall(0, null, { type: wt })}
                className={`px-3 py-2 text-xs font-mono uppercase rounded-sm border ${
                  disabled
                    ? "border-white/10 text-neutral-600 cursor-not-allowed"
                    : "border-[#FF3B30]/40 text-[#FF3B30] hover:bg-[#FF3B30]/10"
                }`}>
                {wt}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
