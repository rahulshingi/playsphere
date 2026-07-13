import { useState } from "react";
import api from "@/lib/api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Timer } from "lucide-react";

/**
 * VendorOvertimeSettings — how vendor bills for time played beyond the booked slot.
 *
 * Two knobs:
 *   • Rate multiplier  — 1.0 × (same as hourly rate) up to 2.0 ×
 *   • Block size       — round overtime UP to nearest N minutes (15/30/60)
 *
 * Applied by both online (vendor_bookings) and offline (private_bookings) at
 * booking completion time — see complete_* endpoints.
 */
export default function VendorOvertimeSettings({ vendor, onSaved }) {
  const [multiplier, setMultiplier] = useState(vendor?.overtime_charge_multiplier ?? 1.0);
  const [block, setBlock] = useState(vendor?.overtime_block_minutes ?? 15);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    setBusy(true);
    try {
      await api.patch("/vendors/me", {
        overtime_charge_multiplier: Number(multiplier),
        overtime_block_minutes: Number(block),
      });
      toast.success("Overtime settings saved");
      onSaved?.();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="overtime-settings" className="mt-6 border border-[#FACC15]/30 bg-[#FACC15]/5 rounded-sm p-5">
      <div className="flex items-center gap-2 mb-1">
        <Timer className="w-4 h-4 text-[#FACC15]" />
        <div className="font-mono text-[10px] uppercase tracking-widest text-[#FACC15]">/ Overtime settings</div>
      </div>
      <p className="text-xs text-neutral-400 mb-4 max-w-2xl">
        When a customer plays beyond their booked slot, we bill the extra time
        automatically at completion. Set your rate multiplier below (applied to
        the listing&rsquo;s hourly rate) and pick a rounding block.
      </p>

      <div className="grid md:grid-cols-3 gap-4">
        <div>
          <Label className="text-[10px] font-mono uppercase text-neutral-500">Rate multiplier</Label>
          <div className="flex items-center gap-2 mt-1.5">
            <Input
              data-testid="overtime-multiplier"
              type="number"
              step="0.05"
              min="0"
              max="3"
              value={multiplier}
              onChange={(e) => setMultiplier(e.target.value)}
              className="bg-black/40 border-white/10 text-white"
            />
            <span className="text-sm text-neutral-400">× hourly</span>
          </div>
          <p className="text-[10px] text-neutral-500 mt-1">1.0 = same rate · 1.5 = 50% surcharge · 2.0 = double</p>
        </div>

        <div>
          <Label className="text-[10px] font-mono uppercase text-neutral-500">Round-up block</Label>
          <Select value={String(block)} onValueChange={(v) => setBlock(v)}>
            <SelectTrigger data-testid="overtime-block" className="mt-1.5 bg-black/40 border-white/10 text-white"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#141414] text-white border-white/10">
              <SelectItem value="15">Every 15 minutes</SelectItem>
              <SelectItem value="30">Every 30 minutes</SelectItem>
              <SelectItem value="60">Every hour</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-[10px] text-neutral-500 mt-1">A 20-min overrun becomes {block === 15 ? "30 min" : block === 30 ? "30 min" : "60 min"} of billed overtime.</p>
        </div>

        <div className="flex items-end">
          <Button
            data-testid="overtime-save"
            onClick={save}
            disabled={busy}
            className="bg-[#FACC15] hover:bg-[#EAB308] text-black font-semibold rounded-sm h-10 w-full md:w-auto"
          >
            {busy ? "Saving…" : "Save overtime settings"}
          </Button>
        </div>
      </div>
    </div>
  );
}
