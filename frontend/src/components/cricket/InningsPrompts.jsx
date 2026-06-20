import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

/**
 * After a wicket: pick the incoming batsman.
 */
export function WicketPrompt({ availableBatsmen, busy, onSubmit }) {
  const [newBatter, setNewBatter] = useState("");
  return (
    <div className="border border-[#FF3B30]/40 bg-[#FF3B30]/10 rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase text-[#FF3B30]">/ WICKET — pick the new batsman</div>
      <div className="flex gap-2 mt-3">
        <Select value={newBatter} onValueChange={setNewBatter}>
          <SelectTrigger data-testid="new-batsman-select" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select incoming batsman" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            {availableBatsmen.map((p) => (
              <SelectItem key={p.player_id} value={p.player_id}>{p.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button data-testid="new-batsman-submit" disabled={!newBatter || busy}
          onClick={() => { onSubmit(newBatter); setNewBatter(""); }}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Send in</Button>
      </div>
    </div>
  );
}

/**
 * After an over finishes: pick the next bowler.
 */
export function OverBreakPrompt({ availableBowlers, busy, onSubmit }) {
  const [newBowler, setNewBowler] = useState("");
  return (
    <div className="border border-[#84CC16]/40 bg-[#84CC16]/10 rounded-sm p-4">
      <div className="font-mono text-[10px] uppercase text-[#84CC16]">/ END OF OVER — pick the next bowler</div>
      <div className="flex gap-2 mt-3">
        <Select value={newBowler} onValueChange={setNewBowler}>
          <SelectTrigger data-testid="new-bowler-select" className="bg-black/40 border-white/10 text-white"><SelectValue placeholder="Select bowler" /></SelectTrigger>
          <SelectContent className="bg-[#141414] text-white border-white/10">
            {availableBowlers.map((p) => (
              <SelectItem key={p.player_id} value={p.player_id}>{p.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button data-testid="new-bowler-submit" disabled={!newBowler || busy}
          onClick={() => { onSubmit(newBowler); setNewBowler(""); }}
          className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">Confirm</Button>
      </div>
    </div>
  );
}
