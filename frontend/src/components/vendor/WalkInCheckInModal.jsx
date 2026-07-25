import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { UserPlus, Loader2 } from "lucide-react";

/**
 * Walk-in Check-In modal.
 *
 * Vendor's flow when a guest walks in without a booking (or scans an unknown
 * QR): open this modal, capture name + phone + optional email + sport + hours,
 * hit POST /api/checkin/walk-in. The backend creates BOTH a VendorCustomer
 * (deduping on phone) AND a private_booking already in `checked_in` state.
 *
 * Prefills:
 *   - `defaultListingId` — from the vendor's first listing
 *   - `defaultPhone` — set when the caller scanned a QR that turned out to be a
 *     mobile number so the vendor doesn't type it twice.
 */
export default function WalkInCheckInModal({ open, onOpenChange, listings, defaultListingId, defaultPhone, onDone }) {
  const [form, setForm] = useState({
    listing_id: defaultListingId || "",
    client_name: "",
    client_phone: defaultPhone || "",
    client_email: "",
    sport: "",
    hours: 1,
    amount: 0,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm((f) => ({
        ...f,
        listing_id: defaultListingId || listings?.[0]?.id || "",
        client_phone: defaultPhone || "",
        client_name: "",
        client_email: "",
        sport: "",
        hours: 1,
        amount: 0,
      }));
    }
  }, [open, defaultListingId, defaultPhone, listings]);

  const save = async () => {
    if (!form.listing_id) { toast.error("Pick a listing"); return; }
    if (!form.client_name.trim() || !form.client_phone.trim()) {
      toast.error("Name and mobile are required"); return;
    }
    setSaving(true);
    try {
      await api.post("/checkin/walk-in", { ...form, hours: Number(form.hours) || 1, amount: Number(form.amount) || 0 });
      toast.success(`${form.client_name.trim()} checked in`);
      onOpenChange(false);
      onDone?.();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Walk-in failed");
    } finally {
      setSaving(false);
    }
  };

  const listingOptions = listings || [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="walkin-modal" className="bg-[#141414] text-white border-white/10 max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display tracking-wider text-2xl flex items-center gap-2">
            <UserPlus className="w-5 h-5 text-[#FACC15]" /> WALK-IN CHECK-IN
          </DialogTitle>
          <DialogDescription className="text-neutral-400 text-sm">
            No booking? Capture the guest and check them in. Their details join your customer directory automatically.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3">
          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Listing / venue</Label>
            <Select value={form.listing_id} onValueChange={(v) => setForm({ ...form, listing_id: v })}>
              <SelectTrigger data-testid="walkin-listing" className="mt-2 bg-black/40 border-white/10 text-white">
                <SelectValue placeholder="Pick a listing" />
              </SelectTrigger>
              <SelectContent className="bg-[#141414] text-white border-white/10">
                {listingOptions.map((l) => (
                  <SelectItem key={l.id} value={l.id}>{l.title}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Name <span className="text-red-400">*</span></Label>
              <Input data-testid="walkin-name" value={form.client_name}
                     onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                     placeholder="Guest name" className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Mobile <span className="text-red-400">*</span></Label>
              <Input data-testid="walkin-phone" value={form.client_phone}
                     onChange={(e) => setForm({ ...form, client_phone: e.target.value })}
                     placeholder="+91…" className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
          </div>

          <div>
            <Label className="text-xs font-mono uppercase text-neutral-500">Email <span className="text-neutral-600">(optional)</span></Label>
            <Input data-testid="walkin-email" value={form.client_email}
                   onChange={(e) => setForm({ ...form, client_email: e.target.value })}
                   placeholder="guest@example.com" className="mt-2 bg-black/40 border-white/10 text-white" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Sport</Label>
              <Input data-testid="walkin-sport" value={form.sport}
                     onChange={(e) => setForm({ ...form, sport: e.target.value })}
                     placeholder="cricket" className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Hours</Label>
              <Input data-testid="walkin-hours" type="number" min="1" step="1" value={form.hours}
                     onChange={(e) => setForm({ ...form, hours: e.target.value })}
                     className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
            <div>
              <Label className="text-xs font-mono uppercase text-neutral-500">Amount</Label>
              <Input data-testid="walkin-amount" type="number" min="0" step="1" value={form.amount}
                     onChange={(e) => setForm({ ...form, amount: e.target.value })}
                     placeholder="0" className="mt-2 bg-black/40 border-white/10 text-white" />
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} className="border-white/10 text-white">Cancel</Button>
          <Button data-testid="walkin-save" onClick={save} disabled={saving}
                  className="bg-[#84CC16] hover:bg-[#65A30D] text-black font-semibold rounded-sm">
            {saving ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <UserPlus className="w-4 h-4 mr-1" />}
            Check-in
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
